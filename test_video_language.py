import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import ImageDraw
from content_renderer import render_ending, render_scene
from content_timeline import DEFAULT_ENDING_TEXT, ending_scene, plan_item
from content_types import REGISTRY, sample_document
from engine import Renderer, Settings, frame, parse_questions
from video_language import COPY_EN, CONTENT_LABELS_EN, ENGLISH_TEMPLATES


class VideoLanguageTests(unittest.TestCase):
    def test_generated_scene_labels_are_english_for_every_content_type(self):
        for template in ENGLISH_TEMPLATES:
            for kind in REGISTRY:
                document = sample_document(kind)
                _, rows = parse_questions(json.dumps(document))
                scenes = plan_item(rows[0], Settings(template=template))
                if kind != "multiple_meanings":  # These headings are authored words.
                    for scene in scenes:
                        self.assertTrue(scene.label.isascii(), (template, kind, scene.label))
            self.assertIn("The answer is B.", plan_item({"question": "Test?", "options": ["One", "Two"], "answer_index": 1}, Settings(template=template))[ -1].narration)
            row = {"type": "true_false", "statement": "Test statement", "answer": False}
            answer = plan_item(row, Settings(template=template))[-1]
            self.assertEqual(answer.text, "FALSE (X)")
            self.assertTrue(answer.narration.startswith("False."))
            self.assertEqual(ending_scene(Settings(template=template)).narration, "Keep practicing and prepare for your next exam!")
        self.assertEqual(ending_scene(Settings(template="english")).narration, DEFAULT_ENDING_TEXT)
        self.assertEqual(plan_item(row, Settings(template="english"))[-1].text, "SAI (X)")

    def test_rendered_prep_copy_is_english_in_countdown_answers_and_ending(self):
        row = {"type": "multiple_choice", "question": "Which component stores data?", "options": ["CPU", "SSD"], "answer_index": 1, "explanation": "An SSD stores files."}
        original = ImageDraw.ImageDraw.text
        for template in ENGLISH_TEMPLATES:
            rendered = []
            def capture(draw, xy, text, *args, **kwargs):
                rendered.append(text)
                return original(draw, xy, text, *args, **kwargs)
            settings = Settings(template=template, brand="Practice", left_logo_enabled=False, right_chibi_enabled=False, watermark_enabled=False)
            with patch.object(ImageDraw.ImageDraw, "text", capture):
                frame(row, 1, 2, "Practice test", settings, countdown=5)
                frame(row, 1, 2, "Practice test", settings, reveal=True)
                render_ending(settings)
                for kind, item in [
                    ("listening", dict(type="listening", audio_text="Listen", transcript="Listen", translation="Listen", explanation="Listen")),
                    ("word_order", dict(type="word_order", tokens=[dict(id="a", text="A"), dict(id="b", text="test")], answer_order=["a", "b"])),
                    ("true_false", dict(type="true_false", statement="The sky is blue.", answer=True)),
                ]:
                    for scene in plan_item(item, settings):
                        if scene.phase != "arrange":
                            render_scene(item, scene, 1, 2, "Practice test", settings)
            # The middle dot is a separator, not Vietnamese copy.
            self.assertTrue(all(text.replace("·", "").isascii() for text in rendered), rendered)
            for expected in ["05 SEC", "CHOOSE YOUR ANSWER", "ANSWER B · EXPLANATION", "PRACTICE COMPLETE", "5 seconds", "TRUE (+)"]:
                self.assertIn(expected, rendered)

    def test_authored_prompts_are_preserved_and_auto_detection_uses_english(self):
        row = dict(type="word_order", subject="ASVAB", prompt="Nội dung tự nhập", tokens=[dict(id="a", text="Test")], answer_order=["a"])
        scenes = plan_item(row, Settings())
        self.assertEqual(scenes[0].label, row["prompt"])
        self.assertIn("Put the words in order to make a sentence.", scenes[0].narration)
        self.assertEqual(ending_scene(Settings(template="exam", ending_text="My custom outro")).narration, "My custom outro")
        self.assertEqual(set(CONTENT_LABELS_EN), set(REGISTRY))

    def test_prep_uses_english_voice_for_untagged_narration_and_studio(self):
        for template in ENGLISH_TEMPLATES:
            for studio in [False, True]:
                with self.subTest(template=template, studio=studio), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    settings = Settings(template=template, english_voice="voicestudio:english" if studio else "en-US-GuyNeural", voice_studio={"enabled": studio})
                    renderer = Renderer(settings)
                    def run(args):
                        Path(args[-1]).write_bytes(b"audio")
                    with patch("preferences.BackgroundStore", return_value=SimpleNamespace(directory=root)), \
                         patch.object(renderer, "_synthesize_speech") as provider, \
                         patch.object(renderer, "_voice_studio_part") as local, \
                         patch.object(renderer, "run", side_effect=run):
                        asyncio.run(renderer.speech("The answer is B.", root/"out.wav", root))
                    if studio:
                        self.assertEqual(local.call_args.args[1], "english")
                        provider.assert_not_called()
                    else:
                        self.assertEqual(provider.call_args.args[1], "en-US-GuyNeural")
                        local.assert_not_called()


if __name__ == "__main__":
    unittest.main()
