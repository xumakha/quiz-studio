"""Independent corner images across templates, persistence and alpha layers."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from branding import add_logo
from engine import Settings, frame, parse_questions
from preferences import BrandingStore


class CornerBrandingTests(unittest.TestCase):
    def test_corner_toggles_and_replacements_in_every_render_path(self):
        title, rows = parse_questions('[{"question":"One?","options":["One","Two"],"answer":0}]')
        guess_title, guess_rows = parse_questions((Path(__file__).parent / "examples/guess_word.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            left, right = Path(directory) / "left.png", Path(directory) / "right.png"
            Image.new("RGB", (1000, 1000), "red").save(left)
            Image.new("RGB", (1000, 1000), "blue").save(right)
            for template, quiz_title, row in [(kind, title, rows[0]) for kind in ("math", "english", "classic")] + [("english", guess_title, guess_rows[0])]:
                for enabled_left, enabled_right in ((False, False), (True, False), (False, True), (True, True)):
                    with self.subTest(template=template, kind=row["type"], left=enabled_left, right=enabled_right):
                        settings = Settings(template=template, left_logo_image=str(left), right_chibi_image=str(right),
                                            left_logo_enabled=enabled_left, right_chibi_enabled=enabled_right)
                        picture = frame(row, 1, 1, quiz_title, settings)
                        self.assertEqual(picture.getpixel((100, 160)) == (255, 0, 0), enabled_left)
                        self.assertEqual(picture.getpixel((900, 160)) == (0, 0, 255), enabled_right)

    def test_disabled_corners_do_not_load_images_or_hide_watermark(self):
        settings = Settings(left_logo_enabled=False, right_chibi_enabled=False,
                            left_logo_image="missing-left.png", right_chibi_image="missing-right.png")
        canvas = Image.new("RGBA", (1080, 1920))
        add_logo(canvas, settings=settings)
        self.assertIsNone(canvas.getbbox())
        add_logo(canvas, watermark=True, logo_image=settings.logo_image)
        self.assertIsNotNone(canvas.getbbox())
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "transparent.png"
            Image.new("RGBA", (100, 100), (0, 0, 255, 128)).save(source)
            settings.right_chibi_enabled = True
            settings.right_chibi_image = str(source)
            clean = Image.new("RGBA", canvas.size)
            add_logo(clean, settings=settings)
            self.assertEqual(clean.getpixel((910, 60)), (0, 0, 255, 128))

    def test_corner_uploads_survive_reopen_and_legacy_logo_migrates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "Ảnh góc.png"
            Image.new("RGB", (100, 100), "red").save(image)
            store = BrandingStore(root / "data")
            state = store.select("left_logo_image", image)
            store.select_saved("right_chibi_image", state["left_logo_image"])
            image.unlink()
            restored = BrandingStore(store.directory).load()
            self.assertEqual(restored["right_chibi_image"], state["left_logo_image"])
            self.assertEqual(restored["right_chibi_image_name"], "Ảnh góc.png")
            store.config.write_text(json.dumps({"logo_image": {"file": Path(state["left_logo_image"]).name,
                                                                    "name": "Logo trước đây"}}), encoding="utf-8")
            migrated = BrandingStore(store.directory).load()
            self.assertEqual(migrated["left_logo_image"], migrated["logo_image"])
            self.assertEqual(migrated["left_logo_image_name"], "Logo trước đây")
            self.assertEqual(migrated["right_chibi_image"], "")


if __name__ == "__main__":
    unittest.main()
