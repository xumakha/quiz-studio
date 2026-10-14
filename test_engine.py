import json
import tempfile
import threading
import unittest
from pathlib import Path
from PIL import Image

from engine import Cancelled, Renderer, Settings, frame, parse_questions
from video_themes import detect_template


class EngineTests(unittest.TestCase):
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
        area = (0, 1800, 1080, 1920)
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
