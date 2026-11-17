import json
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import requests

from content_types import REGISTRY, sample_document
from engine import Cancelled
from openai_video import ConversationStore, check_connection, generate_video, output_schema


def api_response(document=None, status=200, **overrides):
    data = dict(status="completed", output=[dict(type="message", content=[dict(type="output_text", text=json.dumps(document))])])
    data.update(overrides)
    response = Mock(ok=status < 400, status_code=status)
    response.json.return_value = data
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    return response


class OpenAIVideoTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = ConversationStore(self.directory.name)
        self.conversation = self.store.create("English", "Giải thích tiếng Việt, không lặp câu đã tạo.")
        self.cancel = threading.Event()

    def generate(self, mode="multiple_choice"):
        return generate_video(self.store, self.conversation["id"], "test-key", "gpt-4.1-mini", "Tạo 5 câu", mode, "English", self.cancel)

    def test_strict_schemas_cover_every_video_type(self):
        def walk(value):
            if isinstance(value, dict):
                if value.get("type") == "object":
                    self.assertFalse(value["additionalProperties"])
                    self.assertEqual(set(value["required"]), set(value["properties"]))
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        for mode in (*REGISTRY, "mixed"):
            with self.subTest(mode=mode):
                schema = output_schema(mode)
                walk(schema)
                self.assertEqual(schema["properties"]["mode"]["enum"], [mode])

    def test_generation_all_types_persists_and_replays_context_without_secrets(self):
        for mode in (*REGISTRY, "mixed"):
            document = sample_document(mode)
            document["caption"] = "Caption\n#English"
            with self.subTest(mode=mode), patch("openai_video.requests.post", return_value=api_response(document)) as post:
                source = self.generate(mode)
                self.assertEqual(json.loads(source), document)
                payload = post.call_args.kwargs["json"]
                self.assertFalse(payload["store"])
                self.assertEqual(payload["text"]["format"]["type"], "json_schema")
                self.assertIn("không lặp", payload["instructions"])
                self.assertEqual(post.call_args.args[0], "https://api.openai.com/v1/responses")
                self.assertNotIn("test-key", json.dumps(payload))
        reopened = ConversationStore(self.directory.name)
        turns = reopened.turns(self.conversation["id"])
        self.assertEqual(len(turns), len(REGISTRY) + 1)
        with patch("openai_video.requests.post", return_value=api_response(sample_document("listening"))) as post:
            self.generate("listening")
            history = post.call_args.kwargs["json"]["input"]
            self.assertEqual(len(history), len(turns) * 2 + 1)
            self.assertEqual(history[1]["content"], turns[0]["source"])
        self.assertNotIn(b"test-key", self.store.path.read_bytes())

    def test_errors_refusals_incomplete_and_cancel_do_not_commit_turns(self):
        invalid = {"title": "Broken", "questions": []}
        # Response HTTP status and response-body status are separate.
        incomplete = api_response()
        incomplete.json.return_value = {"status": "incomplete", "output": []}
        refused = api_response()
        refused.json.return_value = {"status": "completed", "output": [{"content": [{"type": "refusal"}]}]}
        cases = [api_response(status=401), api_response(status=429), api_response(invalid), incomplete, refused]
        for response in cases:
            with self.subTest(response=response), patch("openai_video.requests.post", return_value=response):
                with self.assertRaises(ValueError):
                    self.generate()
            self.assertEqual(self.store.turns(self.conversation["id"]), [])
        with patch("openai_video.requests.post", side_effect=requests.Timeout):
            with self.assertRaisesRegex(ValueError, "không tự gửi lại"):
                self.generate()
        self.cancel.set()
        with patch("openai_video.requests.post") as post, self.assertRaises(Cancelled):
            self.generate()
        post.assert_not_called()
        self.cancel.clear()

        def cancelled_request(*args, **kwargs):
            self.cancel.set()
            return api_response(sample_document("multiple_choice"))

        with patch("openai_video.requests.post", side_effect=cancelled_request), self.assertRaises(Cancelled):
            self.generate()
        self.assertEqual(self.store.turns(self.conversation["id"]), [])

    def test_connection_checks_access_without_generation(self):
        with patch("openai_video.requests.get", return_value=api_response()) as get:
            check_connection("test-key", "gpt-4.1-mini")
            self.assertEqual(get.call_args.args[0], "https://api.openai.com/v1/models/gpt-4.1-mini")
        with patch("openai_video.requests.get", return_value=api_response(status=401)):
            with self.assertRaisesRegex(ValueError, "API key"):
                check_connection("test-key", "gpt-4.1-mini")

    def test_conversations_are_independent(self):
        second = self.store.create("DMV")
        with patch("openai_video.requests.post", return_value=api_response(sample_document("multiple_choice"))):
            self.generate()
        self.assertEqual(self.store.turns(second["id"]), [])
        self.assertNotEqual(self.conversation["id"], second["id"])


if __name__ == "__main__":
    unittest.main()
