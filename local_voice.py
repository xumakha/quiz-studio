"""Run the optional, isolated VieNeu Nano CPU voice without importing ML in the UI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

VOICE_ID = "local:adam"
VOICE_LABEL = "Việt • Nam — Adam (Local)"
_slot = threading.Semaphore(1)
_spawn_lock = threading.Lock()


class LocalVoiceError(RuntimeError):
    pass


def project_directory():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parents[3 if sys.platform == "darwin" else 2]
    return Path(__file__).resolve().parent


def runtime_directory():
    return project_directory() / ".vieneu-runtime"


def runtime_python(root=None):
    return (root or runtime_directory()) / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def worker_path():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "local_voice_worker.py"


def environment(root=None, *, offline=True):
    root = root or runtime_directory()
    env = os.environ.copy()
    for name in ("PYTHONHOME", "PYTHONPATH", "__PYVENV_LAUNCHER__"):
        env.pop(name, None)
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        for name in ("PATH", "DYLD_LIBRARY_PATH"):
            env[name] = os.pathsep.join(
                item for item in env.get(name, "").split(os.pathsep)
                if item and not Path(item).resolve().is_relative_to(Path(bundle).resolve()))
        if "LD_LIBRARY_PATH_ORIG" in env:
            env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
        else:
            env.pop("LD_LIBRARY_PATH", None)
    env.update({"HF_HOME": str(root / "hf"), "HF_HUB_CACHE": str(root / "hf" / "hub"),
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1", "OMP_NUM_THREADS": "4",
                "SSL_CERT_FILE": str(root / "system-ca.pem"),
                "REQUESTS_CA_BUNDLE": str(root / "system-ca.pem")})
    if offline:
        env["HF_HUB_OFFLINE"] = "1"
    return env


def installed():
    return runtime_python().is_file() and (runtime_directory() / "installed.json").is_file()


def _start_worker(target):
    # PyInstaller's Windows DLL search directory is inherited by children.
    # An independent Python must not load the app's python3.dll / python313.dll.
    with _spawn_lock:
        kernel = None
        previous = None
        if sys.platform == "win32" and getattr(sys, "frozen", False):
            import ctypes
            kernel = ctypes.windll.kernel32
            buffer = ctypes.create_unicode_buffer(32768)
            if kernel.GetDllDirectoryW(len(buffer), buffer):
                previous = buffer.value
            if not kernel.SetDllDirectoryW(None):
                raise ctypes.WinError()
        try:
            return subprocess.Popen(
                [str(runtime_python()), "-I", str(worker_path()), str(runtime_directory() / "model"), str(target)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=runtime_directory(), env=environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        finally:
            if kernel is not None:
                kernel.SetDllDirectoryW(previous)


def synthesize(text, target, *, check=lambda: None, timeout=180):
    if not installed():
        raise LocalVoiceError("Chưa cài Adam local. Chạy Cai-Giong-local.bat trong thư mục Quiz Studio trước.")
    while not _slot.acquire(timeout=0.2):
        check()
    process = None
    try:
        check()
        process = _start_worker(Path(target).resolve())
        import time
        deadline = time.monotonic() + timeout
        payload = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
        while True:
            check()
            if time.monotonic() >= deadline:
                raise LocalVoiceError("Adam local tạo giọng quá lâu. Hãy thử câu ngắn hơn hoặc giải phóng RAM.")
            try:
                stdout, stderr = process.communicate(input=payload, timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                payload = None
        if process.returncode:
            detail = stderr.decode("utf-8", errors="replace")[-1200:]
            raise LocalVoiceError("Không tạo được Adam local: " + detail)
        check()
        if not Path(target).is_file() or Path(target).stat().st_size <= 44:
            raise LocalVoiceError("Adam local không trả về âm thanh.")
    except OSError as error:
        raise LocalVoiceError("Không mở được bộ chạy Adam local. Chạy lại Cai-Giong-local.bat để sửa cài đặt.") from error
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate()
        _slot.release()

