import copy
import unittest
from content_types import sample_document, normalize, masked_word, document_warnings
from content_timeline import plan_item, estimated_seconds
from content_renderer import render_scene
from engine import Settings, parse_legacy_questions


class GuessWordTests(unittest.TestCase):
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
        self.assertEqual(scenes[reveal].narration, '[en]activity[/en]')
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
