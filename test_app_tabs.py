"""Exercise workspace isolation and asynchronous lifecycle with real Tk widgets."""
import json
import tempfile
import threading
import time
import tkinter as tk
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import App
from content_types import sample_document
from engine import Cancelled, Renderer
from preferences import USER_DEFAULTS, UserSettingsStore


class WorkspaceTabTests(unittest.TestCase):
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

    def pump_until(self, condition, timeout=8):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            self.host.update()
            time.sleep(0.01)
        self.assertTrue(condition(), "Timed out waiting for tab worker or callback")

    def image(self, name, color):
        path = self.root / name
        Image.new("RGBA", (80, 120), color).save(path)
        return path

    def reopen(self):
        self.host.close()
        self.host = App(data_dir=self.root / "data")
        self.host.withdraw()

    def test_three_default_tabs_restore_all_settings_and_media_independently(self):
        self.assertEqual([tab.profile_id for tab in self.host.tabs],
                         ["mot-chut-english", "easy-prep", "asvab-prep"])
        self.assertEqual([tab.tab_name for tab in self.host.tabs],
                         ["Một chút English", "Easy Prep", "ASVAB-Prep"])
        self.assertIs(self.host.active_tab, self.host.tabs[0])
        snapshots = {}
        sources = []
        for index, tab in enumerate(self.host.tabs):
            # The second and third tabs are edited without selecting them.
            chosen = {
                "voice": "English • Male — Guy", "en_voice": "English • Google (HTTP)",
                "dialogue_voice_a": "English • Male — Guy",
                "dialogue_voice_b": "English • Female — Jenny",
                "rate": 11 + index, "pitch": -10 + index, "countdown": 4 + index,
                "resolution": "720 × 1280", "video_template": "Tiếng Anh · Xanh sáng",
                "brand": f"Brand {index}", "watermark_enabled": index == 1,
                "read_options": index != 1, "read_explanation": index == 2,
                "speech": False, "music_volume": 20 + index, "reveal": index == 1,
                "ending_text": f"Câu kết riêng {index}",
                "left_logo_enabled": index == 0, "right_chibi_enabled": index == 2,
            }
            self.assertEqual(set(chosen), set(USER_DEFAULTS))
            for name, value in chosen.items():
                getattr(tab, name).set(value)
            tab.background_dim.set(15 + index)
            picture = self.image(f"Profile {index}.png", ("red", "green", "blue")[index])
            music = self.root / f"Music {index}.wav"
            with wave.open(str(music), "wb") as stream:
                stream.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                stream.writeframes(bytes([index, 0]) * 8000)
            sources.extend((picture, music))
            with patch("app.filedialog.askopenfilename", return_value=str(picture)):
                tab.choose_media("background")
                for kind in tab.branding_store.KINDS:
                    tab.choose_branding(kind)
            with patch("app.filedialog.askopenfilename", return_value=str(music)):
                tab.choose_media("music")
            # Schedule one last debounced save after music's immediate save.
            tab.rate.set(31 + index)
            snapshots[tab.profile_id] = (tab.user_settings(), tab.settings())

        self.pump_until(lambda: all(tab.settings_save_timer is None and tab.dim_save_timer is None
                                    for tab in self.host.tabs))
        for tab in self.host.tabs:
            saved = UserSettingsStore(self.root / "data", config_dir=tab.user_store.config.parent).load()
            for name, value in snapshots[tab.profile_id][0].items():
                self.assertEqual(saved[name], value, (tab.profile_id, name))
        self.assertEqual(len({tab.user_store.config for tab in self.host.tabs}), 3)
        for source in sources:
            source.unlink()
        self.host.select_tab(self.host.tabs[-1])
        self.reopen()
        for tab in self.host.tabs:
            self.assertEqual(tab.user_settings(), snapshots[tab.profile_id][0])
            self.assertEqual(tab.settings(), snapshots[tab.profile_id][1])
            for name in ("background", "music", *tab.branding_store.KINDS):
                self.assertTrue(Path(getattr(tab, name)).is_file(), (tab.profile_id, name))

        # Clearing one profile must not overwrite either neighbor on exit.
        second = self.host.tabs[1]
        second.clear_media()
        second.reset_branding("ending_image")
        self.host.select_tab(second)
        self.reopen()
        self.assertEqual(self.host.tabs[1].background, "")
        self.assertEqual(self.host.tabs[1].music, "")
        self.assertEqual(self.host.tabs[1].ending_image, "")
        for tab in (self.host.tabs[0], self.host.tabs[2]):
            self.assertEqual(tab.settings(), snapshots[tab.profile_id][1])
        self.errors.assert_not_called()

    def test_renamed_default_and_extra_profiles_keep_identity_after_restart(self):
        first = self.host.active_tab
        first.countdown.set(8)
        first.ending_text.set("Câu kết gốc")
        extra = self.host.new_tab()
        self.assertEqual(extra.settings(), first.settings())
        self.assertNotEqual(extra.profile_id, first.profile_id)
        self.assertNotEqual(extra.user_store.config, first.user_store.config)
        extra.countdown.set(12)
        extra.ending_text.set("Câu kết tab thêm")
        for tab in (first, extra):
            self.assertTrue(self.host.rename_tab(tab, "Tên trùng nhau"))
        extra_id = extra.profile_id
        first_id = first.profile_id
        self.host.close_tab(first, confirm=False)
        self.assertNotIn(first, self.host.tabs)
        self.reopen()
        self.assertEqual(len(self.host.tabs), 4)
        self.assertEqual(self.host.tabs[0].profile_id, first_id)
        self.assertEqual(self.host.tabs[0].tab_name, "Tên trùng nhau")
        self.assertEqual(self.host.tabs[0].countdown.get(), 8)
        self.assertEqual(self.host.tabs[0].ending_text.get(), "Câu kết gốc")
        extra = next(tab for tab in self.host.tabs if tab.profile_id == extra_id)
        self.assertEqual(extra.tab_name, "Tên trùng nhau")
        self.assertEqual(extra.countdown.get(), 12)
        self.assertEqual(extra.ending_text.get(), "Câu kết tab thêm")
        self.host.close_tab(extra, confirm=False)
        self.reopen()
        self.assertEqual(len(self.host.tabs), 3)
        self.assertNotIn(extra_id, [tab.profile_id for tab in self.host.tabs])
        self.assertEqual(self.host.tabs[0].countdown.get(), 8)
        self.errors.assert_not_called()

    def test_rename_tab_updates_caption_and_window_without_touching_content(self):
        first = self.host.active_tab
        second = self.host.new_tab()
        source = first.content_editor.source()
        self.assertTrue(self.host.rename_tab(first, "  Từ vựng   bài 1  "))
        self.assertEqual(first.tab_name, "Từ vựng bài 1")
        self.assertIn("Từ vựng bài 1", self.host.tab_widgets[first][1].cget("text"))
        self.assertIn(second.tab_name, self.host.title())
        self.host.select_tab(first)
        self.assertEqual(self.host.title(), "Từ vựng bài 1 — Quiz Studio")
        self.assertEqual(first.content_editor.source(), source)
        with patch("app.simpledialog.askstring", return_value=None):
            self.assertFalse(self.host.rename_tab(first))
        with patch("app.messagebox.showwarning"):
            self.assertFalse(self.host.rename_tab(first, "  "))
            self.assertFalse(self.host.rename_tab(first, "a" * 81))
        self.assertEqual(first.tab_name, "Từ vựng bài 1")

    def test_ending_text_is_independent_and_preview_uses_custom_narration(self):
        first = self.host.active_tab
        first.ending_text.set("Câu kết video thứ nhất.")
        snapshot = first.settings()
        second = self.host.new_tab()
        second.ending_text.set("[en]Thanks for watching![/en]")
        self.assertEqual(first.settings().ending_text, snapshot.ending_text)
        self.assertNotEqual(first.settings().ending_text, second.settings().ending_text)
        second.speech.set(True)
        self.host.update()
        with patch.object(Renderer, "speech") as speech, \
             patch.object(Renderer, "audio_duration", return_value=6.25), \
             patch("content_timeline.preview_audio", return_value=None):
            second.play_preview(ending_only=True)
            self.pump_until(lambda: not second.busy)
            self.assertEqual(speech.call_count, 1)
            self.assertEqual(speech.call_args.args[0], second.ending_text.get())
        self.assertIsNotNone(second.preview_directory)
        self.assertAlmostEqual(float(second.preview_seek.cget("to")), 6.7666666667)
        second.ending_text.set("")
        self.assertIsNone(second.preview_directory)
        self.assertEqual(first.settings().ending_text, snapshot.ending_text)
        self.errors.assert_not_called()

    def test_saved_branding_pickers_refresh_across_tabs_and_preserve_selection(self):
        first, second = self.host.active_tab, self.host.new_tab()
        red, blue = self.image("Logo đỏ.png", "red"), self.image("Kết xanh.png", "blue")
        for kind, source in (("logo_image", red), ("ending_image", blue)):
            with patch("app.filedialog.askopenfilename", return_value=str(source)):
                first.choose_branding(kind)
        red.unlink()
        blue.unlink()
        snapshot = first.settings()
        self.host.select_tab(first)
        self.host.select_tab(second)
        entries = second.branding_library_entries
        self.assertEqual(len(entries), 2)
        for kind, name in (("logo_image", "Kết xanh.png"), ("ending_image", "Logo đỏ.png")):
            index = next(i for i, entry in enumerate(entries) if entry["name"] == name)
            second.branding_library_boxes[kind].current(index)
            second.choose_saved_branding(kind)
            self.assertEqual(getattr(second, kind + "_name"), name)
            self.assertTrue(Path(getattr(second, kind)).is_file())
        second.reset_branding("logo_image")
        self.assertEqual(len(second.branding_library_entries), 2)
        self.assertEqual(first.logo_image, snapshot.logo_image)
        self.assertEqual(first.ending_image, snapshot.ending_image)
        self.errors.assert_not_called()

    def test_drafts_settings_media_and_branding_are_independent(self):
        first = self.host.active_tab
        first.speech.set(False)
        first.content_editor.write(json.dumps(sample_document("listening")))
        first.brand.set("First video")
        first_source = first.content_editor.source()
        second = self.host.new_tab()
        second.content_editor.write(json.dumps(sample_document("phrase_lesson")))
        second.brand.set("Second video")
        second.countdown.set(9)
        red = self.image("red.png", "red")
        blue = self.image("blue.png", "blue")
        with patch("app.filedialog.askopenfilename", return_value=str(red)):
            first.choose_media("background")
            first.choose_branding("logo_image")
            first.choose_branding("ending_image")
        first_settings = first.settings()
        with patch("app.filedialog.askopenfilename", return_value=str(blue)):
            second.choose_media("background")
            second.choose_branding("logo_image")
            second.choose_branding("ending_image")
        self.assertNotEqual(first.background, second.background)
        self.assertNotEqual(first.logo_image, second.logo_image)
        self.assertNotEqual(first.ending_image, second.ending_image)
        second.clear_media()
        second.reset_branding("logo_image")
        self.host.select_tab(first)
        self.assertEqual(first.content_editor.source(), first_source)
        self.assertEqual(first.content_editor.mode, "listening")
        self.assertEqual(second.content_editor.mode, "phrase_lesson")
        self.assertEqual(first.brand.get(), "First video")
        self.assertEqual(second.brand.get(), "Second video")
        self.assertNotEqual(first.countdown.get(), second.countdown.get())
        self.assertEqual(first.settings().background, first_settings.background)
        self.assertEqual(first.settings().logo_image, first_settings.logo_image)
        self.assertEqual(first.settings().ending_image, first_settings.ending_image)
        self.assertEqual(second.background, "")
        self.assertEqual(second.logo_image, "")
        self.errors.assert_not_called()

    def test_corner_controls_keep_tab_settings_separate_and_reuse_uploads(self):
        first = self.host.active_tab
        source = self.image("Logo và chibi.png", "blue")
        for kind in ("left_logo_image", "right_chibi_image"):
            with patch("app.filedialog.askopenfilename", return_value=str(source)):
                first.choose_branding(kind)
        first.left_logo_enabled.set(False)
        first.right_chibi_enabled.set(True)
        snapshot = first.settings()
        second = self.host.new_tab()
        second.left_logo_enabled.set(True)
        second.right_chibi_enabled.set(False)
        second.reset_branding("left_logo_image")
        source.unlink()
        self.assertEqual(first.settings(), snapshot)
        self.assertFalse(first.settings().left_logo_enabled)
        self.assertTrue(first.settings().right_chibi_enabled)
        self.assertTrue(second.settings().left_logo_enabled)
        self.assertFalse(second.settings().right_chibi_enabled)
        self.assertEqual(second.left_logo_image, "")
        self.assertEqual(second.right_chibi_image, first.right_chibi_image)
        second.branding_library_boxes["left_logo_image"].current(0)
        second.choose_saved_branding("left_logo_image")
        self.assertEqual(second.left_logo_image, snapshot.left_logo_image)
        self.assertTrue(first.show_preview())
        self.assertTrue(second.show_preview())
        self.errors.assert_not_called()

    def test_jobs_run_together_with_independent_progress_and_cancellation(self):
        first, second = self.host.active_tab, self.host.new_tab()
        started = {first: threading.Event(), second: threading.Event()}

        def job(tab, percent):
            started[tab].set()
            tab.events.put(("progress", (percent, f"Progress {tab.number}")))
            while not self.release.wait(0.01):
                if tab.cancel.is_set():
                    raise Cancelled("Cancelled only this tab")
            return {"message": "Finished", "path": str(self.root / f"{tab.number}.mp4")}

        first.start_job(lambda: job(first, 20), exporting=True)
        second.start_job(lambda: job(second, 60), exporting=True)
        self.pump_until(lambda: all(event.is_set() for event in started.values())
                        and first.progress_label.cget("text") == "20%"
                        and second.progress_label.cget("text") == "60%")
        self.assertTrue(first.busy and second.busy)
        self.host.select_tab(first)
        self.assertFalse(first.cancel.is_set() or second.cancel.is_set())
        first.cancel_job()
        self.pump_until(lambda: not first.busy)
        self.assertEqual(first.job_state, "Đã hủy")
        self.assertTrue(second.busy)
        self.assertFalse(second.cancel.is_set())
        self.assertEqual(second.progress_label.cget("text"), "60%")
        self.release.set()
        self.pump_until(lambda: not second.busy)
        self.assertEqual(second.job_state, "Xong")
        self.assertEqual(second.progress_label.cget("text"), "100%")
        self.errors.assert_not_called()

    def test_export_reserves_destination_and_snapshots_settings(self):
        first, second = self.host.active_tab, self.host.new_tab()
        destination = self.root / "video.mp4"
        started = threading.Event()
        snapshots = []

        def render(renderer, title, rows, path):
            snapshots.append(renderer.settings)
            started.set()
            self.release.wait(8)
            renderer.check()
            Path(path).write_bytes(b"completed video")
            renderer.duration = 3

        with patch.object(Renderer, "render", render), patch(
                "app.filedialog.asksaveasfilename", return_value=str(destination)), patch(
                "app.messagebox.showwarning") as warnings:
            first.brand.set("Captured brand")
            first.export()
            self.pump_until(started.is_set)
            first.brand.set("Edited while exporting")
            self.assertEqual(snapshots[0].brand, "Captured brand")
            second.export()
            warnings.assert_called_once()
            self.assertFalse(second.busy)
            self.assertEqual(len(snapshots), 1)
            self.release.set()
            self.pump_until(lambda: not first.busy)
            self.assertEqual(self.host.output_owners, {})
            second.export()
            self.pump_until(lambda: not second.busy)
            self.assertEqual(len(snapshots), 2)
            self.assertEqual(second.last_output, destination)
            self.assertEqual(self.host.output_owners, {})
        self.errors.assert_not_called()

    def test_failed_export_releases_destination(self):
        tab = self.host.active_tab
        destination = self.root / "failure.mp4"
        with patch.object(Renderer, "render", side_effect=RuntimeError("render failed")), patch(
                "app.filedialog.asksaveasfilename", return_value=str(destination)):
            tab.export()
            self.pump_until(lambda: not tab.busy)
        self.assertEqual(tab.job_state, "Lỗi")
        self.assertEqual(self.host.output_owners, {})
        self.assertIsNone(tab.export_path)
        self.assertFalse(destination.exists())
        self.errors.assert_called_once()

    def test_closing_tab_only_cancels_its_callbacks(self):
        first, second = self.host.active_tab, self.host.new_tab()
        callbacks = []
        first.after(400, lambda: callbacks.append("closed tab"))
        second.after(400, lambda: callbacks.append("open tab"))
        self.host.close_tab(first, confirm=False)
        self.pump_until(lambda: "open tab" in callbacks)
        self.assertEqual(callbacks, ["open tab"])
        self.assertTrue(first.disposed)
        self.assertEqual(first._timers, set())
        self.assertFalse(second.disposed)
        self.assertIs(self.host.active_tab, second)
        self.assertTrue(second.poll_timer)

    def test_busy_tab_closes_after_worker_stops_and_keeps_other_tab_alive(self):
        first, second = self.host.active_tab, self.host.new_tab()
        destination = self.root / "closing.mp4"
        started = threading.Event()
        self.assertTrue(self.host.reserve_output(first, destination))

        def job():
            started.set()
            self.release.wait(8)
            if first.cancel.is_set():
                raise Cancelled("Closed tab cancelled")
            return {"message": "Finished", "path": str(destination)}

        first.start_job(job, exporting=True)
        self.pump_until(started.is_set)
        self.host.close_tab(first, confirm=False)
        self.assertTrue(first.closing and first.busy)
        self.assertFalse(first.disposed)
        self.assertIn(first, self.host.output_owners.values())
        self.assertFalse(second.cancel.is_set())
        callback = threading.Event()
        second.after(20, callback.set)
        self.pump_until(callback.is_set)
        self.release.set()
        self.pump_until(lambda: first.disposed)
        self.assertNotIn(first, self.host.tabs)
        self.assertEqual(self.host.output_owners, {})
        self.assertIs(self.host.active_tab, second)
        self.assertFalse(second.disposed)
        self.errors.assert_not_called()

    def test_switching_discards_queued_preview_and_cleans_directory(self):
        first, second = self.host.active_tab, self.host.new_tab()
        self.host.select_tab(first)
        preview_dir = self.root / "prepared-preview"
        preview_dir.mkdir()
        (preview_dir / "track.wav").write_bytes(b"placeholder")
        first.preview_generation = 1
        first.preview_cancel = threading.Event()
        first.busy = True
        first.job_exporting = False
        data = (1, list(first.rows), first.quiz_title, first.settings(), [], preview_dir, None)
        first.events.put(("preview_ready", data))
        first.events.put(("done", "Preview prepared"))
        with patch.object(first.audio_player, "play") as play:
            self.host.select_tab(second)
            self.pump_until(lambda: not first.busy)
            play.assert_not_called()
        self.assertFalse(preview_dir.exists())
        self.assertIsNone(getattr(first, "preview_directory", None))
        self.assertFalse(second.cancel.is_set())
        self.errors.assert_not_called()


if __name__ == "__main__":
    unittest.main()
