"""Reproducible local VoiceStudio setup for a fresh Quiz Studio checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import ssl
import stat
import subprocess
import sys
import time
import zipfile

import certifi
import requests

PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT / ".voicestudio-runtime"
SOURCE_REVISION = "fc154e767227f46f2297621b854bed8685e27247"
MODEL_REPO = "k2-fsa/OmniVoice"
MODEL_REVISION = "c5fdb5ccb189668d56333f77ba2629f4cd7535f4"


def ca_bundle():
    pem = Path(certifi.where()).read_text(encoding="ascii")
    if sys.platform == "win32":
        for store in ("ROOT", "CA"):
            for certificate, encoding, _ in ssl.enum_certificates(store):
                if encoding == "x509_asn":
                    pem += "\n" + ssl.DER_cert_to_PEM_cert(certificate)
    path = ROOT / "system-ca.pem"
    path.write_text(pem, encoding="ascii")
    return path


def extract_source(archive):
    destination = ROOT / "source"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.comment.decode("ascii", errors="replace") != SOURCE_REVISION:
            raise RuntimeError("The source archive does not match the pinned VoiceStudio revision.")
        for item in zipped.infolist():
            parts = Path(item.filename).parts[1:]
            if not parts or item.is_dir():
                continue
            if any(part in (".agents", ".claude", ".github", ".dagger") for part in parts):
                continue
            if parts[-1] in ("AGENTS.md", "CLAUDE.md") or stat.S_ISLNK(item.external_attr >> 16):
                continue
            target = destination.joinpath(*parts).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise RuntimeError("Invalid archive path")
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zipped.read(item))
    (ROOT / "source-revision.txt").write_text(SOURCE_REVISION, encoding="ascii")


def download(session, url, target, *, size=None, sha256=None):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and size is not None and target.stat().st_size == size:
        if not sha256 or file_digest(target) == sha256:
            print("Present:", target.name, flush=True)
            return
    temporary = target.with_name(target.name + ".part")
    for attempt in range(1, 6):
        try:
            offset = temporary.stat().st_size if temporary.exists() else 0
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            with session.get(url, headers=headers, stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
                append = offset > 0 and response.status_code == 206
                written = offset if append else 0
                report_at = written + 128 * 1024**2
                with temporary.open("ab" if append else "wb") as stream:
                    for block in response.iter_content(1024**2):
                        stream.write(block)
                        written += len(block)
                        if written >= report_at:
                            print(target.name, f"{written / 2**20:.0f} MiB", flush=True)
                            report_at += 128 * 1024**2
            if size is not None and temporary.stat().st_size != size:
                raise RuntimeError("Incomplete download")
            if sha256 and file_digest(temporary) != sha256:
                # Retry from byte zero if the completed file has a bad checksum.
                with temporary.open("wb"):
                    pass
                raise RuntimeError("Checksum mismatch")
            os.replace(temporary, target)
            print("Installed:", target.name, flush=True)
            return
        except (requests.RequestException, RuntimeError) as error:
            print("Retry", attempt, target.name, type(error).__name__, flush=True)
            if attempt == 5:
                raise
            time.sleep(2)


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def install_model(session):
    response = session.get(f"https://huggingface.co/api/models/{MODEL_REPO}/tree/{MODEL_REVISION}",
                           params={"recursive": "true", "limit": 1000}, timeout=(15, 90))
    response.raise_for_status()
    entries = [entry for entry in response.json() if entry["type"] == "file"]
    snapshot = ROOT / "models" / "hf" / "hub" / "models--k2-fsa--OmniVoice" / "snapshots" / MODEL_REVISION
    print("Model:", MODEL_REPO, "files:", len(entries), "GiB:", round(sum(e["size"] for e in entries) / 2**30, 2), flush=True)
    for entry in entries:
        relative = entry["path"]
        target = (snapshot / relative).resolve()
        if not target.is_relative_to(snapshot.resolve()):
            raise RuntimeError("Invalid model path")
        # Reuse files from the first interrupted setup without another download.
        legacy = ROOT / "models" / "omnivoice" / relative
        if not target.exists() and legacy.is_file() and legacy.stat().st_size == entry["size"]:
            if not legacy.resolve().is_relative_to(ROOT.resolve()):
                raise RuntimeError("Invalid legacy model path")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(legacy, target)
        download(session, f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{relative}",
                 target, size=entry["size"], sha256=entry.get("lfs", {}).get("oid"))
    references = snapshot.parent.parent / "refs"
    references.mkdir(parents=True, exist_ok=True)
    (references / "main").write_text(MODEL_REVISION, encoding="ascii")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-zip", type=Path, help="Use the supplied pinned source ZIP instead of downloading it")
    args = parser.parse_args()
    ROOT.mkdir(exist_ok=True)
    session = requests.Session()
    session.verify = str(ca_bundle())
    if shutil.disk_usage(ROOT).free < 10 * 2**30:
        raise RuntimeError("VoiceStudio setup needs at least 10 GiB free disk space.")
    print("VoiceStudio setup directory:", ROOT, flush=True)
    source = ROOT / "source"
    if not (source / "pyproject.toml").is_file():
        archive = args.source_zip or ROOT / "source.zip"
        if args.source_zip is None:
            download(session, f"https://github.com/debpalash/VoiceStudio/archive/{SOURCE_REVISION}.zip", archive)
        extract_source(archive)
    uv = PROJECT / ".venv" / ("Scripts/uv.exe" if os.name == "nt" else "bin/uv")
    if not uv.is_file():
        subprocess.run([sys.executable, "-m", "pip", "install", "uv"], check=True)
        uv = Path(shutil.which("uv") or Path(sys.executable).parent / ("uv.exe" if os.name == "nt" else "uv"))
    env = os.environ.copy()
    env.update({"UV_PYTHON_INSTALL_DIR": str(ROOT / "python"), "UV_CACHE_DIR": str(ROOT / "uv-cache"),
                "UV_CONCURRENT_DOWNLOADS": "1", "UV_CONCURRENT_INSTALLS": "1",
                "UV_HTTP_TIMEOUT": "120", "UV_HTTP_RETRIES": "8", "UV_LINK_MODE": "copy",
                "SSL_CERT_FILE": str(ROOT / "system-ca.pem")})
    command = [str(uv), "--system-certs", "sync", "--directory", str(source), "--frozen",
               "--no-default-groups", "--group", "cpu", "--python", "3.11"]
    for attempt in range(3):
        print("Installing Python runtime and CPU dependencies; attempt", attempt + 1, flush=True)
        if subprocess.run(command, env=env).returncode == 0:
            break
    else:
        raise RuntimeError("Runtime installation failed. Run setup again to resume cached downloads.")
    install_model(session)
    manifest = {"source_revision": SOURCE_REVISION, "model": MODEL_REPO,
                "model_revision": MODEL_REVISION, "device": "cpu"}
    (ROOT / "installed.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("VOICESTUDIO_SETUP_COMPLETE", flush=True)
    print("The model's first-use terms can be reviewed in the VoiceStudio window.", flush=True)


if __name__ == "__main__":
    main()
