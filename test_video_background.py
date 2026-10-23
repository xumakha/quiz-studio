import tempfile
import unittest
import time
from pathlib import Path

from PIL import Image

from background_media import VideoPreview
from engine import Renderer, Settings, frame, parse_questions
from preferences import BackgroundStore


class VideoBackgroundTests(unittest.TestCase):
    def test_live_preview_moves_loops_seeks_and_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "motion.mp4"
            Renderer(Settings()).run([
                "-f", "lavfi", "-i", "testsrc2=size=180x320:rate=30:duration=0.7",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", source])
            for offset in (0, 1.1):
                reader = VideoPreview(source, (124, 220), offset)
                try:
                    samples = set()
                    deadline = time.monotonic() + 2.5
                    while time.monotonic() < deadline:
                        if reader.image is not None:
                            self.assertEqual(reader.image.size, (124, 220))
                            samples.add(reader.image.tobytes())
                        time.sleep(0.05)
                    self.assertIsNone(reader.error)
                    self.assertIsNone(reader.process.poll())
                    self.assertGreater(len(samples), 3)
                finally:
                    reader.close()
                    reader.thread.join(timeout=3)
                self.assertFalse(reader.thread.is_alive())
                self.assertIsNotNone(reader.process.poll())

    def test_video_storage_preview_and_looping_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'background.mp4'
            settings = Settings(width=180, height=320, speech=False, countdown=1, background_dim=0)
            renderer = Renderer(settings)
            renderer.run(['-f', 'lavfi', '-i', 'testsrc2=size=180x320:rate=30:duration=0.7',
                          '-c:v', 'libx264', '-pix_fmt', 'yuv420p', source])
            store = BackgroundStore(root / 'data')
            selected = store.select(source, 0)
            self.assertEqual(Path(selected["background"]).parent.name, "videos")
            self.assertEqual(store.library()["videos"][0]["name"], "background.mp4")
            store.clear(0)
            store.select_saved(selected["background"], 0)
            source.unlink()
            settings.background = store.load()['background']
            self.assertEqual(settings.background, selected['background'])
            title, rows = parse_questions('[{"question":"Test?","options":["A","B"],"answer":0}]')
            for template in ('classic', 'math', 'english'):
                settings.template = template
                self.assertEqual(frame(rows[0], 1, 1, title, settings).mode, 'RGB')
            settings.background_overlay = True
            overlay = frame(rows[0], 1, 1, title, settings)
            self.assertEqual(overlay.mode, 'RGBA')
            self.assertEqual(overlay.getpixel((0, 0))[3], 0)
            picture = root / 'overlay.png'
            overlay.save(picture)
            target = root / 'segment.mov'
            renderer.segment(picture, target, 1.3, background_offset=1.0)
            renderer.run(['-i', target, '-f', 'null', '-'])
            captures = []
            for index, time in enumerate((0, 0.3)):
                capture = root / f'capture-{index}.png'
                renderer.run(['-ss', time, '-i', target, '-frames:v', '1', capture])
                with Image.open(capture) as image:
                    captures.append(image.crop((0, 0, 180, 12)).tobytes())
            self.assertNotEqual(*captures)
            settings.background_overlay = False
            renderer.render(title, rows, root / 'finished.mp4')
            renderer.run(['-i', root / 'finished.mp4', '-f', 'null', '-'])
            bad = root / 'broken.mp4'
            bad.write_bytes(b'not a video')
            with self.assertRaises(ValueError):
                store.select(bad, 0)
            self.assertEqual(store.load()['background'], settings.background)


if __name__ == '__main__':
    unittest.main()
