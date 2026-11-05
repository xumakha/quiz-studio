"""Start the local VoiceStudio companion installed beside this project."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request


_lock = threading.Lock()
_process = None


def runtime_directory():
    project = Path(sys.executable).resolve().parents[2] if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    return project / ".voicestudio-runtime"


def installed():
    root = runtime_directory()
    return runtime_python(root).is_file() and (root / "installed.json").is_file()


def runtime_python(root):
    return root / "source" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def environment(root=None):
    root = root or runtime_directory()
    values = os.environ.copy()
    values.update({
        "OMNIVOICE_DATA_DIR": str(root / "data"),
        "OMNIVOICE_CACHE_DIR": str(root / "models" / "hf"),
        "HF_HOME": str(root / "models" / "hf"),
        "HF_HUB_CACHE": str(root / "models" / "hf" / "hub"),
        "OMNIVOICE_MODEL": "k2-fsa/OmniVoice",
        "OMNIVOICE_BIND_HOST": "127.0.0.1", "OMNIVOICE_PORT": "3900",
        "OMNIVOICE_DEVICE": "cpu", "CUDA_VISIBLE_DEVICES": "",
        "OMNIVOICE_TTS_BACKEND": "omnivoice", "PYTHONUNBUFFERED": "1",
        "OMNIVOICE_MODEL_LOAD_TIMEOUT": "1800",
        "SSL_CERT_FILE": str(root / "system-ca.pem"),
        "REQUESTS_CA_BUNDLE": str(root / "system-ca.pem"),
    })
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    values["FFMPEG_PATH"] = ffmpeg
    return values


def health():
    try:
        with urllib.request.urlopen("http://127.0.0.1:3900/health", timeout=2) as response:
            if response.headers.get("x-omnivoice-backend"):
                return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 503 and error.headers.get("x-omnivoice-backend"):
            return json.load(error)
    except (OSError, ValueError):
        pass
    return None


def ensure_running(check=lambda: None, timeout=180):
    global _process
    state = health()
    if state and state.get("status") == "ok":
        return state
    with _lock:
        state = health()
        if state is None and (_process is None or _process.poll() is not None):
            if not installed():
                raise RuntimeError("Chưa cài bộ chạy VoiceStudio local trên máy này.")
            root = runtime_directory()
            with (root / "backend.log").open("ab") as log:
                _process = subprocess.Popen(
                    [str(runtime_python(root)),
                     str(root / "source" / "backend" / "main.py")],
                    cwd=root / "source", env=environment(root), stdout=log, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check()
        state = health()
        if state and state.get("status") == "ok":
            return state
        if _process is not None and _process.poll() is not None:
            raise RuntimeError("VoiceStudio khởi động thất bại. Xem .voicestudio-runtime/backend.log.")
        time.sleep(0.3)
    raise RuntimeError("VoiceStudio chưa khởi động xong. Chờ thêm rồi kiểm tra kết nối lại.")


if __name__ == "__main__":
    print(json.dumps(ensure_running(), ensure_ascii=False))
