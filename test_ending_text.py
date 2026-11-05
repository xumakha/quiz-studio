"""Custom outro narration shares the measured preview/export scene pipeline."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from content_timeline import DEFAULT_ENDING_TEXT, ending_scene, prepare_scene
from engine import Renderer, Settings, parse_questions


class EndingTextTests(unittest.TestCase):
    def test_custom_ending_reaches_export_and_preserves_measured_duration(self):
        title, rows = parse_questions('[{"question":"One?","options":["One","Two"],"answer":0}]')
        custom = "Cảm ơn bạn! [en]See you next time![/en]"
        for text, speech in ((custom, True), ("", True), (custom, False)):
            with self.subTest(text=text, speech=speech), tempfile.TemporaryDirectory() as directory:
                renderer = Renderer(Settings(ending_text=text, speech=speech, countdown=1, width=180, height=320))
                spoken = []

                async def capture(value, target, temporary):
                    spoken.append(value)

                def fake_run(args):
                    Path(args[-1]).touch()
                    return ""

                with patch.object(renderer, "speech", side_effect=capture), \
                     patch.object(renderer, "audio_duration", return_value=6.25), \
                     patch.object(renderer, "segment") as segment, \
                     patch.object(renderer, "run", side_effect=fake_run):
                    renderer.render(title, rows, Path(directory) / "video.mp4")
                ending = segment.call_args_list[-1].args
                self.assertEqual(ending[0].name, "ending.png")
                if text and speech:
                    self.assertEqual(spoken[-1], custom)
                    self.assertEqual(spoken.count(custom), 1)
                    self.assertAlmostEqual(ending[2], 6.7666666667)
                else:
                    self.assertNotIn(custom, spoken)
                    self.assertEqual(ending[2], 3)
                    self.assertIsNone(ending[3])
                self.assertNotIn(DEFAULT_ENDING_TEXT, spoken)

    def test_preview_scene_defaults_trim_blank_and_skip_tts(self):
        self.assertEqual(ending_scene().narration, DEFAULT_ENDING_TEXT)
        self.assertEqual(ending_scene(Settings()).narration, DEFAULT_ENDING_TEXT)
        self.assertEqual(ending_scene(Settings(ending_text="  Hẹn gặp lại!  ")).narration, "Hẹn gặp lại!")
        with tempfile.TemporaryDirectory() as directory:
            renderer = Renderer(Settings(ending_text=" \t "))
            with patch.object(renderer, "speech", new_callable=AsyncMock) as speech:
                prepared = prepare_scene(renderer, ending_scene(renderer.settings), Path(directory), "ending", 1)
            speech.assert_not_called()
            self.assertEqual(prepared.seconds, 3)
            self.assertIsNone(prepared.audio)


if __name__ == "__main__":
    unittest.main()
