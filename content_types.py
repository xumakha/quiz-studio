"""Versioned content registry, validation and legacy normalization (no UI dependencies)."""
import copy
import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ContentType:
    label: str
    required: tuple
    sample: dict
    lesson: bool = False


def en(text):
    return f"[en]{text}[/en]"


REGISTRY = {
    "multiple_choice": ContentType("Trắc nghiệm ABCD", ("question",), dict(question=en("She ... a student."), options=list(map(en, ["am", "is", "are", "be"])), answer="B", explanation="Chủ ngữ She dùng is.")),
    "error_correction": ContentType("Tìm lỗi sai", ("question", "answer", "explanation"), dict(question=en("She don't like coffee."), answer=en("She doesn't like coffee."), highlight=dict(wrong="don't", correct="doesn't"), explanation="Chủ ngữ She dùng doesn't.")),
    "fill_blank": ContentType("Điền từ", ("question", "answer", "explanation"), dict(question=en("She ___ a student."), answer=en("is"), explanation="Chủ ngữ She dùng is.")),
    "word_order": ContentType("Sắp xếp từ", ("explanation",), dict(tokens=[dict(id="t1", text=en("usually")), dict(id="t2", text=en("I")), dict(id="t3", text=en("get up"))], answer_order=["t2", "t1", "t3"], explanation="Trạng từ đứng trước động từ thường.")),
    "translation": ContentType("Dịch nhanh", ("source_text", "source_language", "target_language", "explanation"), dict(source_text="Tôi thích đọc sách.", source_language="vi", target_language="en", suggested_answers=[en("I like reading books.")], explanation="Có thể dùng like reading hoặc like to read.", show_alternatives=False)),
    "listening": ContentType("Nghe đoán câu", ("audio_text", "transcript", "translation", "explanation"), dict(audio_text=en("How are you today?"), transcript=en("How are you today?"), translation="Hôm nay bạn thế nào?", replay_count=1, explanation="Câu hỏi thăm sức khỏe.")),
    "dialogue": ContentType("Hoàn thành hội thoại", ("explanation",), dict(dialogue=[dict(speaker="A", text=en("How are you?")), dict(speaker="B", text="___")], missing_turn_index=1, suggested_answers=[en("I'm fine, thanks.")], explanation="Một cách trả lời lời hỏi thăm.")),
    "true_false": ContentType("Đúng / Sai", ("statement", "explanation"), dict(statement=en("She are a student."), answer=False, correction=en("She is a student."), explanation="She dùng is.")),
    "multiple_meanings": ContentType("Một từ, nhiều nghĩa", ("word",), dict(word=en("book"), senses=[dict(phrase=en("a book"), meaning="một cuốn sách", example=en("This is a book.")), dict(phrase=en("book a room"), meaning="đặt phòng", example=en("I'd like to book a room."))]), True),
    "sentence_upgrade": ContentType("Nâng cấp câu nói", ("original", "alternative", "nuance"), dict(original=en("I'm tired."), alternative=en("I'm exhausted."), nuance="Exhausted thể hiện mức độ mệt rất cao, tùy ngữ cảnh."), True),
    "phrase_lesson": ContentType("Học theo cụm", ("phrase", "meaning", "example"), dict(phrase=en("take a break"), meaning="nghỉ giải lao", example=en("Let's take a break."), example_translation="Chúng ta nghỉ giải lao nhé."), True),
}
LABELS = {key: spec.label for key, spec in REGISTRY.items()} | {"mixed": "Tổng hợp nhiều dạng"}
DEFAULT_MODE = "multiple_choice"  # Deliberately never persisted as a user preference.


def sample_document(mode):
    types = list(REGISTRY) if mode == "mixed" else [mode]
    return dict(schema_version=2, title="MỘT CHÚT ENGLISH", mode=mode, settings=dict(thinking_seconds=5),
                items=[dict(id=f"{key}-01", type=key, subject=REGISTRY[key].label.upper(), **copy.deepcopy(REGISTRY[key].sample)) for key in types])


def plain(value):
    return re.sub(r"\[/?en\]", "", value, flags=re.I)


def check_tags(value, path):
    if isinstance(value, str):
        opened = False
        for tag in re.findall(r"\[/?en\]", value, re.I):
            if (tag.lower() == "[en]") == opened:
                raise ValueError(f"{path}: thẻ [en] chưa được đóng hoặc lồng sai.")
            opened = not opened
        if opened:
            raise ValueError(f"{path}: thẻ [en] chưa được đóng.")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            check_tags(child, f"{path}[{i}]")
    elif isinstance(value, dict):
        for key, child in value.items():
            check_tags(child, f"{path}.{key}")


def seconds(value, path):
    if type(value) is not int or not 0 <= value <= 30:
        raise ValueError(f"{path}: phải là số nguyên từ 0 đến 30.")


def validate_item(row, index):
    prefix = f"Câu {index}"
    def require(ok, message):
        if not ok:
            raise ValueError(f"{prefix}: {message}")
    def text(obj, field):
        require(isinstance(obj.get(field), str) and bool(obj[field].strip()), f"thiếu {field} hoặc không phải chuỗi.")
    require(isinstance(row, dict), "phải là object.")
    kind = row.get("type")
    require(isinstance(kind, str) and kind in REGISTRY, "type không được hỗ trợ.")
    spec = REGISTRY[kind]
    for field in spec.required:
        text(row, field)
    for field in ("explanation", "prompt", "subject", "completed_sentence", "correction", "example_context", "example_translation", "id"):
        if field in row:
            require(isinstance(row[field], str), f"{field} phải là chuỗi.")
    if "thinking_seconds" in row:
        seconds(row["thinking_seconds"], prefix + ".thinking_seconds")
    if kind == "multiple_choice":
        opts = row.get("options")
        require(isinstance(opts, list) and len(opts) == 4 and all(isinstance(x, str) and x.strip() for x in opts), "options phải có đúng 4 chuỗi không rỗng.")
        require(isinstance(row.get("answer"), str) and row["answer"] in list("ABCD"), "answer phải là A, B, C hoặc D.")
        row["answer_index"] = "ABCD".index(row["answer"])
        row.setdefault("explanation", "")
    elif kind == "error_correction":
        h = row.get("highlight")
        require(isinstance(h, dict), "thiếu highlight.")
        text(h, "wrong"); text(h, "correct")
        source = plain(row["question"])
        starts = [m.start() for m in re.finditer(re.escape(h["wrong"]), source)]
        occurrence = h.get("occurrence", 1)
        require(type(occurrence) is int and 1 <= occurrence <= len(starts), "highlight.occurrence không tồn tại (bắt đầu từ 1).")
        start = h.get("start", starts[occurrence - 1])
        require(type(start) is int and start in starts, "highlight.start không khớp vị trí wrong trong câu đã bỏ thẻ.")
        require(source[:start] + h["correct"] + source[start + len(h["wrong"]):] == plain(row["answer"]), "answer không khớp phép sửa highlight tại vị trí đã chọn.")
    elif kind == "fill_blank":
        require(plain(row["question"]).count("___") == 1, "question phải có đúng một chỗ trống ___.")
        if row.get("completed_sentence"):
            require(plain(row["completed_sentence"]) == plain(row["question"]).replace("___", plain(row["answer"]), 1), "completed_sentence không khớp câu sau khi điền answer.")
    elif kind == "word_order":
        tokens = row.get("tokens")
        require(isinstance(tokens, list) and bool(tokens), "tokens phải là mảng không rỗng.")
        for token in tokens:
            require(isinstance(token, dict), "token phải là object.")
            text(token, "id"); text(token, "text")
        ids = [t["id"] for t in tokens]
        require(len(ids) == len(set(ids)), "tokens có id trùng.")
        order = row.get("answer_order")
        require(isinstance(order, list) and all(isinstance(x, str) for x in order) and len(order) == len(ids) and set(order) == set(ids), "answer_order chứa token không tồn tại, trùng hoặc thiếu token.")
    elif kind in ("translation", "dialogue"):
        answers = row.get("suggested_answers")
        require(isinstance(answers, list) and bool(answers) and all(isinstance(x, str) and x.strip() for x in answers), "suggested_answers phải là mảng chuỗi không rỗng.")
        if "show_alternatives" in row:
            require(type(row["show_alternatives"]) is bool, "show_alternatives phải là boolean.")
        if kind == "translation":
            require(row["source_language"] in ("en", "vi") and row["target_language"] in ("en", "vi"), "source_language/target_language phải là en hoặc vi.")
        else:
            turns = row.get("dialogue")
            require(isinstance(turns, list) and len(turns) >= 2, "dialogue cần ít nhất hai lượt.")
            for turn in turns:
                require(isinstance(turn, dict), "lượt thoại phải là object.")
                text(turn, "speaker"); text(turn, "text")
            missing = row.get("missing_turn_index")
            require(type(missing) is int and 0 <= missing < len(turns), "missing_turn_index nằm ngoài dialogue (bắt đầu từ 0).")
    elif kind == "listening":
        require(type(row.get("replay_count", 1)) is int and 1 <= row.get("replay_count", 1) <= 5, "replay_count phải từ 1 đến 5.")
    elif kind == "true_false":
        require(type(row.get("answer")) is bool, "answer phải là boolean.")
    elif kind == "multiple_meanings":
        senses = row.get("senses")
        require(isinstance(senses, list) and bool(senses), "senses phải là mảng không rỗng.")
        for sense in senses:
            require(isinstance(sense, dict), "sense phải là object.")
            for field in ("phrase", "meaning", "example"):
                text(sense, field)
    check_tags(row, prefix)
    return row


def normalize(data, legacy_parser):
    if not isinstance(data, dict) or "items" not in data:
        title, rows = legacy_parser(json.dumps(data, ensure_ascii=False))
        for i, row in enumerate(rows, 1):
            check_tags(row, f"Câu {i}")
            row.update(type="multiple_choice", answer=chr(65 + row["answer_index"]), _legacy=True)
        return title, rows, DEFAULT_MODE
    if data.get("schema_version") != 2:
        raise ValueError("schema_version phải là 2.")
    rows = data["items"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("items phải là mảng không rỗng.")
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("settings phải là object.")
    if "thinking_seconds" in settings:
        seconds(settings["thinking_seconds"], "settings.thinking_seconds")
    rows = [validate_item(copy.deepcopy(row), i) for i, row in enumerate(rows, 1)]
    types = {row["type"] for row in rows}
    mode = data.get("mode", next(iter(types)) if len(types) == 1 else "mixed")
    if not isinstance(mode, str) or mode not in LABELS or (mode != "mixed" and types != {mode}):
        raise ValueError("mode phải khớp type của tất cả item hoặc là mixed.")
    ids = [row["id"] for row in rows if "id" in row]
    if len(ids) != len(set(ids)):
        raise ValueError("items có id trùng.")
    for row in rows:
        if "thinking_seconds" not in row and "thinking_seconds" in settings:
            row["_default_thinking_seconds"] = settings["thinking_seconds"]
    return str(data.get("title", "MỘT CHÚT ENGLISH")), rows, mode


def export_document(title, rows, mode):
    items = [{k: v for k, v in row.items() if not k.startswith("_") and k != "answer_index"} for row in rows]
    # Keep historical 2-6-option files in their original compatible schema.
    if any(row.get("_legacy") and len(row["options"]) != 4 for row in rows):
        return dict(title=title, questions=[{k: v for k, v in row.items() if k != "type"} for row in items])
    settings = next((dict(thinking_seconds=row["_default_thinking_seconds"]) for row in rows if "_default_thinking_seconds" in row), {})
    return dict(schema_version=2, title=title, mode=mode, settings=settings, items=items)
