import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from app import App


class AppBackgroundTests(unittest.TestCase):
    def test_selection_survives_close_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "background.png"
            Image.new("RGB", (1080, 1920), (150, 190, 220)).save(source)
            app = App(data_dir=root / "data")
            app.withdraw()
            try:
                with patch("app.filedialog.askopenfilename", return_value=str(source)):
                    app.choose_media("background")
                selected = app.background
                app.background_dim.set(8)
            finally:
                app.close()
            source.unlink()
            app = App(data_dir=root / "data")
            app.withdraw()
            try:
                self.assertEqual(app.background, selected)
                self.assertEqual(app.background_dim.get(), 8)
                self.assertTrue(app.show_preview())
                self.assertEqual(app.settings().background, selected)
                app.clear_media()
            finally:
                app.close()
            app = App(data_dir=root / "data")
            app.withdraw()
            try:
                self.assertEqual(app.background, "")
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
