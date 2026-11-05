"""Non-modal, tab-owned VoiceStudio settings and voice authoring window."""
import asyncio
from copy import deepcopy
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

import customtkinter as ctk

from platform_support import AudioPlayer
from ui_components import ACCENT, BG, INK, MUTED, box, button, entry, label
from voice_studio import DEFAULTS, VoiceStudioClient, validated


class VoiceStudioWindow(ctk.CTkToplevel):
    def __init__(self, tab):
        super().__init__(tab)
        self.tab = tab
        self.title(f"VoiceStudio — {tab.tab_name}")
        self.geometry("920x810")
        self.minsize(760, 650)
        self.configure(fg_color=BG)
        self.transient(tab.winfo_toplevel())
        self.cancel = threading.Event()
        self.results = queue.Queue()
        self.running = False
        self.closed = False
        self.audio_player = AudioPlayer()
        self.voice_ids = {}
        self.engines = []
        self.pickers = {}
        self.variables = {}
        for name, value in tab.voice_studio_config.items():
            variable = tk.BooleanVar if type(value) is bool else tk.StringVar
            self.variables[name] = variable(master=self, value=value)
        label(self, f"VoiceStudio · {tab.tab_name}", 23, bold=True).pack(anchor="w", padx=24, pady=(20, 4))
        label(self, "Giọng đọc, nhái giọng và thiết kế giọng. Cấu hình được lưu riêng cho tab này.",
              12, MUTED).pack(anchor="w", padx=24, pady=(0, 14))
        footer = box(self)
        footer.pack(side="bottom", fill="x", padx=24, pady=15)
        button(footer, "Lưu & đóng", self.close, primary=True).pack(side="right", padx=(8, 0))
        button(footer, "Áp dụng", self.apply).pack(side="right")
        self.status = label(footer, "Sẵn sàng. Đóng cửa sổ cũng lưu cấu hình.", 11, MUTED,
                            wraplength=530, justify="left")
        self.status.pack(side="left", fill="x", expand=True, padx=(0, 14))
        self.pages = ttk.Notebook(self)
        self.pages.pack(fill="both", expand=True, padx=24, pady=(0, 6))
        self._connection_page()
        self._voices_page()
        self._clone_page()
        self._design_page()
        self._audio_page()
        self._models_page()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.poll_timer = self.after(100, self.poll)

    def page(self, title):
        panel = ctk.CTkScrollableFrame(self.pages, fg_color="white", corner_radius=0)
        self.pages.add(panel, text=title)
        return panel

    def text(self, parent, title, value="", height=85):
        label(parent, title, 12).pack(anchor="w", padx=16, pady=(12, 5))
        field = ctk.CTkTextbox(parent, height=height, fg_color=BG, text_color=INK,
                               border_width=1, border_color="#e3e8ed", font=("Segoe UI", 12))
        field.pack(fill="x", padx=16, pady=(0, 7))
        field.insert("1.0", value)
        return field

    def field(self, parent, title, key, *, choices=None, secret=False):
        label(parent, title, 12).pack(anchor="w", padx=16, pady=(10, 5))
        if choices is not None:
            widget = ttk.Combobox(parent, textvariable=self.variables[key], values=choices, height=10)
            self.pickers[key] = widget
        else:
            widget = entry(parent, self.variables[key], **({"show": "•"} if secret else {}))
        widget.pack(fill="x", padx=16, pady=(0, 4))
        return widget

    def note(self, parent, text):
        label(parent, text, 11, MUTED, wraplength=790, justify="left").pack(fill="x", padx=16, pady=10)

    def _connection_page(self):
        page = self.page("Kết nối")
        self.note(page, "Mở VoiceStudio trên máy này hoặc máy chủ của bạn, cài model cần dùng, "
                  "sau đó kiểm tra kết nối. Model AI được chạy bởi VoiceStudio riêng.")
        self.field(page, "Địa chỉ máy chủ VoiceStudio", "url")
        self.field(page, "API key (để trống nếu máy chủ local không yêu cầu)", "api_key", secret=True)
        self.field(page, "Thời gian chờ tạo giọng (giây, 15–1800)", "timeout")
        button(page, "Kiểm tra kết nối & tải danh sách giọng", self.refresh, primary=True).pack(fill="x", padx=16, pady=12)
        button(page, "Khởi động bộ chạy VoiceStudio local", self.start_local).pack(fill="x", padx=16, pady=6)
        button(page, "Mở ứng dụng VoiceStudio đã cài…", self.launch_installed).pack(fill="x", padx=16, pady=6)
        button(page, "Trang tải VoiceStudio", lambda: webbrowser.open("https://github.com/debpalash/VoiceStudio/releases/latest")).pack(fill="x", padx=16, pady=6)
        self.note(page, "Chỉ gửi văn bản và file mẫu đến địa chỉ máy chủ bạn nhập ở đây. "
                  "API key được che trên màn hình và lưu cùng cấu hình của tab trong dữ liệu người dùng.")

    def _voices_page(self):
        page = self.page("Giọng đọc")
        ctk.CTkSwitch(page, text="Dùng VoiceStudio khi preview / xuất video của tab này",
                      variable=self.variables["enabled"], text_color=INK,
                      progress_color=ACCENT).pack(anchor="w", padx=16, pady=16)
        self.field(page, "Engine / model ID", "engine", choices=["omnivoice"])
        for key, title in (("main_voice", "Giọng lời dẫn chính"), ("english_voice", "Giọng cho đoạn [en]…[/en]"),
                           ("dialogue_a", "Giọng nhân vật hội thoại A"), ("dialogue_b", "Giọng nhân vật hội thoại B")):
            self.field(page, title, key, choices=["default"])
        self.field(page, "Ngôn ngữ lời dẫn chính (vi, en, …)", "main_language", choices=["vi", "en"])
        self.note(page, "Bấm kiểm tra kết nối để lấy các giọng đã lưu. Có thể nhập trực tiếp ID giọng hoặc preset. "
                  "Chọn hai giọng khác nhau cho hội thoại A/B. Tốc độ và cao độ dùng thanh chỉnh trong tab Giọng đọc của Quiz Studio.")
        self.instructions = self.text(page, "Chỉ dẫn phong cách (tùy engine)", self.variables["instructions"].get(), 65)
        self.description = self.text(page, "Mô tả chất giọng (engine hỗ trợ voice design)", self.variables["description"].get(), 65)
        self.field(page, "Số bước tạo giọng (1–128)", "num_step")
        self.field(page, "Guidance scale (0,01–20)", "guidance_scale")
        self.field(page, "Seed (−1 để ngẫu nhiên)", "seed")
        for key, title in (("denoise", "Khử nhiễu"), ("preprocess_prompt", "Tiền xử lý âm thanh tham chiếu")):
            ctk.CTkCheckBox(page, text=title, variable=self.variables[key], text_color=INK,
                           fg_color=ACCENT).pack(anchor="w", padx=16, pady=10)

    def _clone_page(self):
        page = self.page("Nhái giọng")
        self.note(page, "Chọn bản ghi giọng nói rõ, ít tiếng nền. File mẫu được tải lên máy chủ VoiceStudio "
                  "và lưu thành một giọng có thể chọn cho tab này hoặc tab khác.")
        self.clone_name = self.text(page, "Tên giọng mới", height=44)
        self.reference = tk.StringVar(master=self)
        label(page, "File âm thanh / video mẫu", 12).pack(anchor="w", padx=16, pady=(12, 5))
        entry(page, self.reference).pack(fill="x", padx=16)
        button(page, "Chọn file mẫu…", self.choose_reference).pack(anchor="w", padx=16, pady=8)
        self.reference_text = self.text(page, "Lời nói trong file mẫu (nên nhập chính xác; để trống để VoiceStudio chép lời)", height=105)
        button(page, "Tạo giọng từ mẫu", self.clone_voice, primary=True).pack(fill="x", padx=16, pady=16)
        self.note(page, "Sau khi tạo, giọng mới được chọn làm lời dẫn chính trong cửa sổ này. "
                  "Bấm Áp dụng để dùng cho video; bạn cũng có thể gán giọng vào phần tiếng Anh hoặc A/B.")

    def _design_page(self):
        page = self.page("Thiết kế giọng")
        self.design_name = self.text(page, "Tên giọng thiết kế", height=44)
        self.design_description = self.text(page, "Mô tả giọng (tiếng Anh thường được engine hiểu tốt hơn)",
                                            "A warm young adult female voice with an American accent.", 120)
        self.note(page, "Ví dụ: giới tính, độ tuổi, độ trầm/cao, cách đọc và giọng vùng miền. "
                  "Khả năng thiết kế tùy engine đã chọn. VoiceStudio sẽ báo các từ mô tả không ánh xạ được.")
        button(page, "Thiết kế & lưu giọng mới", self.design_voice, primary=True).pack(fill="x", padx=16, pady=16)
        self.design_feedback = self.text(page, "Kết quả thiết kế", height=140)

    def _audio_page(self):
        page = self.page("Nghe thử / xuất audio")
        self.sample = self.text(page, "Văn bản tạo giọng; hỗ trợ [en]…[/en]", "Xin chào! [en]Welcome to the quiz![/en]", 180)
        self.sample_role = tk.StringVar(master=self, value="main")
        label(page, "Giọng nghe thử", 12).pack(anchor="w", padx=16, pady=(12, 5))
        ttk.Combobox(page, textvariable=self.sample_role, state="readonly",
                     values=["main", "english", "dialogue_a", "dialogue_b"]).pack(fill="x", padx=16)
        row = box(page)
        row.pack(fill="x", padx=16, pady=16)
        button(row, "Tạo & nghe thử", lambda: self.generate_audio(False), primary=True).pack(side="left", padx=(0, 8))
        button(row, "Xuất file WAV…", lambda: self.generate_audio(True)).pack(side="left", padx=(0, 8))
        button(row, "Dừng", self.stop).pack(side="left")
        self.note(page, "Lần tạo đầu tiên có thể chờ model khởi động. Nghe thử dùng cấu hình đang chỉnh trong cửa sổ này; "
                  "preview và xuất video dùng cấu hình đã Áp dụng.")

    def _models_page(self):
        page = self.page("Engine / model")
        self.model_list = self.text(page, "Engine được máy chủ báo cáo", height=330)
        button(page, "Làm mới engine & giọng", self.refresh).pack(fill="x", padx=16, pady=8)
        button(page, "Kiểm tra engine đang chọn", self.check_engine).pack(fill="x", padx=16, pady=8)
        self.note(page, "Cài engine và tải model trong Model Manager của VoiceStudio. Engine được gửi theo từng yêu cầu tạo giọng, "
                  "vì vậy các tab có thể chọn engine riêng mà không đổi lựa chọn chung của máy chủ.")

    def current(self):
        config = {key: value.get() for key, value in self.variables.items()}
        for key in ("num_step", "seed", "timeout"):
            try:
                config[key] = int(config[key])
            except ValueError as error:
                raise ValueError(f"{key} phải là số nguyên.") from error
        try:
            config["guidance_scale"] = float(config["guidance_scale"].replace(",", "."))
        except ValueError as error:
            raise ValueError("Guidance scale phải là số.") from error
        for key in ("main_voice", "english_voice", "dialogue_a", "dialogue_b"):
            config[key] = self.voice_ids.get(config[key], config[key])
        config["instructions"] = self.instructions.get("1.0", "end").strip()
        config["description"] = self.description.get("1.0", "end").strip()
        return validated(config, strict=True)

    def apply(self, show_status=True):
        try:
            self.tab.apply_voice_studio(self.current())
        except (OSError, ValueError) as error:
            messagebox.showerror("Cài đặt VoiceStudio", str(error), parent=self)
            return False
        if show_status:
            self.status.configure(text=f"Đã lưu cấu hình riêng cho {self.tab.tab_name}.")
        return True

    def run(self, operation, done, message):
        if self.running:
            self.status.configure(text="Đang có tác vụ VoiceStudio chạy; chờ hoàn tất hoặc bấm Dừng.")
            return
        self.running = True
        self.cancel.clear()
        self.status.configure(text=message)
        def worker():
            try:
                result = operation()
                self.results.put((done, result, None))
            except Exception as error:
                self.results.put((done, None, error))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                done, result, error = self.results.get_nowait()
                self.running = False
                if self.cancel.is_set():
                    self.status.configure(text="Đã dừng tác vụ VoiceStudio.")
                elif error:
                    self.status.configure(text=str(error))
                    messagebox.showerror("VoiceStudio", str(error), parent=self)
                else:
                    done(result)
        except queue.Empty:
            pass
        self.poll_timer = self.after(100, self.poll)

    def refresh(self):
        try:
            client = VoiceStudioClient(self.current())
        except ValueError as error:
            messagebox.showerror("VoiceStudio", str(error), parent=self)
            return
        self.run(client.inventory, self.inventory_loaded, "Đang kết nối VoiceStudio…")

    def start_local(self):
        from voice_studio_runtime import ensure_running
        def done(result):
            self.status.configure(text=f"VoiceStudio local sẵn sàng · {result.get('device', 'CPU')}.")
            self.refresh()
        self.run(ensure_running, done, "Đang khởi động VoiceStudio local…")

    def inventory_loaded(self, result):
        before = self.current()
        self.voice_ids = {f"{item['name']} · {item['id']}": item["id"] for item in result["profiles"]}
        options = ["default", *self.voice_ids]
        for key in ("main_voice", "english_voice", "dialogue_a", "dialogue_b"):
            self.pickers[key].configure(values=options)
            self.variables[key].set(next((label for label, value in self.voice_ids.items() if value == before[key]), before[key]))
        self.engines = result["engines"]
        self.pickers["engine"].configure(values=[item["id"] for item in self.engines] or ["omnivoice"])
        descriptions = []
        for item in self.engines:
            availability = "sẵn sàng" if item.get("available") else "chưa sẵn sàng"
            presets = item.get("preset_voices", [])
            descriptions.append(f"{item['id']} — {item.get('name', item.get('label', ''))} · {availability}\n"
                                f"{item.get('reason') or ''}\nPreset: {presets or 'không có'}\n")
        self.model_list.delete("1.0", "end")
        self.model_list.insert("1.0", "\n".join(descriptions))
        self.status.configure(text=f"Đã kết nối · {len(self.engines)} engine · {len(result['profiles'])} giọng đã lưu.")

    def choose_reference(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Âm thanh / video", "*.wav *.mp3 *.flac *.m4a *.ogg *.mp4 *.webm"), ("Tất cả", "*.*")])
        if path:
            self.reference.set(path)

    def profile_created(self, profile):
        self.variables["main_voice"].set(profile["id"])
        self.status.configure(text=f"Đã tạo giọng {profile.get('name', profile['id'])}. Bấm Áp dụng để dùng cho video.")
        self.refresh()

    def clone_voice(self):
        try:
            config = self.current()
            client = VoiceStudioClient(config)
            name, source = self.clone_name.get("1.0", "end").strip(), self.reference.get()
            transcript = self.reference_text.get("1.0", "end").strip()
            if not name or not Path(source).is_file():
                raise ValueError("Hãy nhập tên giọng và chọn file mẫu.")
        except ValueError as error:
            messagebox.showerror("Nhái giọng", str(error), parent=self)
            return
        self.run(lambda: client.clone(name, source, transcript, config["main_language"]),
                 self.profile_created, "Đang tạo giọng từ file mẫu…")

    def design_voice(self):
        try:
            config = self.current()
            client = VoiceStudioClient(config)
            name = self.design_name.get("1.0", "end").strip()
            description = self.design_description.get("1.0", "end").strip()
            if not name or not description:
                raise ValueError("Hãy nhập tên và mô tả giọng muốn tạo.")
        except ValueError as error:
            messagebox.showerror("Thiết kế giọng", str(error), parent=self)
            return
        def done(result):
            self.design_feedback.delete("1.0", "end")
            self.design_feedback.insert("1.0", f"Đã lưu giọng: {result['profile'].get('name', name)}\n"
                                        f"Mô tả chưa ánh xạ được: {result['unmatched'] or 'không có'}")
            self.profile_created(result["profile"])
        self.run(lambda: client.design(name, description, config["main_language"]), done, "Đang thiết kế giọng…")

    def generate_audio(self, export):
        from engine import Cancelled, Renderer, Settings, plain
        try:
            config = self.current()
            config["enabled"] = True
            text = self.sample.get("1.0", "end").strip()
            if not text:
                raise ValueError("Hãy nhập văn bản cần đọc.")
            role = self.sample_role.get()
            if role != "main":
                text = "[en]" + plain(text) + "[/en]"
            settings = Settings(voice="google:en" if config["main_language"].startswith("en") else "google:vi",
                                english_voice="voicestudio:" + (role if role != "main" else "english"),
                                voice_studio=deepcopy(config), rate=self.tab.rate.get(), pitch=self.tab.pitch.get())
        except (ValueError, tk.TclError) as error:
            messagebox.showerror("Tạo giọng", str(error), parent=self)
            return
        destination = filedialog.asksaveasfilename(parent=self, defaultextension=".wav", filetypes=[("WAV", "*.wav")]) if export else None
        if export and not destination:
            return
        self.tab.stop_preview()
        def operation():
            with tempfile.TemporaryDirectory(prefix="quiz-voicestudio-", dir=str(Path(destination).parent) if destination else None) as directory:
                renderer = Renderer(settings, cancel=self.cancel)
                path = Path(directory) / "voice.wav"
                asyncio.run(renderer.speech(text, path, Path(directory)))
                renderer.check()
                if destination:
                    os.replace(path, destination)
                    return "Đã xuất WAV: " + destination
                self.audio_player.play(path, wait=True, cancel=self.cancel)
                renderer.check()
                return "Đã phát giọng nghe thử."
        self.run(operation, lambda text: self.status.configure(text=text), "Đang tạo âm thanh bằng VoiceStudio…")

    def check_engine(self):
        try:
            config = self.current()
            client = VoiceStudioClient(config)
            from urllib.parse import quote
            route = "/engines/" + quote(config["engine"], safe="") + "/health"
        except ValueError as error:
            messagebox.showerror("VoiceStudio", str(error), parent=self)
            return
        def done(result):
            import json
            self.model_list.delete("1.0", "end")
            self.model_list.insert("1.0", json.dumps(result, ensure_ascii=False, indent=2))
            self.status.configure(text="Đã kiểm tra trạng thái engine.")
        self.run(lambda: client.request("GET", route), done, "Đang kiểm tra engine…")

    def launch_installed(self):
        path = filedialog.askopenfilename(parent=self, title="Chọn ứng dụng VoiceStudio đã cài",
                                         filetypes=[("Ứng dụng", "*.exe"), ("Tất cả", "*.*")])
        if path:
            try:
                subprocess.Popen([path], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.status.configure(text="Đã mở VoiceStudio. Chờ máy chủ khởi động rồi kiểm tra kết nối.")
            except OSError as error:
                messagebox.showerror("Mở VoiceStudio", str(error), parent=self)

    def stop(self):
        self.cancel.set()
        self.audio_player.stop()
        self.status.configure(text="Đã yêu cầu dừng; đang chờ dịch vụ kết thúc yêu cầu hiện tại.")

    def close(self):
        if self.apply(False):
            self.destroy()

    def destroy(self):
        if self.closed:
            return
        self.closed = True
        self.cancel.set()
        self.audio_player.stop()
        if getattr(self, "poll_timer", None):
            self.after_cancel(self.poll_timer)
        self.tab.voice_studio_window = None
        super().destroy()
