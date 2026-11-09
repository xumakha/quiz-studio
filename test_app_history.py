"""History follows completed exports, using the document captured at startup."""
import json
import sqlite3
import tempfile
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from app import App
from content_types import sample_document
from engine import Cancelled, Renderer


class AppHistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.host = App(data_dir=self.root / "data")
        self.host.withdraw()
        self.release = threading.Event()
        self.errors_patch = patch("app.messagebox.showerror")
        self.errors = self.errors_patch.start()

    def tearDown(self):
        self.release.set()
        self.host.close()
        deadline = time.monotonic() + 10
        try:
            while self.host.winfo_exists() and time.monotonic() < deadline:
                self.host.update()
                time.sleep(0.01)
        except tk.TclError:
            pass
        self.errors_patch.stop()
        self.directory.cleanup()

    def pump_until(self, predicate):
        deadline = time.monotonic() + 10
        while not predicate() and time.monotonic() < deadline:
            self.host.update()
            time.sleep(0.01)
        self.assertTrue(predicate(), "Export did not finish")

    def load_document(self, tab, mode="guess_word", caption="Caption gốc\n#hoctienganh 🎬"):
        document = sample_document(mode)
        document["caption"] = caption
        tab.speech.set(False)
        tab.content_editor.write(json.dumps(document, ensure_ascii=False))
        self.assertTrue(tab.rows)
        return document

    def export_to(self, tab, path):
        with patch("app.filedialog.asksaveasfilename", return_value=str(path)):
            tab.export()

    def test_success_captures_document_and_survives_restart(self):
        tab = self.host.active_tab
        document = self.load_document(tab)
        channel = tab.tab_name
        path = self.root / "original.mp4"
        started = threading.Event()

        def render(renderer, title, rows, output):
            started.set()
            self.release.wait(8)
            Path(output).write_bytes(b"export complete")
            renderer.duration = 12.5

        with patch.object(Renderer, "render", render):
            self.export_to(tab, path)
            self.pump_until(started.is_set)
            self.assertEqual(self.host.history_store.load(), [])
            self.load_document(tab, "listening", "Caption đã thay đổi")
            self.host.rename_tab(tab, "Kênh mới")
            self.release.set()
            self.pump_until(lambda: not tab.busy)
        records = self.host.history_store.load()
        self.assertEqual(len(records), 1)
        saved = records[0]
        self.assertEqual(saved["title"], document["title"])
        self.assertEqual(saved["video_type"], "guess_word")
        self.assertEqual(saved["caption"], document["caption"])
        self.assertEqual(saved["tab_name"], channel)
        self.assertEqual(saved["output_path"], str(path.resolve()))
        self.assertEqual(saved["duration"], 12.5)
        self.host.close()
        self.host = App(data_dir=self.root / "data")
        self.host.withdraw()
        self.assertEqual(self.host.history_store.load(), records)
        self.errors.assert_not_called()

    def test_cancel_failure_and_save_dialog_cancel_leave_no_history(self):
        tab = self.host.active_tab
        self.load_document(tab)
        with patch.object(Renderer, "render") as render:
            self.export_to(tab, "")
            render.assert_not_called()
        for error in (Cancelled("Đã hủy"), RuntimeError("Render failed")):
            with self.subTest(error=type(error).__name__):
                with patch.object(Renderer, "render", side_effect=error):
                    self.export_to(tab, self.root / "failed.mp4")
                    self.pump_until(lambda: not tab.busy)
                self.assertEqual(self.host.history_store.load(), [])
                self.assertIsNone(tab.last_output)
        self.errors.assert_called_once()

    def test_parallel_tabs_keep_both_records_and_window_is_shared(self):
        first, second = self.host.tabs[:2]
        self.load_document(first, "guess_word", "Caption một")
        self.load_document(second, "mixed", "Caption hai")
        window = self.host.open_video_history()
        window.withdraw()
        self.host.select_tab(second)
        self.assertIs(self.host.open_video_history(), window)
        window.withdraw()
        with patch.object(window, "refresh", wraps=window.refresh) as refresh:
            def render(renderer, title, rows, output):
                self.release.wait(8)
                Path(output).write_bytes(b"complete")
                renderer.duration = 10
            with patch.object(Renderer, "render", render):
                self.export_to(first, self.root / "first.mp4")
                self.export_to(second, self.root / "second.mp4")
                self.release.set()
                self.pump_until(lambda: not first.busy and not second.busy)
            self.assertEqual(refresh.call_count, 2)
        records = self.host.history_store.load()
        self.assertEqual({record["caption"] for record in records}, {"Caption một", "Caption hai"})
        self.assertEqual({record["video_type"] for record in records}, {"guess_word", "mixed"})
        self.errors.assert_not_called()

    def test_history_write_failure_does_not_turn_success_into_render_error(self):
        tab = self.host.active_tab
        self.load_document(tab)
        path = self.root / "completed.mp4"
        window = self.host.open_video_history()
        window.withdraw()

        def render(renderer, title, rows, output):
            Path(output).write_bytes(b"complete")
            renderer.duration = 10

        with patch.object(Renderer, "render", render), \
             patch.object(self.host.history_store, "add", side_effect=sqlite3.OperationalError("disk full")), \
             patch.object(self.host.history_store, "load", side_effect=sqlite3.DatabaseError("corrupt database")), \
             patch("app.messagebox.showwarning") as warning:
            self.export_to(tab, path)
            self.pump_until(lambda: not tab.busy)
            warning.assert_called_once()
        self.assertTrue(path.is_file())
        self.assertEqual(tab.last_output, path)
        self.assertEqual(tab.progress_label.cget("text"), "100%")
        self.assertIn("không lưu được lịch sử", tab.status.cget("text"))
        self.assertFalse(self.host.output_owners)
        self.assertIsNotNone(tab.poll_timer)
        self.assertIn("Không đọc được lịch sử", window.status.cget("text"))
        self.errors.assert_not_called()

    def test_json_save_preserves_caption_and_legacy_editing(self):
        tab = self.host.active_tab
        caption = "  Caption đăng bài\n\n#English 🎬  "
        document = self.load_document(tab, caption=caption)
        path = self.root / "caption.json"
        legacy = {"title": "Bài cũ", "caption": caption, "questions": [
            {"question": "Chọn đáp án", "options": ["Một", "Hai"], "answer": "A"}
        ]}
        for source in (document, legacy):
            with self.subTest(schema="v2" if "items" in source else "legacy"):
                tab.content_editor.write(json.dumps(source, ensure_ascii=False))
                tab.content_editor.duplicate()
                self.assertEqual(json.loads(tab.content_editor.source())["caption"], caption)
                with patch("app.filedialog.asksaveasfilename", return_value=str(path)):
                    tab.save_json()
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["caption"], caption)
        self.errors.assert_not_called()


if __name__ == "__main__":
    unittest.main()
