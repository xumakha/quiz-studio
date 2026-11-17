import json
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from app import App
from content_types import sample_document
from test_openai_video import api_response


class AppOpenAITests(unittest.TestCase):
    def test_connect_generate_autofill_undo_error_cancel_and_restore_conversation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            host = App(data_dir=directory)
            host.withdraw()
            tab = host.active_tab
            errors = patch("app.messagebox.showerror")
            errors.start()
            try:
                def pump(condition, timeout=15):
                    deadline = time.monotonic() + timeout
                    while not condition() and time.monotonic() < deadline:
                        host.update()
                        time.sleep(0.01)
                    self.assertTrue(condition(), "Timed out waiting for OpenAI task")

                window = tab.open_chatgpt()
                self.assertEqual(window.title(), "Kết nối OpenAI API")
                window.key_variable.set("test-key")
                window.conversation_name.set("English video")
                window.instructions.insert("1.0", "Giải thích bằng tiếng Việt.")
                # A first connection must work without finding the manual create button.
                self.assertEqual(host.openai_store.list(), [])
                with patch("chatgpt_ui.check_connection", side_effect=ValueError("API key không hợp lệ")):
                    window.connect_button.invoke()
                    pump(lambda: window.connect_button.cget("state") == "normal")
                self.assertIn("API key không hợp lệ", window.message_variable.get())
                self.assertEqual(host.openai_store.list(), [])
                with patch("chatgpt_ui.check_connection") as check:
                    window.connect_button.invoke()
                    pump(lambda: not window.winfo_exists())
                    check.assert_called_once_with("test-key", "gpt-4.1-mini")
                conversation_id = tab.openai_conversation_id.get()
                self.assertTrue(conversation_id)
                self.assertEqual(len(host.openai_store.list()), 1)
                self.assertEqual(host.openai_store.get(conversation_id)["name"], "English video")
                self.assertEqual(host.openai_store.get(conversation_id)["instructions"], "Giải thích bằng tiếng Việt.")
                self.assertEqual(host.openai_key, "test-key")
                window = tab.open_chatgpt()
                with patch("chatgpt_ui.check_connection"):
                    window.connect_button.invoke()
                    pump(lambda: not window.winfo_exists())
                self.assertEqual(tab.openai_conversation_id.get(), conversation_id)
                self.assertEqual(len(host.openai_store.list()), 1)
                other = host.tabs[1]
                self.assertFalse(other.openai_conversation_id.get())
                original = tab.content_editor.source()
                document = sample_document("multiple_choice")
                document["title"] = "AI generated title"
                document["caption"] = "Generated caption\n#quiz"
                tab.openai_prompt.set("Tạo 5 câu tiếng Anh")
                release = threading.Event()

                def response(*args, **kwargs):
                    release.wait(5)
                    return api_response(document)

                with patch("openai_video.requests.post", side_effect=response):
                    self.assertTrue(tab.generate_openai_json())
                    self.assertFalse(tab.generate_openai_json())
                    host.select_tab(other)
                    self.assertFalse(tab.cancel.is_set())
                    other.openai_conversation_id.set(conversation_id)
                    other.openai_prompt.set("Khác")
                    with patch("app.messagebox.showinfo") as info:
                        self.assertFalse(other.generate_openai_json())
                        info.assert_called_once()
                    release.set()
                    pump(lambda: not tab.busy)
                host.select_tab(tab)
                self.assertEqual(json.loads(tab.content_editor.source()), document)
                self.assertTrue(tab.rows and tab.preview_image and tab.dirty)
                tab.text.edit_undo()
                self.assertEqual(tab.content_editor.source(), original)
                tab.validate()
                with patch("openai_video.requests.post", return_value=api_response(status=401)):
                    self.assertTrue(tab.generate_openai_json())
                    pump(lambda: not tab.busy)
                self.assertEqual(tab.content_editor.source(), original)
                self.assertFalse(host.openai_inflight)
                # A result arriving after a new manual edit must remain in history.
                release.clear()
                with patch("openai_video.requests.post", side_effect=response):
                    self.assertTrue(tab.generate_openai_json())
                    tab.text.insert("end", " ")
                    edited = tab.content_editor.source()
                    release.set()
                    pump(lambda: not tab.busy)
                self.assertEqual(tab.content_editor.source(), edited)
                self.assertIn("Nạp JSON gần nhất", tab.status.cget("text"))
                release.clear()
                before = len(host.openai_store.turns(conversation_id))
                with patch("openai_video.requests.post", side_effect=response):
                    self.assertTrue(tab.generate_openai_json())
                    tab.cancel_job()
                    release.set()
                    pump(lambda: not tab.busy)
                self.assertEqual(tab.content_editor.source(), edited)
                self.assertEqual(len(host.openai_store.turns(conversation_id)), before)
                self.assertFalse(host.openai_inflight)
                tab.mark_clean()
                other.mark_clean()
            finally:
                host.close()
                errors.stop()
            host = App(data_dir=directory)
            host.withdraw()
            try:
                self.assertEqual(host.active_tab.openai_conversation_id.get(), conversation_id)
                self.assertEqual(host.active_tab.openai_prompt.get(), "Tạo 5 câu tiếng Anh")
                self.assertFalse(host.openai_key)
                self.assertEqual(len(host.openai_store.turns(conversation_id)), before)
            finally:
                host.close()


if __name__ == "__main__":
    unittest.main()
