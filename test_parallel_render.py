import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from engine import Cancelled, Renderer, Settings, parse_questions
from preferences import BrandingStore


class ParallelRenderTests(unittest.TestCase):
    @staticmethod
    def make_renderer(root, name, logo_color, ending_color):
        logo, ending = root / f"{name}-logo.png", root / f"{name}-ending.png"
        Image.new("RGB", (1000, 1000), logo_color).save(logo)
        Image.new("RGB", (90, 160), ending_color).save(ending)
        store = BrandingStore(root / "data")
        store.select("logo_image", logo)
        assets = store.select("ending_image", ending)
        return Renderer(Settings(width=180, height=320, speech=False, countdown=1,
                                 logo_image=assets["logo_image"], left_logo_image=assets["logo_image"],
                                 ending_image=assets["ending_image"]))

    def assert_video_colors(self, renderer, target, logo_color, ending_color):
        for phase, position, expected in (("logo", (22, 32), logo_color),
                                          ("ending", (90, 160), ending_color)):
            capture = target.with_name(f"{target.stem}-{phase}.png")
            seek = ["-ss", "0.2"] if phase == "logo" else ["-sseof", "-0.2"]
            renderer.run([*seek, "-i", target, "-frames:v", "1", capture])
            with Image.open(capture) as image:
                actual = image.convert("RGB").getpixel(position)
            for channel, intended in zip(actual, expected):
                self.assertLess(abs(channel - intended), 20, (phase, actual, expected))

    def test_parallel_exports_keep_images_and_temporary_files_separate(self):
        title, rows = parse_questions('[{"question":"One?","options":["One","Two"],"answer":0}]')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.make_renderer(root, "first", "red", "lime")
            second = self.make_renderer(root, "second", "blue", "yellow")
            self.assertNotEqual(first.settings.logo_image, second.settings.logo_image)
            self.assertNotEqual(first.settings.ending_image, second.settings.ending_image)
            barrier = threading.Barrier(2)
            temporary_directories = {}

            def synchronize(renderer, name):
                original = renderer.segment

                def segment(image, output, *args, **kwargs):
                    if name not in temporary_directories:
                        temporary_directories[name] = image.parent
                        barrier.wait(timeout=20)
                    return original(image, output, *args, **kwargs)

                return segment

            with patch.object(first, "segment", side_effect=synchronize(first, "first")), \
                 patch.object(second, "segment", side_effect=synchronize(second, "second")), \
                 ThreadPoolExecutor(max_workers=2) as executor:
                exports = [executor.submit(renderer.render, title, rows, root / f"{name}.mp4")
                           for name, renderer in (("first", first), ("second", second))]
                for export in exports:
                    export.result(timeout=90)
            self.assertNotEqual(temporary_directories["first"], temporary_directories["second"])
            self.assertFalse(any(path.exists() for path in temporary_directories.values()))
            self.assert_video_colors(first, root / "first.mp4", (255, 0, 0), (0, 255, 0))
            self.assert_video_colors(second, root / "second.mp4", (0, 0, 255), (255, 255, 0))

    def test_cancelling_one_parallel_export_does_not_cancel_the_other(self):
        title, rows = parse_questions('[{"question":"One?","options":["One","Two"],"answer":0}]')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cancelled = self.make_renderer(root, "cancelled", "red", "lime")
            successful = self.make_renderer(root, "successful", "blue", "yellow")
            preserved = root / "cancelled.mp4"
            preserved.write_bytes(b"previous completed video")
            barrier = threading.Barrier(2)

            def synchronize(renderer, should_cancel):
                original = renderer.segment
                first_segment = True

                def segment(*args, **kwargs):
                    nonlocal first_segment
                    if first_segment:
                        first_segment = False
                        barrier.wait(timeout=20)
                        result = original(*args, **kwargs)
                        if should_cancel:
                            renderer.cancel.set()
                        return result
                    return original(*args, **kwargs)

                return segment

            with patch.object(cancelled, "segment", side_effect=synchronize(cancelled, True)), \
                 patch.object(successful, "segment", side_effect=synchronize(successful, False)), \
                 ThreadPoolExecutor(max_workers=2) as executor:
                stopped = executor.submit(cancelled.render, title, rows, preserved)
                completed = executor.submit(successful.render, title, rows, root / "successful.mp4")
                with self.assertRaises(Cancelled):
                    stopped.result(timeout=90)
                completed.result(timeout=90)
            self.assertEqual(preserved.read_bytes(), b"previous completed video")
            self.assertFalse(successful.cancel.is_set())
            self.assert_video_colors(successful, root / "successful.mp4", (0, 0, 255), (255, 255, 0))


if __name__ == "__main__":
    unittest.main()
