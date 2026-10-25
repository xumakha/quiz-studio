import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import platform_support as desktop


class DesktopTests(unittest.TestCase):
    @patch.object(desktop.sys, "platform", "win32")
    @patch.object(desktop.subprocess, "Popen")
    def test_windows_audio_keeps_sync_and_async_modes(self, popen):
        sound = Mock(SND_FILENAME=1, SND_ASYNC=2, SND_PURGE=4)
        with patch.dict("sys.modules", {"winsound": sound}):
            player = desktop.AudioPlayer()
            player.play("voice.wav")
            sound.PlaySound.assert_called_with("voice.wav", 3)
            player.play("voice.wav", wait=True)
            sound.PlaySound.assert_called_with("voice.wav", 1)
            player.stop()
            sound.PlaySound.assert_called_with(None, 4)
            popen.assert_not_called()

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
