"""VoiceStudio API integration; models stay in its independent AI runtime."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

import requests


DEFAULTS = {
    "enabled": False, "url": "http://127.0.0.1:3900", "api_key": "",
    "engine": "omnivoice", "main_voice": "default", "english_voice": "default",
    "dialogue_a": "default", "dialogue_b": "default", "main_language": "vi",
    "instructions": "", "description": "", "num_step": 16,
    "guidance_scale": 2.0, "seed": -1, "denoise": True,
    "preprocess_prompt": True, "timeout": 600,
}


class VoiceStudioError(RuntimeError):
    pass


def validated(data, *, strict=False):
    result = deepcopy(DEFAULTS)
    if not isinstance(data, dict):
        if strict:
            raise ValueError("Cài đặt VoiceStudio phải là object.")
        return result
    ranges = {"num_step": (1, 128), "guidance_scale": (0.01, 20),
              "seed": (-1, 2147483647), "timeout": (15, 1800)}
    for key, default in DEFAULTS.items():
        value = data.get(key, default)
        valid_type = (type(value) in (int, float) if isinstance(default, float)
                      else type(value) is type(default))
        okay = valid_type
        if okay and key in ranges:
            okay = math.isfinite(value) and ranges[key][0] <= value <= ranges[key][1]
        if okay and isinstance(default, str):
            okay = len(value) <= (4096 if key in ("instructions", "description") else 2048)
        if not okay:
            if strict:
                raise ValueError(f"Giá trị VoiceStudio không hợp lệ: {key}.")
            continue
        result[key] = value
    try:
        result["url"] = normalized_url(result["url"])
        for key in ("engine", "main_voice", "english_voice", "dialogue_a", "dialogue_b", "main_language"):
            result[key] = result[key].strip()
            if not result[key]:
                raise ValueError(f"Hãy nhập {key} cho VoiceStudio.")
        if "\n" in result["api_key"] or "\r" in result["api_key"]:
            raise ValueError("API key không hợp lệ.")
    except ValueError:
        if strict:
            raise
        return deepcopy(DEFAULTS)
    return result


def normalized_url(value):
    value = value.strip().rstrip("/")
    parts = urlsplit(value)
    if (parts.scheme not in ("http", "https") or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment):
        raise ValueError("Địa chỉ VoiceStudio phải là URL http/https, ví dụ http://127.0.0.1:3900.")
    try:
        parts.port
    except ValueError as error:
        raise ValueError("Cổng VoiceStudio không hợp lệ.") from error
    return value


class VoiceStudioStore:
    def __init__(self, config_dir):
        self.config = Path(config_dir) / "voicestudio.json"
        self.warning = ""

    def load(self):
        try:
            if self.config.exists():
                return validated(json.loads(self.config.read_text(encoding="utf-8")), strict=True)
        except (OSError, ValueError) as error:
            self.warning = f"Không nạp được cấu hình VoiceStudio; dùng mặc định. ({error})"
        return deepcopy(DEFAULTS)

    def save(self, data):
        data = validated(data, strict=True)
        self.config.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.config.parent,
                                         suffix=".json", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
        try:
            os.replace(temporary, self.config)
        finally:
            temporary.unlink(missing_ok=True)
        return data


class VoiceStudioClient:
    def __init__(self, config, check=lambda: None):
        self.config = validated(config, strict=True)
        self.check = check

    def request(self, method, route, *, audio=None, **kwargs):
        self.check()
        if self.config["url"] in ("http://127.0.0.1:3900", "http://localhost:3900"):
            from voice_studio_runtime import ensure_running, installed
            if installed():
                try:
                    ensure_running(check=self.check)
                except RuntimeError as error:
                    raise VoiceStudioError(str(error)) from error
        headers = {"Authorization": "Bearer " + self.config["api_key"]} if self.config["api_key"] else {}
        try:
            with requests.request(method, self.config["url"] + route, headers=headers,
                                  timeout=(5, self.config["timeout"]), allow_redirects=False,
                                  stream=audio is not None, **kwargs) as response:
                self.check()
                if not 200 <= response.status_code < 300:
                    detail = ""
                    try:
                        payload = response.json()
                        detail = payload.get("detail") or payload.get("error", {})
                        if isinstance(detail, dict):
                            detail = detail.get("message") or detail
                        detail = str(detail)[:900]
                    except (ValueError, AttributeError):
                        pass
                    raise VoiceStudioError(f"VoiceStudio HTTP {response.status_code}: {detail or 'Yêu cầu bị từ chối.'}")
                if audio is not None:
                    with Path(audio).open("wb") as stream:
                        for block in response.iter_content(65536):
                            self.check()
                            stream.write(block)
                    if not Path(audio).stat().st_size:
                        raise VoiceStudioError("VoiceStudio không trả về âm thanh.")
                    return Path(audio)
                return response.json()
        except requests.RequestException as error:
            # Avoid echoing request headers or the saved API key in error dialogs.
            raise VoiceStudioError("Không kết nối được VoiceStudio. Hãy mở VoiceStudio, "
                                   "kiểm tra địa chỉ máy chủ và model đã cài trong cửa sổ VoiceStudio.") from error

    def inventory(self):
        engines = self.request("GET", "/engines/tts")
        profiles = self.request("GET", "/profiles")
        return {"engines": engines.get("backends", []), "active": engines.get("active", ""),
                "profiles": profiles if isinstance(profiles, list) else []}

    def clone(self, name, source, transcript, language):
        source = Path(source)
        if not name.strip() or not source.is_file():
            raise ValueError("Hãy nhập tên giọng và chọn file âm thanh mẫu.")
        with source.open("rb") as stream:
            return self.request("POST", "/profiles", data={"name": name.strip(), "kind": "clone",
                                "ref_text": transcript, "language": language},
                                files={"ref_audio": (source.name, stream, "application/octet-stream")})

    def design(self, name, description, language):
        if not name.strip() or not description.strip():
            raise ValueError("Hãy nhập tên và mô tả giọng muốn tạo.")
        parsed = self.request("POST", "/design/describe", json={"description": description})
        attrs = parsed.get("attrs", {})
        recipe = {"version": 1, "description": description, "picks": attrs}
        profile = self.request("POST", "/profiles", data={"name": name.strip(), "kind": "design",
                               "language": language, "engine": self.config["engine"],
                               "instruct": parsed.get("instruct", ""),
                               "vd_states": json.dumps(attrs), "design_recipe": json.dumps(recipe),
                               "seed": self.config["seed"] if self.config["seed"] >= 0 else 42})
        return {"profile": profile, "unmatched": parsed.get("unmatched", [])}

    def synthesize(self, text, voice, language, target, *, speed=1.0):
        if not 0.25 <= speed <= 4:
            raise ValueError("Tốc độ VoiceStudio phải từ 0,25 đến 4 lần.")
        cfg = self.config
        payload = {"model": cfg["engine"], "input": text, "voice": voice,
                   "language": language, "response_format": "wav", "speed": speed,
                   "denoise": cfg["denoise"], "preprocess_prompt": cfg["preprocess_prompt"],
                   "num_step": cfg["num_step"], "guidance_scale": cfg["guidance_scale"]}
        for key in ("instructions", "description"):
            if cfg[key].strip():
                payload[key] = cfg[key].strip()
        if cfg["seed"] >= 0:
            payload["seed"] = cfg["seed"]
        self.request("POST", "/v1/audio/speech", json=payload, audio=target)

    def transcribe(self, source, *, language="", translate=False):
        source = Path(source)
        route = "/v1/audio/translations" if translate else "/v1/audio/transcriptions"
        data = {"model": "whisper-1", "response_format": "json"}
        if language and not translate:
            data["language"] = language
        with source.open("rb") as stream:
            return self.request("POST", route, data=data,
                                files={"file": (source.name, stream, "application/octet-stream")})
