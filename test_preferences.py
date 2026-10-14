import tempfile
import unittest
from pathlib import Path
from PIL import Image
from preferences import BackgroundStore


class BackgroundPersistenceTests(unittest.TestCase):
    def test_reopen_after_original_is_deleted_and_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "ảnh nền.png"
            Image.new("RGB", (100, 180), (120, 200, 240)).save(original)
            store = BackgroundStore(root / "data")
            selected = store.select(original, 20)
            original.unlink()
            reopened = BackgroundStore(root / "data")
            self.assertEqual(reopened.load(), selected)
            self.assertTrue(Path(reopened.load()["background"]).is_file())
            reopened.save_dim(7)
            self.assertEqual(BackgroundStore(root / "data").load()["background_dim"], 7)
            reopened.clear(7)
            self.assertEqual(BackgroundStore(root / "data").load()["background"], "")

    def test_bad_selection_keeps_existing_background(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = root / "valid.png"
            invalid = root / "invalid.png"
            Image.new("RGB", (50, 50)).save(valid)
            invalid.write_text("not an image")
            store = BackgroundStore(root / "data")
            previous = store.select(valid, 12)
            with self.assertRaises(OSError):
                store.select(invalid, 12)
            self.assertEqual(store.load(), previous)
            store.config.write_text("broken json")
            self.assertEqual(store.load()["background"], "")
            self.assertTrue(store.warning)


if __name__ == "__main__":
    unittest.main()
