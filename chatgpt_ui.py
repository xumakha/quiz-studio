"""Configure an actual OpenAI API connection and local conversations."""
import json
import queue
import sqlite3
import threading
import tkinter as tk
import customtkinter as ctk

from openai_video import check_connection
from ui_components import BG, MUTED, box, label, button, entry, dropdown


def choose_conversation(app):
    existing = getattr(app, "chatgpt_window", None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        return existing
    window = ctk.CTkToplevel(app)
    app.chatgpt_window = window
    window.title("Kết nối OpenAI API")
    window.geometry("760x820")
    window.minsize(620, 620)
    window.configure(fg_color=BG)
    window.transient(app.winfo_toplevel())
    actions = box(window)
    actions.pack(side="bottom", fill="x", padx=24, pady=16)
    body = ctk.CTkScrollableFrame(window, fg_color=BG)
    body.pack(fill="both", expand=True, padx=14, pady=(14, 0))
    label(body, "Kết nối OpenAI để tự tạo nội dung", 21, bold=True).pack(anchor="w", padx=10)
    label(body, "Nhập yêu cầu → AI tạo nội dung → tự điền JSON và xem trước.", 12, MUTED).pack(anchor="w", padx=10, pady=(4, 14))
    key = tk.StringVar(master=window, value=app.host.openai_key)
    model = tk.StringVar(master=window, value=app.openai_model.get())
    label(body, "OpenAI API key", 12, bold=True).pack(anchor="w", padx=10)
    entry(body, key, show="•", placeholder_text="sk-...").pack(fill="x", padx=10, pady=(4, 6))
    label(body, "Key chỉ giữ trong phiên app, không ghi vào JSON hay lịch sử.\nĐặt OPENAI_API_KEY để tự nạp khi mở app. API dùng hạn mức tài khoản của bạn.",
          11, MUTED, justify="left", wraplength=630).pack(anchor="w", padx=10, pady=(0, 10))
    label(body, "Model hỗ trợ Structured Outputs", 12).pack(anchor="w", padx=10)
    entry(body, model).pack(fill="x", padx=10, pady=(4, 14))
    store = app.host.openai_store
    message, choice = tk.StringVar(master=window), tk.StringVar(master=window)
    label(body, f"Hội thoại cố định cho tab: {app.tab_name}", 13, bold=True).pack(anchor="w", padx=10)
    selector = dropdown(body, choice, ["Chưa có hội thoại"])
    selector.pack(fill="x", padx=10, pady=(6, 8))
    choices = {}
    transcript = ctk.CTkTextbox(body, height=135, fg_color="white", text_color="#25333d", wrap="word")
    transcript.pack(fill="x", padx=10, pady=(0, 8))

    def display(*args):
        selected = choices.get(choice.get())
        text = "Chưa có hội thoại. Bấm Kiểm tra & kết nối để tự tạo hội thoại cho tab này."
        if selected:
            turns = store.turns(selected["id"])
            text = "Hướng dẫn: " + (selected["instructions"] or "Chưa đặt hướng dẫn riêng.")
            text += f"\n\nĐã tạo {len(turns)} lượt nội dung."
            for turn in turns[-5:]:
                text += f"\n\nBạn: {turn['prompt']}\nAI: {json.loads(turn['source']).get('title', 'Video')}"
        transcript.configure(state="normal")
        transcript.delete("1.0", "end")
        transcript.insert("1.0", text)
        transcript.configure(state="disabled")

    def refresh(selected=None):
        choices.clear()
        choices.update({f"{index + 1}. {item['name']}": item for index, item in enumerate(store.list())})
        empty_choice = "Tự tạo hội thoại khi kết nối"
        selector.configure(values=list(choices) or [empty_choice])
        choice.set(next((name for name, item in choices.items() if item["id"] == selected), next(iter(choices), empty_choice)))

    choice.trace_add("write", display)
    refresh(app.openai_conversation_id.get())
    label(body, "Hội thoại mới (tự tạo nếu chưa có)", 13, bold=True).pack(anchor="w", padx=10, pady=(12, 5))
    name = tk.StringVar(master=window, value=app.tab_name)
    entry(body, name, placeholder_text="Tên hội thoại").pack(fill="x", padx=10, pady=(0, 8))
    label(body, "Hướng dẫn dùng cho mọi lượt tạo trong hội thoại này", 11).pack(anchor="w", padx=10)
    instructions = ctk.CTkTextbox(body, height=75, fg_color="white", text_color="#25333d", wrap="word")
    instructions.pack(fill="x", padx=10, pady=(4, 8))

    def create():
        try:
            record = store.create(name.get(), instructions.get("1.0", "end-1c"))
            refresh(record["id"])
            message.set("Đã tạo hội thoại. Bấm Kiểm tra & kết nối để dùng cho tab này.")
        except (OSError, ValueError, sqlite3.Error) as error:
            message.set(str(error))

    button(body, "Tạo hội thoại", create, symbol="plus").pack(anchor="w", padx=10, pady=(0, 10))

    def latest():
        selected = choices.get(choice.get())
        turns = store.turns(selected["id"]) if selected else []
        if not turns or app.busy:
            message.set("Chưa có JSON đã tạo, hoặc tab đang có tác vụ. Hãy thử lại sau.")
            return
        app.apply_generated_json(turns[-1]["source"])
        window.destroy()

    button(body, "Nạp JSON gần nhất", latest, symbol="file-json").pack(anchor="w", padx=10)
    label(body, "Hội thoại lưu riêng trong app, không dùng link hay lịch sử tại chatgpt.com.",
          11, MUTED, wraplength=630).pack(anchor="w", padx=10, pady=10)
    ctk.CTkLabel(actions, textvariable=message, text_color="#a46716", wraplength=650, justify="left", anchor="w").pack(fill="x", pady=(0, 10))
    buttons = box(actions)
    buttons.pack(fill="x")
    button(buttons, "Đóng", window.destroy, width=80).pack(side="left")
    results = queue.Queue()

    def connect():
        selected = choices.get(choice.get())
        if app.busy:
            message.set("Tab đang xử lý tác vụ. Chờ tác vụ hoàn tất rồi kết nối lại.")
            return
        api_key, model_name = key.get().strip(), model.get().strip()
        if not api_key or not model_name:
            message.set("Hãy nhập API key và tên model.")
            return
        new_name = name.get().strip() or app.tab_name
        new_instructions = instructions.get("1.0", "end-1c")
        if selected is None and len(new_name) > 100:
            message.set("Tên hội thoại cần có từ 1 đến 100 ký tự.")
            return
        connect_button.configure(state="disabled")
        selector.configure(state="disabled")
        message.set("Đang kiểm tra API key và quyền truy cập model…")
        record_id = selected["id"] if selected else None

        def worker():
            try:
                check_connection(api_key, model_name)
                results.put((True, ""))
            except Exception as error:
                results.put((False, str(error)))

        def poll():
            if not window.winfo_exists():
                return
            try:
                ok, error = results.get_nowait()
            except queue.Empty:
                app.after(100, poll)
                return
            connect_button.configure(state="normal")
            selector.configure(state="readonly")
            if not ok or app.busy:
                message.set(error or "Chờ tác vụ hiện tại hoàn tất rồi kết nối lại.")
                return
            try:
                selected_id = record_id
                if selected_id is None:
                    record = store.create(new_name, new_instructions)
                    selected_id = record["id"]
                    refresh(selected_id)
            except (OSError, ValueError, sqlite3.Error) as error:
                message.set(f"Key đã được kiểm tra, nhưng không tạo được hội thoại: {error}")
                return
            previous = (app.openai_model.get(), app.openai_conversation_id.get())
            app.openai_model.set(model_name)
            app.openai_conversation_id.set(selected_id)
            if not app.save_user_settings():
                app.openai_model.set(previous[0])
                app.openai_conversation_id.set(previous[1])
                message.set("Không lưu được lựa chọn hội thoại.")
                return
            app.host.openai_key = api_key
            for tab in app.host.tabs:
                tab.update_openai_summary()
            app.status.configure(text="Đã kết nối OpenAI API. Nhập yêu cầu rồi bấm Tạo & điền JSON.")
            window.destroy()

        threading.Thread(target=worker, daemon=True).start()
        app.after(100, poll)

    connect_button = button(buttons, "Kiểm tra & kết nối", connect, primary=True, symbol="check")
    connect_button.pack(side="right")
    window.key_variable, window.model_variable = key, model
    window.conversation_name, window.instructions = name, instructions
    window.create_conversation, window.connect_button = create, connect_button
    window.message_variable = message
    window.after(100, window.lift)
    return window
