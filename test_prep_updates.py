import array
import asyncio
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

from engine import Renderer, Settings, frame, parse_questions
from content_timeline import plan_item, thinking_seconds, prepare_scene
from content_types import sample_document
from preferences import UserSettingsStore
from video_themes import detect_template
from workspace_profiles import WorkspaceProfiles


class PrepUpdateTests(unittest.TestCase):
    def test_profile_defaults_upgrade_once_and_preserve_manual_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            profiles = WorkspaceProfiles(directory)
            for record, expected in zip(profiles.load()[1:], ["Luyện thi · Chứng chỉ", "Quân sự · ASVAB"]):
                target = profiles._profile_directory(record["id"])
                target.mkdir(parents=True)
                (target / "settings.json").write_text(json.dumps({"video_template": "Tự động theo môn học", "rate": 13}))
                profiles.prepare(record)
                store = UserSettingsStore(directory, config_dir=target)
                state = store.load()
                self.assertEqual(state["video_template"], expected)
                self.assertEqual(state["rate"], 13)
                state["video_template"] = "Tự động theo môn học"
                store.save(state)
                profiles.prepare(record)
                self.assertEqual(store.load()["video_template"], "Tự động theo môn học")

    def test_countdown_uses_editor_unless_json_overrides_it(self):
        doc = sample_document("guess_word")
        doc.pop("settings", None)
        _, rows = parse_questions(json.dumps(doc))
        settings = Settings(countdown=9, speech=False)
        self.assertEqual(thinking_seconds(rows[0], settings), 9)
        self.assertEqual([s.countdown for s in plan_item(rows[0], settings) if s.countdown is not None], list(range(9, 0, -1)))
        doc["settings"] = {"thinking_seconds": 7}
        doc["items"][0]["thinking_seconds"] = 3
        _, rows = parse_questions(json.dumps(doc))
        self.assertEqual(thinking_seconds(rows[0], settings), 3)
        self.assertEqual(thinking_seconds(rows[1], settings), 7)
        with tempfile.TemporaryDirectory() as directory:
            for scene in plan_item(rows[0], settings):
                if scene.countdown is not None:
                    self.assertEqual(prepare_scene(Renderer(settings), scene, Path(directory), "test", 1).seconds, 1)

    def test_prep_templates_support_all_option_counts_and_phases(self):
        from content_renderer import render_ending
        for theme in ["exam", "military", "tech", "easy_pass", "dmv"]:
            settings = Settings(template=theme, width=360, height=640, watermark_enabled=False,
                                left_logo_enabled=False, right_chibi_enabled=False)
            self.assertEqual(render_ending(settings).size, (360, 640))
            for count in [2, 4, 6]:
                _, rows = parse_questions(json.dumps([{"question": "Select the correct answer.", "options": ["Practice option"]*count, "answer": "A", "thinking_seconds": 12}]))
                for phase in [{}, {"countdown": 12}, {"countdown": 1}, {"reveal": True}]:
                    with self.subTest(theme=theme, count=count, phase=phase):
                        self.assertEqual(frame(rows[0], 1, 10, "Exam practice", settings, **phase).size, (360, 640))
        for subject, expected in [("ASVAB", "military"), ("Tin học", "tech"), ("Chứng chỉ", "exam")]:
            self.assertEqual(detect_template({"subject": subject}), expected)

    def test_easy_pass_blue_applies_to_question_scene_and_ending(self):
        from content_renderer import render_scene, render_ending
        settings = Settings(template="easy_pass", width=1080, height=1920, speech=False,
                            watermark_enabled=False, logo_watermark_enabled=False,
                            left_logo_enabled=False, right_chibi_enabled=False)
        title, rows = parse_questions(json.dumps(sample_document("multiple_choice")))
        self.assertEqual(frame(rows[0], 1, 1, title, settings).getpixel((0, 0)), (217, 237, 247))
        title, rows = parse_questions(json.dumps(sample_document("guess_word")))
        scene = plan_item(rows[0], settings)[0]
        self.assertEqual(render_scene(rows[0], scene, 1, 1, title, settings).getpixel((0, 0)), (217, 237, 247))
        self.assertEqual(render_ending(settings).getpixel((0, 0)), (217, 237, 247))

    def test_existing_easy_pass_profile_gets_blue_once(self):
        with tempfile.TemporaryDirectory() as directory:
            profiles = WorkspaceProfiles(directory)
            record = next(row for row in profiles.load() if row["id"] == "easy-pass")
            target = profiles._profile_directory("easy-pass")
            target.mkdir(parents=True)
            path = target / "settings.json"
            path.write_text(json.dumps({"video_template": "Luyện thi · Chứng chỉ", "rate": 17}), encoding="utf-8")
            profiles.prepare(record)
            state = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(state, {"video_template": "easy-pass.app · Xanh nhạt", "rate": 17})
            state["video_template"] = "Luyện thi · Chứng chỉ"
            path.write_text(json.dumps(state), encoding="utf-8")
            profiles.prepare(record)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), state)

    def test_dmv_brand_color_and_distinct_layout_match_preview_and_ending(self):
        from branding import CONTENT_OFFSET_Y
        from content_renderer import render_scene, render_ending
        settings = Settings(template="dmv", speech=False, watermark_enabled=False,
                            logo_watermark_enabled=False, left_logo_enabled=False, right_chibi_enabled=False)
        title, rows = parse_questions(Path("examples/dmv_questions.json").read_text(encoding="utf-8"))
        question = frame(rows[0], 1, len(rows), title, settings, countdown=5)
        self.assertEqual(question.getpixel((90, 300+CONTENT_OFFSET_Y)), (68, 113, 253))
        self.assertEqual(question.getpixel((0, 0)), (240, 244, 255))
        scene = next(scene for scene in plan_item(rows[0], settings) if scene.countdown == 5)
        self.assertEqual(render_scene(rows[0], scene, 1, len(rows), title, settings).tobytes(), question.tobytes())
        self.assertEqual(render_ending(settings).getpixel((90, 625)), (68, 113, 253))
        for source in ("DMV practice", "Driving test", "Road signs", "Lái xe"):
            self.assertEqual(detect_template({"subject": source}), "dmv")

    def test_audio_preroll_preserves_initial_samples_and_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            renderer = Renderer(Settings(voice="google:en"))
            calls = []
            async def synthesize(text, voice, target):
                calls.append(text)
                renderer.run(["-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100:duration=0.4", "-c:a", "pcm_s16le", "-f", "wav", target])
            with patch("preferences.BackgroundStore", return_value=SimpleNamespace(directory=root)), patch.object(renderer, "_synthesize_speech", side_effect=synthesize):
                for name in ["first", "cached"]:
                    target = root / f"{name}.wav"
                    asyncio.run(renderer.speech("The rabbit eats the carrot.", target, root))
                    with wave.open(str(target), "rb") as stream:
                        self.assertEqual(stream.getnchannels(), 2)
                        samples = array.array("h", stream.readframes(stream.getnframes()))
                    lead = round(.25*44100)*2
                    self.assertEqual(set(samples[:lead]), {0})
                    onset = samples[lead:lead+4410*2]
                    rms = math.sqrt(sum(x*x for x in onset)/len(onset))
                    self.assertGreater(rms, 2000)
                    self.assertAlmostEqual(renderer.audio_duration(target), .65, places=2)
                self.assertEqual(calls, ["The rabbit eats the carrot."])
                self.assertEqual((root/"first.wav").read_bytes(), (root/"cached.wav").read_bytes())


if __name__ == "__main__":
    unittest.main()
