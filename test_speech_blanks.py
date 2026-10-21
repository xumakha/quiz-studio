import asyncio
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from engine import Renderer, Settings


class SpeechBlankTests(unittest.TestCase):
    def test_both_providers_receive_no_underscores(self):
        for voice in ('google:vi', 'vi-VN-HoaiMyNeural'):
            with self.subTest(voice=voice), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                renderer = Renderer(Settings(voice=voice, english_voice=voice))
                def run(args):
                    Path(args[-1]).write_bytes(b'audio')
                with patch('preferences.BackgroundStore', return_value=SimpleNamespace(directory=root)), \
                     patch('engine.gTTS') as google, \
                     patch('engine.edge_tts.Communicate') as edge, \
                     patch.object(renderer, 'run', side_effect=run):
                    edge.return_value.save = AsyncMock()
                    asyncio.run(renderer.speech('Điền ___: [en]She _ _ is a student.[/en]', root/'out.wav', root))
                    provider = google if voice.startswith('google:') else edge
                    self.assertEqual([c.args[0] for c in provider.call_args_list], ['Điền : ', 'She is a student.'])

    def test_only_blanks_produce_silence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('engine.gTTS') as google, patch('engine.edge_tts.Communicate') as edge:
                asyncio.run(Renderer(Settings()).speech('[en]_ _ ___[/en]', root/'out.wav', root))
                google.assert_not_called()
                edge.assert_not_called()
            with wave.open(str(root/'out.wav')) as audio:
                self.assertEqual(set(audio.readframes(audio.getnframes())), {0})
