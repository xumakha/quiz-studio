"""Durable, per-user background preferences, outside the packaged app."""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from PIL import Image


class BackgroundStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else Path(
            os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "QuizStudio"
        self.config = self.directory / "background.json"
        self.warning = ""

    def load(self):
        state = {"background": "", "background_name": "", "background_dim": 12}
        self.warning = ""
        try:
            if not self.config.exists():
                return state
            data = json.loads(self.config.read_text(encoding="utf-8"))
            dim = data.get("background_dim", 12)
            if type(dim) is int and 0 <= dim <= 70:
                state["background_dim"] = dim
            filename = data.get("file", "")
            if filename:
                if not isinstance(filename, str) or Path(filename).name != filename:
                    raise ValueError("Tên file ảnh đã lưu không hợp lệ.")
                path = self.directory / "backgrounds" / filename
                with Image.open(path) as image:
                    image.verify()
                state.update(background=str(path.resolve()), background_name=str(data.get("name", filename)))
        except (OSError, ValueError, TypeError, AttributeError) as error:
            self.warning = f"Không nạp được ảnh nền đã lưu. Hãy chọn lại ảnh nền. ({error})"
        return state

    def _save(self, state):
        self.directory.mkdir(parents=True, exist_ok=True)
        data = {"file": Path(state["background"]).name if state["background"] else "",
                "name": state["background_name"], "background_dim": state["background_dim"]}
        # A failed write leaves the previous selection intact.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                         suffix=".json", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
        try:
            os.replace(temporary, self.config)
        finally:
            temporary.unlink(missing_ok=True)

    def select(self, source, dim):
        source = Path(source)
        with Image.open(source) as image:
            image.verify()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assets = self.directory / "backgrounds"
        assets.mkdir(parents=True, exist_ok=True)
        target = assets / (digest + source.suffix.lower())
        if not target.exists():
            with tempfile.NamedTemporaryFile(dir=assets, delete=False) as stream:
                temporary = Path(stream.name)
            try:
                shutil.copyfile(source, temporary)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        state = {"background": str(target.resolve()), "background_name": source.name, "background_dim": dim}
        self._save(state)
        return state

    def save_dim(self, dim):
        state = self.load()
        state["background_dim"] = dim
        self._save(state)

    def clear(self, dim):
        self._save({"background": "", "background_name": "", "background_dim": dim})
