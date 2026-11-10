from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import load_workbook

from video_history_excel import export_history_excel


class HistoryExcelTests(unittest.TestCase):
    def test_round_trip_preserves_caption_and_formula_like_text(self):
        caption = "  =Đoán từ 🎬\n\n#English  \n" + "😀" * 33000
        record = dict(id="test", created_at="2026-11-10T10:30:00+07:00",
                      title="=1+1", video_type="guess_word", caption=caption,
                      tab_name="Một chút English", output_path="C:/video.mp4", duration=12.5)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.xlsx"
            self.assertEqual(export_history_excel([record], path), 1)
            workbook = load_workbook(path)
            self.addCleanup(workbook.close)
            sheet = workbook.active
            self.assertEqual(sheet["E2"].value, "=1+1")
            self.assertEqual(sheet["E2"].data_type, "s")
            self.assertEqual("".join(sheet.cell(2, column).value for column in (6, 7, 8)), caption)
            self.assertEqual(sheet["C2"].value, record["tab_name"])
            self.assertEqual(sheet["J2"].value, 12.5)
            self.assertEqual(sheet.max_row, 2)
            self.assertEqual(sheet.freeze_panes, "F2")
            self.assertEqual(sheet.auto_filter.ref, "A1:K2")

    def test_empty_history_and_failed_save_keep_existing_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.xlsx"
            self.assertEqual(export_history_excel([], path), 0)
            before = path.read_bytes()
            with patch("video_history_excel.os.replace", side_effect=PermissionError("Excel is open")):
                with self.assertRaises(PermissionError):
                    export_history_excel([], path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
