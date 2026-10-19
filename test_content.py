import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from content_types import DEFAULT_MODE, REGISTRY, normalize, sample_document, export_document
from content_timeline import plan_item, prepare_scene, PreparedScene, preview_audio
from content_renderer import render_scene
from engine import Settings, Renderer, parse_legacy_questions, parse_questions


class ContentTests(unittest.TestCase):
    def parse(self, doc):
        return normalize(doc, parse_legacy_questions)

    def test_corrected_word_is_drawn_once_on_same_baseline(self):
        from PIL import ImageDraw
        from content_timeline import Scene
        row = dict(type="error_correction", question="He go to school every day.",
                   answer="He goes to school every day.", highlight=dict(wrong="go", correct="goes"))
        calls = []
        original = ImageDraw.ImageDraw.text
        def capture(draw, xy, text, *args, **kwargs):
            if 450 <= xy[1] < 840:
                calls.append((xy, text, kwargs))
            return original(draw, xy, text, *args, **kwargs)
        with patch.object(ImageDraw.ImageDraw, "text", new=capture):
            render_scene(row, Scene("answer", row["answer"], ""), 1, 1, "Test", Settings(watermark_enabled=False))
        selected = [call for call in calls if call[1] == "goes"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0][2]["fill"], "#1267b1")
        self.assertEqual(selected[0][2]["anchor"], "ls")
        baseline = selected[0][0][1]
        same_line = [call for call in calls if call[0][1] == baseline]
        self.assertEqual("".join(call[1] for call in same_line), "He goes to school every")
        self.assertTrue(all(call[2]["anchor"] == "ls" for call in same_line))

    def test_long_fill_blank_instruction_keeps_readable_text(self):
        from PIL import ImageDraw
        doc = sample_document("fill_blank")
        doc["title"] = "10 CÂU TIẾNG ANH: ĐIỀN LÀ GHIỀN!"
        doc["items"][0].update(prompt="Dùng dạng đúng của [en]have[/en]: Cảm ơn bạn! Tôi đã có khoảng thời gian rất vui.",
                               question="[en]Thanks! I ___ a great time.[/en]", answer="[en]had[/en]",
                               completed_sentence="[en]Thanks! I had a great time.[/en]")
        title, rows, _ = self.parse(doc)
        calls = []
        original = ImageDraw.ImageDraw.text
        def capture(draw, xy, text, *args, **kwargs):
            calls.append((xy, kwargs["font"].size))
            return original(draw, xy, text, *args, **kwargs)
        with patch.object(ImageDraw.ImageDraw, "text", new=capture):
            for scene in plan_item(rows[0], Settings()):
                render_scene(rows[0], scene, 10, 10, title, Settings(watermark_enabled=False))
        self.assertTrue(all(size >= 30 for _, size in calls))
        # The instruction occupies multiple lines before the main sentence.
        self.assertGreater(len({xy[1] for xy, _ in calls if 418 <= xy[1] < 650}), 1)

    def test_layout_failure_precedes_speech_and_preserves_output(self):
        doc = sample_document("fill_blank")
        doc["items"][0]["prompt"] = "Nội dung rất dài. " * 300
        title, rows, _ = self.parse(doc)
        renderer = Renderer(Settings())
        with tempfile.TemporaryDirectory() as directory, patch.object(renderer, "speech") as speech:
            output = Path(directory) / "existing.mp4"
            output.write_bytes(b"original")
            with self.assertRaisesRegex(ValueError, "Câu 1: hướng dẫn"):
                renderer.render(title, rows, output)
            speech.assert_not_called()
            self.assertEqual(output.read_bytes(), b"original")

    def test_samples_roundtrip_and_render_every_scene(self):
        settings = Settings(speech=False, width=180, height=320)
        for mode in [*REGISTRY, "mixed"]:
            with self.subTest(mode=mode):
                title, rows, actual = self.parse(sample_document(mode))
                self.assertEqual(actual, mode)
                self.parse(export_document(title, rows, mode))
                for row in rows:
                    for scene in plan_item(row, settings):
                        self.assertEqual(render_scene(row, scene, 1, len(rows), title, settings).size, (180, 320))

    def test_new_layouts_keep_header_artwork_and_clear_mobile_footer(self):
        from PIL import Image
        settings = Settings(speech=False, watermark_enabled=False, width=180, height=320)
        for kind in REGISTRY:
            if kind == "multiple_choice":
                continue
            title, rows, _ = self.parse(sample_document(kind))
            for scene in (plan_item(rows[0], settings)[0], plan_item(rows[0], settings)[-1]):
                with self.subTest(kind=kind, phase=scene.phase):
                    image = render_scene(rows[0], scene, 1, 1, title, settings)
                    header = image.crop((0, 24, 180, 44))
                    self.assertNotEqual(header.tobytes(), Image.new("RGB", header.size, "#e6f1f8").tobytes())
                    footer = image.crop((0, 263, 180, 320))
                    self.assertEqual(footer.tobytes(), Image.new("RGB", footer.size, "#e6f1f8").tobytes())

    def test_listening_and_missing_dialogue_never_leak_before_reveal(self):
        for kind, secret in [("listening", "How are you today?"), ("dialogue", "I'm fine, thanks.")]:
            _, rows, _ = self.parse(sample_document(kind))
            row = rows[0]
            if kind == "dialogue":
                row["dialogue"][1]["text"] = secret
            for scene in plan_item(row, Settings()):
                if scene.phase in ("question", "countdown"):
                    self.assertNotIn(secret, scene.text)
                    self.assertNotIn(secret, scene.detail)

    def test_countdown_after_all_question_audio_and_overrides(self):
        doc = sample_document("listening")
        doc["settings"]["thinking_seconds"] = 7
        doc["items"][0]["replay_count"] = 2
        _, rows, _ = self.parse(doc)
        scenes = plan_item(rows[0], Settings())
        self.assertEqual([s.phase for s in scenes[:3]], ["question", "question", "countdown"])
        self.assertEqual([s.countdown for s in scenes if s.countdown], list(range(7, 0, -1)))
        rows[0]["thinking_seconds"] = 2
        self.assertEqual(len([s for s in plan_item(rows[0], Settings()) if s.countdown]), 2)

    def test_lessons_without_answer_or_countdown(self):
        for kind in ("multiple_meanings", "phrase_lesson", "sentence_upgrade"):
            _, rows, _ = self.parse(sample_document(kind))
            self.assertTrue(all(s.phase == "lesson" for s in plan_item(rows[0], Settings())))

    def test_invalid_fields_report_item_and_do_not_mutate_input(self):
        cases = [("multiple_choice", "answer", "Z"), ("fill_blank", "question", "___ and ___"),
                 ("word_order", "answer_order", ["unknown"]), ("listening", "transcript", ""),
                 ("phrase_lesson", "phrase", "[en]oops"), ("true_false", "answer", "false")]
        for kind, field, value in cases:
            doc = sample_document(kind)
            doc["items"][0][field] = value
            before = copy.deepcopy(doc)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "Câu 1"):
                self.parse(doc)
            self.assertEqual(before, doc)

    def test_highlight_occurrence_and_token_duplicates(self):
        doc = sample_document("error_correction")
        row = doc["items"][0]
        row.update(question="[en]go go[/en]", answer="[en]go goes[/en]", highlight=dict(wrong="go", correct="goes", occurrence=2))
        self.parse(doc)
        row["highlight"]["occurrence"] = 1
        with self.assertRaises(ValueError):
            self.parse(doc)
        doc = sample_document("word_order")
        doc["items"][0]["tokens"][1]["text"] = doc["items"][0]["tokens"][0]["text"]
        self.parse(doc)  # Same text, distinct IDs are valid.

    def test_default_and_legacy_compatibility(self):
        self.assertEqual(DEFAULT_MODE, "multiple_choice")
        title, rows = parse_questions(Path("examples/questions.json").read_text(encoding="utf-8"))
        self.assertTrue(rows)
        self.assertTrue(all(row["type"] == DEFAULT_MODE for row in rows))

    def test_measured_audio_duration_and_failure(self):
        _, rows, _ = self.parse(sample_document("listening"))
        scene = plan_item(rows[0], Settings())[0]
        renderer = Renderer(Settings())
        async def speech(*args, **kwargs):
            pass
        with tempfile.TemporaryDirectory() as directory, patch.object(renderer, "speech", side_effect=speech), patch.object(renderer, "audio_duration", return_value=8.4):
            prepared = prepare_scene(renderer, scene, Path(directory), "test", 3)
            self.assertGreaterEqual(prepared.seconds, 8.9)
        with tempfile.TemporaryDirectory() as directory, patch.object(renderer, "speech", side_effect=RuntimeError("network")):
            with self.assertRaisesRegex(RuntimeError, "Câu 3.*TTS"):
                prepare_scene(renderer, scene, Path(directory), "test", 3)

    def test_all_modes_export_real_mp4(self):
        # One mixed render exercises every renderer, transition and the existing CTA.
        doc = sample_document("mixed")
        doc["settings"]["thinking_seconds"] = 0
        title, rows, _ = self.parse(doc)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "mixed.mp4"
            Renderer(Settings(speech=False, width=180, height=320)).render(title, rows, output)
            self.assertGreater(output.stat().st_size, 1000)

    def test_preview_audio_has_exact_scene_lengths_and_silence(self):
        import wave
        from content_timeline import Scene
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "voice.wav"
            with wave.open(str(audio), "wb") as output:
                output.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
                output.writeframes(b"\x01\x00\x01\x00" * 44100)
            scene = Scene("question", "", "")
            parts = [PreparedScene(scene, 1.5, audio), PreparedScene(scene, 1)]
            target = preview_audio(Renderer(Settings()), parts, root)
            with wave.open(str(target), "rb") as source:
                self.assertEqual(source.getnframes(), round(2.5*44100))
                self.assertEqual(source.readframes(44100), b"\x01\x00\x01\x00"*44100)
                self.assertEqual(set(source.readframes(round(1.5*44100))), {0})

    def test_dialogue_uses_each_speakers_voice_and_narrator(self):
        import wave
        settings = Settings(english_voice="google:en", dialogue_voice_a="en-US-JennyNeural", dialogue_voice_b="en-US-GuyNeural")
        doc = sample_document("dialogue")
        doc["items"][0]["prompt"] = "Hoàn thành đoạn hội thoại."
        _, rows, _ = self.parse(doc)
        scenes = plan_item(rows[0], settings)
        question, answer = scenes[0], scenes[-1]
        self.assertEqual([v for _, v in question.speech_parts], [None, settings.dialogue_voice_a])
        self.assertEqual([v for _, v in answer.speech_parts], [settings.dialogue_voice_a, settings.dialogue_voice_b, None])
        self.assertNotIn("I'm fine", " ".join(t for t, _ in question.speech_parts))
        captured = []
        async def fake_speech(speaker, text, target, directory, on_part=lambda fraction: None):
            captured.append((text, speaker.settings.english_voice))
            with wave.open(str(target), "wb") as output:
                output.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
                output.writeframes(bytes(4410*4))
        with tempfile.TemporaryDirectory() as directory, patch.object(Renderer, "speech", new=fake_speech):
            prepared = prepare_scene(Renderer(settings), answer, Path(directory), "answer", 1)
            self.assertTrue(prepared.audio.is_file())
            self.assertGreaterEqual(prepared.seconds, .8)
        self.assertEqual([v for _, v in captured], [settings.dialogue_voice_a, settings.dialogue_voice_b, settings.english_voice])
        settings.read_explanation = False
        self.assertEqual(len(plan_item(rows[0], settings)[-1].speech_parts), 2)


if __name__ == "__main__":
    unittest.main()
