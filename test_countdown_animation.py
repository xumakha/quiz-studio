import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from content_renderer import render_scene
from content_timeline import estimated_seconds, plan_item, thinking_seconds
from content_types import normalize, sample_document
from countdown_animation import CountdownAnimation
from engine import Renderer, Settings, parse_legacy_questions


def countdown_case(kind, template, seconds=4, **options):
    title, rows, _ = normalize(sample_document(kind), parse_legacy_questions)
    row = dict(rows[0], thinking_seconds=seconds)
    settings = Settings(width=360, height=640, template=template, countdown=9,
                        speech=False, logo_watermark_enabled=False, **options)
    scene = next(scene for scene in plan_item(row, settings) if scene.countdown is not None)
    return title, row, settings, scene


def artwork(title, row, settings, scene, remaining):
    return render_scene(row, scene, 1, 1, title, settings, countdown_remaining=remaining)


class CountdownAnimationTests(unittest.TestCase):
    def test_fractional_timer_preserves_labels_and_respects_item_duration(self):
        cases = [("multiple_choice", theme) for theme in
                 ("english", "math", "classic", "exam", "military", "tech")]
        cases += [("guess_word", "english"), ("fill_blank", "exam"), ("word_order", "military")]
        for kind, theme in cases:
            with self.subTest(kind=kind, theme=theme):
                title, row, settings, scene = countdown_case(kind, theme)
                self.assertEqual(scene.countdown, 4)
                full = artwork(title, row, settings, scene, 4)
                half = artwork(title, row, settings, scene, 2)
                empty = artwork(title, row, settings, scene, 0)
                bounds = ImageChops.difference(full, empty).getbbox()
                self.assertIsNotNone(bounds)
                left, top, right, bottom = bounds
                # All changed pixels belong to the thin bar, below its integer label.
                self.assertGreater(top, 450)
                self.assertLess(bottom-top, 15)
                restored = half.copy()
                restored.paste(full.crop(bounds), bounds)
                self.assertEqual(restored.tobytes(), full.tobytes())
                half_bounds = ImageChops.difference(half, empty).getbbox()
                self.assertAlmostEqual((half_bounds[2]-left)/(right-left), .5, delta=.04)
                self.assertEqual(artwork(title, row, settings, scene, -1).tobytes(), empty.tobytes())
                self.assertEqual(artwork(title, row, settings, scene, 10).tobytes(), full.tobytes())

    def test_animation_is_continuous_at_second_boundaries_and_preserves_alpha(self):
        for overlay in (False, True):
            with self.subTest(overlay=overlay):
                title, row, settings, scene = countdown_case(
                    "guess_word", "english", background_overlay=overlay, background_dim=35)
                full = artwork(title, row, settings, scene, 4)
                empty = artwork(title, row, settings, scene, 0)
                animation = CountdownAnimation(full, empty, 4, thinking_seconds(row, settings))
                next_scene = replace(scene, countdown=3)
                next_animation = CountdownAnimation(
                    artwork(title, row, settings, next_scene, 4),
                    artwork(title, row, settings, next_scene, 0), 3, 4)
                self.assertEqual(animation.patch(1).tobytes(), next_animation.patch(0).tobytes())
                self.assertEqual(animation.frame(4).tobytes(), empty.tobytes())
                self.assertEqual(animation.frame(10).tobytes(), empty.tobytes())
                self.assertEqual(animation.frame(-1).tobytes(), full.tobytes())
                self.assertNotEqual(animation.patch(.1).tobytes(), animation.patch(.2).tobytes())
                if overlay:
                    base = animation.base_frame()
                    self.assertIsNone(base.crop(animation.bounds).getchannel("A").getbbox())
                    patch = animation.patch(.5)
                    self.assertLess(patch.getchannel("A").getextrema()[0], 255)
                    base.paste(patch, animation.bounds)
                    self.assertEqual(base.tobytes(), animation.frame(.5).tobytes())

    def test_export_moves_each_frame_without_boundary_jumps_or_dark_seams(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            background = root / "background.png"
            Image.new("RGB", (360, 640), (150, 200, 240)).save(background)
            motion = root / "motion.mp4"
            setup = Renderer(Settings())
            # Movement remains visible above the timer; its background stays a
            # known color so alpha errors around the animated patch are measurable.
            setup.run(["-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30:duration=1",
                       "-vf", "drawbox=x=0:y=390:w=iw:h=250:color=0x96c8f0:t=fill",
                       "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", motion])
            for kind, theme in (("multiple_choice", "classic"), ("guess_word", "english")):
                for source in (background, motion):
                    with self.subTest(kind=kind, background=source.suffix):
                        title, row, settings, scene = countdown_case(
                            kind, theme, seconds=2, background=str(source), background_dim=35,
                            read_explanation=False)
                        renderer = Renderer(settings)
                        target = root / f"{kind}-{source.stem}.mp4"
                        renderer.render(title, [row], target)
                        scenes = plan_item(row, settings)
                        start = sum(math.ceil(estimated_seconds(item)*30)/30 for item in
                                    scenes[:scenes.index(scene)])
                        decoded = root / "countdown.rgb"
                        renderer.run(["-ss", f"{start:.9f}", "-i", target, "-frames:v", "60",
                                      "-vf", "crop=360:140:0:390", "-pix_fmt", "rgb24",
                                      "-f", "rawvideo", decoded])
                        data = decoded.read_bytes()
                        frame_bytes = 360*140*3
                        self.assertEqual(len(data), 60*frame_bytes)
                        pictures = [Image.frombytes("RGB", (360, 140), data[i:i+frame_bytes])
                                    for i in range(0, len(data), frame_bytes)]
                        reference_settings = replace(settings, background=str(background))
                        full = artwork(title, row, reference_settings, scene, 2)
                        empty = artwork(title, row, reference_settings, scene, 0)
                        animation = CountdownAnimation(full, empty, 2, 2)
                        left, top, right, bottom = animation.bounds
                        center = (top+bottom)//2
                        counts = []
                        for picture in pictures:
                            count = 0
                            for x in range(left+3, right-3):
                                actual = picture.getpixel((x, center-390))
                                filled = full.getpixel((x, center))
                                blank = empty.getpixel((x, center))
                                distance = lambda color: sum((a-b)**2 for a, b in zip(actual, color))
                                count += distance(filled) < distance(blank)
                            counts.append(count)
                        for offset in (0, 30):
                            self.assertGreater(len(set(counts[offset:offset+30])), 24)
                        self.assertGreater(counts[0], (right-left)*.9)
                        self.assertLess(counts[-1], (right-left)*.06)
                        steps = [a-b for a, b in zip(counts, counts[1:])]
                        self.assertTrue(all(-1 <= step <= (right-left)/30 for step in steps), steps)
                        # The second change should be one ordinary frame of motion.
                        self.assertLessEqual(steps[29], max(steps[:29])+2)
                        # Check the whole bar and its transparent fringe against
                        # the preview at a mid-second point, including dimmed video.
                        area = (left-3, top-3, right+3, bottom+3)
                        actual = pictures[15].crop((area[0], area[1]-390, area[2], area[3]-390))
                        expected = animation.frame(.5).crop(area)
                        self.assertLess(max(ImageStat.Stat(ImageChops.difference(actual, expected)).mean), 9)
                        label_area = (80, 15, 280, 45)
                        stable = ImageChops.difference(pictures[5].crop(label_area), pictures[20].crop(label_area))
                        self.assertLess(max(ImageStat.Stat(stable).mean), 2)


if __name__ == "__main__":
    unittest.main()
