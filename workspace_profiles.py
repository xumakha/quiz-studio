"""Stable workspace identities with separate settings and a shared media library."""
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

from preferences import BackgroundStore, BrandingStore, USER_DEFAULTS
from voice_studio import DEFAULTS as VOICE_STUDIO_DEFAULTS


DEFAULT_PROFILES = (
    ("mot-chut-english", "Một chút English"),
    ("easy-prep", "Easy Prep"),
    ("asvab-prep", "ASVAB-Prep"),
    ("easy-pass", "easy-pass.app"),
    ("dmv-prep", "dmv-prep.org"),
)
DEFAULT_IDS = frozenset(profile_id for profile_id, _ in DEFAULT_PROFILES)
CONFIG_FILES = ("settings.json", "background.json", "branding.json", "voicestudio.json")


class WorkspaceProfiles:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.config = self.directory / "tabs.json"
        self.warning = ""
        self._records = None

    @staticmethod
    def _valid_id(profile_id):
        return (isinstance(profile_id, str)
                and (profile_id in DEFAULT_IDS or re.fullmatch(r"extra-[0-9a-f]{32}", profile_id)))

    @classmethod
    def _validate_records(cls, records):
        if not isinstance(records, list):
            raise ValueError("Danh sách tab không hợp lệ.")
        result, seen = [], set()
        for record in records:
            if not isinstance(record, dict) or not cls._valid_id(record.get("id")):
                raise ValueError("Mã tab không hợp lệ.")
            profile_id, name = record["id"], record.get("name")
            if profile_id in seen:
                raise ValueError("Mã tab bị trùng.")
            if not isinstance(name, str) or not name.strip() or len(name) > 80:
                raise ValueError("Tên tab cần có từ 1 đến 80 ký tự.")
            result.append({"id": profile_id, "name": " ".join(name.split())})
            seen.add(profile_id)
        return result

    @staticmethod
    def _with_defaults(records, previous=()):
        names = {profile_id: name for profile_id, name in DEFAULT_PROFILES}
        names.update({record["id"]: record["name"] for record in previous if record["id"] in DEFAULT_IDS})
        names.update({record["id"]: record["name"] for record in records if record["id"] in DEFAULT_IDS})
        return ([{"id": profile_id, "name": names[profile_id]} for profile_id, _ in DEFAULT_PROFILES]
                + [dict(record) for record in records if record["id"] not in DEFAULT_IDS])

    def load(self):
        self.warning = ""
        records = []
        try:
            if self.config.exists():
                data = json.loads(self.config.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
                    raise ValueError("Định dạng cài đặt tab không hợp lệ.")
                records = self._validate_records(data.get("tabs"))
        except (OSError, ValueError) as error:
            self.warning = f"Không nạp được danh sách tab đã lưu; mở các tab mặc định. ({error})"
        self._records = self._with_defaults(records)
        return [dict(record) for record in self._records]

    @staticmethod
    def _write_json(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".json", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
        try:
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, records):
        records = self._validate_records(records)
        if self._records is None:
            self.load()
        saved = self._with_defaults(records, self._records)
        self._write_json(self.config, {"version": 1, "tabs": saved})
        self._records = saved

    @staticmethod
    def new_record(number):
        return {"id": "extra-" + uuid.uuid4().hex, "name": f"Video {number}"}

    def _profile_directory(self, profile_id):
        if not self._valid_id(profile_id):
            raise ValueError("Mã tab không hợp lệ.")
        path = self.directory / "profiles" / profile_id
        if not path.resolve().is_relative_to(self.directory.resolve()):
            raise ValueError("Thư mục tab nằm ngoài thư mục dữ liệu.")
        return path

    def prepare(self, record, source_id=None):
        """Seed missing config files once, preserving existing and legacy files."""
        record = self._validate_records([record])[0]
        profile_id = record["id"]
        target = self._profile_directory(profile_id)
        source = None
        if source_id is not None:
            source = self._profile_directory(source_id)
        elif profile_id == "mot-chut-english":
            source = self.directory
        settings = dict(USER_DEFAULTS)
        if profile_id in DEFAULT_IDS:
            settings["brand"] = record["name"]
        if profile_id in ("easy-prep", "asvab-prep", "easy-pass", "dmv-prep"):
            settings["ending_text"] = ""
            settings["video_template"] = "Quân sự · ASVAB" if profile_id == "asvab-prep" else "Luyện thi · Chứng chỉ"
            settings.update(left_logo_enabled=False, right_chibi_enabled=False, watermark_enabled=False, logo_watermark_enabled=False)
        if profile_id == "easy-pass":
            settings["video_template"] = "easy-pass.app · Xanh nhạt"
        if profile_id == "dmv-prep":
            settings["video_template"] = "dmv-prep.org · Luyện thi lái xe"
        settings.update(music_file="", music_name="")
        defaults = {
            "voicestudio.json": VOICE_STUDIO_DEFAULTS,
            "settings.json": settings,
            "background.json": {"file": "", "name": "", "background_dim": 12, "folder": ""},
            "branding.json": {kind: {"file": "", "name": ""} for kind in BrandingStore.KINDS},
        }
        target.mkdir(parents=True, exist_ok=True)
        for filename in CONFIG_FILES:
            destination = target / filename
            if destination.exists():
                continue
            original = source / filename if source is not None else None
            if original is not None and original.is_file():
                BackgroundStore._copy_asset(original, destination)
            else:
                self._write_json(destination, defaults[filename])
        # Upgrade existing prep tabs once; preserve manually selected templates.
        if profile_id in ("easy-prep", "asvab-prep") and source_id is None:
            path = target / "settings.json"
            marker = target / ".prep-layout-v1"
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(current, dict) and not marker.exists():
                    if current.get("video_template", "Tự động theo môn học") == "Tự động theo môn học":
                        current["video_template"] = settings["video_template"]
                        branding = json.loads((target / "branding.json").read_text(encoding="utf-8"))
                        for flag, asset in (("left_logo_enabled", "left_logo_image"),
                                            ("right_chibi_enabled", "right_chibi_image"),
                                            ("watermark_enabled", "logo_image")):
                            entry = branding.get(asset, {}) if isinstance(branding, dict) else None
                            if isinstance(entry, dict) and not entry.get("file"):
                                current[flag] = False
                    self._write_json(path, current)
                    marker.write_text("1", encoding="utf-8")
            except (OSError, ValueError):
                pass  # The settings store reports malformed files to the user.
        if profile_id == "easy-pass" and source_id is None:
            path = target / "settings.json"
            marker = target / ".easy-pass-blue-v1"
            if not marker.exists():
                try:
                    current = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(current, dict):
                        if current.get("video_template", "Tự động theo môn học") in (
                                "Tự động theo môn học", "Luyện thi · Chứng chỉ"):
                            current["video_template"] = settings["video_template"]
                            self._write_json(path, current)
                        marker.write_text("1", encoding="utf-8")
                except (OSError, ValueError):
                    pass  # The settings store reports malformed files.
        return target
