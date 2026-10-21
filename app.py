import asyncio
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import ImageTk
from engine import Cancelled, Renderer, Settings, VOICES, frame, parse_questions
from preferences import BackgroundStore, UserSettingsStore, USER_DEFAULTS
from video_themes import TEMPLATES, video_template

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))


class App(tk.Tk):
    def __init__(self, data_dir=None):
        super().__init__()
        self.title("Quiz Studio — Tạo video trắc nghiệm")
        self.geometry("1380x900")
        self.minsize(1100, 740)
        self.configure(bg="#10172b")
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.rows = []
        self.background_store = BackgroundStore(data_dir)
        saved_background = self.background_store.load()
        self.background = saved_background["background"]
        self.background_name = saved_background["background_name"]
        self.dim_save_timer = None
        self.settings_save_timer = None
        self.user_store = UserSettingsStore(self.background_store.directory)
        saved_settings = self.user_store.load()
        self.music = saved_settings["music"]
        self.music_name = saved_settings["music_name"]
        self.last_output = None
        self.job_exporting = False
        from modern_ui import build_ui
        build_ui(self, {**saved_background, **saved_settings})
        for name in USER_DEFAULTS:
            getattr(self, name).trace_add("write", self.user_settings_changed)
        self.text.insert("1.0", (ROOT / "examples/questions.json").read_text(encoding="utf-8"))
        self.validate()
        warnings = [store.warning for store in (self.background_store, self.user_store) if store.warning]
        if warnings:
            self.status.configure(text="\n".join(warnings))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.poll)

    def move_question(self, direction):
        if self.rows:
            self.selected.set(max(1, min(len(self.rows), self.selected.get() + direction)))
            self.show_preview()

    def user_settings(self):
        return {name: getattr(self, name).get() for name in USER_DEFAULTS}

    def user_settings_changed(self, *args):
        if self.settings_save_timer:
            self.after_cancel(self.settings_save_timer)
        self.settings_save_timer = self.after(350, self.save_user_settings)

    def save_user_settings(self):
        self.settings_save_timer = None
        try:
            self.user_store.save(self.user_settings())
            return True
        except (OSError, ValueError, tk.TclError) as error:
            self.status.configure(text=f"Không lưu được cài đặt: {error}")
            return False

    def json_changed(self, event=None):
        if self.text.edit_modified():
            self.stop_preview()
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        timer = getattr(self, "json_color_timer", None)
        if timer:
            self.after_cancel(timer)
        self.json_color_timer = self.after(180, self.highlight_json)

    def highlight_json(self):
        self.json_color_timer = None
        source = self.text.get("1.0", "end-1c")
        for tag in ("json_key", "json_string"):
            self.text.tag_remove(tag, "1.0", "end")
        for token in re.finditer(r'"(?:\\.|[^"\\])*"', source):
            key = source[token.end():].lstrip().startswith(":")
            self.text.tag_add("json_key" if key else "json_string", f"1.0+{token.start()}c", f"1.0+{token.end()}c")

    def update_watermark(self):
        self.watermark_entry.configure(state="normal" if self.watermark_enabled.get() else "disabled")
        self.show_preview()

    def select_list_question(self, event=None):
        selection = self.question_list.selection()
        if selection:
            self.selected.set(int(selection[0]) + 1)
            self.show_preview()

    def combo(self, parent, label, variable, values):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 4))
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=29).pack(fill="x", padx=(0, 16))

    def spin(self, parent, label, variable, low, high):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 4))
        ttk.Spinbox(parent, from_=low, to=high, textvariable=variable, width=27).pack(fill="x", padx=(0, 16))

    def settings(self):
        if any(row.get("type") == "dialogue" for row in self.rows) and self.dialogue_voice_a.get() == self.dialogue_voice_b.get():
            raise ValueError("Hội thoại: hãy chọn hai giọng khác nhau cho nhân vật A và B trong tab Giọng đọc.")
        rate, pitch, countdown, volume = self.rate.get(), self.pitch.get(), self.countdown.get(), self.music_volume.get()
        dim = self.background_dim.get()
        if not (-50 <= rate <= 100 and -50 <= pitch <= 50 and 1 <= countdown <= 30 and 0 <= volume <= 100):
            raise ValueError("Kiểm tra tốc độ (-50…100), cao độ (-50…50), đếm ngược (1…30) và âm lượng (0…100).")
        if not 0 <= dim <= 70:
            raise ValueError("Mức làm tối nền phải từ 0 đến 70%.")
        width, height = (720, 1280) if self.resolution.get().startswith("720") else (1080, 1920)
        return Settings(voice=VOICES[self.voice.get()], english_voice=VOICES[self.en_voice.get()], dialogue_voice_a=VOICES[self.dialogue_voice_a.get()], dialogue_voice_b=VOICES[self.dialogue_voice_b.get()], rate=rate, pitch=pitch, countdown=countdown, width=width, height=height, read_options=self.read_options.get(), read_explanation=self.read_explanation.get(), speech=self.speech.get(), brand=self.brand.get(), watermark_enabled=self.watermark_enabled.get(), template=TEMPLATES[self.video_template.get()], background=self.background, background_dim=dim, music=self.music, music_volume=volume / 100)

    def validate(self):
        try:
            self.highlight_json()
            self.quiz_title, self.rows = parse_questions(self.text.get("1.0", "end"))
            from content_types import normalize
            from engine import parse_legacy_questions
            _, _, mode = normalize(json.loads(self.text.get("1.0", "end")), parse_legacy_questions)
            self.content_editor.detect(mode)
            self.validation.configure(text=f"JSON hợp lệ: {len(self.rows)} câu hỏi.", foreground="#218c7c")
            from content_types import document_warnings
            warnings = document_warnings(self.quiz_title, self.rows)
            if warnings:
                self.validation.configure(text="Cảnh báo: " + " · ".join(warnings), foreground="#a46716")
            self.question_count.configure(text=f"{len(self.rows)} câu hỏi")
            self.question_list.delete(*self.question_list.get_children())
            for index, row in enumerate(self.rows):
                from engine import plain
                from content_timeline import plan_item
                scenes = plan_item(row, self.settings())
                from content_types import LABELS
                self.question_list.insert("", "end", iid=str(index), values=(f"{index + 1}. {plain(scenes[0].text)}", LABELS[row["type"]]))
            from content_timeline import plan_item, estimated_seconds
            duration = sum(estimated_seconds(scene) for row in self.rows for scene in plan_item(row, self.settings())) + 3
            self.duration_label.configure(text=f"Ước tính: {duration:.0f}s. Export cập nhật theo TTS thực tế.")
            return self.show_preview()
        except Exception as error:
            self.rows = []
            self.validation.configure(text=str(error), foreground="#ba4247")
            return False

    def show_preview(self):
        if not self.rows:
            return False
        try:
            index = max(0, min(self.selected.get() - 1, len(self.rows) - 1))
            self.selected.set(index + 1)
            settings = self.settings()
            theme = video_template(self.rows, self.quiz_title, settings.template)
            settings.template = theme
            self.template_label.configure(text={"math": "TOÁN · XANH BẠC HÀ", "english": "TIẾNG ANH · XANH SÁNG", "classic": "QUIZ · NHIỀU MÀU"}[theme])
            picture = frame(self.rows[index], index + 1, len(self.rows), self.quiz_title, settings, reveal=self.reveal.get(), countdown=self.countdown.get())
            picture.thumbnail((180, 220))
            self.preview_image = ImageTk.PhotoImage(picture)
            self.preview.configure(image=self.preview_image)
            return True
        except Exception as error:
            self.validation.configure(text=str(error), foreground="#ba4247")
            return False

    def open_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            try:
                data = Path(path).read_text(encoding="utf-8-sig")
                self.content_editor.drafts[self.content_editor.mode] = self.content_editor.source()
                self.stop_preview()
                self.text.delete("1.0", "end")
                self.text.insert("1.0", data)
                self.validate()
            except Exception as error:
                messagebox.showerror("Không mở được JSON", str(error))

    def save_json(self):
        if not self.validate():
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            from content_types import export_document
            document = export_document(self.quiz_title, self.rows, self.content_editor.mode)
            Path(path).write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

    def stop_preview(self):
        self.seek_preview = lambda value: None
        if getattr(self, "preview_cancel", None):
            self.preview_cancel.set()
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        timer = getattr(self, "playback_timer", None)
        if timer:
            self.after_cancel(timer)
            self.playback_timer = None
        directory = getattr(self, "preview_directory", None)
        if directory:
            import shutil
            shutil.rmtree(directory, ignore_errors=True)
            self.preview_directory = None

    def play_preview(self, whole=False):
        self.stop_preview()
        if self.busy or not self.validate():
            return
        from content_timeline import plan_item, prepare_scene, ending_scene, preview_audio
        settings = self.settings()
        settings.template = video_template(self.rows, self.quiz_title, settings.template)
        indexes = range(len(self.rows)) if whole else [self.selected.get()-1]
        rows, title = list(self.rows), self.quiz_title
        scenes = [(i, scene) for i in indexes for scene in plan_item(rows[i], settings)]
        if whole:
            scenes.append((len(rows)-1, ending_scene()))
        self.preview_cancel = threading.Event()
        cancel = self.preview_cancel
        self.preview_generation = getattr(self, "preview_generation", 0) + 1
        generation = self.preview_generation
        def prepare():
            directory = Path(tempfile.mkdtemp(prefix="quiz-preview-"))
            renderer = Renderer(settings, cancel=cancel)
            try:
                from content_renderer import validate_layout
                validate_layout(title, rows, settings, renderer.check)
                prepared = [(i, prepare_scene(renderer, scene, directory, str(n), i+1)) for n, (i, scene) in enumerate(scenes)]
                audio = preview_audio(renderer, [p for _, p in prepared], directory)
                renderer.check()
                self.events.put(("preview_ready", (generation, rows, title, settings, prepared, directory, audio)))
            except Exception as error:
                import shutil
                shutil.rmtree(directory, ignore_errors=True)
                if not cancel.is_set():
                    self.events.put(("error", str(error)))
            return "Đã chuẩn bị preview."
        self.start_job(prepare)

    def begin_preview(self, data):
        generation, rows, title, settings, scenes, directory, audio = data
        if generation != getattr(self, "preview_generation", 0) or self.preview_cancel.is_set():
            import shutil
            shutil.rmtree(directory, ignore_errors=True)
            return
        self.preview_directory = directory
        self.duration_label.configure(text=f"Thời lượng preview theo âm thanh: {sum(p.seconds for _, p in scenes):.1f}s")
        from content_renderer import render_scene, render_ending
        import time
        started = None
        elapsed = 0
        self.preview_seek.configure(to=sum(p.seconds for _, p in scenes))
        self.preview_seek.set(0)
        def advance(position=0, offset=0, audio_source=None):
            nonlocal started, elapsed
            if position >= len(scenes):
                self.stop_preview()
                return
            index, prepared = scenes[position]
            try:
                picture = render_ending(settings) if prepared.scene.phase == "ending" else render_scene(rows[index], prepared.scene, index+1, len(rows), title, settings)
                picture.thumbnail((180, 220))
                self.preview_image = ImageTk.PhotoImage(picture)
                self.preview.configure(image=self.preview_image)
                self.selected.set(index+1)
                self.preview_seek.set(elapsed)
                if started is None:
                    if audio:
                        import winsound
                        winsound.PlaySound(str(audio_source or audio), winsound.SND_FILENAME | winsound.SND_ASYNC)
                    started = time.monotonic()
                    started -= elapsed
                elapsed += prepared.seconds - offset
                self.playback_timer = self.after(max(1, round((started+elapsed-time.monotonic())*1000)), lambda: advance(position+1))
            except Exception as error:
                self.validation.configure(text=str(error), foreground="#ba4247")
        def seek(timestamp):
            nonlocal started, elapsed
            import wave
            timer = getattr(self, "playback_timer", None)
            if timer:
                self.after_cancel(timer)
            position, offset = 0, float(timestamp)
            while position < len(scenes)-1 and offset >= scenes[position][1].seconds:
                offset -= scenes[position][1].seconds
                position += 1
            timestamp = min(float(timestamp), sum(p.seconds for _, p in scenes)-1/30)
            offset = max(0, timestamp - sum(p.seconds for _, p in scenes[:position]))
            source = None
            if audio:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
                source = directory / "seek-track.wav"
                with wave.open(str(audio), "rb") as track, wave.open(str(source), "wb") as target:
                    target.setparams(track.getparams())
                    track.setpos(min(track.getnframes(), round(timestamp*track.getframerate())))
                    while block := track.readframes(44100):
                        target.writeframesraw(block)
            started, elapsed = None, timestamp
            advance(position, offset, source)
        self.seek_preview = seek
        advance()

    def choose_media(self, kind):
        types = [("Ảnh", "*.png *.jpg *.jpeg *.webp")] if kind == "background" else [("Âm thanh", "*.mp3 *.wav *.m4a *.aac")]
        path = filedialog.askopenfilename(filetypes=types)
        if path:
            try:
                if kind == "background":
                    saved = self.background_store.select(path, self.background_dim.get())
                    self.background = saved["background"]
                    self.background_name = saved["background_name"]
                    self.status.configure(text="Đã lưu ảnh nền. Lần mở app tiếp theo sẽ tự sử dụng ảnh này.")
                else:
                    Renderer(Settings()).run(["-i", path, "-t", "0.1", "-map", "0:a:0", "-f", "null", "-"])
                    saved = self.user_store.select_music(path, self.user_settings())
                    self.music, self.music_name = saved["music"], saved["music_name"]
                    self.status.configure(text="Đã lưu nhạc nền. Lần mở app tiếp theo sẽ tự sử dụng nhạc này.")
            except Exception as error:
                messagebox.showerror("Không lưu được ảnh nền" if kind == "background" else "Không lưu được nhạc nền", str(error))
                return
            self.update_media_label()
            self.show_preview()

    def update_media_label(self):
        self.media_label.configure(text=f"Ảnh: {self.background_name or 'Chưa chọn'}\nNhạc: {self.music_name or 'Chưa chọn'}")

    def background_dim_changed(self, *args):
        self.show_preview()
        if self.dim_save_timer:
            self.after_cancel(self.dim_save_timer)
        self.dim_save_timer = self.after(350, self.save_background_dim)

    def save_background_dim(self):
        self.dim_save_timer = None
        try:
            dim = self.background_dim.get()
            if 0 <= dim <= 70:
                self.background_store.save_dim(dim)
        except (ValueError, tk.TclError):
            pass
        except OSError as error:
            self.status.configure(text=f"Không lưu được mức làm tối nền: {error}")

    def clear_media(self):
        try:
            self.background_store.clear(self.background_dim.get())
            self.user_store.clear_music(self.user_settings())
        except Exception as error:
            messagebox.showerror("Không lưu được thay đổi", str(error))
            return
        self.background = self.music = ""
        self.background_name = ""
        self.music_name = ""
        self.update_media_label()
        self.show_preview()

    def start_job(self, job, exporting=False):
        if self.busy:
            return
        self.busy = True
        self.job_exporting = exporting
        self.cancel.clear()
        self.export_button.configure(state="disabled")
        self.progress.stop()
        self.progress.configure(mode="determinate" if exporting else "indeterminate", value=0)
        self.progress_label.configure(text="0%" if exporting else "Chờ…")
        if exporting:
            self.last_output = None
            self.folder_button.configure(state="disabled")
        else:
            self.progress.start()
        def worker():
            try:
                result = job()
                self.events.put(("done", result))
            except Cancelled as error:
                self.events.put(("cancel", str(error)))
            except Exception as error:
                self.events.put(("error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def voice_preview(self):
        if self.busy:
            return
        try:
            settings = self.settings()
        except Exception as error:
            messagebox.showerror("Cài đặt", str(error))
            return
        def job():
            self.events.put(("log", "Đang tạo giọng nghe thử…"))
            directory = Path(tempfile.mkdtemp(prefix="quiz-voice-"))
            target = directory / "preview.wav"
            text = "Xin chào! Bạn đã sẵn sàng cho câu hỏi tiếp theo chưa? [en]Welcome to the quiz challenge![/en]"
            if settings.voice.startswith("en") or settings.voice == "google:en":
                text = "Welcome! Are you ready for the next question?"
            renderer = Renderer(settings, cancel=self.cancel)
            asyncio.run(renderer.speech(text, target, directory))
            import winsound
            winsound.PlaySound(str(target), winsound.SND_FILENAME)
            import shutil
            shutil.rmtree(directory)
            return "Đã phát giọng nghe thử."
        self.start_job(job)

    def export(self):
        if self.busy or not self.validate():
            return
        filename = datetime.now().strftime("%d-%m-%Y-%Hh%M.mp4")
        path = filedialog.asksaveasfilename(defaultextension=".mp4", initialfile=filename, filetypes=[("Video MP4", "*.mp4")])
        if not path:
            return
        settings, rows, title = self.settings(), list(self.rows), self.quiz_title
        def job():
            renderer = Renderer(settings, lambda text: self.events.put(("log", text)), self.cancel,
                                progress=lambda percent, message: self.events.put(("progress", (percent, message))))
            renderer.render(title, rows, path)
            return {"message": f"Đã xuất video: {path}", "path": str(Path(path).resolve()), "duration": renderer.duration}
        self.start_job(job, exporting=True)

    def open_output_folder(self):
        if not self.last_output:
            return
        if not self.last_output.is_file():
            messagebox.showwarning("Không tìm thấy video", f"Video đã bị chuyển hoặc xóa:\n{self.last_output}")
            return
        try:
            # Windows Explorer selects the completed file, including paths with spaces.
            subprocess.Popen(["explorer.exe", f'/select,{self.last_output}'])
        except OSError as error:
            messagebox.showerror("Không mở được thư mục", str(error))

    def poll(self):
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "preview_ready":
                    self.begin_preview(text)
                    continue
                if kind == "progress":
                    percent, message = text
                    self.progress["value"] = percent
                    self.progress_label.configure(text=f"{int(percent)}%")
                    self.status.configure(text=message)
                    continue
                if kind == "done" and self.job_exporting:
                    self.last_output = Path(text["path"])
                    if "duration" in text:
                        self.duration_label.configure(text=f"Thời lượng video thực tế: {text['duration']:.1f}s")
                    text = text["message"]
                    self.folder_button.configure(state="normal")
                self.status.configure(text=text)
                if kind != "log":
                    self.busy = False
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                    if kind == "done" and self.job_exporting:
                        self.progress["value"] = 100
                        self.progress_label.configure(text="100%")
                    elif kind == "done":
                        self.progress["value"] = 0
                        self.progress_label.configure(text="Xong")
                    elif kind == "cancel":
                        self.progress_label.configure(text="Đã hủy")
                    else:
                        self.progress_label.configure(text="Lỗi")
                    self.export_button.configure(state="normal")
                    if kind == "error":
                        guidance = "\n\nKiểm tra Internet rồi thử lại, hoặc bỏ chọn Tạo giọng đọc để xuất offline." if "(TTS)" in text else ""
                        messagebox.showerror("Tác vụ thất bại", text + guidance)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def close(self):
        self.stop_preview()
        if self.busy:
            self.cancel.set()
            self.status.configure(text="Đang hủy tác vụ, hãy đóng cửa sổ sau khi tác vụ dừng.")
            return
        if self.dim_save_timer:
            self.after_cancel(self.dim_save_timer)
            self.save_background_dim()
        if self.settings_save_timer:
            self.after_cancel(self.settings_save_timer)
        if not self.save_user_settings():
            return
        for timer in self.tk.call("after", "info"):
            self.after_cancel(timer)
        self.destroy()


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        report = Path(sys.argv[sys.argv.index("--self-check") + 1])
        try:
            app = App()
            app.withdraw()
            app.update_idletasks()
            assert len(app.rows) == 2 and app.show_preview()
            from content_types import DEFAULT_MODE, REGISTRY, sample_document
            from content_timeline import plan_item
            from content_renderer import render_scene
            assert app.content_editor.mode == DEFAULT_MODE
            checked_settings = Settings(speech=False, width=180, height=320)
            for kind in REGISTRY:
                checked_title, checked_rows = parse_questions(json.dumps(sample_document(kind)))
                for scene in plan_item(checked_rows[0], checked_settings):
                    render_scene(checked_rows[0], scene, 1, 1, checked_title, checked_settings)
            app.reveal.set(True)
            assert app.show_preview()
            app.job_exporting = True
            app.busy = True
            app.events.put(("progress", (50, "Đang dựng video…")))
            app.poll()
            assert app.progress["value"] == 50
            assert app.progress_label["text"] == "50%"
            checked_path = str(report.resolve().with_suffix(".mp4"))
            app.events.put(("done", {"message": "Đã xuất video", "path": checked_path}))
            app.poll()
            assert app.progress["value"] == 100 and not app.busy
            assert app.last_output == Path(checked_path)
            assert str(app.folder_button.cget("state")) == "normal"
            ffmpeg = Renderer(app.settings()).ffmpeg
            assert Path(ffmpeg).is_file()
            app.destroy()
            report.write_text(json.dumps({"ok": True, "questions": 2, "default_mode": DEFAULT_MODE, "content_types": len(REGISTRY), "ffmpeg": ffmpeg, "progress_and_output_button": True}), encoding="utf-8")
        except Exception as error:
            report.write_text(json.dumps({"ok": False, "error": str(error)}), encoding="utf-8")
            sys.exit(1)
    else:
        App().mainloop()
