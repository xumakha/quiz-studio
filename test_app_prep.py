import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from app import App
from content_types import sample_document
from engine import frame
from video_themes import TEMPLATES


class PrepInterfaceTests(unittest.TestCase):
    def test_selecting_uploaded_or_saved_watermark_enables_only_the_logo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "my-logo.png"
            Image.new("RGB", (40, 40), "red").save(source)
            host = App(data_dir=root / "data")
            host.withdraw()
            try:
                tab = host.tabs[1]
                self.assertFalse(tab.logo_watermark_enabled.get())
                self.assertFalse(tab.watermark_enabled.get())
                with patch("app.filedialog.askopenfilename", return_value=str(source)):
                    tab.choose_branding("logo_image")
                self.assertTrue(tab.logo_watermark_enabled.get())
                self.assertFalse(tab.watermark_enabled.get())
                self.assertTrue(tab.show_preview())
                self.assertFalse(host.tabs[2].logo_watermark_enabled.get())
                tab.logo_watermark_enabled.set(False)
                tab.branding_library_boxes["logo_image"].current(0)
                tab.choose_saved_branding("logo_image")
                self.assertTrue(tab.logo_watermark_enabled.get())
                self.assertFalse(tab.watermark_enabled.get())
                self.assertTrue(tab.persist())
                self.assertTrue(tab.user_store.load()["logo_watermark_enabled"])
            finally:
                host.close()

    def test_templates_and_countdown_refresh_in_each_tab(self):
        with tempfile.TemporaryDirectory() as directory:
            host = App(data_dir=directory)
            host.withdraw()
            try:
                english, easy, asvab = host.tabs
                self.assertEqual(TEMPLATES[easy.video_template.get()], "exam")
                self.assertEqual(TEMPLATES[asvab.video_template.get()], "military")
                self.assertFalse(easy.right_chibi_enabled.get())
                for label in TEMPLATES:
                    easy.video_template.set(label)
                    self.assertTrue(easy.show_preview(), easy.validation.cget("text"))
                self.assertEqual(TEMPLATES[asvab.video_template.get()], "military")
                doc = sample_document("guess_word")
                doc.pop("settings", None)
                easy.content_editor.write(json.dumps(doc))
                self.assertTrue(easy.validate())
                with patch("app.frame", wraps=frame) as render:
                    easy.countdown.set(8)
                    self.assertEqual(render.call_args.kwargs["countdown"], 8)
                    easy.rows[0]["thinking_seconds"] = 3
                    easy.countdown.set(9)
                    self.assertEqual(render.call_args.kwargs["countdown"], 3)
                self.assertEqual(english.countdown.get(), 5)
            finally:
                host.close()


if __name__ == "__main__":
    unittest.main()
