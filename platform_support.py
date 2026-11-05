"""Desktop integration shared by Windows and macOS."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import wave


class AudioPlayer:
    """Play WAV previews and release files before cleanup or seeking."""

    # PlaySound has one playback slot for the whole process, across all tabs.
    _windows_lock = threading.Lock()
    _windows_playback = None

    def __init__(self):
        self.process = None
        self._process_lock = threading.RLock()

    def play(self, path, wait=False, cancel=None):
        if cancel is not None and cancel.is_set():
            return
        if sys.platform == "win32":
            import winsound
            duration = 0
            if wait:
                with wave.open(str(path), "rb") as source:
                    duration = source.getnframes() / source.getframerate()
            finished = threading.Event()
            playback = (self, finished)
            with AudioPlayer._windows_lock:
                if cancel is not None and cancel.is_set():
                    return
                previous = AudioPlayer._windows_playback
                if previous is not None:
                    previous[1].set()
                AudioPlayer._windows_playback = None
                # Start asynchronously under the lock so stop cannot race with
                # startup; wait outside the lock so another tab can interrupt.
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                AudioPlayer._windows_playback = playback
            if wait:
                finished.wait(duration)
                with AudioPlayer._windows_lock:
                    if AudioPlayer._windows_playback is playback:
                        winsound.PlaySound(None, winsound.SND_PURGE)
                        AudioPlayer._windows_playback = None
                        finished.set()
            return
        if sys.platform != "darwin":
            raise RuntimeError("Phát thử âm thanh hiện hỗ trợ Windows và macOS.")
        with self._process_lock:
            if cancel is not None and cancel.is_set():
                return
            self.stop()
            process = subprocess.Popen(["/usr/bin/afplay", str(path)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.process = process
        if wait:
            code = process.wait()
            with self._process_lock:
                if self.process is process:
                    self.process = None
                    if code:
                        raise RuntimeError(f"Không phát được âm thanh (afplay: {code}).")

    def stop(self):
        if sys.platform == "win32":
            import winsound
            with AudioPlayer._windows_lock:
                playback = AudioPlayer._windows_playback
                if playback is not None and playback[0] is self:
                    winsound.PlaySound(None, winsound.SND_PURGE)
                    AudioPlayer._windows_playback = None
                    playback[1].set()
        with self._process_lock:
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
