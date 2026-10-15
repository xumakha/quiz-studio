"""Shared logo placement for video frames and previews."""
from functools import lru_cache
from pathlib import Path

from PIL import Image


@lru_cache(maxsize=4)
def _logo(width, height, opacity):
    with Image.open(Path(__file__).resolve().parent / "assets" / "logo-mce.png") as source:
        logo = source.convert("RGBA")
    bounds = logo.getbbox()
    if bounds:
        logo = logo.crop(bounds)
    logo.thumbnail((width, height), Image.Resampling.LANCZOS)
    logo.putalpha(logo.getchannel("A").point(lambda value: round(value * opacity)))
    return logo


def add_logo(image, *, watermark=False):
    """Place branding on the 1080 x 1920 design canvas."""
    logo = _logo(800, 800, 0.07) if watermark else _logo(112, 100, 1.0)
    position = ((image.width - logo.width) // 2, (image.height - logo.height) // 2) if watermark else (image.width - logo.width - 48, 48)
    image.paste(logo, position, logo)
