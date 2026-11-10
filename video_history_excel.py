"""Portable Excel backup of video history, including complete captions."""
from datetime import datetime
import os
from pathlib import Path
import tempfile

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from content_types import LABELS


def export_history_excel(records, path):
    """Write every supplied record atomically; store user content as literal text."""
    records = list(records)
    # Excel limits each cell to 32767 characters. Continue long captions in
    # additional columns rather than letting the writer silently truncate them.
    chunk_size = 16000
    caption_columns = max((max(1, (len(r["caption"]) + chunk_size - 1) // chunk_size)
                           for r in records), default=1)
    headers = ["Ngày xuất", "Giờ xuất", "Kênh", "Loại video", "Tên video", "Caption"]
    headers += [f"Caption (tiếp {index})" for index in range(2, caption_columns + 1)]
    headers += ["File video", "Thời lượng (giây)", "ID video"]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Lịch sử video"
    sheet.append(headers)
    for record in records:
        try:
            created = datetime.fromisoformat(record["created_at"]).astimezone()
            date, time = created.strftime("%d/%m/%Y"), created.strftime("%H:%M:%S")
        except (TypeError, ValueError, OverflowError):
            date, time = record["created_at"] or "", ""
        caption = record["caption"]
        values = [date, time, record["tab_name"],
                  LABELS.get(record["video_type"], record["video_type"]), record["title"]]
        values += [caption[index * chunk_size:(index + 1) * chunk_size]
                   for index in range(caption_columns)]
        values += [record["output_path"], record.get("duration"), record["id"]]
        sheet.append(values)
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, str):
                cell.data_type = "s"
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        sheet.row_dimensions[sheet.max_row].height = 90
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="247561")
    widths = [15, 12, 25, 28, 45] + [80] * caption_columns + [55, 20, 38]
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "F2"
    sheet.auto_filter.ref = sheet.dimensions
    path = Path(path)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".xlsx", delete=False) as temporary:
            temporary_path = Path(temporary.name)
        workbook.save(temporary_path)
        os.replace(temporary_path, path)
    finally:
        workbook.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return len(records)
