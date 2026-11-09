from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
import uuid

from video_history import VideoHistoryStore


class VideoHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "data"
        self.store = VideoHistoryStore(self.directory)

    @staticmethod
    def record(title="Đoán từ tiếng Anh", **updates):
        return {"title": title, "video_type": "guess_word", "output_path": "outputs/video.mp4", **updates}

    def test_empty_history_does_not_create_files(self):
        self.assertFalse(self.directory.exists())
        self.assertEqual(self.store.load(), [])
        self.assertFalse(self.directory.exists())

    def test_reopen_keeps_unicode_caption_and_returns_newest_first(self):
        caption = "  Đố bạn đoán được từ này? 🎬\n\nHọc tiếng Anh mỗi ngày!\n#English #ĐoánTừ  \n"
        source = self.record(caption=caption, tab_name="Một chút English", duration=61.25,
                             output_path=self.directory / "Đoán từ.mp4")
        first = self.store.add(source)
        second = self.store.add(self.record(title="Video tiếp theo"))
        self.assertEqual(VideoHistoryStore(self.directory).load(), [second, first])
        self.assertEqual(first["caption"], caption)
        self.assertEqual(first["output_path"], str(source["output_path"]))
        self.assertEqual(first["tab_name"], "Một chút English")
        self.assertEqual(first["duration"], 61.25)
        self.assertIsNotNone(datetime.fromisoformat(first["created_at"]).utcoffset())
        self.assertEqual(str(uuid.UUID(first["id"])), first["id"])
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotIn("id", source)
        self.assertEqual(second["caption"], "")
        self.assertEqual(second["tab_name"], "")
        self.assertEqual(second["duration"], 0)

    def test_repeated_export_of_same_file_is_a_separate_entry(self):
        first = self.store.add(self.record())
        second = self.store.add({**first, "caption": "New caption"})
        self.assertNotEqual(second["id"], first["id"])
        self.assertEqual(self.store.load(), [second, first])

    def test_simultaneous_writers_share_one_history_without_lost_records(self):
        start = threading.Barrier(12)

        def write(worker):
            start.wait(timeout=10)
            saved = []
            for index in range(4):
                store = self.store if index % 2 == 0 else VideoHistoryStore(self.directory)
                saved.append(store.add(self.record(title=f"Video {worker}-{index}")))
                # Readers can query while independent connections keep writing.
                self.assertIn(saved[-1], VideoHistoryStore(self.directory).load())
            return saved

        with ThreadPoolExecutor(max_workers=12) as executor:
            batches = list(executor.map(write, range(12)))
        expected = {record["id"]: record for batch in batches for record in batch}
        actual = self.store.load()
        self.assertEqual(len(actual), 48)
        self.assertEqual({record["id"]: record for record in actual}, expected)

    def test_invalid_records_do_not_change_history(self):
        first = self.store.add(self.record())
        invalid = [None, [], {}, self.record(title=" "), self.record(video_type=1),
                   self.record(output_path=""), self.record(caption=None), self.record(tab_name=[])]
        invalid += [self.record(duration=value)
                    for value in (-1, float("nan"), float("inf"), True, "12", 10 ** 1000)]
        for record in invalid:
            with self.subTest(record=record), self.assertRaises(ValueError):
                self.store.add(record)
        self.assertEqual(self.store.load(), [first])

    def test_corrupt_database_reports_failure_without_overwriting_it(self):
        self.directory.mkdir()
        broken = b"not a SQLite database"
        self.store.path.write_bytes(broken)
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.load()
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.add(self.record())
        self.assertEqual(self.store.path.read_bytes(), broken)

    def test_locked_history_read_fails_promptly_and_recovers_after_unlock(self):
        saved = self.store.add(self.record())
        with closing(sqlite3.connect(self.store.path)) as writer:
            writer.execute("BEGIN EXCLUSIVE")
            started = time.monotonic()
            with self.assertRaises(sqlite3.OperationalError):
                self.store.load()
            elapsed = time.monotonic() - started
            writer.rollback()
        self.assertLess(elapsed, 2, "A history refresh must not block the UI for the writer timeout")
        self.assertEqual(self.store.load(), [saved])


if __name__ == "__main__":
    unittest.main()
