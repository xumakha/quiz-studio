"""Exercise preview timing without a Tk window or an audio device."""
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

from app import VideoTab
from content_timeline import PreparedScene, Scene
from engine import Settings


class PreviewHarness:
    def __init__(self, directory, *, video=False, count=2):
        self.now = 100.0
        self.scheduled = {}
        self.next_timer = 0
        self.preview_generation = 1
        self.preview_cancel = threading.Event()
        self.closing = False
        self.host = SimpleNamespace(active_tab=self)
        self.duration_label = Mock()
        self.preview_seek = Mock()
        self.preview = Mock()
        self.selected = Mock()
        self.validation = Mock()
        self.audio_player = Mock()
        self.background_preview_reader = None
        self.directory = Path(directory)
        self.settings = Settings(countdown=count, background="motion.mp4" if video else "")
        self.rows = [{"type": "multiple_choice"}]
        self.scenes = [(0, PreparedScene(Scene("question", "", ""), .25))]
        self.scenes += [(0, PreparedScene(Scene("countdown", "", "", countdown=n), 1))
                        for n in range(count, 0, -1)]
        self.scenes += [(0, PreparedScene(Scene("answer", "", ""), .25))]
        self.stop_preview = Mock(side_effect=self.preview_cancel.set)

    def after(self, delay, callback):
        self.next_timer += 1
        self.scheduled[self.next_timer] = delay, callback
        return self.next_timer

    def after_cancel(self, timer):
        self.scheduled.pop(timer, None)

    def stop_background_preview(self):
        self.background_preview_reader = None

    def start_background_preview(self, settings, picture, offset):
        self.background_preview_reader = object()
        self.background_preview_overlay = picture.convert("RGBA")

    def render_scene(self, row, scene, number, total, title, settings, countdown_remaining=None):
        # A tiny synthetic layout isolates playback scheduling from text fitting.
        picture = Image.new("RGBA" if settings.background_overlay else "RGB", (180, 320), "white")
        draw = ImageDraw.Draw(picture)
        draw.rectangle((10, 10, 20, 20), fill=(scene.countdown or 0, 70, 90))
        if scene.countdown is not None:
            draw.rounded_rectangle((10, 100, 170, 112), 6, fill="#dddddd")
            if countdown_remaining:
                draw.rounded_rectangle((10, 100, 10+160*countdown_remaining/settings.countdown, 112),
                                       6, fill="#225588")
        return picture

    def begin(self, audio=None):
        VideoTab.begin_preview(self, (1, self.rows, "Quiz", self.settings, self.scenes, self.directory, audio))

    def step(self, timestamp):
        self.now = timestamp
        _, callback = self.scheduled.pop(self.playback_timer)
        callback()

    def picture(self):
        return self.background_preview_overlay if self.settings.background_overlay else self.preview_image


class CountdownPreviewTests(unittest.TestCase):
    def test_smooth_ticks_seek_and_background_reader_share_one_clock(self):
        for video in (False, True):
            with self.subTest(video=video), tempfile.TemporaryDirectory() as directory:
                tab = PreviewHarness(directory, video=video)
                audio = Path(directory) / "preview.wav"
                with wave.open(str(audio), "wb") as track:
                    track.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
                    track.writeframes(bytes(110250*4))
                with patch("time.monotonic", side_effect=lambda: tab.now), \
                        patch("app.ImageTk.PhotoImage", side_effect=lambda picture: picture.copy()), \
                        patch("content_renderer.render_scene", side_effect=tab.render_scene) as render:
                    tab.begin(audio)
                    self.assertEqual(tab.scheduled[tab.playback_timer][0], 250)
                    tab.audio_player.play.assert_called_once_with(audio)
                    tab.step(100.25)
                    first = tab.picture().copy()
                    calls = render.call_count
                    reader = tab.background_preview_reader
                    tab.step(100.75)
                    halfway = tab.picture().copy()
                    self.assertNotEqual(first.tobytes(), halfway.tobytes())
                    self.assertEqual(render.call_count, calls, "Ticks must reuse the rendered layout")
                    self.assertLessEqual(tab.scheduled[tab.playback_timer][0], 34)
                    if video:
                        self.assertIs(tab.background_preview_reader, reader)
                    tab.step(101.25)
                    self.assertEqual(render.call_count, calls+2)
                    tab.seek_preview(.75)  # Halfway through the first countdown second.
                    self.assertEqual(tab.picture().tobytes(), halfway.tobytes())
                    self.assertEqual(render.call_count, calls+2, "Recent scenes remain cached when seeking")
                    if video:
                        self.assertIsNot(tab.background_preview_reader, reader)
                    sought_audio = Path(directory) / "seek-track.wav"
                    tab.audio_player.play.assert_called_with(sought_audio)
                    with wave.open(str(sought_audio), "rb") as track:
                        self.assertEqual(track.getnframes(), round(1.75*44100))
                    tab.step(103)
                    tab.stop_preview.assert_called_once()
                    tab.validation.configure.assert_not_called()

    def test_long_preview_releases_old_layouts_and_can_render_them_again_on_seek(self):
        with tempfile.TemporaryDirectory() as directory:
            tab = PreviewHarness(directory, count=5)
            with patch("time.monotonic", side_effect=lambda: tab.now), \
                    patch("app.ImageTk.PhotoImage", side_effect=lambda picture: picture.copy()), \
                    patch("content_renderer.render_scene", side_effect=tab.render_scene) as render:
                tab.begin()
                for timestamp in (100.25, 101.25, 102.25, 103.25):
                    tab.step(timestamp)
                calls = render.call_count
                tab.seek_preview(.75)
                self.assertEqual(render.call_count, calls+2, "Evicted scenes must be rebuilt when revisited")
                calls = render.call_count
                tab.step(103.5)
                self.assertEqual(render.call_count, calls)
                tab.validation.configure.assert_not_called()

    def test_late_callbacks_skip_expired_scenes_and_cancelled_callbacks_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            tab = PreviewHarness(directory)
            with patch("time.monotonic", side_effect=lambda: tab.now), \
                    patch("app.ImageTk.PhotoImage", side_effect=lambda picture: picture.copy()), \
                    patch("content_renderer.render_scene", side_effect=tab.render_scene) as render:
                tab.begin()
                tab.step(101.5)
                self.assertEqual(render.call_args.args[1].countdown, 1)
                tab.preview_seek.set.assert_called_with(1.5)
                calls = render.call_count
                tab.preview_cancel.set()
                tab.step(101.6)
                self.assertEqual(render.call_count, calls)
                self.assertIsNone(tab.playback_timer)
                self.assertEqual(tab.scheduled, {})


if __name__ == "__main__":
    unittest.main()
