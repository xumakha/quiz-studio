"""Offline regression tests for transient speech failures and cancellation."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from edge_tts.exceptions import NoAudioReceived
from gtts.tts import gTTSError

from engine import Cancelled, Renderer, Settings, SpeechError


class SpeechRetryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.renderer = Renderer(Settings(voice="en-US-GuyNeural", rate=26, pitch=-5))
        self.path = self.root / "voice.mp3"

    def save_audio(self, path):
        Path(path).write_bytes(b"complete audio")

    def test_edge_retries_with_fresh_request_and_preserves_selected_voice(self):
        async def partial_failure(path):
            Path(path).write_bytes(b"partial response")
            raise NoAudioReceived("No audio was received.")

        failed = SimpleNamespace(save=AsyncMock(side_effect=partial_failure))
        successful = SimpleNamespace(save=AsyncMock(side_effect=self.save_audio))
        with patch("engine.edge_tts.Communicate", side_effect=[failed, successful]) as edge, \
             patch("engine.gTTS") as google, \
             patch.object(self.renderer.cancel, "wait", return_value=False):
            asyncio.run(self.renderer._synthesize_speech("Hello!", "en-US-GuyNeural", self.path))
        self.assertEqual(self.path.read_bytes(), b"complete audio")
        self.assertEqual(edge.call_count, 2)
        failed.save.assert_awaited_once()
        successful.save.assert_awaited_once()
        for call in edge.call_args_list:
            self.assertEqual(call.args[:2], ("Hello!", "en-US-GuyNeural"))
            self.assertEqual(call.kwargs["rate"], "+26%")
            self.assertEqual(call.kwargs["pitch"], "-5Hz")
        google.assert_not_called()
        self.assertEqual(self.renderer.settings.voice, "en-US-GuyNeural")

    def test_exhausted_edge_attempts_report_voice_and_never_cache_partial_audio(self):
        async def partial_failure(path):
            Path(path).write_bytes(b"partial response")
            raise NoAudioReceived("No audio was received.")

        with patch("preferences.BackgroundStore", return_value=SimpleNamespace(directory=self.root)), \
             patch("engine.edge_tts.Communicate") as edge, patch("engine.gTTS") as google, \
             patch.object(self.renderer.cancel, "wait", return_value=False), \
             patch.object(self.renderer, "run") as ffmpeg:
            edge.return_value.save = AsyncMock(side_effect=partial_failure)
            target = self.root / "result.wav"
            with self.assertRaises(SpeechError) as raised:
                asyncio.run(self.renderer.speech("Hello!", target, self.root))
        self.assertEqual(edge.call_count, 3)
        self.assertIn("en-US-GuyNeural", str(raised.exception))
        self.assertIn("(TTS)", str(raised.exception))
        self.assertFalse(target.exists())
        self.assertEqual(list((self.root / "tts-cache").iterdir()), [])
        ffmpeg.assert_not_called()
        google.assert_not_called()

    def test_cancel_after_failed_request_stops_without_another_attempt(self):
        async def cancel_request(path):
            self.renderer.cancel.set()
            raise NoAudioReceived("No audio was received.")

        with patch("engine.edge_tts.Communicate") as edge, \
             patch.object(self.renderer.cancel, "wait") as wait:
            edge.return_value.save = AsyncMock(side_effect=cancel_request)
            with self.assertRaises(Cancelled):
                asyncio.run(self.renderer._synthesize_speech("Hello!", "en-US-GuyNeural", self.path))
        self.assertEqual(edge.call_count, 1)
        wait.assert_not_called()

    def test_cancel_during_retry_delay_stops_without_another_attempt(self):
        def cancel_wait(seconds):
            self.renderer.cancel.set()
            return True

        with patch("engine.edge_tts.Communicate") as edge, \
             patch.object(self.renderer.cancel, "wait", side_effect=cancel_wait):
            edge.return_value.save = AsyncMock(side_effect=NoAudioReceived("No audio was received."))
            with self.assertRaises(Cancelled):
                asyncio.run(self.renderer._synthesize_speech("Hello!", "en-US-GuyNeural", self.path))
        self.assertEqual(edge.call_count, 1)

    def test_google_retries_transient_failure_without_switching_provider(self):
        attempts = []

        def save(path):
            attempts.append(path)
            if len(attempts) == 1:
                raise gTTSError("temporary service failure")
            self.save_audio(path)

        with patch("engine.gTTS") as google, patch("engine.edge_tts.Communicate") as edge, \
             patch.object(self.renderer.cancel, "wait", return_value=False):
            google.return_value.save.side_effect = save
            asyncio.run(self.renderer._synthesize_speech("Xin chào!", "google:vi", self.path))
        self.assertEqual(google.call_count, 2)
        for call in google.call_args_list:
            self.assertEqual(call.args[0], "Xin chào!")
            self.assertEqual(call.kwargs["lang"], "vi")
        edge.assert_not_called()
        self.assertEqual(self.path.read_bytes(), b"complete audio")

    def test_empty_provider_response_is_retried_and_reported(self):
        with patch("engine.edge_tts.Communicate") as edge, \
             patch.object(self.renderer.cancel, "wait", return_value=False):
            edge.return_value.save = AsyncMock(side_effect=lambda path: Path(path).touch())
            with self.assertRaises(SpeechError):
                asyncio.run(self.renderer._synthesize_speech("Hello!", "en-US-GuyNeural", self.path))
        self.assertEqual(edge.call_count, 3)

    def test_local_or_invalid_parameter_failures_are_not_retried(self):
        for error in (OSError("disk full"), ValueError("invalid voice")):
            with self.subTest(error=error), patch("engine.edge_tts.Communicate") as edge, \
                 patch.object(self.renderer.cancel, "wait") as wait:
                edge.return_value.save = AsyncMock(side_effect=error)
                with self.assertRaises(type(error)):
                    asyncio.run(self.renderer._synthesize_speech("Hello!", "en-US-GuyNeural", self.path))
                self.assertEqual(edge.call_count, 1)
                wait.assert_not_called()

    def test_only_completed_speech_is_cached_and_reused(self):
        attempts = []

        async def save(path):
            attempts.append(path)
            if len(attempts) == 1:
                raise NoAudioReceived("No audio was received.")
            self.save_audio(path)

        def ffmpeg(args):
            Path(args[-1]).write_bytes(b"completed wav")

        with patch("preferences.BackgroundStore", return_value=SimpleNamespace(directory=self.root)), \
             patch("engine.edge_tts.Communicate") as edge, \
             patch.object(self.renderer.cancel, "wait", return_value=False), \
             patch.object(self.renderer, "run", side_effect=ffmpeg) as run:
            edge.return_value.save = AsyncMock(side_effect=save)
            asyncio.run(self.renderer.speech("Hello!", self.root / "first.wav", self.root))
            asyncio.run(self.renderer.speech("Hello!", self.root / "second.wav", self.root))
        self.assertEqual(edge.call_count, 2)
        run.assert_called_once()
        self.assertEqual((self.root / "second.wav").read_bytes(), b"completed wav")
        self.assertEqual(len(list((self.root / "tts-cache").glob("*.wav"))), 1)


if __name__ == "__main__":
    unittest.main()
