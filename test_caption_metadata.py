"""Posting captions survive content validation, conversion and item editing."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from content_editor import ContentEditor
from content_types import document_caption, export_document, normalize, sample_document
from engine import parse_legacy_questions, parse_questions


class CaptionMetadataTests(unittest.TestCase):
    caption = "  Học một chút mỗi ngày ✨\n\n#tienganh #quiz\n[en] là chữ trong caption.  \n"

    def documents(self):
        yield sample_document("guess_word")
        yield sample_document("mixed")
        for count in (2, 4, 6):
            yield dict(title="Quiz thử", questions=[dict(question="Chọn đáp án", options=list("ABCDEF"[:count]), answer="A")])

    def test_caption_roundtrip_is_lossless_for_v2_and_legacy(self):
        for document in self.documents():
            with self.subTest(schema=document.get("mode", "legacy"), options=document.get("questions")):
                document["caption"] = self.caption
                before = copy.deepcopy(document)
                title, rows, mode = normalize(document, parse_legacy_questions)
                saved = export_document(title, rows, mode, caption=document_caption(document))
                loaded = json.loads(json.dumps(saved, ensure_ascii=False))
                self.assertEqual(loaded["caption"], self.caption)
                loaded_title, loaded_rows, loaded_mode = normalize(loaded, parse_legacy_questions)
                self.assertEqual((loaded_title, loaded_mode), (title, mode))
                # Four-option legacy content becomes v2; its internal marker disappears.
                public_rows = lambda items: [{key: value for key, value in item.items() if key != "_legacy"} for item in items]
                self.assertEqual(public_rows(loaded_rows), public_rows(rows))
                self.assertEqual(document, before)
                self.assertTrue(all("caption" not in item for item in rows))

    def test_caption_is_optional_and_explicit_empty_string_is_saved(self):
        document = sample_document("multiple_choice")
        title, rows, mode = normalize(document, parse_legacy_questions)
        self.assertEqual(document_caption(document), "")
        self.assertEqual(document_caption([]), "")
        self.assertNotIn("caption", export_document(title, rows, mode))
        self.assertEqual(export_document(title, rows, mode, caption="")["caption"], "")

    def test_invalid_caption_rejected_by_public_parser_for_both_schemas(self):
        for document in self.documents():
            for invalid in (None, 17, False, [], {}):
                with self.subTest(schema=document.get("mode", "legacy"), caption=invalid):
                    document["caption"] = invalid
                    with self.assertRaisesRegex(ValueError, "caption phải là chuỗi"):
                        parse_questions(json.dumps(document, ensure_ascii=False))

    def test_export_rejects_non_string_caption(self):
        title, rows, mode = normalize(sample_document("multiple_choice"), parse_legacy_questions)
        with self.assertRaisesRegex(ValueError, "caption phải là chuỗi"):
            export_document(title, rows, mode, caption=["text"])

    def test_editor_item_actions_keep_caption_in_both_schemas(self):
        for document in self.documents():
            with self.subTest(schema=document.get("mode", "legacy"), options=document.get("questions")):
                document["caption"] = self.caption
                source = [json.dumps(document, ensure_ascii=False)]
                editor = ContentEditor.__new__(ContentEditor)
                editor.app = SimpleNamespace(selected=Mock(get=Mock(return_value=1)), validation=Mock())
                editor.source = lambda: source[0]
                editor.write = lambda value: source.__setitem__(0, value)
                original_count = len(document.get("items", document.get("questions", [])))
                editor.duplicate()
                editor.move(1)
                editor.delete()
                changed = json.loads(source[0])
                self.assertEqual(changed["caption"], self.caption)
                self.assertEqual(len(changed.get("items", changed.get("questions", []))), original_count)
                normalize(changed, parse_legacy_questions)
                editor.app.validation.configure.assert_not_called()

    def test_editor_keeps_missing_caption_absent_when_converting_legacy(self):
        document = dict(title="Quiz", questions=[dict(question="Chọn", options=list("ABCD"), answer="A")])
        editor = ContentEditor.__new__(ContentEditor)
        editor.source = lambda: json.dumps(document)
        self.assertNotIn("caption", editor.document())


if __name__ == "__main__":
    unittest.main()
