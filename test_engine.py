import json
import math
import array
import wave
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image

from engine import Cancelled, Renderer, Settings, frame, parse_questions
from video_themes import detect_template, video_template


class EngineTests(unittest.TestCase):
    def test_audio_stays_continuous_across_countdown_and_answer(self):
        class OfflineRenderer(Renderer):
            messages = None

            async def speech(self, text, target, directory, on_part=lambda fraction: None):
                self.run(["-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100:duration=0.537",
                          "-ac", "2", target])

            def run(self, args):
                info = super().run(args)
                if self.messages is not None:
                    self.messages.append(info)
                return info

        _, rows = parse_questions(json.dumps([
            {"question": "Test?", "options": ["one", "two"], "answer": "A"}
        ] * 2))
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            music = directory / "music.wav"
            setup = Renderer(Settings())
            # A short, seamless tone forces music looping during the final countdown seconds.
            setup.run(["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=0.4", music])
            compressed_music = directory / "music.mp3"
            setup.run(["-i", music, "-ar", "48000", compressed_music])
            for music_source in ["", str(music), str(compressed_music)]:
                with self.subTest(music=music_source):
                    settings = Settings(width=180, height=320, countdown=2,
                                        music=music_source, music_volume=.5)
                    renderer = OfflineRenderer(settings)
                    renderer.messages = []
                    target = directory / "video.mp4"
                    renderer.render("Quiz", rows, target)
                    self.assertFalse(any("non-monoton" in info.lower() for info in renderer.messages),
                                     "Segment joins must preserve audio timestamps")
                    decoded = directory / "decoded.wav"
                    renderer.run(["-i", target, "-vn", "-ac", "1", "-c:a", "pcm_s16le", decoded])
                    with wave.open(str(decoded), "rb") as stream:
                        samples = array.array("h", stream.readframes(stream.getnframes()))
                        sample_rate = stream.getframerate()
                    phase_seconds = math.ceil((.537 + .5) * 30) / 30
                    expected_seconds = 2 * (2 * phase_seconds + 2)
                    self.assertAlmostEqual(len(samples) / sample_rate, expected_seconds, delta=.04)
                    for phase_start in [0, phase_seconds + 2, 2 * phase_seconds + 2, 3 * phase_seconds + 4]:
                        start = round((phase_start + .2) * sample_rate)
                        chunk = samples[start:start + sample_rate // 10]
                        rms = math.sqrt(sum(value * value for value in chunk) / len(chunk))
                        self.assertGreater(rms, 1600, "Question/answer audio must remain at its intended time")
                    if music_source:
                        # Scan every 10 ms, including all joins and loop boundaries.
                        window = sample_rate // 100
                        for start in range(window, len(samples) - 2 * window, window):
                            chunk = samples[start:start + window]
                            rms = math.sqrt(sum(value * value for value in chunk) / len(chunk))
                            self.assertGreater(rms, 800, f"Audio dipped at {start / sample_rate:.3f}s")

    def test_video_content_leaves_bottom_clear_for_page_and_caption(self):
        with tempfile.TemporaryDirectory() as directory:
            background = Path(directory) / "background.png"
            color = (150, 200, 240)
            Image.new("RGB", (1080, 1920), color).save(background)
            for theme in ["english", "math", "classic"]:
                for count in [2, 4, 6]:
                    _, rows = parse_questions(json.dumps([{
                        "question": "Cụm look for trong câu I'm looking for my keys có nghĩa là gì?",
                        "options": ["Đang tìm chìa khóa"] * count,
                        "answer": "B",
                        "explanation": "Look for nghĩa là tìm kiếm. Câu này có nghĩa là tôi đang tìm chìa khóa của mình."
                    }]))
                    for width, height in [(1080, 1920), (720, 1280)]:
                        settings = Settings(template=theme, background=str(background), background_dim=0,
                                            width=width, height=height)
                        for phase in [{}, {"reveal": True}, {"countdown": 3}]:
                            with self.subTest(theme=theme, count=count, width=width, phase=phase):
                                picture = frame(rows[0], 1, 1, "18 CÂU ĐỐ TIẾNG ANH", settings, **phase)
                                # Leave the lower 22% for the social player's page name and caption.
                                bottom = picture.crop((0, round(height * .78), width, height))
                                self.assertEqual(bottom.tobytes(), Image.new("RGB", bottom.size, color).tobytes())

    def test_mixed_subject_video_uses_one_template_in_every_phase(self):
        title, rows = parse_questions(json.dumps([
            {"subject": subject, "question": "Test?", "options": ["one", "two"], "answer": "A"}
            for subject in ["Toán", "Tiếng Anh"]
        ]))
        settings = Settings(width=360, height=640, speech=False, countdown=1)
        for selected, expected in [("auto", "math"), ("english", "english"), ("classic", "classic")]:
            settings.template = selected
            self.assertEqual(video_template(rows, title, selected), expected)
            with tempfile.TemporaryDirectory() as directory, patch("engine.frame", wraps=frame) as frames:
                Renderer(settings).render(title, rows, Path(directory) / "video.mp4")
            self.assertEqual(frames.call_count, 6)
            self.assertEqual({call.args[4].template for call in frames.call_args_list}, {expected})
            self.assertEqual(settings.template, selected)

    def test_subject_detection_and_manual_override(self):
        self.assertEqual(detect_template({"subject": "TOÁN VUI", "question": "[en]one[/en]"}, "ENGLISH"), "math")
        self.assertEqual(detect_template({"subject": "Tiếng Anh cơ bản"}), "english")
        self.assertEqual(detect_template({"subject": "toan lop 3"}), "math")
        self.assertEqual(detect_template({"question": "[en]Hello[/en]"}), "english")
        self.assertEqual(detect_template({"subject": "Lịch sử"}), "classic")
        self.assertEqual(detect_template({"subject": "TOÁN"}, selected="english"), "english")
        self.assertEqual(detect_template({"subject": "English"}, selected="math"), "math")
    def test_watermark_toggle_removes_the_entire_footer(self):
        title, rows = parse_questions(Path("examples/questions.json").read_text(encoding="utf-8"))
        area = (0, 1420, 1080, 1470)
        disabled = frame(rows[0], 1, 2, title, Settings(watermark_enabled=False)).crop(area)
        blank = frame(rows[0], 1, 2, title, Settings(brand=" ")).crop(area)
        self.assertEqual(disabled.tobytes(), blank.tobytes())
        custom = frame(rows[0], 1, 2, title, Settings(brand="Học tiếng Anh mỗi ngày")).crop(area)
        default = frame(rows[0], 1, 2, title, Settings()).crop(area)
        self.assertNotEqual(custom.tobytes(), disabled.tobytes())
        self.assertNotEqual(custom.tobytes(), default.tobytes())

    def test_answers_and_invalid_input(self):
        for answer in ["B", 1, "second"]:
            _, rows = parse_questions(json.dumps([{"question": "Test?", "options": ["first", "second"], "answer": answer}]))
            self.assertEqual(rows[0]["answer_index"], 1)
        for answer in [True, 2, "Z", None]:
            with self.assertRaises(ValueError):
                parse_questions(json.dumps([{"question": "Test?", "options": ["first", "second"], "answer": answer}]))

    def test_render_and_cancel_preserve_destination(self):
        title, rows = parse_questions(Path("examples/questions.json").read_text(encoding="utf-8"))
        settings = Settings(width=360, height=640, speech=False, countdown=1)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "video.mp4"
            progress = []
            renderer = Renderer(settings, progress=lambda percent, message: progress.append((percent, target.exists())))
            renderer.render(title, rows[:1], target)
            percentages = [value for value, _ in progress]
            self.assertEqual(percentages[0], 0)
            self.assertEqual(percentages[-1], 100)
            self.assertEqual(percentages, sorted(percentages))
            self.assertTrue(progress[-1][1], "100% must mean the destination is saved")
            self.assertGreater(len(set(percentages)), 5)
            self.assertGreater(target.stat().st_size, 10000)
            # Actually decode the complete generated file to check codec/container validity.
            info = renderer.run(["-i", target, "-f", "null", "-"])
            self.assertIn("360x640", info)
            self.assertIn("aac", info)
            before = target.read_bytes()
            cancel = threading.Event()
            cancel.set()
            with self.assertRaises(Cancelled):
                Renderer(settings, cancel=cancel).render(title, rows[:1], target)
            self.assertEqual(before, target.read_bytes())

    def test_preview_has_valid_size(self):
        title, rows = parse_questions(Path("examples/questions.json").read_text(encoding="utf-8"))
        self.assertEqual(frame(rows[0], 1, 2, title, Settings(), reveal=True).size, (1080, 1920))

    def test_background_keeps_detail_and_cards_are_translucent(self):
        title, rows = parse_questions(Path("examples/questions.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "background.png"
            Image.new("RGB", (1080, 1920), (150, 200, 240)).save(path)
            settings = Settings(background=str(path), background_dim=0)
            picture = frame(rows[0], 1, 2, title, settings)
            self.assertEqual(picture.getpixel((10, 10)), (150, 200, 240))
            # The card protects text while still allowing the picture through.
            red = picture.getpixel((880, 1000))[0]
            self.assertGreater(red, 150)
            self.assertLess(red, 255)
            settings.background_dim = 12
            dimmed = frame(rows[0], 1, 2, title, settings)
            self.assertGreater(dimmed.getpixel((10, 10))[0], 125)


if __name__ == "__main__":
    unittest.main()
