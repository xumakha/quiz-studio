"""Exercise actual macOS playback with local WAVs, without a TTS network call."""
import sys
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from app import App
from engine import Renderer


@unittest.skipUnless(sys.platform == "darwin", "macOS audio integration")
class MacAudioTests(unittest.TestCase):
    def test_preview_seek_stop_and_voice_sample(self):
        generated = []

        async def local_speech(renderer, text, target, directory, **kwargs):
            generated.append(Path(target))
            with wave.open(str(target), "wb") as stream:
                stream.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
                stream.writeframes(bytes(44100 * 4))

        with tempfile.TemporaryDirectory() as directory:
            app = App(data_dir=directory)
            app.withdraw()
            try:
                app.speech.set(True)
                app.countdown.set(3)
                app.update()
                with patch.object(Renderer, "speech", local_speech), patch("app.messagebox.showerror") as errors:
                    app.play_preview()
                    deadline = time.monotonic() + 15
                    while app.audio_player.process is None and time.monotonic() < deadline:
                        app.update()
                        time.sleep(0.02)
                    process = app.audio_player.process
                    errors.assert_not_called()
                    self.assertIsNotNone(process, app.validation.cget("text"))
                    self.assertIsNone(process.poll())
                    preview_directory = app.preview_directory
                    app.seek_preview(0.5)
                    self.assertIsNot(process, app.audio_player.process)
                    self.assertIsNotNone(process.poll())
                    replacement = app.audio_player.process
                    self.assertIsNone(replacement.poll())
                    app.stop_preview()
                    self.assertIsNotNone(replacement.poll())
                    self.assertFalse(preview_directory.exists())
                    # Complete the worker's queued status before the next action.
                    app.update()
                    app.busy = False
                    results = []
                    with patch.object(app, "start_job", lambda job: results.append(job())):
                        app.voice_preview()
                    self.assertEqual(results, ["Đã phát giọng nghe thử."])
                    self.assertIsNone(app.audio_player.process)
                    self.assertFalse(generated[-1].exists())
                    errors.assert_not_called()
            finally:
                app.busy = False
                app.close()


if __name__ == "__main__":
    unittest.main()
