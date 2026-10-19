import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from app import App
from content_types import DEFAULT_MODE, LABELS, sample_document


class AppContentTests(unittest.TestCase):
    def test_drafts_forms_import_and_abcd_on_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            app = App(data_dir=directory)
            app.withdraw()
            try:
                app.speech.set(False)
                self.assertEqual(app.content_editor.mode, DEFAULT_MODE)
                original = app.content_editor.source()
                editor = app.content_editor
                editor.variable.set(LABELS["listening"]); editor.switch()
                self.assertEqual(editor.source(), "")
                editor.sample()
                listening = editor.source()
                editor.variable.set(LABELS[DEFAULT_MODE]); editor.switch()
                self.assertEqual(editor.source(), original)
                editor.variable.set(LABELS["listening"]); editor.switch()
                self.assertEqual(editor.source(), listening)
                editor.duplicate()
                self.assertEqual(len(app.rows), 2)
                self.assertNotEqual(app.rows[0]["id"], app.rows[1]["id"])
                editor.move(1)
                editor.delete()
                self.assertEqual(len(app.rows), 1)
                editor.form()
                forms = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
                self.assertEqual(len(forms), 1)
                forms[0].destroy()
                editor.write(json.dumps(sample_document("mixed"), ensure_ascii=False))
                self.assertEqual(editor.mode, "mixed")
                output = Path(directory) / "v2.json"
                with patch("app.filedialog.asksaveasfilename", return_value=str(output)):
                    app.save_json()
                self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["schema_version"], 2)
                editor.write('{"invalid":')
                self.assertEqual(editor.source(), '{"invalid":')
                editor.variable.set(LABELS["fill_blank"]); editor.switch()
                editor.add()
                added = json.loads(editor.source())["items"][0]
                self.assertEqual(added["question"], "")
                self.assertEqual(added["answer"], "")
                forms = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
                self.assertEqual(len(forms), 1)
                forms[0].destroy()
            finally:
                app.close()
            app = App(data_dir=directory)
            app.withdraw()
            try:
                self.assertEqual(app.content_editor.mode, DEFAULT_MODE)
                self.assertTrue(all(row["type"] == DEFAULT_MODE for row in app.rows))
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
