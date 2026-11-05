import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from branding import add_logo
from content_renderer import render_ending
from engine import Settings, frame, parse_questions
from preferences import BrandingStore
from preferences import UserSettingsStore


class BrandingAssetTests(unittest.TestCase):
    def test_custom_watermark_visible_over_cards_with_footer_disabled(self):
        from dataclasses import replace
        from content_types import sample_document
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "small-logo.png"
            Image.new("RGBA", (24, 24), (255, 0, 0, 255)).save(source)
            for template in ("exam", "military", "tech", "english", "math", "classic"):
                for kind in ("multiple_choice", "fill_blank"):
                    title, rows = parse_questions(json.dumps(sample_document(kind)))
                    settings = Settings(template=template, logo_image=str(source), logo_watermark_enabled=True,
                                        watermark_enabled=False, left_logo_enabled=False, right_chibi_enabled=False)
                    visible = frame(rows[0], 1, 1, title, settings)
                    hidden = frame(rows[0], 1, 1, title, replace(settings, logo_watermark_enabled=False))
                    with self.subTest(template=template, kind=kind):
                        # Center lies inside the opaque question/answer cards.
                        self.assertNotEqual(visible.getpixel((540, 1056)), hidden.getpixel((540, 1056)))
                        self.assertEqual(visible.crop((80, 1516, 1000, 1566)).tobytes(), hidden.crop((80, 1516, 1000, 1566)).tobytes())

    def test_watermark_setting_migrates_and_saves_independently(self):
        for enabled in (False, True):
            self.assertEqual(UserSettingsStore.validated({"watermark_enabled": enabled})["logo_watermark_enabled"], enabled)
        with tempfile.TemporaryDirectory() as directory:
            store = UserSettingsStore(directory)
            store.save({"watermark_enabled": False, "logo_watermark_enabled": True})
            saved = store.load()
            self.assertFalse(saved["watermark_enabled"])
            self.assertTrue(saved["logo_watermark_enabled"])

    def test_library_reuses_uploads_after_reset_reopen_and_source_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = BrandingStore(root / "data")
            for name, color, kind in (("Logo cũ.png", "red", "logo_image"),
                                      ("Ảnh kết.png", "blue", "ending_image")):
                source = root / name
                Image.new("RGB", (80, 120), color).save(source)
                store.select(kind, source)
                source.unlink()
            store.reset("logo_image")
            store.reset("ending_image")
            reopened = BrandingStore(store.directory)
            entries = reopened.library()
            self.assertEqual({entry["name"] for entry in entries}, {"Logo cũ.png", "Ảnh kết.png"})
            logo = next(entry for entry in entries if entry["name"] == "Logo cũ.png")
            selected = reopened.select_saved("logo_image", logo["path"])
            self.assertEqual(selected["logo_image_name"], "Logo cũ.png")
            self.assertEqual(selected["ending_image"], "")
            with self.assertRaises(ValueError):
                reopened.select_saved("ending_image", root / "outside.png")
            Path(logo["path"]).unlink()
            with self.assertRaises(ValueError):
                reopened.select_saved("logo_image", logo["path"])

    def test_library_discovers_legacy_uploads_without_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BrandingStore(directory)
            assets = store.library_directory()
            assets.mkdir(parents=True)
            image = assets / "legacy.png"
            Image.new("RGB", (50, 50), "red").save(image)
            self.assertEqual(store.library(), [{"path": str(image.resolve()), "name": "legacy.png"}])

    def test_copied_images_survive_original_deletion_and_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "Ảnh của tôi.png"
            Image.new("RGBA", (80, 120), (210, 40, 30, 100)).save(original)
            store = BrandingStore(root / "data")
            store.select("logo_image", original)
            saved = store.select("ending_image", original)
            original.unlink()
            self.assertEqual(BrandingStore(store.directory).load(), saved)
            self.assertEqual(saved["logo_image_name"], original.name)
            reset = store.reset("logo_image")
            self.assertEqual(reset["logo_image"], "")
            self.assertEqual(reset["ending_image"], saved["ending_image"])
            self.assertTrue(Path(saved["logo_image"]).is_file())
            self.assertEqual(BrandingStore(store.directory).load(), reset)

    def test_tab_selection_does_not_reload_another_tabs_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = BrandingStore(root / "data"), BrandingStore(root / "data")
            first.load()
            second.load()
            image = root / "red.png"
            Image.new("RGB", (80, 120), "red").save(image)
            first_state = first.select("logo_image", image)
            second_state = second.select("ending_image", image)
            self.assertEqual(second_state["logo_image"], "")
            first.save()
            self.assertEqual(BrandingStore(first.directory).load(), first_state)
            second.save()
            self.assertEqual(BrandingStore(second.directory).load(), second_state)
            self.assertEqual(first.reset("ending_image")["logo_image"], first_state["logo_image"])

    def test_invalid_selection_and_failed_save_keep_previous_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "image.png"
            Image.new("RGB", (80, 120), "blue").save(source)
            store = BrandingStore(root / "data")
            previous = store.select("logo_image", source)
            source.write_text("broken image")
            with self.assertRaises(OSError):
                store.select("logo_image", source)
            with patch("preferences.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    store.reset("logo_image")
            self.assertEqual(store.load(), previous)

    def test_invalid_saved_logo_preserves_valid_ending(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "ending.png"
            Image.new("RGB", (80, 120), "blue").save(source)
            store = BrandingStore(root / "data")
            previous = store.select("ending_image", source)
            data = json.loads(store.config.read_text(encoding="utf-8"))
            data["logo_image"] = {"file": "../outside.png"}
            store.config.write_text(json.dumps(data), encoding="utf-8")
            loaded = store.load()
            self.assertEqual(loaded["logo_image"], "")
            self.assertEqual(loaded["ending_image"], previous["ending_image"])
            self.assertTrue(store.warning)

    def test_rendered_custom_ending_and_default_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "ending.png"
            Image.new("RGB", (90, 160), "red").save(source)
            custom = render_ending(Settings(width=180, height=320, ending_image=str(source)))
            self.assertEqual(custom.size, (180, 320))
            self.assertEqual(custom.getpixel((90, 160)), (255, 0, 0))
            default = render_ending(Settings(width=180, height=320))
            self.assertNotEqual(custom.tobytes(), default.tobytes())

    def test_logo_replacement_in_all_templates_and_learning_content(self):
        title, rows = parse_questions(json.dumps([
            {"question": "One?", "options": ["One", "Two"], "answer": "A"}
        ]))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "logo.png"
            Image.new("RGB", (1000, 1000), "red").save(source)
            for template in ("math", "english", "classic"):
                with self.subTest(template=template):
                    result = frame(rows[0], 1, 1, title, Settings(template=template, logo_image=str(source), left_logo_image=str(source)))
                    self.assertEqual(result.getpixel((100, 160)), (255, 0, 0))
            title, rows = parse_questions((Path(__file__).parent / "examples/guess_word.json").read_text(encoding="utf-8"))
            result = frame(rows[0], 1, len(rows), title, Settings(logo_image=str(source), left_logo_image=str(source)))
            self.assertEqual(result.getpixel((100, 160)), (255, 0, 0))

    def test_parallel_watermark_rendering_keeps_separate_images_and_alpha(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            red, blue = root / "red.png", root / "blue.png"
            Image.new("RGBA", (1000, 1000), (255, 0, 0, 128)).save(red)
            Image.new("RGBA", (1000, 1000), (0, 0, 255, 128)).save(blue)

            def render(path):
                canvas = Image.new("RGBA", (1080, 1920))
                add_logo(canvas, watermark=True, logo_image=str(path))
                return canvas.getpixel((540, 960))

            with ThreadPoolExecutor(max_workers=2) as executor:
                pixels = list(executor.map(render, [red, blue, red, blue]))
            self.assertEqual(pixels, [(255, 0, 0, 9), (0, 0, 255, 9)] * 2)


if __name__ == "__main__":
    unittest.main()
