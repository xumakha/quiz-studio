"""OpenAI Responses API generation and durable local conversations."""
import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

import requests

from content_types import REGISTRY, sample_document
from engine import Cancelled, parse_questions

API_ROOT = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4.1-mini"


class ConversationStore:
    def __init__(self, directory):
        self.path = Path(directory) / "openai_conversations.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, name TEXT NOT NULL, instructions TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS turns (id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, prompt TEXT NOT NULL, source TEXT NOT NULL, model TEXT NOT NULL)")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def list(self):
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute("SELECT * FROM conversations ORDER BY rowid")]

    def get(self, conversation_id):
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            if row is None:
                raise ValueError("Hãy tạo hoặc chọn một hội thoại trong Kết nối OpenAI.")
            return dict(row)

    def create(self, name, instructions=""):
        name = name.strip()
        if not name or len(name) > 100:
            raise ValueError("Tên hội thoại cần có từ 1 đến 100 ký tự.")
        record = dict(id=uuid.uuid4().hex, name=name, instructions=instructions.strip())
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO conversations VALUES (:id, :name, :instructions)", record)
        return record

    def turns(self, conversation_id):
        self.get(conversation_id)
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute("SELECT * FROM turns WHERE conversation_id = ? ORDER BY id", (conversation_id,))]

    def append(self, conversation_id, prompt, source, model):
        self.get(conversation_id)
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO turns (conversation_id, prompt, source, model) VALUES (?, ?, ?, ?)",
                       (conversation_id, prompt, source, model))


def output_schema(mode):
    """Build the strict subset supported by Structured Outputs from registry samples."""
    def schema(value):
        if isinstance(value, dict):
            properties = {key: schema(item) for key, item in value.items()}
            return dict(type="object", properties=properties, required=list(properties), additionalProperties=False)
        if isinstance(value, list):
            return dict(type="array", items=schema(value[0]))
        if isinstance(value, bool):
            return {"type": "boolean"}
        if isinstance(value, int):
            return {"type": "integer"}
        return {"type": "string"}

    document = sample_document(mode)
    document["caption"] = ""
    root = schema(document)
    root["properties"]["schema_version"] = {"type": "integer", "enum": [2]}
    root["properties"]["mode"] = {"type": "string", "enum": [mode]}
    variants = []
    for kind in (REGISTRY if mode == "mixed" else [mode]):
        item = schema(sample_document(kind)["items"][0])
        item["properties"]["type"] = {"type": "string", "enum": [kind]}
        if kind == "multiple_choice":
            item["properties"]["answer"] = {"type": "string", "enum": list("ABCD")}
        variants.append(item)
    root["properties"]["items"]["items"] = {"anyOf": variants} if mode == "mixed" else variants[0]
    return root


def _checked_response(response):
    if not response.ok:
        messages = {401: "API key không hợp lệ hoặc đã bị thu hồi.",
                    403: "API key chưa được cấp quyền dùng model này.",
                    404: "Không tìm thấy model. Hãy kiểm tra tên model và quyền truy cập.",
                    429: "API đã hết hạn mức hoặc đang giới hạn tốc độ. Kiểm tra billing/quota rồi thử lại."}
        raise ValueError(messages.get(response.status_code,
                         f"OpenAI API trả lỗi HTTP {response.status_code}. Hãy kiểm tra model hoặc thử lại sau."))
    try:
        return response.json()
    except ValueError:
        raise ValueError("OpenAI API trả về dữ liệu không đọc được.") from None


def check_connection(key, model):
    if not key.strip() or not model.strip():
        raise ValueError("Hãy nhập API key và tên model.")
    # A model lookup checks access without generating billed content.
    from urllib.parse import quote
    try:
        with requests.get(f"{API_ROOT}/models/{quote(model.strip(), safe='')}",
                          headers={"Authorization": f"Bearer {key.strip()}"}, timeout=(10, 30)) as response:
            _checked_response(response)
    except requests.RequestException:
        raise ValueError("Không kết nối được OpenAI API. Kiểm tra Internet rồi thử lại.") from None


def generate_video(store, conversation_id, key, model, prompt, mode, channel, cancel):
    if cancel.is_set():
        raise Cancelled("Đã hủy tạo nội dung.")
    if not key.strip() or not prompt.strip():
        raise ValueError("Hãy kết nối OpenAI và nhập yêu cầu tạo nội dung.")
    conversation = store.get(conversation_id)
    history = []
    for turn in store.turns(conversation_id):
        history.extend([dict(role="user", content=turn["prompt"]), dict(role="assistant", content=turn["source"])])
    instructions = (
        "You create accurate, concise educational videos for Quiz Studio. Return only the requested JSON document. "
        "Follow the selected schema and mode, even if an earlier turn used another mode. Include a suitable title and posting caption. "
        "Keep text short enough for a vertical video. Use [en]...[/en] for English inside Vietnamese explanations. "
        "Each item id must be unique. multiple_choice must have exactly four options and answer A/B/C/D. "
        "fill_blank must contain exactly one ___. error_correction: replace highlight.wrong exactly once with highlight.correct "
        "to get answer (ignoring [en] tags). word_order: unique token ids, answer_order contains each id once. "
        "dialogue: at least two turns, missing_turn_index is zero-based. translation language codes must be vi or en. "
        "guess_word.answer must be one English word, 2-20 ASCII letters; meaning_vi/context_hint/subject must not reveal that word. "
        "Use the user's requested language and topic; English-only channels should have English content. "
        f"Current channel: {channel}. Current mode: {mode}.\n"
        + conversation["instructions"] + "\nExample structure (replace with original content):\n"
        + json.dumps(sample_document(mode), ensure_ascii=False)
    )
    payload = dict(model=model.strip(), store=False, instructions=instructions,
                   input=history + [dict(role="user", content=prompt.strip())],
                   text={"format": dict(type="json_schema", name="quiz_studio_video", strict=True, schema=output_schema(mode))},
                   max_output_tokens=12000)
    try:
        with requests.post(f"{API_ROOT}/responses", headers={"Authorization": f"Bearer {key.strip()}"},
                           json=payload, timeout=(10, 180)) as response:
            data = _checked_response(response)
    except requests.RequestException:
        raise ValueError("Không nhận được phản hồi từ OpenAI. Kiểm tra Internet; yêu cầu có thể đã được xử lý. App không tự gửi lại.") from None
    if cancel.is_set():
        raise Cancelled("Đã hủy nhận nội dung. Yêu cầu đã gửi tới API có thể vẫn được tính phí.")
    if data.get("status") != "completed":
        raise ValueError("OpenAI chưa trả nội dung hoàn chỉnh (có thể vượt giới hạn độ dài). Hãy yêu cầu ít câu hơn.")
    parts = []
    for output in data.get("output", []):
        for content in output.get("content", []):
            if content.get("type") == "refusal":
                raise ValueError("OpenAI từ chối yêu cầu này. Hãy điều chỉnh yêu cầu rồi thử lại.")
            if content.get("type") == "output_text":
                parts.append(content["text"])
    source = "".join(parts)
    try:
        document = json.loads(source)
        parse_questions(source)
        if document.get("mode") != mode:
            raise ValueError("Dạng video không khớp lựa chọn.")
    except (ValueError, TypeError, KeyError) as error:
        raise ValueError(f"JSON do AI tạo chưa hợp lệ: {error}. Nội dung hiện tại được giữ nguyên.") from None
    source = json.dumps(document, ensure_ascii=False, indent=2)
    if cancel.is_set():
        raise Cancelled("Đã hủy tạo nội dung.")
    store.append(conversation_id, prompt.strip(), source, model.strip())
    return source
