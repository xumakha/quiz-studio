"""Executed by the optional VieNeu Python environment, never by the app interpreter."""
import json
import sys


def main():
    from vieneu import Vieneu
    import numpy as np
    import soundfile as sf

    request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    tts = Vieneu(mode="v3nano", onnx_dir=sys.argv[1], threads=4)
    audio = tts.infer(request["text"], voice="Adam", seed=42)
    audio = np.asarray(audio)
    if not audio.size or not np.isfinite(audio).all() or np.max(np.abs(audio)) < 1e-5:
        raise RuntimeError("Model trả về âm thanh rỗng hoặc im lặng.")
    sf.write(sys.argv[2], audio, tts.sample_rate, subtype="PCM_16")


if __name__ == "__main__":
    main()
