"""Install pinned VieNeu Nano and validate its Adam voice in an isolated CPU runtime."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import requests

from local_voice import environment, runtime_directory, runtime_python, worker_path
from setup_voice_studio import ca_bundle, download

ROOT = runtime_directory()
REPO = "pnnbao-ump/VieNeu-TTS-v3-Nano"
REVISION = "aba295eb96a6fa6003ebe417cc1f2802a7adc1dc"
FILES = {"config.json", "constants.npz", "text_encoder.onnx", "duration_predictor.onnx",
         "vector_estimator.onnx", "codec_decoder.onnx"}


def main():
    ROOT.mkdir(exist_ok=True)
    if shutil.disk_usage(ROOT).free < 2 * 2**30:
        raise RuntimeError("Cần ít nhất 2 GiB trống để cài Adam local.")
    session = requests.Session()
    session.verify = str(ca_bundle(ROOT))
    uv = Path(sys.executable).parent / ("uv.exe" if os.name == "nt" else "uv")
    if not uv.is_file():
        subprocess.run([sys.executable, "-m", "pip", "install", "uv"], check=True)
    env = environment(ROOT, offline=False)
    env.update({"UV_PYTHON_INSTALL_DIR": str(ROOT / "python"),
                "UV_CACHE_DIR": str(ROOT / "uv-cache"), "UV_LINK_MODE": "copy",
                "UV_HTTP_TIMEOUT": "120"})
    # Reuse the already downloaded package cache when the companion is installed.
    shared_cache = ROOT.parent / ".voicestudio-runtime" / "uv-cache"
    if shared_cache.is_dir():
        env["UV_CACHE_DIR"] = str(shared_cache)
    if not runtime_python().is_file():
        subprocess.run([str(uv), "--system-certs", "venv", "--python", "3.11", str(ROOT / ".venv")], env=env, check=True)
    subprocess.run([str(uv), "--system-certs", "pip", "install", "--python", str(runtime_python()),
                    "vieneu==3.8.4"], env=env, check=True)
    response = session.get(f"https://huggingface.co/api/models/{REPO}/tree/{REVISION}",
                           params={"recursive": "true", "limit": 1000}, timeout=(15, 60))
    response.raise_for_status()
    entries = {e["path"]: e for e in response.json() if e["type"] == "file"}
    print("Downloading VieNeu Nano (~280 MB), voice Adam, CPU.", flush=True)
    for name in sorted(FILES):
        entry = entries[name]
        download(session, f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}",
                 ROOT / "model" / name, size=entry["size"], sha256=entry.get("lfs", {}).get("oid"))
    preview = ROOT / "adam-preview.wav"
    payload = json.dumps({"text": "Bạn đã sẵn sàng chưa? Cùng thử sức với câu hỏi hôm nay nhé!"}, ensure_ascii=False)
    print("Generating Adam preview...", flush=True)
    subprocess.run([str(runtime_python()), str(worker_path()), str(ROOT / "model"), str(preview)],
                   input=payload.encode("utf-8"), env=env, timeout=300, check=True)
    manifest = {"sdk": "vieneu==3.8.4", "model": REPO, "revision": REVISION, "voice": "Adam", "device": "cpu"}
    (ROOT / "installed.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("ADAM_LOCAL_READY", preview, flush=True)


if __name__ == "__main__":
    main()
