import tempfile
import unittest
import json
from unittest.mock import patch
from pathlib import Path
from PIL import Image
from preferences import BackgroundStore, UserSettingsStore, USER_DEFAULTS


class UserSettingsTests(unittest.TestCase):
    def test_invalid_settings_and_missing_music_preserve_valid_values(self):
        with tempfile.TemporaryDirectory() as directory:
            store = UserSettingsStore(directory)
            store.config.write_text(json.dumps({"rate": 999, "countdown": True, "voice": "missing",
                                               "brand": "Page của tôi", "music_volume": 30,
                                               "music_file": "missing.mp3"}), encoding="utf-8")
            state = store.load()
            self.assertEqual(state["rate"], USER_DEFAULTS["rate"])
            self.assertEqual(state["countdown"], USER_DEFAULTS["countdown"])
            self.assertEqual(state["voice"], USER_DEFAULTS["voice"])
            self.assertEqual(state["brand"], "Page của tôi")
            self.assertEqual(state["music_volume"], 30)
            self.assertEqual(state["music"], "")
            self.assertTrue(store.warning)
            store.config.write_text("[]")
            self.assertEqual(store.load()["rate"], 0)
            self.assertTrue(store.warning)

    def test_failed_save_keeps_previous_settings_and_music(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "music.wav"
            source.write_bytes(b"audio")
            store = UserSettingsStore(root / "data")
            previous = store.select_music(source, {**USER_DEFAULTS, "rate": 15})
            source.unlink()
            with patch("preferences.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    store.clear_music({**USER_DEFAULTS, "rate": 20})
            state = UserSettingsStore(root / "data").load()
            self.assertEqual(state["rate"], 15)
            self.assertEqual(state["music"], previous["music"])
            self.assertEqual(store.music_file, Path(previous["music"]).name)


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
