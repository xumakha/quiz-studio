import unittest
import threading
from pathlib import Path
from unittest.mock import Mock, patch

import platform_support as desktop


class DesktopTests(unittest.TestCase):
    @patch.object(desktop.sys, "platform", "win32")
    @patch.object(desktop.subprocess, "Popen")
    def test_windows_audio_keeps_wait_and_async_modes(self, popen):
        sound = Mock(SND_FILENAME=1, SND_ASYNC=2, SND_PURGE=4)
        source = Mock()
        source.getnframes.return_value = 0
        source.getframerate.return_value = 44100
        with patch.dict("sys.modules", {"winsound": sound}), patch.object(desktop.wave, "open") as wav:
            wav.return_value.__enter__.return_value = source
            player = desktop.AudioPlayer()
            player.play("voice.wav")
            sound.PlaySound.assert_called_with("voice.wav", 3)
            player.play("voice.wav", wait=True)
            sound.PlaySound.assert_called_with(None, 4)
            self.assertIsNone(desktop.AudioPlayer._windows_playback)
            sound.PlaySound.reset_mock()
            player.stop()
            sound.PlaySound.assert_not_called()
            popen.assert_not_called()

    @patch.object(desktop.sys, "platform", "win32")
    def test_windows_inactive_and_replaced_players_do_not_stop_active_audio(self):
        sound = Mock(SND_FILENAME=1, SND_ASYNC=2, SND_PURGE=4)
        with patch.dict("sys.modules", {"winsound": sound}):
            first, second = desktop.AudioPlayer(), desktop.AudioPlayer()
            try:
                first.play("first.wav")
                sound.PlaySound.reset_mock()
                second.stop()
                sound.PlaySound.assert_not_called()
                second.play("second.wav")
                sound.PlaySound.reset_mock()
                first.stop()
                sound.PlaySound.assert_not_called()
                second.stop()
                sound.PlaySound.assert_called_once_with(None, 4)
            finally:
                first.stop()
                second.stop()

    @patch.object(desktop.sys, "platform", "win32")
    def test_windows_wait_can_be_interrupted_without_clearing_replacement(self):
        sound = Mock(SND_FILENAME=1, SND_ASYNC=2, SND_PURGE=4)
        source = Mock()
        source.getnframes.return_value = 44100 * 60
        source.getframerate.return_value = 44100
        with patch.dict("sys.modules", {"winsound": sound}), patch.object(desktop.wave, "open") as wav:
            wav.return_value.__enter__.return_value = source
            for same_player in (False, True):
                with self.subTest(same_player=same_player):
                    started = threading.Event()
                    sound.PlaySound.side_effect = lambda path, flags: started.set() if path == "first.wav" else None
                    first = desktop.AudioPlayer()
                    replacement = first if same_player else desktop.AudioPlayer()
                    worker = threading.Thread(target=lambda: first.play("first.wav", wait=True))
                    worker.start()
                    try:
                        self.assertTrue(started.wait(2))
                        replacement.play("second.wav")
                        worker.join(timeout=2)
                        self.assertFalse(worker.is_alive(), "wait must finish when another playback replaces it")
                        self.assertIs(desktop.AudioPlayer._windows_playback[0], replacement)
                        sound.PlaySound.reset_mock()
                        if not same_player:
                            first.stop()
                            sound.PlaySound.assert_not_called()
                        replacement.stop()
                        sound.PlaySound.assert_called_once_with(None, 4)
                    finally:
                        first.stop()
                        replacement.stop()
                        worker.join(timeout=2)

    @patch.object(desktop.sys, "platform", "win32")
    def test_windows_owner_stop_interrupts_wait(self):
        sound = Mock(SND_FILENAME=1, SND_ASYNC=2, SND_PURGE=4)
        source = Mock()
        source.getnframes.return_value = 44100 * 60
        source.getframerate.return_value = 44100
        started = threading.Event()
        sound.PlaySound.side_effect = lambda path, flags: started.set() if path else None
        with patch.dict("sys.modules", {"winsound": sound}), patch.object(desktop.wave, "open") as wav:
            wav.return_value.__enter__.return_value = source
            player = desktop.AudioPlayer()
            worker = threading.Thread(target=lambda: player.play("voice.wav", wait=True))
            worker.start()
            try:
                self.assertTrue(started.wait(2))
                sound.PlaySound.reset_mock()
                player.stop()
                worker.join(timeout=2)
                self.assertFalse(worker.is_alive())
                sound.PlaySound.assert_called_once_with(None, 4)
                self.assertIsNone(desktop.AudioPlayer._windows_playback)
            finally:
                player.stop()
                worker.join(timeout=2)

    @patch.object(desktop.sys, "platform", "win32")
    def test_windows_cancelled_sample_does_not_play_or_stop_active_owner(self):
        sound = Mock(SND_FILENAME=1, SND_ASYNC=2, SND_PURGE=4)
        cancelled = threading.Event()
        cancelled.set()
        with patch.dict("sys.modules", {"winsound": sound}), patch.object(desktop.wave, "open") as wav:
            active = desktop.AudioPlayer()
            try:
                active.play("active.wav")
                sound.PlaySound.reset_mock()
                for player in (active, desktop.AudioPlayer()):
                    player.play("cancelled.wav", wait=True, cancel=cancelled)
                sound.PlaySound.assert_not_called()
                wav.assert_not_called()
                self.assertIs(desktop.AudioPlayer._windows_playback[0], active)
            finally:
                active.stop()

    @patch.object(desktop.sys, "platform", "win32")
    def test_windows_cancellation_while_reading_sample_does_not_replace_active_owner(self):
        sound = Mock(SND_FILENAME=1, SND_ASYNC=2, SND_PURGE=4)
        cancelled = threading.Event()
        source = Mock()
        source.getnframes.return_value = 44100
        source.getframerate.return_value = 44100
        with patch.dict("sys.modules", {"winsound": sound}), patch.object(desktop.wave, "open") as wav:
            wav.return_value.__enter__.return_value = source
            wav.return_value.__exit__.side_effect = lambda *args: cancelled.set()
            active = desktop.AudioPlayer()
            try:
                active.play("active.wav")
                sound.PlaySound.reset_mock()
                desktop.AudioPlayer().play("cancelled.wav", wait=True, cancel=cancelled)
                sound.PlaySound.assert_not_called()
                self.assertIs(desktop.AudioPlayer._windows_playback[0], active)
            finally:
                active.stop()

    @patch.object(desktop.sys, "platform", "darwin")
    @patch.object(desktop.subprocess, "Popen")
    def test_macos_cancelled_sample_preserves_current_playback(self, popen):
        cancelled = threading.Event()
        player = desktop.AudioPlayer()
        player.play("active.wav")
        current = player.process
        cancelled.set()
        player.play("cancelled.wav", wait=True, cancel=cancelled)
        self.assertIs(player.process, current)
        self.assertEqual(popen.call_count, 1)
        current.terminate.assert_not_called()
        player.stop()

    @patch.object(desktop.sys, "platform", "darwin")
    @patch.object(desktop.subprocess, "Popen")
    def test_macos_audio_does_not_import_windows_module(self, popen):
        with patch.dict("sys.modules", {"winsound": None}):
            player = desktop.AudioPlayer()
            player.play("giọng đọc.wav")
            self.assertEqual(popen.call_args.args[0], ["/usr/bin/afplay", "giọng đọc.wav"])
            player.stop()

    @patch.object(desktop.sys, "platform", "win32")
    @patch.object(desktop.os, "startfile", create=True)
    @patch.object(desktop.subprocess, "Popen")
    def test_windows_opens_library_without_macos_command(self, popen, startfile):
        folder = Path("quiz backgrounds")
        desktop.open_in_file_manager(folder)
        startfile.assert_called_once_with(str(folder.resolve()))
        popen.assert_not_called()

    @patch.dict(desktop.os.environ, {"WINDIR": "C:/Windows"})
    def test_windows_preserves_original_font_preferences(self):
        fonts = Path("C:/Windows/Fonts")
        self.assertEqual(next(desktop.font_paths()), fonts / "arial.ttf")
        self.assertEqual(next(desktop.font_paths(bold=True)), fonts / "arialbd.ttf")
        self.assertEqual(next(desktop.font_paths(ipa=True)), fonts / "segoeui.ttf")

    @patch.object(desktop.sys, "platform", "darwin")
    @patch.object(desktop.subprocess, "Popen")
    def test_audio_failure_is_reported_and_process_released(self, popen):
        popen.return_value.wait.return_value = 1
        player = desktop.AudioPlayer()
        with self.assertRaisesRegex(RuntimeError, "afplay"):
            player.play("voice.wav", wait=True)
        self.assertIsNone(player.process)

    @patch.object(desktop.sys, "platform", "darwin")
    def test_macos_storage(self):
        self.assertEqual(desktop.data_directory(), Path.home() / "Library/Application Support/QuizStudio")

    @patch.object(desktop.sys, "platform", "darwin")
    @patch.object(desktop.subprocess, "Popen")
    def test_finder_selects_output_with_spaces(self, popen):
        output = Path("/tmp/quiz video.mp4")
        desktop.open_in_file_manager(output, select=True)
        popen.assert_called_once_with(["open", "-R", str(output.resolve())])

    @patch.object(desktop.sys, "platform", "darwin")
    @patch.object(desktop.subprocess, "Popen")
    def test_finder_opens_library(self, popen):
        folder = Path("/tmp/quiz backgrounds")
        desktop.open_in_file_manager(folder)
        popen.assert_called_once_with(["open", str(folder.resolve())])

    @patch.object(desktop.sys, "platform", "win32")
    @patch.dict(desktop.os.environ, {"LOCALAPPDATA": "C:/Users/test/AppData/Local"})
    def test_windows_storage_is_preserved(self):
        self.assertEqual(desktop.data_directory(), Path("C:/Users/test/AppData/Local/QuizStudio"))

    @patch.object(desktop.sys, "platform", "win32")
    @patch.object(desktop.subprocess, "Popen")
    def test_windows_select_is_preserved(self, popen):
        output = Path("/tmp/quiz video.mp4")
        desktop.open_in_file_manager(output, select=True)
        popen.assert_called_once_with(["explorer.exe", f"/select,{output.resolve()}"])

    def test_macos_fonts_include_regular_and_bold(self):
        self.assertIn(Path("/System/Library/Fonts/Supplemental/Arial.ttf"), list(desktop.font_paths()))
        self.assertIn(Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"), list(desktop.font_paths(True)))


if __name__ == "__main__":
    unittest.main()
