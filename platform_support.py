"""Desktop integration shared by Windows and macOS."""
import os
from pathlib import Path
import subprocess
import sys


class AudioPlayer:
    """Play WAV previews and release files before cleanup or seeking."""

    def __init__(self):
        self.process = None

    def play(self, path, wait=False):
        self.stop()
        if sys.platform == "win32":
            import winsound
            flags = winsound.SND_FILENAME
            if not wait:
                flags |= winsound.SND_ASYNC
            winsound.PlaySound(str(path), flags)
            return
        if sys.platform != "darwin":
            raise RuntimeError("Phát thử âm thanh hiện hỗ trợ Windows và macOS.")
        process = subprocess.Popen(["/usr/bin/afplay", str(path)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.process = process
        if wait:
            code = process.wait()
            if self.process is process:
                self.process = None
                if code:
                    raise RuntimeError(f"Không phát được âm thanh (afplay: {code}).")

    def stop(self):
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        process, self.process = self.process, None
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            else:
                process.wait()


def data_directory():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "QuizStudio"
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "QuizStudio"


def open_in_file_manager(path, select=False):
    path = Path(path).resolve()
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if select else ["open", str(path)])
    elif sys.platform == "win32":
        if select:
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        else:
            os.startfile(str(path))
    else:
        subprocess.Popen(["xdg-open", str(path.parent if select else path)])


def font_paths(bold=False, ipa=False):
    windows = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    names = ("arialbd.ttf", "segoeuib.ttf") if bold else ("arial.ttf", "segoeui.ttf")
    if ipa and not bold:
        names = ("segoeui.ttf", "arial.ttf")
    yield from (windows / name for name in names)
    name = "Arial Bold.ttf" if bold else "Arial.ttf"
    for directory in (Path("/System/Library/Fonts/Supplemental"), Path("/Library/Fonts"), Path.home() / "Library/Fonts"):
        yield directory / name
