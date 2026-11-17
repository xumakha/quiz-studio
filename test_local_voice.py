import asyncio
from pathlib import Path
from types import SimpleNamespace
import tempfile
import sys
import threading
import unittest
from unittest.mock import patch

from engine import Cancelled, Renderer, Settings, SpeechError
import local_voice


class LocalVoiceTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'Windows DLL inheritance')
    def test_frozen_worker_clears_dll_directory_and_restores_it_on_spawn_failure(self):
        import ctypes
        kernel = ctypes.windll.kernel32
        def dll_directory():
            value = ctypes.create_unicode_buffer(32768)
            kernel.GetDllDirectoryW(len(value), value)
            return value.value or None
        original = dll_directory()
        with tempfile.TemporaryDirectory() as directory:
            try:
                kernel.SetDllDirectoryW(directory)
                def spawn(command, **kwargs):
                    self.assertIsNone(dll_directory())
                    self.assertIn('-I', command)
                    raise OSError('spawn failed')
                with patch.object(sys, 'frozen', True, create=True), \
                        patch.object(sys, '_MEIPASS', directory, create=True), \
                        patch('local_voice.subprocess.Popen', side_effect=spawn):
                    with self.assertRaises(OSError):
                        local_voice._start_worker(Path(directory) / 'test.wav')
                self.assertEqual(dll_directory(), directory)
            finally:
                kernel.SetDllDirectoryW(original)

    def test_worker_environment_excludes_parent_python_settings(self):
        with patch.dict(local_voice.os.environ, {'PYTHONHOME': 'wrong', 'PYTHONPATH': 'wrong'}):
            env = local_voice.environment()
        self.assertNotIn('PYTHONHOME', env)
        self.assertNotIn('PYTHONPATH', env)

    def test_missing_runtime_does_not_call_online_services(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch('local_voice.installed', return_value=False), \
                patch('engine.edge_tts.Communicate') as edge, patch('engine.gTTS') as google:
            target = Path(directory) / 'part.wav'
            renderer = Renderer(Settings(voice='local:adam'))
            with self.assertRaisesRegex(SpeechError, 'Cai-Giong-local.bat'):
                asyncio.run(renderer._synthesize_speech('Xin chào', 'local:adam', target))
            self.assertFalse(target.exists())
            edge.assert_not_called()
            google.assert_not_called()

    def test_local_audio_uses_wav_and_applies_speed_and_pitch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            renderer = Renderer(Settings(voice='local:adam', rate=25, pitch=-10))
            def synthesize(text, target, **kwargs):
                self.assertEqual(target.suffix, '.wav')
                target.write_bytes(b'audio')
            commands = []
            def run(args):
                commands.append(args)
                if '-af' in args:
                    self.assertNotEqual(Path(args[args.index('-i') + 1]), Path(args[-1]))
                Path(args[-1]).write_bytes(b'processed')
            with patch('preferences.BackgroundStore', return_value=SimpleNamespace(directory=root)), \
                    patch('local_voice.synthesize', side_effect=synthesize), patch.object(renderer, 'run', side_effect=run):
                asyncio.run(renderer.speech('Xin chào', root / 'output.wav', root))
            self.assertTrue(any('asetrate=' in str(a) and 'atempo=' in str(a) for c in commands for a in c))
            self.assertEqual((root / 'output.wav').read_bytes(), b'processed')

    def test_cancellation_kills_local_worker(self):
        cancel = threading.Event()
        def check():
            if cancel.is_set():
                raise Cancelled('cancelled')
        with patch('local_voice.installed', return_value=True), patch('local_voice.subprocess.Popen') as spawn:
            process = spawn.return_value
            process.poll.return_value = None
            def communicate(**kwargs):
                if not cancel.is_set():
                    cancel.set()
                    raise local_voice.subprocess.TimeoutExpired('worker', 0.2)
                return b'', b''
            process.communicate.side_effect = communicate
            with self.assertRaises(Cancelled):
                local_voice.synthesize('Xin chào', Path('unused.wav'), check=check)
            process.kill.assert_called_once()


if __name__ == '__main__':
    unittest.main()
