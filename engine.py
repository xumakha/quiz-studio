"""Validation, bilingual speech and deterministic quiz-video rendering."""
import asyncio
import json
import math
import os
import re
import subprocess
import tempfile
import threading
import hashlib
import shutil
from dataclasses import dataclass, replace
from pathlib import Path

import edge_tts
import edge_tts.communicate
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps
from gtts import gTTS

# Retain certificate verification and additionally trust the OS certificate store
# (necessary on Windows networks using an installed corporate root CA).
edge_tts.communicate._SSL_CTX.load_default_certs()

VOICES = {
    "Việt • Nữ — Hoài My": "vi-VN-HoaiMyNeural",
    "Việt • Nam — Nam Minh": "vi-VN-NamMinhNeural",
    "English • Female — Jenny": "en-US-JennyNeural",
    "English • Male — Guy": "en-US-GuyNeural",
    "Việt • Google (HTTP)": "google:vi",
    "English • Google (HTTP)": "google:en",
}


def plain(text):
    return re.sub(r"\[/?en\]", "", str(text), flags=re.I)


def parse_legacy_questions(raw):
    data = json.loads(raw)
    title = data.get("title", "QUIZ CHALLENGE") if isinstance(data, dict) else "QUIZ CHALLENGE"
    rows = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        raise ValueError("JSON phải là mảng câu hỏi hoặc object có questions là mảng không rỗng.")
    result = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Câu {i}: phải là object.")
        q, options = row.get("question"), row.get("options")
        if not isinstance(q, str) or not q.strip():
            raise ValueError(f"Câu {i}: thiếu question.")
        if not isinstance(options, list) or not 2 <= len(options) <= 6 or any(not isinstance(x, str) or not x.strip() for x in options):
            raise ValueError(f"Câu {i}: options phải có 2–6 chuỗi không rỗng.")
        answer = row.get("answer", row.get("correct_answer", row.get("answer_index")))
        if isinstance(answer, bool):
            raise ValueError(f"Câu {i}: đáp án không hợp lệ.")
        if isinstance(answer, int):
            index = answer
        elif isinstance(answer, str) and answer.strip().upper() in list("ABCDEF"):
            index = ord(answer.strip().upper()) - ord("A")
        elif isinstance(answer, str) and answer in options:
            index = options.index(answer)
        else:
            raise ValueError(f"Câu {i}: answer phải là A–F, nguyên văn lựa chọn hoặc chỉ số bắt đầu từ 0.")
        if not 0 <= index < len(options):
            raise ValueError(f"Câu {i}: đáp án nằm ngoài options.")
        explanation = row.get("explanation", "")
        if not isinstance(explanation, str):
            raise ValueError(f"Câu {i}: explanation phải là chuỗi.")
        result.append({**row, "question": q.strip(), "options": options, "answer_index": index, "explanation": explanation})
    return str(title), result


def parse_questions(raw):
    from content_types import normalize
    title, rows, _ = normalize(json.loads(raw), parse_legacy_questions)
    return title, rows


@dataclass
class Settings:
    voice: str = "vi-VN-HoaiMyNeural"
    english_voice: str = "en-US-JennyNeural"
    dialogue_voice_a: str = "en-US-JennyNeural"
    dialogue_voice_b: str = "en-US-GuyNeural"
    rate: int = 0
    pitch: int = 0
    countdown: int = 5
    width: int = 1080
    height: int = 1920
    read_options: bool = True
    read_explanation: bool = True
    speech: bool = True
    brand: str = "QUIZ STUDIO"
    watermark_enabled: bool = True
    template: str = "auto"
    background: str = ""
    background_dim: int = 12
    background_overlay: bool = False
    music: str = ""
    music_volume: float = 0.12


def font(size, bold=False):
    from platform_support import font_paths
    for path in font_paths(bold):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def wrap(draw, text, face, width):
    lines = []
    for paragraph in plain(text).split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}".strip()
            if line and draw.textlength(candidate, font=face) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines


def fitted(draw, text, size, width, max_height, bold=False):
    for value in range(size, 19, -2):
        face = font(value, bold)
        lines = wrap(draw, text, face, width)
        if (len(lines) * (value + 12) <= max_height
                and all(draw.textlength(line, font=face) <= width for line in lines)):
            return face, lines, value + 12
    raise ValueError("Nội dung quá dài để hiển thị rõ trên video. Hãy rút gọn câu hỏi/lựa chọn/giải thích.")


def draw_option_text(draw, text, rectangle, size, color):
    left, top, right, bottom = rectangle
    face, lines, _ = fitted(draw, text, size, right - left, bottom - top, bold=True)
    content = "\n".join(lines)
    # Center the visible glyphs, including accents and descenders, in the text area.
    bounds = draw.multiline_textbbox((0, 0), content, font=face, spacing=12, align="center")
    x = (left + right - (bounds[2] - bounds[0])) / 2 - bounds[0]
    y = (top + bottom - (bounds[3] - bounds[1])) / 2 - bounds[1]
    draw.multiline_text((x, y), content, font=face, fill=color, spacing=12, align="center")


def frame(row, number, total, title, settings, reveal=False, countdown=None):
    from content_timeline import plan_item
    from content_renderer import render_scene
    scenes = plan_item(row, settings)
    if reveal:
        scene = scenes[-1]
    elif countdown is not None:
        scene = next((s for s in scenes if s.countdown is not None), scenes[0])
        if scene.countdown is not None:
            scene = replace(scene, countdown=countdown)
    else:
        scene = scenes[0]
    return render_scene(row, scene, number, total, title, settings)



class Cancelled(Exception):
    pass


class Renderer:
    def __init__(self, settings, log=lambda message: None, cancel=None, progress=lambda percent, message: None):
        self.settings = settings
        self.log = log
        self.cancel = cancel or threading.Event()
        self.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        self.progress = progress

    def check(self):
        if self.cancel.is_set():
            raise Cancelled("Đã hủy xuất video.")

    def run(self, args):
        self.check()
        process = subprocess.Popen([self.ffmpeg, "-hide_banner", "-y", *map(str, args)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if self.cancel.is_set():
                    process.kill()
                    process.communicate()
                    self.check()
        if process.returncode:
            raise RuntimeError(stderr.decode("utf-8", errors="replace")[-2500:])
        return stderr.decode("utf-8", errors="replace")

    async def speech(self, text, target, directory, on_part=lambda fraction: None):
        # Blanks belong to the picture, never to either speech provider. Clean
        # before hashing as well so previously cached spoken blanks are bypassed.
        text = re.sub(r"\s+", " ", re.sub(r"_+", " ", text)).strip()
        if not re.search(r"\w", plain(text)):
            import wave
            with wave.open(str(target), "wb") as output:
                output.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
                output.writeframes(bytes(4410 * 4))
            on_part(1)
            return
        from preferences import BackgroundStore
        cache = BackgroundStore().directory / "tts-cache"
        cache.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(json.dumps([text, self.settings.voice, self.settings.english_voice,
                                        self.settings.rate, self.settings.pitch], ensure_ascii=False).encode("utf-8")).hexdigest()
        cached = cache / f"{key}.wav"
        if cached.exists():
            self.check()
            shutil.copyfile(cached, target)
            on_part(1)
            return
        parts = re.split(r"(\[en\].*?\[/en\])", text, flags=re.I | re.S)
        parts = [part for part in parts if re.search(r"\w", plain(part))]
        files = []
        for index, part in enumerate(parts):
            self.check()
            if not re.search(r"\w", plain(part)):
                continue
            voice = self.settings.english_voice if part.lower().startswith("[en]") else self.settings.voice
            path = directory / f"speech-{target.stem}-{index}.mp3"
            if voice.startswith("google:"):
                await asyncio.to_thread(gTTS(plain(part), lang=voice.split(":")[1], pre_processor_funcs=[], timeout=(15, 45)).save, str(path))
                adjusted = path.with_suffix(".wav")
                # Pitch is mapped from the UI range to +/- 6 semitones for Google;
                # atempo compensates pitch-induced speed before applying rate.
                factor = 2 ** (self.settings.pitch / 100)
                speed = (1 + self.settings.rate / 100) / factor
                filters = [f"aresample=44100", f"asetrate={44100 * factor:.3f}", "aresample=44100"]
                while speed < 0.5:
                    filters.append("atempo=0.5")
                    speed /= 0.5
                while speed > 2:
                    filters.append("atempo=2")
                    speed /= 2
                filters.append(f"atempo={speed:.6f}")
                self.run(["-i", path, "-af", ",".join(filters), adjusted])
                path = adjusted
            else:
                await edge_tts.Communicate(plain(part), voice, rate=f"{self.settings.rate:+d}%", pitch=f"{self.settings.pitch:+d}Hz", connect_timeout=15, receive_timeout=45).save(str(path))
            files.append(path)
            on_part((index + 1) / len(parts))
        if not files:
            raise ValueError("Không có nội dung để đọc.")
        args = []
        for path in files:
            args.extend(["-i", path])
        inputs = "".join(f"[{i}:a]" for i in range(len(files)))
        self.run([*args, "-filter_complex", f"{inputs}concat=n={len(files)}:v=0:a=1[out]", "-map", "[out]", "-ar", "44100", "-ac", "2", target])
        staging = cache / f"{key}-{os.getpid()}-{threading.get_ident()}.tmp"
        try:
            shutil.copyfile(target, staging)
            os.replace(staging, cached)
        finally:
            staging.unlink(missing_ok=True)

    def audio_duration(self, path):
        info = self.run(["-i", path, "-f", "null", "-"])
        match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", info)
        if not match:
            raise RuntimeError("Không xác định được thời lượng giọng đọc.")
        h, m, s = map(float, match.groups())
        return h * 3600 + m * 60 + s

    def segment(self, image, output, seconds, audio=None, background_offset=None):
        # Match PCM samples to the exact video-frame duration. Encoding AAC for
        # every segment adds encoder priming/padding at each countdown join.
        frames = math.ceil(seconds * 30)
        samples = frames * 1470  # 44100 Hz / 30 fps
        args = ["-loop", "1", "-framerate", "30", "-i", image]
        args += ["-i", audio] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        video_map = "0:v:0"
        filters = ["-vf", "format=yuv420p"]
        if background_offset is not None:
            args += ["-stream_loop", "-1", "-ss", f"{background_offset:.9f}", "-i", self.settings.background]
            filters = ["-filter_complex",
                       f"[2:v]setpts=PTS-STARTPTS,scale={self.settings.width}:{self.settings.height}:"
                       f"force_original_aspect_ratio=increase,crop={self.settings.width}:{self.settings.height},"
                       "setsar=1,fps=30[bg];[bg][0:v]overlay=shortest=1,format=yuv420p[v]"]
            video_map = "[v]"
        self.run([*args, "-t", f"{frames / 30:.9f}", *filters, "-af",
                  f"aresample=44100,apad,atrim=end_sample={samples},asetpts=N/SR/TB",
                  "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-r", "30",
                  "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2", "-map", video_map, "-map", "1:a:0", output])

    def render(self, title, rows, output):
        from video_themes import video_template
        settings = replace(self.settings, template=video_template(rows, title, self.settings.template))
        from background_media import is_video
        settings.background_overlay = bool(settings.background and is_video(settings.background))
        destination = Path(output).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        from content_timeline import plan_item
        total_steps = sum(len(plan_item(row, settings)) for row in rows) + 4 + bool(settings.music)
        completed = 0
        def update(message, increment=0, fraction=0):
            nonlocal completed
            completed += increment
            self.progress(min(99, 100 * (completed + fraction) / total_steps), message)
            if not fraction:
                self.log(message)
        update("Chuẩn bị tạo video…")
        from content_renderer import validate_layout
        validate_layout(title, rows, settings, self.check)
        # Final file is replaced only after a complete successful render.
        with tempfile.TemporaryDirectory(prefix="quiz-", dir=destination.parent) as temp:
            directory = Path(temp)
            segments = []
            question_frames = 0
            for number, row in enumerate(rows, 1):
                self.check()
                prefix = f"Câu {number}/{len(rows)}"
                from content_timeline import plan_item, prepare_scene
                from content_renderer import render_scene
                scenes = plan_item(row, settings)
                for scene_index, scene in enumerate(scenes):
                    self.check()
                    update(f"{prefix}: {scene.label or scene.phase}")
                    prepared = prepare_scene(self, scene, directory, f"{number}-{scene_index}", number)
                    duration, audio = prepared.seconds, prepared.audio
                    picture = directory / f"{number}-{scene_index}.png"
                    if row.get("type", "multiple_choice") == "multiple_choice":
                        frame(row, number, len(rows), title, settings, reveal=scene.phase == "answer", countdown=scene.countdown).save(picture)
                    else:
                        render_scene(row, scene, number, len(rows), title, settings).save(picture)
                    video = picture.with_suffix(".mov")
                    if settings.background_overlay:
                        self.segment(picture, video, duration, audio, background_offset=question_frames / 30)
                    else:
                        self.segment(picture, video, duration, audio)
                    segments.append(video)
                    question_frames += math.ceil(duration * 30)
                    update(f"{prefix}: {scene.label or scene.phase} ({duration:.1f}s)", increment=1)
            update("Tạo giọng kêu gọi theo dõi…")
            from content_timeline import ending_scene, prepare_scene
            from content_renderer import render_ending
            prepared = prepare_scene(self, ending_scene(), directory, "ending", len(rows))
            audio, duration = prepared.audio, prepared.seconds
            picture = directory / "ending.png"
            render_ending(settings).save(picture)
            video = picture.with_suffix(".mov")
            ending_frames = math.ceil(duration * 30)
            self.duration = (question_frames + ending_frames) / 30
            self.segment(picture, video, duration, audio if settings.speech else None)
            segments.append(video)
            update("Đã dựng đoạn kết", increment=1)
            update("Ghép các câu hỏi và hoàn thiện MP4…")
            listing = directory / "segments.txt"
            listing.write_text("\n".join(f"file '{p.name}'" for p in segments), encoding="utf-8")
            joined = directory / "joined.mov"
            self.run(["-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", joined])
            update("Đã ghép video", increment=1)
            finished = directory / "finished.mp4"
            if settings.music:
                update("Đang trộn nhạc nền…")
                self.run(["-i", joined, "-stream_loop", "-1", "-i", settings.music, "-filter_complex",
                          f"[0:a]asetpts=N/SR/TB[voice];[1:a]aresample=44100,asetpts=N/SR/TB,volume={settings.music_volume},"
                          f"afade=t=out:ss={question_frames * 1470}:ns={ending_frames * 1470}[bg];"
                          "[voice][bg]amix=inputs=2:duration=first:normalize=0:dropout_transition=0[a]",
                          "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                          "-ar", "44100", "-ac", "2", "-movflags", "+faststart", finished])
                update("Đã trộn nhạc nền", increment=1)
            else:
                self.run(["-i", joined, "-map", "0:v", "-map", "0:a", "-c:v", "copy",
                          "-af", "asetpts=N/SR/TB", "-c:a", "aac", "-ar", "44100", "-ac", "2",
                          "-movflags", "+faststart", finished])
            self.check()
            os.replace(finished, destination)
        self.log(f"Hoàn tất: {destination}")
        self.progress(100, f"Hoàn tất: {destination}")
