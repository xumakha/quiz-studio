from platform_support import AudioPlayer, open_in_file_manager
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
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import ImageTk
from engine import Cancelled, Renderer, Settings, VOICES, frame, parse_questions
from preferences import BackgroundStore, BrandingStore, UserSettingsStore, USER_DEFAULTS
from workspace_profiles import WorkspaceProfiles
from video_themes import TEMPLATES, video_template
from voice_studio import VoiceStudioStore

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))


class VideoTab(tk.Frame):
    """An independent editor, preview and render job within the main window."""

    def __init__(self, host, number, profile, config_dir):
        super().__init__(host.workspace)
        self.host = host
        self.number = number
        self.profile_id = profile["id"]
        self.tab_name = profile["name"]
        self._timers = set()
        self.disposed = False
        self.closing = False
        self.export_path = None
        self.job_state = ""
        self.clean_source = ""
        self.events = queue.Queue()
        self.audio_player = AudioPlayer()
        self.cancel = threading.Event()
        self.busy = False
        self.rows = []
        self.background_store = BackgroundStore(host.data_dir, config_dir=config_dir)
        saved_background = self.background_store.load()
        self.background = saved_background["background"]
        self.background_name = saved_background["background_name"]
        self.dim_save_timer = None
        self.settings_save_timer = None
        self.user_store = UserSettingsStore(self.background_store.directory, config_dir=config_dir)
        self.voice_studio_store = VoiceStudioStore(config_dir)
        self.voice_studio_config = self.voice_studio_store.load()
        self.voice_studio_window = None
        saved_settings = self.user_store.load()
        self.music = saved_settings["music"]
        self.music_name = saved_settings["music_name"]
        self.branding_store = BrandingStore(self.background_store.directory, config_dir=config_dir)
        for name, value in self.branding_store.load().items():
            setattr(self, name, value)
        self.last_output = None
        self.job_exporting = False
        from modern_ui import build_ui
        build_ui(self, {**saved_background, **saved_settings})
        for name in USER_DEFAULTS:
            getattr(self, name).trace_add("write", self.user_settings_changed)
        self.text.insert("1.0", (ROOT / "examples/questions.json").read_text(encoding="utf-8"))
        self.validate()
        self.mark_clean()
        warnings = [store.warning for store in (self.background_store, self.user_store, self.branding_store,
                                                self.voice_studio_store) if store.warning]
        if warnings:
            self.status.configure(text="\n".join(warnings))
        self.poll_timer = self.after(100, self.poll)

    def after(self, ms, func=None, *args):
        if func is None:
            return super().after(ms)
        def invoke():
            self._timers.discard(timer)
            if not self.disposed:
                func(*args)
        timer = super().after(ms, invoke)
        self._timers.add(timer)
        return timer

    def after_cancel(self, timer):
        self._timers.discard(timer)
        super().after_cancel(timer)

    @property
    def dirty(self):
        return self.text.get("1.0", "end-1c") != self.clean_source

    def mark_clean(self):
        self.clean_source = self.text.get("1.0", "end-1c")
        self.host.update_tab(self)

    def persist(self):
        if self.voice_studio_window is not None and self.voice_studio_window.winfo_exists():
            if not self.voice_studio_window.apply(False):
                return False
        if self.dim_save_timer:
            self.after_cancel(self.dim_save_timer)
        if not self.save_background_dim():
            return False
        if self.settings_save_timer:
            self.after_cancel(self.settings_save_timer)
        try:
            self.branding_store.save()
            self.voice_studio_store.save(self.voice_studio_config)
        except OSError as error:
            self.status.configure(text=f"Không lưu được ảnh: {error}")
            return False
        return self.save_user_settings()

    def open_voice_studio(self):
        if self.voice_studio_window is not None and self.voice_studio_window.winfo_exists():
            self.voice_studio_window.deiconify()
            self.voice_studio_window.lift()
            self.voice_studio_window.focus_set()
            return self.voice_studio_window
        from voice_studio_ui import VoiceStudioWindow
        self.voice_studio_window = VoiceStudioWindow(self)
        return self.voice_studio_window

    def apply_voice_studio(self, config):
        saved = self.voice_studio_store.save(config)
        self.voice_studio_config = saved
        self.stop_preview()
        self.voice_studio_summary.configure(text=(
            f"Đang dùng VoiceStudio · {saved['engine']}" if saved["enabled"] else "Đang dùng giọng Google / Edge"))

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
        self.host.update_tab(self)
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
        if (not self.voice_studio_config["enabled"] and any(row.get("type") == "dialogue" for row in self.rows)
                and self.dialogue_voice_a.get() == self.dialogue_voice_b.get()):
            raise ValueError("Hội thoại: hãy chọn hai giọng khác nhau cho nhân vật A và B trong tab Giọng đọc.")
        rate, pitch, countdown, volume = self.rate.get(), self.pitch.get(), self.countdown.get(), self.music_volume.get()
        dim = self.background_dim.get()
        if not (-50 <= rate <= 100 and -50 <= pitch <= 50 and 1 <= countdown <= 30 and 0 <= volume <= 100):
            raise ValueError("Kiểm tra tốc độ (-50…100), cao độ (-50…50), đếm ngược (1…30) và âm lượng (0…100).")
        if not 0 <= dim <= 70:
            raise ValueError("Mức làm tối nền phải từ 0 đến 70%.")
        width, height = (720, 1280) if self.resolution.get().startswith("720") else (1080, 1920)
        from copy import deepcopy
        config = deepcopy(self.voice_studio_config)
        studio = config["enabled"]
        if studio and any(row.get("type") == "dialogue" for row in self.rows) and config["dialogue_a"] == config["dialogue_b"]:
            raise ValueError("VoiceStudio: hãy chọn hai giọng khác nhau cho A và B trong cửa sổ VoiceStudio.")
        return Settings(
            voice=("google:en" if config["main_language"].startswith("en") else "google:vi") if studio else VOICES[self.voice.get()],
            english_voice="voicestudio:english" if studio else VOICES[self.en_voice.get()],
            dialogue_voice_a="voicestudio:dialogue_a" if studio else VOICES[self.dialogue_voice_a.get()],
            dialogue_voice_b="voicestudio:dialogue_b" if studio else VOICES[self.dialogue_voice_b.get()],
            rate=rate, pitch=pitch, countdown=countdown, width=width, height=height,
            read_options=self.read_options.get(), read_explanation=self.read_explanation.get(), speech=self.speech.get(),
            brand=self.brand.get(), watermark_enabled=self.watermark_enabled.get(), logo_watermark_enabled=self.logo_watermark_enabled.get(), template=TEMPLATES[self.video_template.get()],
            background=self.background, background_dim=dim, music=self.music, music_volume=volume / 100,
            logo_image=self.logo_image, ending_image=self.ending_image, ending_text=self.ending_text.get(),
            left_logo_image=self.left_logo_image, right_chibi_image=self.right_chibi_image,
            left_logo_enabled=self.left_logo_enabled.get(), right_chibi_enabled=self.right_chibi_enabled.get(),
            voice_studio=config)

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
            self.stop_preview()
            index = max(0, min(self.selected.get() - 1, len(self.rows) - 1))
            self.selected.set(index + 1)
            settings = self.settings()
            theme = video_template(self.rows, self.quiz_title, settings.template)
            settings.template = theme
            from background_media import is_video
            settings.background_overlay = bool(settings.background and is_video(settings.background))
            self.template_label.configure(text=next(label.upper() for label, value in TEMPLATES.items() if value == theme))
            from content_timeline import thinking_seconds
            picture = frame(self.rows[index], index + 1, len(self.rows), self.quiz_title, settings, reveal=self.reveal.get(), countdown=thinking_seconds(self.rows[index], settings))
            picture.thumbnail((180, 220))
            self.preview_image = ImageTk.PhotoImage(picture)
            self.preview.configure(image=self.preview_image)
            if settings.background_overlay and self.host.active_tab is self:
                self.start_background_preview(settings, picture)
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
                self.mark_clean()
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
            self.mark_clean()

    def stop_background_preview(self):
        timer = getattr(self, "background_preview_timer", None)
        if timer:
            self.after_cancel(timer)
            self.background_preview_timer = None
        reader = getattr(self, "background_preview_reader", None)
        if reader:
            reader.close()
            self.background_preview_reader = None

    def start_background_preview(self, settings, overlay, offset=0):
        from background_media import VideoPreview, open_background
        from PIL import ImageOps
        self.stop_background_preview()
        self.background_preview_overlay = overlay.convert("RGBA")
        with open_background(settings.background) as source:
            self.background_preview_still = ImageOps.fit(source.convert("RGB"), overlay.size)
        reader = VideoPreview(settings.background, overlay.size, offset)
        self.background_preview_reader = reader

        def refresh():
            if self.background_preview_reader is not reader:
                return
            if reader.error:
                self.validation.configure(text=reader.error, foreground="#ba4247")
                self.stop_background_preview()
                return
            background = reader.image or self.background_preview_still
            picture = background.convert("RGBA")
            picture.alpha_composite(self.background_preview_overlay)
            self.preview_image = ImageTk.PhotoImage(picture)
            self.preview.configure(image=self.preview_image)
            self.background_preview_timer = self.after(33, refresh)

        refresh()

    def stop_preview(self):
        self.stop_background_preview()
        self.seek_preview = lambda value: None
        if getattr(self, "preview_cancel", None):
            self.preview_cancel.set()
        self.audio_player.stop()
        timer = getattr(self, "playback_timer", None)
        if timer:
            self.after_cancel(timer)
            self.playback_timer = None
        directory = getattr(self, "preview_directory", None)
        if directory:
            import shutil
            shutil.rmtree(directory, ignore_errors=True)
            self.preview_directory = None

    def play_preview(self, whole=False, ending_only=False):
        self.stop_preview()
        if self.busy or (not ending_only and not self.validate()):
            return
        from content_timeline import plan_item, prepare_scene, ending_scene, preview_audio
        try:
            settings = self.settings()
        except (ValueError, tk.TclError) as error:
            messagebox.showerror("Cài đặt", str(error), parent=self.winfo_toplevel())
            return
        settings.template = video_template(self.rows, self.quiz_title, settings.template)
        indexes = range(len(self.rows)) if whole else [self.selected.get()-1]
        rows, title = list(self.rows), self.quiz_title
        scenes = [] if ending_only else [(i, scene) for i in indexes for scene in plan_item(rows[i], settings)]
        if whole or ending_only:
            scenes.append((max(0, len(rows)-1), ending_scene(settings)))
        self.preview_cancel = threading.Event()
        cancel = self.preview_cancel
        self.preview_generation = getattr(self, "preview_generation", 0) + 1
        generation = self.preview_generation
        def prepare():
            directory = Path(tempfile.mkdtemp(prefix="quiz-preview-"))
            renderer = Renderer(settings, lambda text: self.events.put(("log", text)), cancel=cancel)
            try:
                from content_renderer import validate_layout
                if not ending_only:
                    validate_layout(title, rows, settings, renderer.check)
                prepared = [(i, prepare_scene(renderer, scene, directory, str(n), i+1)) for n, (i, scene) in enumerate(scenes)]
                audio = preview_audio(renderer, [p for _, p in prepared], directory)
                renderer.check()
                self.events.put(("preview_ready", (generation, rows, title, settings, prepared, directory, audio)))
            except Exception as error:
                import shutil
                shutil.rmtree(directory, ignore_errors=True)
                if cancel.is_set():
                    raise Cancelled("Đã dừng chuẩn bị xem trước.") from error
                raise
            return "Đã chuẩn bị preview."
        self.start_job(prepare)

    def begin_preview(self, data):
        generation, rows, title, settings, scenes, directory, audio = data
        if (generation != getattr(self, "preview_generation", 0) or self.preview_cancel.is_set()
                or self.host.active_tab is not self or self.closing):
            import shutil
            shutil.rmtree(directory, ignore_errors=True)
            return
        self.preview_directory = directory
        self.stop_background_preview()
        from background_media import is_video
        settings.background_overlay = bool(settings.background and is_video(settings.background))
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
                if settings.background_overlay and prepared.scene.phase != "ending":
                    if getattr(self, "background_preview_reader", None) is None:
                        self.start_background_preview(settings, picture, elapsed)
                    else:
                        self.background_preview_overlay = picture.convert("RGBA")
                else:
                    self.stop_background_preview()
                    self.preview_image = ImageTk.PhotoImage(picture)
                    self.preview.configure(image=self.preview_image)
                self.selected.set(index+1)
                self.preview_seek.set(elapsed)
                if started is None:
                    if audio:
                        self.audio_player.play(audio_source or audio)
                    started = time.monotonic()
                    started -= elapsed
                elapsed += prepared.seconds - offset
                self.playback_timer = self.after(max(1, round((started+elapsed-time.monotonic())*1000)), lambda: advance(position+1))
            except Exception as error:
                self.stop_preview()
                self.validation.configure(text=str(error), foreground="#ba4247")
        def seek(timestamp):
            nonlocal started, elapsed
            self.stop_background_preview()
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
                self.audio_player.stop()
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
        types = [("Ảnh hoặc video", "*.png *.jpg *.jpeg *.webp *.mp4 *.mov *.mkv *.webm *.avi *.m4v")] if kind == "background" else [("Âm thanh", "*.mp3 *.wav *.m4a *.aac")]
        path = filedialog.askopenfilename(filetypes=types)
        if path:
            try:
                if kind == "background":
                    saved = self.background_store.select(path, self.background_dim.get())
                    self.background = saved["background"]
                    self.background_name = saved["background_name"]
                    self.status.configure(text="Đã lưu nền vào thư viện để chọn lại trong những lần sau.")
                    self.refresh_background_library()
                else:
                    Renderer(Settings()).run(["-i", path, "-t", "0.1", "-map", "0:a:0", "-f", "null", "-"])
                    saved = self.user_store.select_music(path, self.user_settings())
                    self.music, self.music_name = saved["music"], saved["music_name"]
                    self.status.configure(text="Đã lưu nhạc nền. Lần mở app tiếp theo sẽ tự sử dụng nhạc này.")
            except Exception as error:
                messagebox.showerror("Không lưu được nền" if kind == "background" else "Không lưu được nhạc nền", str(error))
                return
            self.update_media_label()
            self.show_preview()

    def update_branding(self, state):
        for name, value in state.items():
            setattr(self, name, value)
        for kind, widget in self.branding_labels.items():
            widget.configure(text=getattr(self, kind + "_name") or "Ảnh mặc định")
        self.refresh_branding_library()

    def refresh_branding_library(self):
        try:
            self.branding_library_entries = self.branding_store.library()
            for kind, picker in self.branding_library_boxes.items():
                entries = self.branding_library_entries
                picker.configure(values=[f"{index + 1}. {entry['name']}" for index, entry in enumerate(entries)])
                if entries:
                    picker.current(next((index for index, entry in enumerate(entries)
                                         if entry["path"] == getattr(self, kind)), 0))
                else:
                    picker.set("Chưa có ảnh đã lưu")
        except (OSError, ValueError) as error:
            self.branding_library_entries = []
            messagebox.showerror("Không đọc được thư viện ảnh", str(error), parent=self.winfo_toplevel())

    def choose_saved_branding(self, kind):
        index = self.branding_library_boxes[kind].current()
        if not 0 <= index < len(self.branding_library_entries):
            return
        try:
            self.update_branding(self.branding_store.select_saved(kind, self.branding_library_entries[index]["path"]))
            if kind == "logo_image":
                self.logo_watermark_enabled.set(True)
            self.show_ending_preview() if kind == "ending_image" else self.show_preview()
            self.status.configure(text="Đã chọn ảnh từ thư viện cho tab này.")
        except (OSError, ValueError) as error:
            messagebox.showerror("Không chọn được ảnh", str(error), parent=self.winfo_toplevel())
            self.refresh_branding_library()

    def open_branding_library_folder(self):
        try:
            directory = self.branding_store.library_directory()
            directory.mkdir(parents=True, exist_ok=True)
            open_in_file_manager(directory)
        except OSError as error:
            messagebox.showerror("Không mở được thư viện ảnh", str(error), parent=self.winfo_toplevel())

    def choose_branding(self, kind):
        titles = {"logo_image": "Chọn logo chìm", "ending_image": "Chọn ảnh cuối video",
                  "left_logo_image": "Chọn logo góc trái", "right_chibi_image": "Chọn ảnh chibi góc phải"}
        path = filedialog.askopenfilename(parent=self.winfo_toplevel(),
            title=titles[kind],
            filetypes=[("Ảnh", "*.png *.jpg *.jpeg *.webp *.bmp")])
        if not path:
            return
        try:
            self.update_branding(self.branding_store.select(kind, path))
            if kind == "logo_image":
                self.logo_watermark_enabled.set(True)
            self.show_ending_preview() if kind == "ending_image" else self.show_preview()
            self.status.configure(text="Đã lưu ảnh. Lựa chọn chỉ thay đổi trong tab này.")
        except (OSError, ValueError) as error:
            messagebox.showerror("Không chọn được ảnh", str(error), parent=self.winfo_toplevel())

    def reset_branding(self, kind):
        try:
            self.update_branding(self.branding_store.reset(kind))
            self.show_ending_preview() if kind == "ending_image" else self.show_preview()
        except (OSError, ValueError) as error:
            messagebox.showerror("Không khôi phục được ảnh", str(error), parent=self.winfo_toplevel())

    def show_ending_preview(self):
        self.stop_preview()
        try:
            from content_renderer import render_ending
            picture = render_ending(self.settings())
            picture.thumbnail((180, 220))
            self.preview_image = ImageTk.PhotoImage(picture, master=self)
            self.preview.configure(image=self.preview_image)
            self.template_label.configure(text="ẢNH CUỐI VIDEO")
        except Exception as error:
            self.validation.configure(text=str(error), foreground="#ba4247")

    def refresh_background_library(self):
        try:
            self.background_library_entries = self.background_store.library()
            for kind, picker in self.background_library_boxes.items():
                entries = self.background_library_entries[kind]
                picker.configure(values=[f"{index + 1}. {entry['name']}" for index, entry in enumerate(entries)])
                if entries:
                    selected = next((index for index, entry in enumerate(entries)
                                     if entry["path"] == self.background), 0)
                    picker.current(selected)
                else:
                    picker.set("Chưa có nền đã lưu")
        except (OSError, ValueError) as error:
            self.background_library_entries = {"images": [], "videos": []}
            messagebox.showerror("Không đọc được thư viện nền", str(error))

    def choose_saved_background(self, kind):
        entries = self.background_library_entries.get(kind, [])
        index = self.background_library_boxes[kind].current()
        if not 0 <= index < len(entries):
            return
        try:
            saved = self.background_store.select_saved(entries[index]["path"], self.background_dim.get())
            self.background, self.background_name = saved["background"], saved["background_name"]
            self.update_media_label()
            self.show_preview()
            self.status.configure(text=f"Đã chọn nền từ thư viện: {self.background_name}")
        except (OSError, ValueError) as error:
            messagebox.showerror("Không chọn được nền", str(error))
            self.refresh_background_library()

    def open_background_library_folder(self, kind):
        try:
            directory = self.background_store.library_directory(kind)
            directory.mkdir(parents=True, exist_ok=True)
            open_in_file_manager(directory)
        except OSError as error:
            messagebox.showerror("Không mở được thư mục nền", str(error))

    def update_media_label(self):
        self.media_label.configure(text=f"Nền: {self.background_name or 'Chưa chọn'}\nNhạc: {self.music_name or 'Chưa chọn'}")

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
                self.background_store.save_selection(self.background, self.background_name, dim)
                return True
        except (ValueError, tk.TclError):
            pass
        except OSError as error:
            self.status.configure(text=f"Không lưu được mức làm tối nền: {error}")
        return False

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
        self.job_state = "0%" if exporting else "Đang chuẩn bị"
        self.host.update_tab(self)
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
        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def cancel_job(self):
        self.cancel.set()
        self.stop_preview()

    def voice_preview(self):
        if self.busy:
            return
        self.stop_preview()
        try:
            settings = self.settings()
        except Exception as error:
            messagebox.showerror("Cài đặt", str(error))
            return
        def job():
            self.events.put(("log", "Đang tạo giọng nghe thử…"))
            with tempfile.TemporaryDirectory(prefix="quiz-voice-") as temporary:
                directory = Path(temporary)
                target = directory / "preview.wav"
                text = "Xin chào! Bạn đã sẵn sàng cho câu hỏi tiếp theo chưa? [en]Welcome to the quiz challenge![/en]"
                if settings.voice.startswith("en") or settings.voice == "google:en":
                    text = "Welcome! Are you ready for the next question?"
                renderer = Renderer(settings, lambda text: self.events.put(("log", text)), cancel=self.cancel)
                asyncio.run(renderer.speech(text, target, directory))
                renderer.check()
                self.audio_player.play(target, wait=True, cancel=self.cancel)
                renderer.check()
            return "Đã phát giọng nghe thử."
        self.start_job(job)

    def export(self):
        if self.busy or not self.validate():
            return
        filename = datetime.now().strftime("%d-%m-%Y-%Hh%M%S") + f"-tab-{self.number}.mp4"
        path = filedialog.asksaveasfilename(defaultextension=".mp4", initialfile=filename, filetypes=[("Video MP4", "*.mp4")])
        if not path:
            return
        try:
            settings, rows, title = self.settings(), list(self.rows), self.quiz_title
        except (ValueError, tk.TclError) as error:
            messagebox.showerror("Cài đặt", str(error), parent=self.winfo_toplevel())
            return
        if not self.host.reserve_output(self, path):
            return
        def job():
            renderer = Renderer(settings, lambda text: self.events.put(("log", text)), self.cancel,
                                progress=lambda percent, message: self.events.put(("progress", (percent, message))))
            renderer.render(title, rows, path)
            return {"message": f"Đã xuất video: {path}", "path": str(Path(path).resolve()), "duration": renderer.duration}
        try:
            self.start_job(job, exporting=True)
        except Exception:
            self.host.release_output(self)
            raise

    def open_output_folder(self):
        if not self.last_output:
            return
        if not self.last_output.is_file():
            messagebox.showwarning("Không tìm thấy video", f"Video đã bị chuyển hoặc xóa:\n{self.last_output}")
            return
        try:
            open_in_file_manager(self.last_output, select=True)
        except OSError as error:
            messagebox.showerror("Không mở được thư mục", str(error))

    def poll(self):
        if getattr(self, "poll_timer", None):
            self.after_cancel(self.poll_timer)
            self.poll_timer = None
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
                    self.job_state = f"{int(percent)}%"
                    self.host.update_tab(self)
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
                    self.host.release_output(self)
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
                    self.job_state = {"done": "Xong", "cancel": "Đã hủy", "error": "Lỗi"}.get(kind, "")
                    self.host.update_tab(self)
                    if kind == "error" and not self.closing:
                        guidance = ("\n\nKiểm tra Internet rồi thử lại. Nếu giọng Edge tiếp tục lỗi, "
                                    "vào Giọng đọc và chọn Việt • Google (HTTP) hoặc English • Google (HTTP) "
                                    "cho đúng ngôn ngữ (kiểm tra cả giọng chính và giọng tiếng Anh). "
                                    "Bạn cũng có thể bỏ chọn Tạo giọng đọc để xuất offline.") if "(TTS)" in text and "VoiceStudio" not in text else ""
                        messagebox.showerror("Tác vụ thất bại", text + guidance)
        except queue.Empty:
            pass
        if self.closing and not self.busy:
            self.host.finish_close_tab(self)
            return
        self.poll_timer = self.after(100, self.poll)

    def destroy(self):
        if self.disposed:
            return
        self.cancel.set()
        self.stop_preview()
        self.disposed = True
        if self.voice_studio_window is not None and self.voice_studio_window.winfo_exists():
            self.voice_studio_window.destroy()
        for timer in list(self._timers):
            self.after_cancel(timer)
        super().destroy()


class App(tk.Tk):
    """Browser-style workspace tabs sharing only the saved media library."""

    def __init__(self, data_dir=None):
        super().__init__()
        self.title("Quiz Studio — Tạo video trắc nghiệm")
        self.geometry("1380x950")
        self.minsize(1100, 790)
        self.configure(bg="#edf2f4")
        from platform_support import data_directory
        self.data_dir = Path(data_dir) if data_dir is not None else data_directory()
        self.profiles = WorkspaceProfiles(self.data_dir)
        self.tabs = []
        self.active_tab = None
        self.next_tab_number = 1
        self.output_owners = {}
        self.closing = False
        self.tab_widgets = {}
        strip = tk.Frame(self, bg="#e7edef", height=44)
        strip.pack(fill="x")
        for text, command in (("‹", lambda: self.tab_canvas.xview_scroll(-2, "units")),
                              ("›", lambda: self.tab_canvas.xview_scroll(2, "units"))):
            tk.Button(strip, text=text, command=command, relief="flat", bg="#e7edef",
                      font=("Segoe UI", 16), width=2).pack(side="left")
        tk.Button(strip, text="+", command=self.new_tab, relief="flat", bg="#e7edef",
                  fg="#218c7c", font=("Segoe UI", 20), width=3).pack(side="right")
        self.tab_canvas = tk.Canvas(strip, height=44, bg="#e7edef", highlightthickness=0)
        self.tab_canvas.pack(side="left", fill="x", expand=True)
        self.tab_strip = tk.Frame(self.tab_canvas, bg="#e7edef")
        self.tab_canvas.create_window((0, 0), window=self.tab_strip, anchor="nw", height=44)
        self.tab_strip.bind("<Configure>", lambda event: self.tab_canvas.configure(
            scrollregion=self.tab_canvas.bbox("all")))
        self.workspace = tk.Frame(self, bg="#f5f7fa")
        self.workspace.pack(fill="both", expand=True)
        self.bind("<Control-t>", lambda event: self._shortcut(self.new_tab))
        self.bind("<Control-w>", lambda event: self._shortcut(lambda: self.close_tab(self.active_tab)))
        self.bind("<Control-Tab>", lambda event: self._shortcut(lambda: self.cycle_tab(1)))
        self.bind("<Control-Shift-Tab>", lambda event: self._shortcut(lambda: self.cycle_tab(-1)))
        if sys.platform == "darwin":
            self.bind("<Command-t>", lambda event: self._shortcut(self.new_tab))
            self.bind("<Command-w>", lambda event: self._shortcut(lambda: self.close_tab(self.active_tab)))
        self.protocol("WM_DELETE_WINDOW", lambda: self.close(confirm=True))
        profiles = self.profiles.load()
        for profile in profiles:
            self._add_tab(profile, activate=False)
        self.select_tab(self.tabs[0])
        if self.profiles.warning:
            self.active_tab.status.configure(text=self.profiles.warning)
        self.save_workspace()

    @staticmethod
    def _shortcut(action):
        action()
        return "break"

    def new_tab(self):
        if self.closing:
            return None
        if self.active_tab and not self.active_tab.persist():
            return None
        profile = self.profiles.new_record(self.next_tab_number)
        try:
            tab = self._add_tab(profile, source_id=self.active_tab.profile_id if self.active_tab else None)
        except OSError as error:
            messagebox.showerror("Không tạo được tab", str(error), parent=self)
            return None
        self.save_workspace()
        return tab

    def save_workspace(self, tabs=None):
        records = [{"id": tab.profile_id, "name": tab.tab_name}
                   for tab in (self.tabs if tabs is None else tabs) if not tab.closing]
        try:
            self.profiles.save(records)
            return True
        except (OSError, ValueError) as error:
            messagebox.showerror("Không lưu được danh sách tab", str(error), parent=self)
            return False

    def _add_tab(self, profile, *, activate=True, source_id=None):
        config_dir = self.profiles.prepare(profile, source_id=source_id)
        tab = VideoTab(self, self.next_tab_number, profile, config_dir)
        self.next_tab_number += 1
        self.tabs.append(tab)
        holder = tk.Frame(self.tab_strip, bg="white", padx=1, pady=4)
        holder.pack(side="left", padx=(0, 3), fill="y")
        select = tk.Button(holder, text="", command=lambda: self.select_tab(tab), relief="flat",
                           anchor="w", width=23, font=("Segoe UI", 10), padx=10)
        select.pack(side="left", fill="y")
        select.bind("<Double-Button-1>", lambda event: self.rename_tab(tab))
        menu = tk.Menu(select, tearoff=False)
        menu.add_command(label="Đổi tên tab…", command=lambda: self.rename_tab(tab))
        menu.add_command(label="Đóng tab", command=lambda: self.close_tab(tab))
        def show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        select.bind("<Button-3>", show_menu)
        close = tk.Button(holder, text="×", command=lambda: self.close_tab(tab), relief="flat",
                          width=2, font=("Segoe UI", 13))
        close.pack(side="right", fill="y")
        self.tab_widgets[tab] = (holder, select, close)
        if activate:
            self.select_tab(tab)
        else:
            self.update_tab(tab)
        return tab

    def update_tab(self, tab):
        widgets = self.tab_widgets.get(tab)
        if not widgets:
            return
        state = "Đang đóng" if tab.closing else tab.job_state
        caption = tab.tab_name + (" *" if tab.dirty else "")
        if state:
            caption += " · " + state
        color = "white" if tab is self.active_tab else "#e7edef"
        widgets[0].configure(bg=color)
        widgets[1].configure(text=caption, bg=color, fg="#218c7c" if tab is self.active_tab else "#526170")
        widgets[2].configure(bg=color)
        if tab is self.active_tab:
            self.title(f"{tab.tab_name} — Quiz Studio")

    def rename_tab(self, tab, name=None):
        if tab not in self.tabs or tab.closing:
            return False
        if name is None:
            name = simpledialog.askstring("Đổi tên tab", "Tên tab mới:", initialvalue=tab.tab_name, parent=self)
        if name is None:
            return False
        name = " ".join(name.split())
        if not name or len(name) > 80:
            messagebox.showwarning("Tên tab không hợp lệ", "Tên tab cần có từ 1 đến 80 ký tự.", parent=self)
            return False
        previous = tab.tab_name
        tab.tab_name = name
        if not self.save_workspace():
            tab.tab_name = previous
            return False
        self.update_tab(tab)
        return True

    def select_tab(self, tab):
        if tab not in self.tabs or self.closing:
            return
        outgoing = self.active_tab
        if outgoing is not tab:
            if outgoing:
                outgoing.stop_preview()
                if outgoing.busy and not outgoing.job_exporting:
                    outgoing.cancel.set()
                outgoing.pack_forget()
            self.active_tab = tab
            tab.pack(fill="both", expand=True)
            if not tab.busy:
                tab.show_preview()
            tab.refresh_background_library()
            tab.refresh_branding_library()
            tab.text.focus_set()
        for item in self.tabs:
            self.update_tab(item)
        self.title(f"{tab.tab_name} — Quiz Studio")
        self.update_idletasks()
        holder = self.tab_widgets[tab][0]
        left, right = holder.winfo_x(), holder.winfo_x() + holder.winfo_width()
        view_left = self.tab_canvas.canvasx(0)
        width = self.tab_canvas.winfo_width()
        total = max(1, self.tab_strip.winfo_reqwidth())
        if left < view_left:
            self.tab_canvas.xview_moveto(left / total)
        elif right > view_left + width:
            self.tab_canvas.xview_moveto(max(0, right - width) / total)

    def cycle_tab(self, direction):
        if self.tabs:
            self.select_tab(self.tabs[(self.tabs.index(self.active_tab) + direction) % len(self.tabs)])

    def reserve_output(self, tab, path):
        key = os.path.normcase(str(Path(path).resolve()))
        if key in self.output_owners:
            other = self.output_owners[key]
            messagebox.showwarning("File đang được xuất",
                f"{other.tab_name} đang xuất vào file này. Hãy chọn tên file khác.", parent=self)
            return False
        self.output_owners[key] = tab
        tab.export_path = key
        return True

    def release_output(self, tab):
        if self.output_owners.get(tab.export_path) is tab:
            del self.output_owners[tab.export_path]
        tab.export_path = None

    def close_tab(self, tab, confirm=True):
        if tab not in self.tabs or tab.closing:
            return
        if confirm and (tab.busy or tab.dirty):
            reason = "Tab đang xử lý video. Đóng sẽ hủy tác vụ." if tab.busy else "Tab có nội dung chưa lưu JSON."
            if not messagebox.askyesno("Đóng tab", reason + "\nBạn có muốn đóng tab này?", parent=self):
                return
        if not tab.persist():
            return
        if not self.save_workspace([item for item in self.tabs if item is not tab]):
            return
        tab.closing = True
        tab.cancel_job()
        self.update_tab(tab)
        if not tab.busy:
            self.finish_close_tab(tab)

    def finish_close_tab(self, tab):
        if tab not in self.tabs:
            return
        index = self.tabs.index(tab)
        self.tabs.remove(tab)
        self.release_output(tab)
        self.tab_widgets.pop(tab)[0].destroy()
        was_active = self.active_tab is tab
        if was_active:
            self.active_tab = None
        tab.destroy()
        if self.closing:
            if not self.tabs:
                self.destroy()
        elif was_active:
            if self.tabs:
                self.select_tab(self.tabs[min(index, len(self.tabs) - 1)])
            else:
                self.new_tab()

    def close(self, confirm=False):
        if self.closing:
            return
        if confirm and any(tab.busy or tab.dirty for tab in self.tabs):
            if not messagebox.askyesno("Đóng Quiz Studio",
                    "Nội dung chưa lưu JSON sẽ mất và các tác vụ đang chạy sẽ bị hủy.\nĐóng tất cả tab?", parent=self):
                return
        if not all(tab.persist() for tab in self.tabs):
            return
        if not self.save_workspace():
            return
        self.closing = True
        for tab in list(self.tabs):
            tab.closing = True
            tab.cancel_job()
            self.update_tab(tab)
            if not tab.busy:
                self.finish_close_tab(tab)

    def destroy(self):
        # Only the entire window owns shared CustomTkinter callbacks.
        for child in list(self.winfo_children()):
            child.destroy()
        for timer in self.tk.call("after", "info"):
            self.after_cancel(timer)
        super().destroy()


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        report = Path(sys.argv[sys.argv.index("--self-check") + 1])
        try:
            check_data = tempfile.TemporaryDirectory(prefix="quiz-self-check-")
            host = App(data_dir=check_data.name)
            host.withdraw()
            host.update_idletasks()
            app = host.active_tab
            assert [tab.tab_name for tab in host.tabs] == ["Một chút English", "Easy Prep", "ASVAB-Prep"]
            assert app is host.tabs[0]
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
            second = host.new_tab()
            second.brand.set("VIDEO 2")
            assert second.brand.get() != app.brand.get()
            assert second.events is not app.events and second.cancel is not app.cancel
            host.select_tab(app)
            host.close_tab(second, confirm=False)
            assert host.active_tab is app and len(host.tabs) == 3
            app.show_ending_preview()
            for index, tab in enumerate(host.tabs):
                tab.brand.set(f"PROFILE {index}")
                tab.countdown.set(index + 3)
            host.rename_tab(host.tabs[1], "Easy Prep đã lưu")
            host.select_tab(host.tabs[2])
            host.close()
            host = App(data_dir=check_data.name)
            host.withdraw()
            assert len(host.tabs) == 3 and host.active_tab is host.tabs[0]
            assert host.tabs[1].tab_name == "Easy Prep đã lưu"
            for index, tab in enumerate(host.tabs):
                assert tab.brand.get() == f"PROFILE {index}"
                assert tab.countdown.get() == index + 3
            host.close()
            check_data.cleanup()
            report.write_text(json.dumps({"ok": True, "questions": 2, "default_mode": DEFAULT_MODE, "content_types": len(REGISTRY), "ffmpeg": ffmpeg, "progress_and_output_button": True, "workspace_tabs": True, "profile_persistence": True}), encoding="utf-8")
        except Exception as error:
            report.write_text(json.dumps({"ok": False, "error": str(error)}), encoding="utf-8")
            sys.exit(1)
    else:
        App().mainloop()
