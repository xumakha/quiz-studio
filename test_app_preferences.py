import tempfile
import unittest
import wave
import time
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from app import App
from preferences import USER_DEFAULTS, UserSettingsStore


class AppBackgroundTests(unittest.TestCase):
    def test_video_preview_animates_and_stops_when_background_changes(self):
        from engine import Renderer, Settings
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "video.mp4"
            Renderer(Settings()).run([
                "-f", "lavfi", "-i", "testsrc2=size=180x320:rate=30:duration=0.7",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", source])
            app = App(data_dir=root / "data")
            app.withdraw()
            def pump(seconds):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    app.update()
                    time.sleep(0.02)
            try:
                pump(0.1)
                app.background = str(source)
                self.assertTrue(app.show_preview())
                reader = app.background_preview_reader
                pump(0.8)
                first = reader.image.tobytes()
                pump(0.3)
                self.assertNotEqual(first, reader.image.tobytes())
                app.speech.set(False)
                app.countdown.set(1)
                app.play_preview()
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and not getattr(app, "preview_directory", None):
                    pump(0.1)
                self.assertIsNotNone(app.preview_directory)
                live = app.background_preview_reader
                pump(0.4)
                self.assertIsNotNone(live.image)
                app.seek_preview(0.5)
                self.assertIsNot(live, app.background_preview_reader)
                live.thread.join(timeout=3)
                self.assertFalse(live.thread.is_alive())
                pump(0.4)
                current = app.background_preview_reader
                app.background = ""
                self.assertTrue(app.show_preview())
                current.thread.join(timeout=3)
                self.assertFalse(current.thread.is_alive())
                self.assertIsNone(app.background_preview_reader)
            finally:
                app.close()

    def test_selection_survives_close_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "background.png"
            Image.new("RGB", (1080, 1920), (150, 190, 220)).save(source)
            music = root / "nhạc nền.wav"
            with wave.open(str(music), "wb") as stream:
                stream.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
                stream.writeframes(b"\x00" * 44100 * 4)
            chosen = {"voice": "Việt • Nam — Nam Minh", "en_voice": "English • Male — Guy",
                      "dialogue_voice_a": "English • Google (HTTP)", "dialogue_voice_b": "English • Female — Jenny",
                      "rate": 25, "pitch": -10, "countdown": 9, "resolution": "720 × 1280",
                      "video_template": "Tiếng Anh · Xanh sáng", "brand": "Mọt Chữ English",
                      "watermark_enabled": False, "read_options": False, "read_explanation": False, "speech": False,
                      "music_volume": 27, "reveal": True}
            self.assertEqual(set(chosen), set(USER_DEFAULTS))
            app = App(data_dir=root / "data")
            app.withdraw()
            try:
                with patch("app.filedialog.askopenfilename", return_value=str(source)):
                    app.choose_media("background")
                selected = app.background
                self.assertEqual(len(app.background_library_entries["images"]), 1)
                app.clear_media()
                app.background_library_boxes["images"].current(0)
                app.choose_saved_background("images")
                self.assertEqual(app.background, selected)
                app.background_dim.set(8)
                for name, value in chosen.items():
                    getattr(app, name).set(value)
                with patch("app.filedialog.askopenfilename", return_value=str(music)):
                    app.choose_media("music")
                selected_music = app.music
                # Changes are saved while the app stays open, not only on exit.
                app.rate.set(26)
                chosen["rate"] = 26
                app.after(450, app.quit)
                app.mainloop()
                self.assertEqual(UserSettingsStore(root / "data").load()["rate"], 26)
            finally:
                app.close()
            source.unlink()
            music.unlink()
            app = App(data_dir=root / "data")
            app.withdraw()
            try:
                self.assertEqual(app.background, selected)
                self.assertEqual(app.background_dim.get(), 8)
                self.assertEqual(app.music, selected_music)
                self.assertEqual(app.music_name, "nhạc nền.wav")
                self.assertTrue(Path(app.music).is_file())
                for name, value in chosen.items():
                    self.assertEqual(getattr(app, name).get(), value, name)
                self.assertEqual(app.watermark_entry.cget("state"), "disabled")
                self.assertTrue(app.show_preview())
                self.assertEqual(app.settings().background, selected)
                self.assertFalse(app.settings().read_explanation)
                app.clear_media()
            finally:
                app.close()
            app = App(data_dir=root / "data")
            app.withdraw()
            try:
                self.assertEqual(app.background, "")
                self.assertEqual(app.music, "")
                self.assertEqual(app.music_volume.get(), 27)
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
