"""Shared deterministic scene plan for preview and FFmpeg export."""
from dataclasses import dataclass, replace
from content_types import REGISTRY, en, plain


@dataclass(frozen=True)
class Scene:
    phase: str
    text: str
    narration: str
    label: str = ""
    countdown: int | None = None
    detail: str = ""
    progress: float = 0
    speech_parts: tuple = ()  # (text, English voice override); narrator uses None.
    trailing_silence: float = 0.5


@dataclass(frozen=True)
class PreparedScene:
    scene: Scene
    seconds: float
    audio: object = None


def prepare_scene(renderer, scene, directory, name, item_number):
    """The same measured and frame-aligned duration is used by preview and export."""
    import asyncio
    import math
    from engine import Cancelled
    duration = estimated_seconds(scene)
    audio = None
    if renderer.settings.speech and scene.narration.strip():
        audio = directory / f"{name}.wav"
        try:
            if scene.speech_parts:
                from engine import Renderer
                paths = []
                for index, (text, voice) in enumerate(scene.speech_parts):
                    renderer.check()
                    if not plain(text).strip():
                        continue
                    part = directory / f"{name}-turn-{index}.wav"
                    speaker = Renderer(replace(renderer.settings, english_voice=voice or renderer.settings.english_voice),
                                       renderer.log, renderer.cancel, renderer.progress)
                    asyncio.run(speaker.speech(text, part, directory))
                    paths.append(part)
                args = [arg for path in paths for arg in ("-i", path)]
                inputs = "".join(f"[{i}:a]" for i in range(len(paths)))
                renderer.run([*args, "-filter_complex", f"{inputs}concat=n={len(paths)}:v=0:a=1[out]",
                              "-map", "[out]", "-ar", "44100", "-ac", "2", audio])
            else:
                asyncio.run(renderer.speech(scene.narration, audio, directory))
            duration = renderer.audio_duration(audio) + scene.trailing_silence
            if scene.phase == "ending":
                duration = max(3, duration)
        except Cancelled:
            raise
        except Exception as error:
            raise RuntimeError(f"Câu {item_number}, {scene.phase} (TTS): {error}. Thử lại preview/xuất video.") from error
    return PreparedScene(scene, math.ceil(duration * 30) / 30, audio)


def preview_audio(renderer, prepared, directory):
    """One continuous PCM track avoids voice overlap and keeps music continuous."""
    import wave
    if not any(p.audio for p in prepared) and not renderer.settings.music:
        return None
    target = directory / "preview-track.wav"
    with wave.open(str(target), "wb") as output:
        output.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
        for part in prepared:
            renderer.check()
            remaining = round(part.seconds*44100)
            if part.audio:
                with wave.open(str(part.audio), "rb") as source:
                    while remaining:
                        block = source.readframes(min(remaining, 44100))
                        if not block:
                            break
                        output.writeframesraw(block)
                        remaining -= len(block)//4
            while remaining:
                count = min(remaining, 44100)
                output.writeframesraw(bytes(count*4))
                remaining -= count
    if renderer.settings.music:
        mixed = directory / "preview-mixed.wav"
        ending = prepared[-1].seconds if prepared[-1].scene.phase == "ending" else 0
        fade = f",afade=t=out:st={sum(p.seconds for p in prepared)-ending}:d={ending}" if ending else ""
        renderer.run(["-i", target, "-stream_loop", "-1", "-i", renderer.settings.music, "-filter_complex",
                      f"[1:a]aresample=44100,asetpts=N/SR/TB,volume={renderer.settings.music_volume}{fade}[bg];"
                      "[0:a][bg]amix=inputs=2:duration=first:normalize=0:dropout_transition=0[a]",
                      "-map", "[a]", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", mixed])
        target = mixed
    return target


def english(text):
    return text if "[en]" in text.lower() else en(text)


def multiple_choice(row, settings):
    question = row["question"]
    if settings.read_options:
        question += ". " + ". ".join(f"{chr(65+i)}. {x}" for i, x in enumerate(row["options"]))
    answer = f"Đáp án đúng là {chr(65 + row['answer_index'])}."
    if settings.voice.startswith("en") or settings.voice == "google:en":
        answer = f"The answer is {chr(65 + row['answer_index'])}."
    return [Scene("question", row["question"], question), Scene("answer", row["options"][row["answer_index"]], answer)]


def error_correction(row, settings):
    correction = f"{plain(row['highlight']['wrong'])} → {plain(row['highlight']['correct'])}"
    return [Scene("question", row["question"], row["question"], "Tìm và sửa lỗi sai"),
            Scene("wrong", row["question"], "", "Phần cần sửa", detail=row["highlight"]["wrong"]),
            Scene("answer", row["answer"], row["answer"], "Câu đã sửa", detail=correction)]


def fill_blank(row, settings):
    answer = row.get("completed_sentence") or row["question"].replace("___", plain(row["answer"]), 1)
    return [Scene("question", row["question"], row["question"], "Điền từ vào chỗ trống"),
            Scene("answer", answer, english(answer), "Câu hoàn chỉnh", detail=plain(row["answer"]))]


def word_order(row, settings):
    tokens = {t["id"]: t["text"] for t in row["tokens"]}
    return [Scene("question", " | ".join(t["text"] for t in row["tokens"]), "Sắp xếp các từ thành câu.", "Sắp xếp từ")] + [
        Scene("arrange", "", "", "Sắp xếp từ", progress=i/12) for i in range(1, 13)] + [
            Scene("answer", " ".join(tokens[t] for t in row["answer_order"]), " ".join(english(tokens[t]) for t in row["answer_order"]), "Câu hoàn chỉnh")]


def translation(row, settings):
    source = english(row["source_text"]) if row["source_language"] == "en" else row["source_text"]
    answers = row["suggested_answers"] if row.get("show_alternatives") else row["suggested_answers"][:1]
    target = "\n".join(answers)
    return [Scene("question", row["source_text"], source, "Dịch nhanh"),
            Scene("answer", target, english(target) if row["target_language"] == "en" else target, "Cách nói gợi ý")]


def listening(row, settings):
    return [Scene("question", "Nghe và đoán câu", english(row["audio_text"]), "Lắng nghe") for _ in range(row.get("replay_count", 1))] + [
        Scene("answer", row["transcript"], english(row["transcript"]) + ". " + row["translation"], "Câu vừa nghe", detail=row["translation"])]


def dialogue(row, settings):
    missing = row["missing_turn_index"]
    speakers = list(dict.fromkeys(t["speaker"] for t in row["dialogue"]))
    def voice(turn):
        label = turn["speaker"].strip().upper()
        slot = 0 if label == "A" else 1 if label == "B" else speakers.index(turn["speaker"]) % 2
        return settings.dialogue_voice_a if slot == 0 else settings.dialogue_voice_b
    question_parts = tuple((english(t["text"]), voice(t)) for i, t in enumerate(row["dialogue"]) if i != missing)
    answer_parts = tuple((english(row["suggested_answers"][0] if i == missing else t["text"]), voice(t)) for i, t in enumerate(row["dialogue"]))
    question = "\n".join(f"{t['speaker']}: " + ("___" if i == missing else t["text"]) for i, t in enumerate(row["dialogue"]))
    narration = ". ".join(english(t["text"]) for i, t in enumerate(row["dialogue"]) if i != missing)
    answer = "\n".join(f"{t['speaker']}: " + (row["suggested_answers"][0] if i == missing else t["text"]) for i, t in enumerate(row["dialogue"]))
    speech = ". ".join(english(row["suggested_answers"][0] if i == missing else t["text"]) for i, t in enumerate(row["dialogue"]))
    return [Scene("question", question, narration, "Hoàn thành hội thoại", speech_parts=question_parts),
            Scene("answer", answer, speech, "Câu đáp gợi ý", speech_parts=answer_parts)]


def true_false(row, settings):
    answer = "ĐÚNG (+)" if row["answer"] else "SAI (X)"
    return [Scene("question", row["statement"], row["statement"], "Đúng hay sai?"),
            Scene("answer", answer, ("Đúng." if row["answer"] else "Sai.") + " " + row.get("correction", ""), "Đáp án", detail=row.get("correction", ""))]


def multiple_meanings(row, settings):
    return [Scene("lesson", s["phrase"], english(s["phrase"]) + ". " + s["meaning"] + ". " + english(s["example"]),
                  plain(row["word"]), detail=s["meaning"] + "\n" + s["example"]) for s in row["senses"]]


def sentence_upgrade(row, settings):
    return [Scene("lesson", row["original"], english(row["original"]), "Câu ban đầu"),
            Scene("lesson", row["alternative"], english(row["alternative"]) + ". " + row["nuance"] + ". " + row.get("example_context", ""), "Thêm một cách nói", detail=row["nuance"] + "\n" + row.get("example_context", ""))]


def phrase_lesson(row, settings):
    return [Scene("lesson", row["phrase"], english(row["phrase"]), "Học theo cụm"),
            Scene("lesson", row["phrase"], row["meaning"], "Nghĩa", detail=row["meaning"]),
            Scene("lesson", row["example"], english(row["example"]) + ". " + row.get("example_translation", ""), "Ví dụ", detail=row.get("example_translation", ""))]


def guess_word(row, settings):
    from content_types import masked_word
    question = ". ".join(filter(None, [row["meaning_vi"], row.get("context_hint", "")]))
    voice = settings.english_voice if settings.english_voice.startswith("en-US-") else "en-US-JennyNeural"
    scenes = [Scene("question", masked_word(row["answer"]), question, "Chuẩn bị"),
              Scene("answer", row["answer"].upper(), "", "Đáp án", detail=row.get("ipa", ""), trailing_silence=1.0)]
    explanation = row["explanation"] if settings.read_explanation else ""
    scenes.append(Scene("explanation", row["answer"].upper(), explanation, "Giải thích", detail=row["explanation"],
                        speech_parts=((explanation, voice),) if explanation else ()))
    if row.get("example"):
        scenes.append(Scene("example", row["example"], english(row["example"]), "Ví dụ", detail=row.get("example_translation", "")))
        if settings.read_explanation and row.get("example_translation"):
            scenes.append(Scene("example", row["example"], row["example_translation"], "Ví dụ", detail=row["example_translation"]))
    return scenes


BUILDERS = {key: globals()[key] for key in REGISTRY}


def ending_scene():
    return Scene("ending", "", "theo dõi một chút english để học thêm một chút tiếng anh mỗi ngày nhé!")


def plan_item(row, settings):
    kind = row.get("type", "multiple_choice")
    scenes = BUILDERS[kind](row, settings)
    if row.get("prompt"):
        parts = ((row["prompt"], None),) + scenes[0].speech_parts if scenes[0].speech_parts else ()
        scenes[0] = replace(scenes[0], label=row["prompt"], narration=row["prompt"] + ". " + scenes[0].narration, speech_parts=parts)
    if not REGISTRY[kind].lesson:
        split = next(i for i, scene in enumerate(scenes) if scene.phase != "question")
        countdown = [Scene("countdown", scenes[split-1].text, "", scenes[split-1].label, n) for n in range(row.get("thinking_seconds", row.get("_default_thinking_seconds", settings.countdown)), 0, -1)]
        scenes[split:split] = countdown
        if kind != "guess_word" and settings.read_explanation and row.get("explanation"):
            last = scenes[-1]
            parts = last.speech_parts + ((row["explanation"], None),) if last.speech_parts else ()
            scenes[-1] = replace(last, narration=last.narration + " " + row["explanation"], speech_parts=parts)
    return scenes


def estimated_seconds(scene):
    if scene.phase == "answer" and not scene.narration and scene.trailing_silence == 1.0:
        return 1.0
    if scene.phase == "ending":
        return 3
    if scene.countdown is not None:
        return 1
    if scene.phase == "wrong":
        return 0.8
    if scene.phase == "arrange":
        return 1/30
    return max(3, len(plain(scene.narration or scene.text)) / 14 + scene.trailing_silence)
