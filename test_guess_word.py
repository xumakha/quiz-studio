import copy
import unittest
from content_types import sample_document, normalize, masked_word, document_warnings
from content_timeline import plan_item, estimated_seconds
from content_renderer import render_scene
from engine import Settings, parse_legacy_questions
from unittest.mock import patch
from content_timeline import prepare_scene
from content_renderer import ipa_font
from engine import Renderer
from pathlib import Path
import tempfile
import wave


class GuessWordTests(unittest.TestCase):
    def test_two_line_context_hint_keeps_readable_font(self):
        from PIL import ImageDraw
        doc = sample_document('guess_word')
        hint = 'Làm một việc gì đó tốt hơn so với lần trước\nGiúp công việc đạt kết quả tốt hơn'
        doc['items'][0].update(context_hint=hint, ipa='/ɪmˈpruːv/')
        title, rows, _ = normalize(doc, parse_legacy_questions)
        settings = Settings(width=180, height=320)
        original = ImageDraw.ImageDraw.text
        for scene in plan_item(rows[0], settings):
            with self.subTest(phase=scene.phase):
                with patch.object(ImageDraw.ImageDraw, 'text', autospec=True, side_effect=original) as draw:
                    render_scene(rows[0], scene, 4, 10, title, settings)
                calls = [c for c in draw.call_args_list if c.args[2] in hint.splitlines()]
                self.assertEqual(len(calls), 2)
                self.assertTrue(all(c.kwargs['font'].size >= 30 for c in calls))

    def test_context_hint_visible_through_question_countdown_and_reveal(self):
        from PIL import ImageDraw
        doc = sample_document('guess_word')
        doc['items'][0].update(meaning_vi='Cải thiện', answer='improve',
                              context_hint='Làm một việc gì đó tốt hơn so với lần trước', ipa='/ɪmˈpruːv/')
        title, rows, _ = normalize(doc, parse_legacy_questions)
        settings = Settings(width=180, height=320)
        original = ImageDraw.ImageDraw.text
        for scene in plan_item(rows[0], settings):
            with patch.object(ImageDraw.ImageDraw, 'text', autospec=True, side_effect=original) as draw:
                render_scene(rows[0], scene, 1, 10, title, settings)
                self.assertIn(rows[0]['context_hint'], [c.args[2] for c in draw.call_args_list])

    def test_ipa_reveal_voice_and_repeat_pause(self):
        doc = sample_document('guess_word')
        doc['items'][0]['ipa'] = '/ækˈtɪv.ə.ti/'
        title, rows, _ = normalize(doc, parse_legacy_questions)
        settings = Settings(english_voice='en-GB-SoniaNeural', width=180, height=320)
        scenes = plan_item(rows[0], settings)
        answer = next(s for s in scenes if s.phase == 'answer')
        self.assertEqual(answer.speech_parts, ())
        self.assertEqual(answer.narration, '')
        explanation = next(s for s in scenes if s.phase == 'explanation')
        self.assertEqual(explanation.speech_parts, ((rows[0]['explanation'], 'en-US-JennyNeural'),))
        captured = []
        async def speech(renderer, text, target, directory, on_part=lambda value: None):
            captured.append((text, renderer.settings.english_voice))
            with wave.open(str(target), 'wb') as audio:
                audio.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))
                audio.writeframes(bytes(44100*4))
        with tempfile.TemporaryDirectory() as directory, patch.object(Renderer, 'speech', new=speech):
            prepared = prepare_scene(Renderer(settings), answer, Path(directory), 'answer', 1)
            self.assertEqual(prepared.seconds, 1)
            self.assertIsNone(prepared.audio)
            self.assertEqual(captured, [])
            prepare_scene(Renderer(settings), explanation, Path(directory), 'explanation', 1)
        self.assertEqual(captured, [(rows[0]['explanation'], 'en-US-JennyNeural')])
        from PIL import ImageDraw
        original = ImageDraw.ImageDraw.text
        for scene in scenes:
            with patch.object(ImageDraw.ImageDraw, 'text', autospec=True, side_effect=original) as draw:
                render_scene(rows[0], scene, 1, 10, title, settings)
                displayed = [c.args[2] for c in draw.call_args_list]
                self.assertEqual(rows[0]['ipa'] in displayed, scene.phase in ('answer', 'explanation'))
        # Missing IPA never creates a placeholder or changes speech.
        rows[0].pop('ipa')
        render_scene(rows[0], answer, 1, 10, title, settings)
        face = ipa_font(48)
        missing = face.getmask('\u0378')
        for char in 'ɑɒæəɚɜɛɪʊʌɔθðŋʃʒɹɾʔˈˌː':
            glyph = face.getmask(char)
            self.assertNotEqual((glyph.size, bytes(glyph)), (missing.size, bytes(missing)), char)

    def test_mask_and_timeline(self):
        self.assertEqual(masked_word(' activity '), 'A _ _ _ _ _ _ _')
        self.assertEqual(masked_word('book'), 'B _ _ _')
        doc = sample_document('guess_word')
        title, rows, mode = normalize(doc, parse_legacy_questions)
        self.assertEqual((len(rows), mode), (10, 'guess_word'))
        scenes = plan_item(rows[0], Settings(countdown=9))
        reveal = next(i for i, s in enumerate(scenes) if s.phase == 'answer')
        self.assertEqual([s.countdown for s in scenes[1:reveal]], [5, 4, 3, 2, 1])
        self.assertEqual(sum(estimated_seconds(s) for s in scenes[1:reveal]), 5)
        for s in scenes[:reveal]:
            self.assertNotIn('activity', (s.text + s.narration + s.detail).lower())
        self.assertEqual(scenes[reveal].narration, '')
        row = dict(rows[0], answer='abcdefghijklmnopqrst', ipa='', example='')
        for s in plan_item(row, Settings()):
            render_scene(row, s, 1, 10, title, Settings(width=180, height=320))

    def test_validation_and_import(self):
        doc = sample_document('guess_word')
        for invalid in ('two words', 'a', 'a-b', '[en]book[/en]', 'a'*21):
            bad = copy.deepcopy(doc)
            bad['items'][2]['answer'] = invalid
            with self.assertRaisesRegex(ValueError, 'Câu 3'):
                normalize(bad, parse_legacy_questions)
        doc['items'][0]['thinking_seconds'] = 3
        doc['settings']['thinking_seconds'] = 7
        _, rows, _ = normalize(doc, parse_legacy_questions)
        self.assertEqual(len([s for s in plan_item(rows[0], Settings()) if s.countdown]), 3)
        self.assertEqual(len([s for s in plan_item(rows[1], Settings()) if s.countdown]), 7)
        doc['type'] = doc.pop('mode')
        self.assertEqual(normalize(doc, parse_legacy_questions)[2], 'guess_word')
        self.assertTrue(document_warnings('9 CÂU TIẾNG ANH', rows))
