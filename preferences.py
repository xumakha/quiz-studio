"""Durable, per-user settings and copied media, outside the packaged app."""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from platform_support import data_directory

from background_media import validate_background, is_video, VIDEO_EXTENSIONS


USER_DEFAULTS = {
    "voice": "Việt • Google (HTTP)", "en_voice": "English • Google (HTTP)",
    "dialogue_voice_a": "English • Female — Jenny", "dialogue_voice_b": "English • Male — Guy",
    "rate": 0, "pitch": 0, "countdown": 5, "resolution": "1080 × 1920",
    "video_template": "Tự động theo môn học", "brand": "QUIZ STUDIO",
    "watermark_enabled": True, "read_options": True, "read_explanation": True, "speech": True,
    "music_volume": 12, "reveal": False,
}


class UserSettingsStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.config = self.directory / "settings.json"
        self.music_file = ""
        self.music_name = ""
        self.warning = ""

    @staticmethod
    def validated(data):
        from engine import VOICES
        from video_themes import TEMPLATES
        choices = {"voice": VOICES, "en_voice": [k for k, v in VOICES.items() if v.startswith("en") or v == "google:en"],
                   "resolution": ["1080 × 1920", "720 × 1280"], "video_template": TEMPLATES}
        choices.update({key: choices["en_voice"] for key in ("dialogue_voice_a", "dialogue_voice_b")})
        ranges = {"rate": (-50, 100), "pitch": (-50, 50), "countdown": (1, 30), "music_volume": (0, 100)}
        result = dict(USER_DEFAULTS)
        for key, default in USER_DEFAULTS.items():
            value = data.get(key, default)
            if type(value) is not type(default):
                continue
            if key in choices and value not in choices[key]:
                continue
            if key in ranges and not ranges[key][0] <= value <= ranges[key][1]:
                continue
            result[key] = value
        return result

    def load(self):
        self.warning = ""
        self.music_file = self.music_name = ""
        data = {}
        try:
            if self.config.exists():
                data = json.loads(self.config.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Cài đặt phải là object.")
        except (OSError, ValueError) as error:
            data = {}
            self.warning = f"Không nạp được cài đặt đã lưu: {error}"
        state = self.validated(data)
        state.update(music="", music_name="")
        filename = data.get("music_file", "")
        if filename:
            try:
                if not isinstance(filename, str) or Path(filename).name != filename:
                    raise ValueError("Tên file nhạc đã lưu không hợp lệ.")
                path = self.directory / "music" / filename
                if not path.is_file() or not path.stat().st_size:
                    raise ValueError("File nhạc đã lưu không còn tồn tại hoặc rỗng.")
                self.music_file = filename
                self.music_name = str(data.get("music_name", filename))
                state.update(music=str(path.resolve()), music_name=self.music_name)
            except (OSError, ValueError) as error:
                self.warning = f"Không nạp được nhạc nền đã lưu. Hãy chọn lại nhạc. ({error})"
        return state

    def save(self, settings, music_file=None, music_name=None):
        filename = self.music_file if music_file is None else music_file
        name = self.music_name if music_name is None else music_name
        data = self.validated(settings)
        data.update(music_file=filename, music_name=name)
        self.directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                         suffix=".json", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
        try:
            os.replace(temporary, self.config)
        finally:
            temporary.unlink(missing_ok=True)
        self.music_file, self.music_name = filename, name

    def select_music(self, source, settings):
        source = Path(source)
        if not source.is_file() or not source.stat().st_size:
            raise ValueError("File nhạc không tồn tại hoặc rỗng.")
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        assets = self.directory / "music"
        assets.mkdir(parents=True, exist_ok=True)
        target = assets / (digest + source.suffix.lower())
        if not target.exists():
            with tempfile.NamedTemporaryFile(dir=assets, delete=False) as stream:
                temporary = Path(stream.name)
            try:
                shutil.copyfile(source, temporary)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        self.save(settings, target.name, source.name)
        return {"music": str(target.resolve()), "music_name": source.name}

    def clear_music(self, settings):
        self.save(settings, "", "")


class BackgroundStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else data_directory()
        self.config = self.directory / "background.json"
        self.warning = ""

    def library_directory(self, kind):
        if kind not in ("images", "videos"):
            raise ValueError("Loại nền không hợp lệ.")
        return self.directory / "backgrounds" / kind

    def library(self):
        """Keep legacy uploads available; copying avoids losing old selections."""
        for kind in ("images", "videos"):
            self.library_directory(kind).mkdir(parents=True, exist_ok=True)
        try:
            saved = json.loads(self.config.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                saved = {}
        except (OSError, ValueError):
            saved = {}
        extensions = VIDEO_EXTENSIONS | {".png", ".jpg", ".jpeg", ".webp"}
        for source in (self.directory / "backgrounds").iterdir():
            if source.is_file() and source.suffix.lower() in extensions:
                target = self.library_directory("videos" if is_video(source) else "images") / source.name
                if not target.exists():
                    self._copy_asset(source, target)
                if source.name == saved.get("file") and not target.with_suffix(target.suffix + ".json").exists():
                    self._save_name(target, str(saved.get("name", source.name)))
        entries = {"images": [], "videos": []}
        for kind in entries:
            for path in self.library_directory(kind).iterdir():
                if not path.is_file() or path.suffix.lower() not in extensions:
                    continue
                name = path.name
                try:
                    metadata = json.loads(path.with_suffix(path.suffix + ".json").read_text(encoding="utf-8"))
                    name = str(metadata["name"])
                except (OSError, ValueError, KeyError, TypeError):
                    pass
                entries[kind].append({"path": str(path.resolve()), "name": name})
            entries[kind].sort(key=lambda entry: (entry["name"].casefold(), entry["path"]))
        return entries

    @staticmethod
    def _copy_asset(source, target):
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            shutil.copyfile(source, temporary)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _save_name(target, name):
        metadata = target.with_suffix(target.suffix + ".json")
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"name": name}, stream, ensure_ascii=False)
        try:
            os.replace(temporary, metadata)
        finally:
            temporary.unlink(missing_ok=True)

    def select_saved(self, path, dim):
        selected = Path(path).resolve()
        entries = self.library()
        entry = next((entry for group in entries.values() for entry in group
                      if Path(entry["path"]) == selected), None)
        if entry is None:
            raise ValueError("Nền không còn trong thư viện. Hãy tải lên lại.")
        validate_background(selected)
        state = {"background": str(selected), "background_name": entry["name"], "background_dim": dim}
        self._save(state)
        return state

    def load(self):
        state = {"background": "", "background_name": "", "background_dim": 12}
        self.warning = ""
        try:
            if not self.config.exists():
                return state
            data = json.loads(self.config.read_text(encoding="utf-8"))
            dim = data.get("background_dim", 12)
            if type(dim) is int and 0 <= dim <= 70:
                state["background_dim"] = dim
            filename = data.get("file", "")
            if filename:
                if not isinstance(filename, str) or Path(filename).name != filename:
                    raise ValueError("Tên file nền đã lưu không hợp lệ.")
                folder = data.get("folder", "")
                if folder not in ("", "images", "videos"):
                    raise ValueError("Thư mục nền không hợp lệ.")
                path = self.directory / "backgrounds" / folder / filename
                validate_background(path)
                state.update(background=str(path.resolve()), background_name=str(data.get("name", filename)))
        except (OSError, ValueError, TypeError, AttributeError) as error:
            self.warning = f"Không nạp được nền đã lưu. Hãy chọn lại ảnh hoặc video nền. ({error})"
        return state

    def _save(self, state):
        self.directory.mkdir(parents=True, exist_ok=True)
        data = {"file": Path(state["background"]).name if state["background"] else "",
                "name": state["background_name"], "background_dim": state["background_dim"]}
        data["folder"] = (Path(state["background"]).parent.name
                          if state["background"] and Path(state["background"]).parent.name in ("images", "videos") else "")
        # A failed write leaves the previous selection intact.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                         suffix=".json", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
        try:
            os.replace(temporary, self.config)
        finally:
            temporary.unlink(missing_ok=True)

    def select(self, source, dim):
        source = Path(source)
        validate_background(source)
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        assets = self.library_directory("videos" if is_video(source) else "images")
        assets.mkdir(parents=True, exist_ok=True)
        target = assets / (digest + source.suffix.lower())
        if not target.exists():
            self._copy_asset(source, target)
        self._save_name(target, source.name)
        state = {"background": str(target.resolve()), "background_name": source.name, "background_dim": dim}
        self._save(state)
        return state

    def save_dim(self, dim):
        state = self.load()
        state["background_dim"] = dim
        self._save(state)

    def clear(self, dim):
        self._save({"background": "", "background_name": "", "background_dim": dim})
