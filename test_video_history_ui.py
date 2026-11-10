"""Verify history browsing and caption copying with real Tk widgets."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from openpyxl import load_workbook
from video_history_ui import VideoHistoryWindow, history_day


class VideoHistoryWindowTests(unittest.TestCase):
    def setUp(self):
        self.host = tk.Tk()
        self.host.withdraw()
        self.records = [
            dict(id="recent", created_at="2026-11-09T15:30:00+07:00", title="Từ mới hôm nay",
                 video_type="guess_word", caption="  Đoán từ nhé!\n#English 🎬\n", tab_name="Một chút English",
                 output_path="missing-history-video.mp4", duration=12.3),
            dict(id="older", created_at="2026-11-08T10:00:00+07:00", title="Kiểm tra kiến thức",
                 video_type="multiple_choice", caption="", tab_name="Easy Prep",
                 output_path="another-video.mp4", duration=6),
        ]
        self.host.history_store = SimpleNamespace(load=Mock(return_value=deepcopy(self.records)))
        self.window = VideoHistoryWindow(self.host)
        self.window.withdraw()
        self.host.update_idletasks()

    def tearDown(self):
        if self.window.winfo_exists():
            self.window.destroy()
        # This test root, like App.destroy(), owns shared CTk appearance timers.
        for timer in self.host.tk.call("after", "info"):
            self.host.after_cancel(timer)
        self.host.destroy()

    def test_details_and_clipboard_keep_complete_caption(self):
        self.assertEqual(self.visible_video_ids(), ("recent", "older"))
        self.assertEqual(self.window.title_text.get("1.0", "end-1c"), self.records[0]["title"])
        self.assertEqual(self.window.caption_text.get("1.0", "end-1c"), self.records[0]["caption"])
        self.window.copy_button.invoke()
        self.assertEqual(self.window.clipboard_get(), self.records[0]["caption"])
        self.assertEqual(self.window.caption_text.cget("state"), "disabled")

    def test_search_matches_captions_channels_and_localized_types(self):
        for query, expected in (("#english", "recent"), ("EASY PREP", "older"), ("Đoán từ", "recent")):
            with self.subTest(query=query):
                self.window.search.set(query)
                self.assertEqual(self.visible_video_ids(), (expected,))
                self.assertEqual(self.window.table.selection(), (expected,))
        self.window.search.set("không có kết quả")
        self.assertFalse(self.window.table.get_children())
        self.assertEqual(self.window.caption_text.get("1.0", "end-1c"), "")
        self.assertEqual(self.window.copy_button.cget("state"), "disabled")

    def test_refresh_preserves_selection_and_retains_display_on_read_failure(self):
        self.window.table.selection_set("older")
        self.window._show_selection()
        self.host.history_store.load.return_value = [dict(self.records[0], id="newest"), *self.records]
        self.assertTrue(self.window.refresh())
        self.assertEqual(self.window.table.selection(), ("older",))
        self.assertEqual(self.window.title_text.get("1.0", "end-1c"), self.records[1]["title"])
        for error in (PermissionError("read denied"), sqlite3.DatabaseError("corrupt database")):
            with self.subTest(error=error):
                self.host.history_store.load.side_effect = error
                self.assertFalse(self.window.refresh())
                self.assertEqual(self.visible_video_ids(), ("newest", "recent", "older"))
                self.assertEqual(self.window.table.selection(), ("older",))
                self.assertIn("Không đọc được lịch sử", self.window.status.cget("text"))

    def test_empty_history_disables_actions(self):
        self.host.history_store.load.return_value = []
        self.window.refresh()
        self.assertFalse(self.window.table.get_children())
        self.assertIn("Chưa có lịch sử", self.window.empty_message.cget("text"))
        self.assertEqual(self.window.copy_button.cget("state"), "disabled")
        self.assertEqual(self.window.folder_button.cget("state"), "disabled")

    def visible_video_ids(self):
        return tuple(video for group in self.window.table.get_children()
                     for video in self.window.table.get_children(group))

    def test_groups_videos_by_local_day_newest_first(self):
        same_day = dict(self.records[0], id="same-day", created_at="2026-11-09T15:31:00+07:00")
        self.host.history_store.load.return_value = [self.records[1], same_day, self.records[0]]
        self.window.refresh()
        groups = self.window.table.get_children()
        self.assertEqual(len(groups), 2)
        day = history_day(same_day["created_at"])
        self.assertEqual(self.window.table.item(groups[0], "text"),
                         f"{day:%d/%m/%Y} · 2 video")
        self.assertEqual(self.window.table.get_children(groups[0]), ("same-day", "recent"))
        self.assertEqual(self.window.table.get_children(groups[1]), ("older",))
        self.assertTrue(self.window.table.item(groups[0], "open"))
        self.window.search.set("#english")
        self.assertEqual(len(self.window.table.get_children()), 1)
        self.assertEqual(self.visible_video_ids(), ("same-day", "recent"))

    def test_selecting_day_clears_video_actions(self):
        self.window.table.selection_set(self.window.table.get_children()[0])
        self.window._show_selection()
        self.assertEqual(self.window.title_text.get("1.0", "end-1c"), "")
        self.assertEqual(self.window.copy_button.cget("state"), "disabled")
        self.assertEqual(self.window.folder_button.cget("state"), "disabled")

    def test_excel_exports_all_history_even_when_search_is_active(self):
        self.window.search.set("#english")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.xlsx"
            with patch("video_history_ui.filedialog.asksaveasfilename", return_value=str(path)):
                self.window.export_excel()
            workbook = load_workbook(path)
            try:
                sheet = workbook.active
                self.assertEqual(sheet.max_row, 3)
                self.assertEqual(sheet["F2"].value, self.records[0]["caption"])
                self.assertEqual(sheet["E3"].value, self.records[1]["title"])
            finally:
                workbook.close()
            self.assertIn("Đã xuất 2 video", self.window.status.cget("text"))

    def test_excel_save_failure_is_reported(self):
        with patch("video_history_ui.filedialog.asksaveasfilename", return_value="history.xlsx"), \
                patch("video_history_ui.export_history_excel", side_effect=PermissionError("locked")), \
                patch("video_history_ui.messagebox.showerror") as error:
            self.window.export_excel()
        error.assert_called_once()

    def test_closing_window_cancels_its_callbacks_and_keeps_host_running(self):
        errors = []
        self.host.tk.createcommand("bgerror", errors.append)
        window_callback, textbox_callback, host_callback = Mock(), Mock(), Mock()
        self.window.after(0, window_callback)
        self.window.caption_text.after(0, textbox_callback)
        self.host.after(0, host_callback)
        self.window.destroy()
        finished = tk.BooleanVar(master=self.host)
        self.host.after(250, lambda: finished.set(True))
        self.host.wait_variable(finished)
        window_callback.assert_not_called()
        textbox_callback.assert_not_called()
        host_callback.assert_called_once()
        self.assertEqual(errors, [])

    def test_open_folder_selects_file_and_handles_missing_export(self):
        with tempfile.TemporaryDirectory() as directory:
            exported = Path(directory) / "video.mp4"
            exported.touch()
            self.window._records_by_id["recent"]["output_path"] = str(exported)
            with patch("video_history_ui.open_in_file_manager") as open_folder:
                self.window.open_output_folder()
                open_folder.assert_called_once_with(exported, select=True)
                exported.unlink()
                with patch("video_history_ui.messagebox.showwarning") as warning:
                    self.window.open_output_folder()
                warning.assert_called_once()
                self.assertEqual(open_folder.call_count, 1)


if __name__ == "__main__":
    unittest.main()
