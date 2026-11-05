"""Standalone Coqui worker, executed only by the separate XTTS Python env."""
import contextlib
import json
from pathlib import Path
import sys


def main():
    protocol = sys.stdout
    # Coqui/torch progress belongs in the log, not in the JSON protocol.
    sys.stdout = sys.stderr
    api, identity = None, None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get("op") != "speech":
                raise ValueError("Unsupported XTTS request")
            folder = Path(request["model_dir"])
            current = (str(folder), request["device"], request["cpu_threads"])
            if api is None:
                # These imports must never occur in Quiz Studio's UI process.
                import torch
                from TTS.api import TTS
                torch.set_num_threads(request["cpu_threads"])
                torch.set_num_interop_threads(1)
                if request["device"] == "cuda" and not torch.cuda.is_available():
                    raise ValueError("CUDA chưa sẵn sàng. Chọn CPU hoặc cài PyTorch phù hợp với GPU.")
                api = TTS(model_path=str(folder / "model.pth"), config_path=str(folder / "config.json"),
                          progress_bar=False).to(request["device"])
                identity = current
            elif identity != current:
                raise ValueError("Cấu hình XTTS thay đổi trong khi tác vụ đang chạy.")
            voice_dir = Path(request["voice_dir"])
            voice_dir.mkdir(parents=True, exist_ok=True)
            speaker = request["speaker"]
            cache = voice_dir / (speaker + ".pth")
            receipt = voice_dir / (speaker + ".json")
            reusable = False
            if cache.is_file() and receipt.is_file():
                with contextlib.suppress(OSError, ValueError):
                    reusable = json.loads(receipt.read_text())["sample_digest"] == request["sample_digest"]
            kwargs = {"text": request["text"], "speaker": speaker, "language": request["language"],
                      "voice_dir": str(voice_dir), "file_path": request["target"]}
            if not reusable:
                kwargs["speaker_wav"] = request["speaker_wav"]
            api.tts_to_file(**kwargs)
            if not reusable and cache.is_file():
                receipt.write_text(json.dumps({"sample_digest": request["sample_digest"]}), encoding="utf-8")
            response = {"ok": True}
        except Exception as error:
            import traceback
            traceback.print_exc(file=sys.stderr)
            response = {"error": f"XTTS: {error}"}
        protocol.write(json.dumps(response, ensure_ascii=False) + "\n")
        protocol.flush()


if __name__ == "__main__":
    main()
