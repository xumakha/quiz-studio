import json
import tempfile
import unittest
from unittest.mock import patch

from app import App
from content_types import sample_document
from engine import frame
from video_themes import TEMPLATES


class PrepInterfaceTests(unittest.TestCase):
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
