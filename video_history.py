"""Persistent export history shared by all tabs and application instances."""
from collections.abc import Mapping
from contextlib import closing, contextmanager
from datetime import datetime
import math
from pathlib import Path
import sqlite3
import uuid


_FIELDS = ("id", "created_at", "title", "video_type", "caption", "tab_name", "output_path", "duration")
_SCHEMA = """
    CREATE TABLE IF NOT EXISTS video_history (
        sequence INTEGER PRIMARY KEY,
        id TEXT UNIQUE NOT NULL,
        created_at TEXT NOT NULL,
        title TEXT NOT NULL,
        video_type TEXT NOT NULL,
        caption TEXT NOT NULL,
        tab_name TEXT NOT NULL,
        output_path TEXT NOT NULL,
        duration REAL NOT NULL CHECK (duration >= 0)
    )
"""


class VideoHistoryStore:
    """Use a short, independent SQLite transaction for each successful export.

    ``add`` requires title, video_type and output_path; caption and tab_name
    default to empty strings and duration defaults to zero seconds. IDs and
    timezone-aware timestamps are generated for every addition. Filesystem and
    SQLite errors propagate so the app can report a failed history write while
    keeping the exported video. Constructing a store does not touch the disk.
    """

    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / "history.sqlite3"

    @contextmanager
    def _connection(self, *, timeout=30):
        self.directory.mkdir(parents=True, exist_ok=True)
        # Connections never cross threads. SQLite serializes writers, including
        # writers in another app instance, without a read/modify/write race.
        with closing(sqlite3.connect(self.path, timeout=timeout)) as connection:
            connection.row_factory = sqlite3.Row
            with connection:
                connection.execute(_SCHEMA)
                yield connection

    @staticmethod
    def _validated(record):
        if not isinstance(record, Mapping):
            raise ValueError("Lịch sử video phải là object.")
        result = {}
        for key in ("title", "video_type", "output_path"):
            value = record.get(key)
            if key == "output_path" and isinstance(value, Path):
                value = str(value)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Thông tin lịch sử video thiếu hoặc không hợp lệ: {key}.")
            result[key] = value
        for key in ("caption", "tab_name"):
            value = record.get(key, "")
            if not isinstance(value, str):
                raise ValueError(f"Thông tin lịch sử video phải là chuỗi: {key}.")
            result[key] = value
        duration = record.get("duration", 0)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise ValueError("Thời lượng video phải là số không âm.")
        try:
            duration = float(duration)
        except OverflowError as error:
            raise ValueError("Thời lượng video không hợp lệ.") from error
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("Thời lượng video phải là số hữu hạn không âm.")
        result["duration"] = duration
        return result

    def add(self, record):
        """Append a completed export atomically and return its saved record."""
        saved = self._validated(record)
        with self._connection() as connection:
            saved.update(id=str(uuid.uuid4()), created_at=datetime.now().astimezone().isoformat())
            connection.execute(
                "INSERT INTO video_history (" + ", ".join(_FIELDS) + ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(saved[key] for key in _FIELDS),
            )
        return saved

    def load(self):
        """Return every completed export, newest first, without a history cap."""
        if not self.path.exists():
            return []
        # Refresh runs on the UI thread: a locked history should report an
        # error promptly while leaving the last displayed records available.
        with self._connection(timeout=0.25) as connection:
            rows = connection.execute(
                "SELECT " + ", ".join(_FIELDS) + " FROM video_history ORDER BY sequence DESC"
            ).fetchall()
        return [dict(row) for row in rows]
