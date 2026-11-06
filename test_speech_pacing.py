"""Validate actual PCM pauses, timing and preserved technical notation offline."""
import array
import asyncio
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

from content_timeline import plan_item, prepare_scene, preview_audio
from engine import Renderer, Settings
from speech_pacing import speech_segments


def samples(path):
    with wave.open(str(path), "rb") as track:
        return array.array("h", track.readframes(track.getnframes()))


def rms_at(data, seconds, duration=.05):
    start = round(seconds*44100)*2
    block = data[start:start+round(duration*44100)*2]
    return math.sqrt(sum(value*value for value in block)/len(block))


class SpeechPacingTests(unittest.TestCase):
    def test_separators_preserve_notation_and_word_hyphens(self):
        text = "Use 1/2, 3:2, 12:30, 8 - 3 and -5 in a well-known rule at https://example.com/a/b."
        parts = speech_segments(text)
        self.assertEqual([part[0] for part in parts], [text])
        self.assertLess(parts[0][2], 1)
        parts = speech_segments("Read / write — compare - choose | review; finish: next → done")
        self.assertEqual([part[0] for part in parts],
                         ["Read slash", "write", "compare", "choose", "review", "finish", "next to", "done"])
        self.assertTrue(all(gap > 0 and tempo < 1 for _, gap, tempo in parts[:-1]))

    def test_prepared_answer_has_real_leading_and_explanation_pauses(self):
        row = dict(type="multiple_choice", question="Question?", options=["One", "Two"],
                   answer_index=0, explanation="Explanation.")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for template in ("exam", "military"):
                renderer = Renderer(Settings(template=template, countdown=1))
                answer = plan_item(row, renderer.settings)[-1]
                captured = []

                async def tone(speaker, text, target, directory, on_part=lambda fraction: None):
                    captured.append(text)
                    # Emulate the existing 250 ms device pre-roll, then speech.
                    speaker.run(["-f", "lavfi", "-i", "sine=frequency=880:duration=0.4:sample_rate=44100",
                                 "-af", "adelay=250:all=1", "-ac", "2", target])

                with self.subTest(template=template), patch.object(Renderer, "speech", tone):
                    prepared = prepare_scene(renderer, answer, root, template, 1)
                    data = samples(prepared.audio)
                    self.assertEqual(captured, ["The answer is A.", "Explanation."])
                    # .75s explicit lead + .25s pre-roll; .4s spoken answer;
                    # .75s gap + the explanation's .25s pre-roll.
                    self.assertEqual(rms_at(data, .9), 0)
                    self.assertGreater(rms_at(data, 1.1), 2000)
                    self.assertEqual(rms_at(data, 1.8), 0)
                    self.assertGreater(rms_at(data, 2.5), 2000)
                    self.assertAlmostEqual(len(data)/2/44100, 2.8, places=3)
                    self.assertAlmostEqual(prepared.seconds, 3.3, places=3)
                    preview = preview_audio(renderer, [prepared], root)
                    self.assertEqual(samples(preview)[:len(data)], data)
                    renderer.settings.read_explanation = False
                    answer = plan_item(row, renderer.settings)[-1]
                    prepared = prepare_scene(renderer, answer, root, template+"-no-explanation", 1)
                    self.assertNotIn("Explanation.", answer.narration)
                    self.assertAlmostEqual(len(samples(prepared.audio))/2/44100, 1.4, places=3)
            for template in ("english", "math", "classic", "tech"):
                answer = plan_item(row, Settings(template=template))[-1]
                self.assertEqual(answer.leading_silence, 0)
                self.assertEqual(answer.speech_gap, 0)

    def test_tts_punctuation_pauses_tempo_voice_and_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            renderer = Renderer(Settings(template="exam", english_voice="en-US-GuyNeural"))
            calls = []

            async def synthesize(text, voice, path):
                calls.append((text, voice))
                renderer.run(["-f", "lavfi", "-i", "sine=frequency=880:duration=0.4:sample_rate=44100",
                              "-ac", "2", "-f", "wav", path])

            with patch("preferences.BackgroundStore", return_value=SimpleNamespace(directory=root)), \
                    patch.object(renderer, "_synthesize_speech", synthesize):
                for name in ("fresh", "cached"):
                    target = root / f"{name}.wav"
                    asyncio.run(renderer.speech("Read / write", target, root))
                    data = samples(target)
                    self.assertEqual(rms_at(data, .1), 0)
                    self.assertGreater(rms_at(data, .35), 2000)
                    self.assertEqual(rms_at(data, .75), 0)
                    self.assertGreater(rms_at(data, 1.1), 2000)
                    expected = .25+.8/.94+.3
                    self.assertAlmostEqual(len(data)/2/44100, expected, delta=.04)
                self.assertEqual(calls, [("Read slash", "en-US-GuyNeural"), ("write", "en-US-GuyNeural")])
                self.assertEqual((root/"fresh.wav").read_bytes(), (root/"cached.wav").read_bytes())

    def test_export_preserves_the_same_pauses_as_preview(self):
        row = dict(type="multiple_choice", question="Question?", options=["One", "Two"],
                   answer_index=0, explanation="Explanation.")

        class OfflineRenderer(Renderer):
            async def _synthesize_speech(self, text, voice, path):
                self.run(["-f", "lavfi", "-i", "sine=frequency=880:duration=0.4:sample_rate=44100",
                          "-ac", "2", "-f", "wav", path])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for template in ("exam", "military"):
                with self.subTest(template=template), \
                        patch("preferences.BackgroundStore", return_value=SimpleNamespace(directory=root)):
                    renderer = OfflineRenderer(Settings(template=template, width=180, height=320,
                                                        countdown=1, ending_text=""))
                    # Speech parts intentionally create Renderer instances, as in
                    # real multi-speaker content; keep all providers offline.
                    with patch.object(Renderer, "_synthesize_speech", OfflineRenderer._synthesize_speech):
                        prepared = [prepare_scene(renderer, scene, root, f"part-{i}", 1)
                                    for i, scene in enumerate(plan_item(row, renderer.settings))]
                        preview = preview_audio(renderer, prepared, root)
                        target = root / f"{template}.mp4"
                        renderer.render("Practice", [row], target)
                    decoded = root / "decoded.wav"
                    renderer.run(["-i", target, "-vn", "-c:a", "pcm_s16le", decoded])
                    data, expected = samples(decoded), samples(preview)
                    answer_start = sum(part.seconds for part in prepared[:-1])
                    for offset, silent in ((.9, True), (1.1, False), (1.8, True), (2.5, False)):
                        actual = rms_at(data, answer_start+offset)
                        reference = rms_at(expected, answer_start+offset)
                        if silent:
                            self.assertLess(actual, 20)
                            self.assertEqual(reference, 0)
                        else:
                            self.assertGreater(actual, 2000)
                            self.assertGreater(reference, 2000)


if __name__ == "__main__":
    unittest.main()
