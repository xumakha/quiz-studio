"""Shared image/video background loading and validation."""
import io
import subprocess
import threading
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def is_video(path):
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


@lru_cache(maxsize=4)
def _video_preview(path, modified, size):
    result = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", path,
         "-map", "0:v:0", "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode or not result.stdout:
        raise ValueError("Không đọc được video nền. Hãy chọn video có hình ảnh hợp lệ.")
    return result.stdout


def open_background(path):
    if not is_video(path):
        return Image.open(path)
    path = Path(path)
    info = path.stat()
    try:
        data = _video_preview(str(path.resolve()), info.st_mtime_ns, info.st_size)
    except subprocess.TimeoutExpired as error:
        raise ValueError("Đọc video nền quá lâu. Hãy chọn video khác.") from error
    return Image.open(io.BytesIO(data))


def validate_background(path):
    with open_background(path) as image:
        image.verify()


class VideoPreview:
    """Decode a looping, silent preview off the Tk thread with bounded memory."""

    def __init__(self, path, size, offset=0):
        self.size = size
        self.image = None
        self.error = None
        self.closed = False
        width, height = size
        self.process = subprocess.Popen(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-re",
             "-stream_loop", "-1", "-ss", str(max(0, offset)), "-i", str(path),
             "-an", "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,"
             f"crop={width}:{height},setsar=1,fps=30",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        length = self.size[0] * self.size[1] * 3
        try:
            while not self.closed:
                data = self.process.stdout.read(length)
                if len(data) != length:
                    if not self.closed:
                        self.error = "Không phát được video nền trong phần xem trước."
                    break
                self.image = Image.frombytes("RGB", self.size, data)
        finally:
            self.process.stdout.close()
            self.process.wait()

    def close(self):
        self.closed = True
        if self.process.poll() is None:
            self.process.kill()
