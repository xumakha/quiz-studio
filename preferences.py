"""Durable, per-user settings and copied media, outside the packaged app."""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from platform_support import data_directory

from background_media import validate_background, is_video, VIDEO_EXTENSIONS
from content_timeline import DEFAULT_ENDING_TEXT


USER_DEFAULTS = {
    "voice": "Việt • Google (HTTP)", "en_voice": "English • Google (HTTP)",
    "dialogue_voice_a": "English • Female — Jenny", "dialogue_voice_b": "English • Male — Guy",
    "rate": 0, "pitch": 0, "countdown": 5, "resolution": "1080 × 1920",
    "video_template": "Tự động theo môn học", "brand": "QUIZ STUDIO",
    "watermark_enabled": True, "read_options": True, "read_explanation": True, "speech": True,
    "music_volume": 12, "reveal": False,
    "ending_text": DEFAULT_ENDING_TEXT,
    "left_logo_enabled": True, "right_chibi_enabled": True,
}


class UserSettingsStore:
    def __init__(self, directory, *, config_dir=None):
        self.directory = Path(directory)
        self.config = (Path(config_dir) if config_dir is not None else self.directory) / "settings.json"
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
        self.config.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.config.parent,
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
    def __init__(self, directory=None, *, config_dir=None):
        self.directory = Path(directory) if directory is not None else data_directory()
        self.config = (Path(config_dir) if config_dir is not None else self.directory) / "background.json"
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
        self.config.parent.mkdir(parents=True, exist_ok=True)
        data = {"file": Path(state["background"]).name if state["background"] else "",
                "name": state["background_name"], "background_dim": state["background_dim"]}
        data["folder"] = (Path(state["background"]).parent.name
                          if state["background"] and Path(state["background"]).parent.name in ("images", "videos") else "")
        # A failed write leaves the previous selection intact.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.config.parent,
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

    def save_selection(self, background, name, dim):
        """Persist this tab's complete selection without loading another tab's."""
        self._save({"background": background, "background_name": name, "background_dim": dim})

    def clear(self, dim):
        self._save({"background": "", "background_name": "", "background_dim": dim})


class BrandingStore:
    """Copy selected artwork durably while keeping each tab's selection separate."""

    KINDS = ("logo_image", "ending_image", "left_logo_image", "right_chibi_image")

    def __init__(self, directory=None, *, config_dir=None):
        self.directory = Path(directory) if directory is not None else data_directory()
        self.config = (Path(config_dir) if config_dir is not None else self.directory) / "branding.json"
        self.warning = ""
        self._state = None

    @staticmethod
    def _validate_image(path):
        from PIL import Image
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
            raise ValueError("Hãy chọn ảnh PNG, JPG, WebP, BMP hoặc GIF.")
        with Image.open(path) as source:
            source.load()

    def load(self):
        state = {key: "" for kind in self.KINDS for key in (kind, kind + "_name")}
        self.warning = ""
        try:
            data = json.loads(self.config.read_text(encoding="utf-8")) if self.config.exists() else {}
            if not isinstance(data, dict):
                raise ValueError("Cài đặt ảnh phải là object.")
        except (OSError, ValueError) as error:
            data = {}
            self.warning = f"Không nạp được ảnh logo / kết thúc đã lưu: {error}"
        warnings = [self.warning] if self.warning else []
        for kind in self.KINDS:
            try:
                entry = data.get(kind, {})
                if not isinstance(entry, dict):
                    raise ValueError("Cài đặt ảnh không hợp lệ.")
                filename = entry.get("file", "")
                if not filename:
                    continue
                if not isinstance(filename, str) or Path(filename).name != filename:
                    raise ValueError("Tên file ảnh đã lưu không hợp lệ.")
                path = self.directory / "branding" / "images" / filename
                self._validate_image(path)
                state[kind] = str(path.resolve())
                state[kind + "_name"] = str(entry.get("name", filename))
            except (OSError, ValueError) as error:
                label = {"logo_image": "logo chìm", "ending_image": "kết thúc",
                         "left_logo_image": "logo góc trái", "right_chibi_image": "chibi góc phải"}[kind]
                warnings.append(f"Không nạp được ảnh {label}; dùng ảnh mặc định. ({error})")
        self.warning = "\n".join(warnings)
        # Before separate corner controls, the selected watermark also supplied
        # the left corner. Retain that image when upgrading an existing config.
        if "left_logo_image" not in data:
            state["left_logo_image"] = state["logo_image"]
            state["left_logo_image_name"] = state["logo_image_name"]
        self._state = state
        return dict(state)

    def _save(self, state):
        self.config.parent.mkdir(parents=True, exist_ok=True)
        data = {kind: {"file": Path(state[kind]).name if state[kind] else "",
                       "name": state[kind + "_name"]} for kind in self.KINDS}
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.config.parent,
                                         suffix=".json", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
        try:
            os.replace(temporary, self.config)
        finally:
            temporary.unlink(missing_ok=True)
        self._state = dict(state)
        return dict(state)

    def select(self, kind, source):
        if kind not in self.KINDS:
            raise ValueError("Loại ảnh không hợp lệ.")
        source = Path(source)
        self._validate_image(source)
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        assets = self.directory / "branding" / "images"
        assets.mkdir(parents=True, exist_ok=True)
        target = assets / (digest + source.suffix.lower())
        if not target.exists():
            BackgroundStore._copy_asset(source, target)
        BackgroundStore._save_name(target, source.name)
        state = dict(self._state if self._state is not None else self.load())
        state.update({kind: str(target.resolve()), kind + "_name": source.name})
        return self._save(state)

    def library_directory(self):
        return self.directory / "branding" / "images"

    def library(self):
        """All pickers can reuse any previously uploaded branding image."""
        assets = self.library_directory()
        assets.mkdir(parents=True, exist_ok=True)
        state = self._state if self._state is not None else self.load()
        entries = []
        for path in assets.iterdir():
            if not path.is_file() or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
                continue
            name = next((state[kind + "_name"] for kind in self.KINDS
                         if state[kind] == str(path.resolve())), path.name)
            try:
                metadata = json.loads(path.with_suffix(path.suffix + ".json").read_text(encoding="utf-8"))
                name = str(metadata["name"])
            except (OSError, ValueError, KeyError, TypeError):
                pass
            entries.append({"path": str(path.resolve()), "name": name})
        return sorted(entries, key=lambda entry: (entry["name"].casefold(), entry["path"]))

    def select_saved(self, kind, path):
        if kind not in self.KINDS:
            raise ValueError("Loại ảnh không hợp lệ.")
        selected = Path(path).resolve()
        entry = next((entry for entry in self.library() if Path(entry["path"]) == selected), None)
        if entry is None:
            raise ValueError("Ảnh không còn trong thư viện. Hãy tải lên lại.")
        self._validate_image(selected)
        state = dict(self._state if self._state is not None else self.load())
        state.update({kind: entry["path"], kind + "_name": entry["name"]})
        return self._save(state)

    def reset(self, kind):
        if kind not in self.KINDS:
            raise ValueError("Loại ảnh không hợp lệ.")
        state = dict(self._state if self._state is not None else self.load())
        state.update({kind: "", kind + "_name": ""})
        return self._save(state)

    def save(self):
        """Make this instance's selection the default for the next launch."""
        state = self._state if self._state is not None else self.load()
        return self._save(state)
