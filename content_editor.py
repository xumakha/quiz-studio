"""Content selector and structured item editing using the JSON text as source of truth."""
import copy
import json
import tkinter as tk
from uuid import uuid4
import customtkinter as ctk
from ui_components import BG, INK, MUTED, ACCENT, LINE, box, label, button, dropdown, entry
from content_types import DEFAULT_MODE, LABELS, REGISTRY, sample_document, normalize, export_document


class ContentEditor:
    def __init__(self, app, parent):
        self.app = app
        self.mode = DEFAULT_MODE
        self.drafts = {}
        self.variable = tk.StringVar(value=LABELS[DEFAULT_MODE])
        area = box(parent, BG, corner_radius=8, border_width=1, border_color=LINE)
        area.pack(fill="x", padx=18, pady=(16, 4))
        choice_row = box(area)
        choice_row.pack(fill="x", padx=12, pady=12)
        label(choice_row, "DẠNG VIDEO", 10, MUTED, True, width=90).pack(side="left", padx=(0, 8))
        dropdown(choice_row, self.variable, list(LABELS.values()), command=self.switch).pack(side="left", fill="x", expand=True)
        self.guide = label(area, "Mỗi dạng có một bản nháp riêng. Dùng [en] cho đoạn tiếng Anh.", 11, MUTED, wraplength=360, justify="left")
        self.guide.pack(fill="x", padx=12, pady=(0, 10))
        area.bind("<Configure>", lambda event: self.guide.configure(wraplength=max(180, event.width-28)))
        def fit_summary(event):
            if event.widget is app:
                if event.height < 820:
                    self.guide.pack_forget()
                elif not self.guide.winfo_manager():
                    self.guide.pack(fill="x", padx=12, pady=(0, 10))
        app.bind("<Configure>", fit_summary, add="+")
        actions = box(parent)
        actions.pack(fill="x", padx=18, pady=(10, 0))
        actions.columnconfigure((0, 1), weight=1)
        button(actions, "Dùng dữ liệu mẫu", self.sample, symbol="file-json", width=140).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        button(actions, "Chỉnh qua form", self.form, primary=True, symbol="edit", width=140).grid(row=0, column=1, sticky="ew", padx=(4, 8))
        button(actions, "", app.open_json, symbol="folder", width=36).grid(row=0, column=2, padx=(0, 6))
        button(actions, "", app.save_json, symbol="save", width=36).grid(row=0, column=3)
        tools = box(parent)
        tools.pack(fill="x", padx=18, pady=(8, 8))
        button(tools, "Thêm", self.add, symbol="plus", width=70, height=32).pack(side="left")
        button(tools, "Nhân bản", self.duplicate, symbol="copy", width=96, height=32).pack(side="left", padx=6)
        button(tools, "Xóa", self.delete, symbol="trash", width=60, height=32).pack(side="left")
        button(tools, "", lambda: self.move(1), symbol="down", width=32, height=32).pack(side="right")
        button(tools, "", lambda: self.move(-1), symbol="up", width=32, height=32).pack(side="right", padx=6)

    def source(self):
        return self.app.text.get("1.0", "end-1c")

    def write(self, source):
        self.app.stop_preview()
        self.app.text.delete("1.0", "end")
        self.app.text.insert("1.0", source)
        self.app.rows = []
        self.app.selected.set(1)
        if source.strip():
            self.app.validate()
        else:
            self.app.preview.configure(image="")
            self.app.question_list.delete(*self.app.question_list.get_children())
            self.app.question_count.configure(text="0 item")
            self.app.validation.configure(text="Bản nháp trống. Nhập JSON, thêm item hoặc dùng dữ liệu mẫu.")

    def switch(self, event=None):
        self.drafts[self.mode] = self.source()
        self.mode = next(k for k, label in LABELS.items() if label == self.variable.get())
        self.guide.configure(text="Bản nháp riêng cho từng dạng. Dùng [en] cho đoạn tiếng Anh.")
        if self.mode in self.drafts:
            self.write(self.drafts[self.mode])
        else:
            self.sample()

    def detect(self, mode):
        if mode != self.mode:
            self.mode = mode
            self.variable.set(LABELS[mode])
        self.guide.configure(text="Chỉnh qua form hoặc JSON. Dùng [en] cho đoạn tiếng Anh.")

    def sample(self):
        self.write(json.dumps(sample_document(self.mode), ensure_ascii=False, indent=2))

    def document(self):
        data = json.loads(self.source())
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data  # Editing incomplete drafts must remain possible.
        from engine import parse_legacy_questions
        title, rows, mode = normalize(data, parse_legacy_questions)
        return export_document(title, rows, mode)

    def change(self, operation):
        try:
            doc = self.document()
            key = "items" if "items" in doc else "questions"
            index = min(max(0, self.app.selected.get()-1), len(doc[key])-1)
            operation(doc[key], index)
            self.write(json.dumps(doc, ensure_ascii=False, indent=2))
        except Exception as error:
            self.app.validation.configure(text=str(error), foreground="#ba4247")

    def add(self):
        if not self.source().strip():
            self.write(json.dumps(dict(schema_version=2, title="MỘT CHÚT ENGLISH", mode=self.mode, items=[]), ensure_ascii=False))
        def append(kind):
            try:
                doc = json.loads(self.source())
                if "items" not in doc:
                    doc = self.document()
                key = "items" if "items" in doc else "questions"
                item = copy.deepcopy(REGISTRY[kind].sample)
                # Add creates an empty form, not invented teaching content/answers.
                for field, value in item.items():
                    if isinstance(value, str):
                        item[field] = ""
                for field in ("options", "suggested_answers"):
                    if field in item:
                        item[field] = [""] * (4 if field == "options" else 1)
                if "highlight" in item:
                    item["highlight"] = dict(wrong="", correct="")
                if "tokens" in item:
                    for token in item["tokens"]:
                        token["text"] = ""
                    item["answer_order"] = []
                if "dialogue" in item:
                    for turn in item["dialogue"]:
                        turn["text"] = ""
                if "senses" in item:
                    item["senses"] = [dict(phrase="", meaning="", example="")]
                item.update(id=uuid4().hex, type=kind)
                doc[key].append(item)
                self.write(json.dumps(doc, ensure_ascii=False, indent=2))
                self.app.selected.set(len(doc[key]))
                self.form()
            except Exception as error:
                self.app.validation.configure(text=str(error), foreground="#ba4247")
        if self.mode != "mixed":
            append(self.mode)
        else:
            window = ctk.CTkToplevel(self.app)
            window.title("Thêm nội dung")
            window.geometry("420x240")
            window.configure(fg_color=BG)
            window.transient(self.app)
            label(window, "Thêm nội dung", 20, bold=True).pack(anchor="w", padx=24, pady=(24, 4))
            label(window, "Chọn dạng cho nội dung mới trong video tổng hợp.", 12, MUTED).pack(anchor="w", padx=24, pady=(0, 16))
            choice = tk.StringVar(value=LABELS[DEFAULT_MODE])
            dropdown(window, choice, [s.label for s in REGISTRY.values()]).pack(fill="x", padx=24)
            def confirm():
                append(next(k for k, s in REGISTRY.items() if s.label == choice.get()))
                window.destroy()
            button(window, "Thêm nội dung", confirm, primary=True, symbol="plus").pack(anchor="e", padx=24, pady=20)

    def duplicate(self):
        def operation(items, index):
            item = copy.deepcopy(items[index]); item["id"] = uuid4().hex
            items.insert(index+1, item)
        self.change(operation)

    def delete(self):
        self.change(lambda items, index: items.pop(index))

    def move(self, direction):
        def operation(items, index):
            other = max(0, min(len(items)-1, index+direction))
            items[index], items[other] = items[other], items[index]
        self.change(operation)

    def form(self):
        try:
            doc = self.document()
            key = "items" if "items" in doc else "questions"
            index = min(max(0, self.app.selected.get()-1), len(doc[key])-1)
            item = doc[key][index]
        except Exception as error:
            self.app.validation.configure(text=str(error), foreground="#ba4247")
            return
        original = self.source()
        window = ctk.CTkToplevel(self.app)
        kind = item.get("type", DEFAULT_MODE)
        window.title(f"Chỉnh nội dung {index+1} - {LABELS[kind]}")
        window.geometry("760x780")
        window.minsize(560, 540)
        window.configure(fg_color=BG)
        window.transient(self.app)
        heading = box(window, "white", corner_radius=0)
        heading.pack(fill="x")
        label(heading, f"Chỉnh nội dung {index+1}", 21, bold=True).pack(anchor="w", padx=24, pady=(20, 3))
        label(heading, LABELS[kind], 12, ACCENT).pack(anchor="w", padx=24, pady=(0, 18))
        footer = box(window, "white", corner_radius=0)
        footer.pack(side="bottom", fill="x")
        message = label(footer, "", 11, "#ba4247", wraplength=650, justify="left")
        message.pack(fill="x", padx=24, pady=(8, 0))
        footer_actions = box(footer)
        footer_actions.pack(fill="x", padx=24, pady=(8, 16))
        button(footer_actions, "Đóng", window.destroy, width=90).pack(side="left")
        body = ctk.CTkScrollableFrame(window, fg_color=BG, corner_radius=0,
                                      scrollbar_button_color="#dbe3e7", scrollbar_button_hover_color="#b8ccc8")
        body.pack(fill="both", expand=True, padx=14, pady=12)
        fields = {}
        label(body, "THÔNG TIN VIDEO", 10, MUTED, True).pack(anchor="w", padx=10, pady=(4, 8))
        general = box(body, "white", corner_radius=8, border_width=1, border_color=LINE)
        general.pack(fill="x", padx=10, pady=(0, 18))
        title = tk.StringVar(value=doc.get("title", ""))
        label(general, "Tiêu đề video", 12, bold=True).pack(anchor="w", padx=14, pady=(14, 6))
        entry(general, title).pack(fill="x", padx=14)
        global_seconds = tk.StringVar(value=str(doc.get("settings", {}).get("thinking_seconds", self.app.countdown.get())))
        timing = box(general)
        timing.pack(fill="x", padx=14, pady=14)
        label(timing, "Thời gian suy nghĩ chung", 12).pack(side="left")
        label(timing, "giây · 0-30", 11, MUTED).pack(side="right")
        entry(timing, global_seconds, width=72, justify="center").pack(side="right", padx=10)
        label(body, "NỘI DUNG", 10, MUTED, True).pack(anchor="w", padx=10, pady=(0, 3))
        label(body, "Giữ xuống dòng và thẻ [en]. Các ô danh sách dùng định dạng JSON.", 11, MUTED, wraplength=470, justify="left").pack(anchor="w", padx=10, pady=(0, 12))
        expanded = dict(item)
        for field in ("prompt", "explanation", "thinking_seconds"):
            expanded.setdefault(field, "")
        optional = {"guess_word": ("meaning_vi", "level", "part_of_speech", "context_hint", "ipa", "example", "example_translation"), "fill_blank": ("completed_sentence",), "translation": ("show_alternatives",), "listening": ("replay_count",), "true_false": ("correction",), "sentence_upgrade": ("example_context",), "phrase_lesson": ("example_translation",)}
        for field in optional.get(kind, ()):
            expanded.setdefault(field, False if field == "show_alternatives" else 1 if field == "replay_count" else "")
        field_labels = {
            "meaning_vi": "Nghĩa tiếng Việt", "level": "Trình độ", "part_of_speech": "Loại từ", "context_hint": "Gợi ý ngữ cảnh", "ipa": "IPA", "id": "Mã nội dung", "subject": "Chủ đề", "prompt": "Hướng dẫn", "question": "Câu hỏi",
            "options": "Các lựa chọn", "answer": "Đáp án", "explanation": "Giải thích",
            "thinking_seconds": "Thời gian suy nghĩ riêng (giây)", "highlight": "Phần cần sửa",
            "completed_sentence": "Câu hoàn chỉnh", "tokens": "Các thẻ từ", "answer_order": "Thứ tự đáp án",
            "source_text": "Câu cần dịch", "source_language": "Ngôn ngữ nguồn", "target_language": "Ngôn ngữ đích",
            "suggested_answers": "Các câu trả lời gợi ý", "show_alternatives": "Hiện các cách dịch khác",
            "audio_text": "Nội dung giọng đọc", "transcript": "Câu được bật mí", "translation": "Bản dịch",
            "replay_count": "Số lượt nghe", "dialogue": "Các lượt hội thoại", "missing_turn_index": "Vị trí lượt cần điền (từ 0)",
            "statement": "Nhận định", "correction": "Nội dung sửa đúng", "word": "Từ vựng", "senses": "Các nghĩa của từ",
            "original": "Câu ban đầu", "alternative": "Cách nói thay thế", "nuance": "Sắc thái",
            "example_context": "Ngữ cảnh ví dụ", "phrase": "Cụm từ", "meaning": "Nghĩa",
            "example": "Câu ví dụ", "example_translation": "Dịch câu ví dụ",
        }
        for field, value in expanded.items():
            if field in ("answer_index", "type"):
                continue
            card = box(body, "white", corner_radius=8, border_width=1, border_color=LINE)
            card.pack(fill="x", padx=10, pady=(0, 10))
            caption = box(card)
            caption.pack(fill="x", padx=14, pady=(12, 6))
            label(caption, field_labels.get(field, field), 12, bold=True).pack(side="left")
            if isinstance(value, (list, dict)):
                label(caption, "JSON", 10, MUTED, fg_color=BG, corner_radius=4, width=42).pack(side="right")
            editor = ctk.CTkTextbox(card, height=120 if isinstance(value, (list, dict)) else 64, wrap="word", undo=True,
                                    fg_color=BG, text_color=INK, border_color=LINE, border_width=1, corner_radius=6,
                                    font=("Consolas", 12) if isinstance(value, (list, dict)) else ("Segoe UI", 13),
                                    scrollbar_button_color="#dbe3e7", scrollbar_button_hover_color="#b8ccc8")
            structured = isinstance(value, (list, dict, bool, int)) or field == "thinking_seconds"
            editor.insert("1.0", json.dumps(value, ensure_ascii=False, indent=2) if structured and value != "" else value)
            editor.pack(fill="x", padx=14, pady=(0, 12))
            fields[field] = (editor, structured)
        def apply():
            try:
                if self.source() != original:
                    raise ValueError("JSON đã thay đổi. Đóng form và mở lại để tránh ghi đè bản mới.")
                edited = {"type": kind}
                for field, (editor, structured) in fields.items():
                    value = editor.get("1.0", "end-1c")
                    if not value and (field not in item or field == "thinking_seconds"):
                        continue
                    edited[field] = json.loads(value) if structured else value
                doc[key][index] = edited
                doc["title"] = title.get()
                if key == "items":
                    doc["settings"] = dict(thinking_seconds=int(global_seconds.get()))
                from engine import parse_legacy_questions
                normalize(doc, parse_legacy_questions)
                self.write(json.dumps(doc, ensure_ascii=False, indent=2))
                self.app.selected.set(index+1); self.app.show_preview()
                window.destroy()
            except Exception as error:
                message.configure(text=str(error))
        button(footer_actions, "Áp dụng và xem trước", apply, primary=True, symbol="check", width=190).pack(side="right")
