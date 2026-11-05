"""Lightweight XTTS configuration, reference library and on-demand worker client.

This module never imports Coqui/PyTorch, installs packages or downloads models.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time


DEFAULTS = {"enabled": False, "python_path": "", "model_dir": "", "device": "cpu",
            "cpu_threads": 2, "main_voice": "", "english_voice": "", "dialogue_a": "",
            "dialogue_b": "", "timeout": 600, "license_acknowledged": False}
VOICE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_inference_slot = threading.Semaphore(1)


class XTTSError(RuntimeError):
    pass


def project_directory():
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return Path(sys.executable).resolve().parents[3]
        return Path(sys.executable).resolve().parents[2]
    return Path(__file__).resolve().parent


def validated(data):
    if not isinstance(data, dict):
        raise ValueError("Cấu hình XTTS phải là object.")
    result = deepcopy(DEFAULTS)
    for key, default in DEFAULTS.items():
        value = data.get(key, default)
        if type(value) is not type(default):
            raise ValueError(f"Cài đặt XTTS không hợp lệ: {key}.")
        result[key] = value.strip() if isinstance(value, str) else value
    if result["device"] not in ("cpu", "cuda"):
        raise ValueError("Thiết bị XTTS phải là cpu hoặc cuda.")
    if not 1 <= result["cpu_threads"] <= 8 or not 15 <= result["timeout"] <= 1800:
        raise ValueError("XTTS: số luồng CPU từ 1–8, thời gian chờ từ 15–1800 giây.")
    for key in ("main_voice", "english_voice", "dialogue_a", "dialogue_b"):
        if result[key] and not VOICE_ID.fullmatch(result[key]):
            raise ValueError("ID giọng chỉ chứa chữ A–Z, số, dấu gạch dưới/gạch ngang, tối đa 64 ký tự.")
    return result


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(data, stream, ensure_ascii=False, indent=2)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class XTTSStore:
    def __init__(self, config_dir):
        self.config = Path(config_dir) / "xtts.json"
        self.warning = ""

    def load(self):
        self.warning = ""
        try:
            if self.config.exists():
                return validated(json.loads(self.config.read_text(encoding="utf-8")))
        except (OSError, ValueError) as error:
            self.warning = f"Không nạp được cài đặt XTTS; dùng mặc định. ({error})"
        return deepcopy(DEFAULTS)

    def save(self, data):
        result = validated(data)
        atomic_json(self.config, result)
        return result


class VoiceLibrary:
    def __init__(self, directory):
        self.directory = Path(directory)

    def get(self, voice_id):
        if not VOICE_ID.fullmatch(voice_id):
            raise ValueError("ID giọng không hợp lệ.")
        metadata = self.directory / "voices" / (voice_id + ".json")
        data = json.loads(metadata.read_text(encoding="utf-8"))
        digest = data.get("sample", "")
        if not re.fullmatch(r"[a-f0-9]{64}\.wav", digest):
            raise ValueError("File mẫu giọng không hợp lệ.")
        sample = self.directory / "samples" / digest
        if not sample.is_file():
            raise ValueError("File mẫu giọng không còn tồn tại. Hãy nhập lại giọng.")
        return {"id": voice_id, "name": str(data.get("name") or voice_id),
                "sample": str(sample.resolve()), "digest": digest[:-4]}

    def list(self):
        folder = self.directory / "voices"
        if not folder.is_dir():
            return []
        result = []
        for file in folder.glob("*.json"):
            try:
                result.append(self.get(file.stem))
            except (OSError, ValueError, TypeError):
                continue
        return sorted(result, key=lambda entry: (entry["name"].casefold(), entry["id"]))

    def import_sample(self, source, voice_id, run):
        if not VOICE_ID.fullmatch(voice_id):
            raise ValueError("Tên giọng: 1–64 chữ A–Z, số, dấu gạch dưới hoặc gạch ngang.")
        metadata = self.directory / "voices" / (voice_id + ".json")
        if metadata.exists():
            raise ValueError("Tên giọng đã tồn tại. Hãy chọn tên khác.")
        source = Path(source)
        if not source.is_file():
            raise ValueError("Hãy chọn file MP3/WAV hoặc video mẫu.")
        folder = self.directory / "samples"
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as temporary:
            normalized = Path(temporary) / "sample.wav"
            # Import is an audio conversion only; no AI model is loaded here.
            run(["-i", source, "-vn", "-t", "30", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", normalized])
            import wave
            with wave.open(str(normalized)) as audio:
                if audio.getnframes() / audio.getframerate() < 3:
                    raise ValueError("File mẫu cần có ít nhất 3 giây âm thanh rõ; nên dùng 6–30 giây.")
            with normalized.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            target = folder / (digest + ".wav")
            if not target.exists():
                os.replace(normalized, target)
        atomic_json(metadata, {"name": voice_id, "sample": target.name})
        return self.get(voice_id)


def python_path(config):
    if config["python_path"]:
        return Path(config["python_path"]).expanduser().resolve()
    return project_directory() / ".xtts-runtime" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def model_directory(config):
    return (Path(config["model_dir"]).expanduser().resolve() if config["model_dir"] else
            project_directory() / ".xtts-runtime" / "models" / "xtts_v2")


def model_fingerprint(config):
    folder = model_directory(config)
    files = []
    for name in ("config.json", "model.pth", "vocab.json"):
        path = folder / name
        try:
            info = path.stat()
            files.append((name, info.st_size, info.st_mtime_ns))
        except OSError:
            files.append((name, "missing"))
    return hashlib.sha256(json.dumps([str(folder), files]).encode()).hexdigest()


def preflight(config, *, require_consent=True):
    cfg = validated(config)
    interpreter, folder = python_path(cfg), model_directory(cfg)
    if not interpreter.is_file():
        raise XTTSError("Chưa cài Python/Coqui cho XTTS. Chọn Python của môi trường riêng hoặc xem docs/xtts.md. Tool không tự tải thư viện.")
    missing = [name for name in ("config.json", "model.pth", "vocab.json") if not (folder / name).is_file()]
    if missing:
        raise XTTSError("Chưa có đủ model XTTS-v2: " + ", ".join(missing) + ". Chọn thư mục model đã tải; tool không tự tải model.")
    if require_consent and not cfg["license_acknowledged"]:
        raise XTTSError("Hãy đọc giấy phép XTTS-v2 và xác nhận quyền sử dụng trong cửa sổ XTTS.")
    return interpreter, folder


class XTTSSession:
    """At most one model in memory; held for a single preview/export job."""
    def __init__(self, config, library_dir, check=lambda: None, log=lambda message: None):
        self.config = validated(config)
        self.library = VoiceLibrary(library_dir)
        self.check, self.log = check, log
        self.process = None
        self.results = queue.Queue()
        self.has_slot = False
        self.stderr = None

    def start(self):
        if self.process is not None:
            return
        interpreter, folder = preflight(self.config)
        while not _inference_slot.acquire(timeout=0.1):
            self.check()
        self.has_slot = True
        try:
            self.check()
            self.library.directory.mkdir(parents=True, exist_ok=True)
            self.stderr = (self.library.directory / "worker.log").open("ab")
            worker = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "xtts_worker.py"
            env = os.environ.copy()
            env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONIOENCODING": "utf-8"})
            self.process = subprocess.Popen([str(interpreter), "-u", "-I", str(worker)],
                                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
                                            text=True, encoding="utf-8", env=env,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            def read_results():
                for line in self.process.stdout:
                    try:
                        self.results.put(json.loads(line))
                    except ValueError:
                        continue
                self.results.put({"error": "Bộ chạy XTTS đã dừng. Xem xtts/worker.log trong thư mục dữ liệu."})
            threading.Thread(target=read_results, daemon=True).start()
        except BaseException:
            self.close()
            raise

    def synthesize(self, text, voice_id, target):
        voice = self.library.get(voice_id)
        try:
            self.start()
            self.check()
            voice_dir = self.library.directory / "embeddings" / model_fingerprint(self.config)
            request = {"op": "speech", "text": text, "speaker": voice_id,
                       "speaker_wav": voice["sample"], "sample_digest": voice["digest"],
                       "voice_dir": str(voice_dir.resolve()), "language": "en", "target": str(Path(target).resolve()),
                       "model_dir": str(model_directory(self.config)), "device": self.config["device"],
                       "cpu_threads": self.config["cpu_threads"]}
            self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
            deadline = time.monotonic() + self.config["timeout"]
            while True:
                self.check()
                if time.monotonic() > deadline:
                    raise XTTSError("XTTS quá thời gian chờ. Hãy giảm độ dài văn bản hoặc tăng thời gian chờ.")
                try:
                    result = self.results.get(timeout=0.1)
                    break
                except queue.Empty:
                    continue
            if result.get("error"):
                raise XTTSError(result["error"])
            if not Path(target).is_file() or not Path(target).stat().st_size:
                raise XTTSError("XTTS không tạo được file WAV.")
        except BaseException:
            self.close()
            raise

    def close(self):
        process, self.process = self.process, None
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()
        if self.stderr is not None:
            self.stderr.close()
            self.stderr = None
        if self.has_slot:
            self.has_slot = False
            _inference_slot.release()
