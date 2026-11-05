"""Shared logo placement for video frames and previews."""
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

CONTENT_OFFSET_Y = 96
CONTENT_MARGIN_X = 80


def compose_content(background, content, settings):
    """Keep the background fixed while moving all video elements below mobile UI."""
    if settings.background_overlay:
        background = Image.new("RGBA", background.size,
                               (8, 15, 34, round(255 * settings.background_dim / 100)))
        background.alpha_composite(content, (0, CONTENT_OFFSET_Y))
        return background.resize((settings.width, settings.height), Image.Resampling.LANCZOS)
    background = background.convert("RGBA")
    background.alpha_composite(content, (0, CONTENT_OFFSET_Y))
    return background.convert("RGB").resize(
        (settings.width, settings.height), Image.Resampling.LANCZOS)


@lru_cache(maxsize=32)
def _logo(width, height, opacity, path=""):
    with Image.open(path or Path(__file__).resolve().parent / "assets" / "logo-mce.png") as source:
        logo = ImageOps.exif_transpose(source).convert("RGBA")
    bounds = logo.getbbox()
    if bounds:
        logo = logo.crop(bounds)
    logo.thumbnail((width, height), Image.Resampling.LANCZOS)
    logo.putalpha(logo.getchannel("A").point(lambda value: round(value * opacity)))
    return logo


@lru_cache(maxsize=16)
def _character(path=""):
    with Image.open(path or Path(__file__).resolve().parent / "assets" / "chibi.png") as source:
        character = ImageOps.exif_transpose(source).convert("RGBA")
    bounds = character.getbbox()
    if bounds:
        character = character.crop(bounds)
    character.thumbnail((124, 124), Image.Resampling.LANCZOS)
    return character


def add_logo(image, *, watermark=False, logo_image="", settings=None):
    """Place branding on the 1080 x 1920 design canvas."""
    def composite(asset, position):
        if image.mode == "RGBA":
            image.alpha_composite(asset, position)
        else:
            image.paste(asset, position, asset)

    if watermark:
        logo = _logo(800, 800, 0.07, logo_image)
        composite(logo, ((image.width - logo.width) // 2, (image.height - logo.height) // 2))
        return
    if settings is None or settings.left_logo_enabled:
        path = logo_image if settings is None else settings.left_logo_image
        composite(_logo(132, 118, 1.0, path), (CONTENT_MARGIN_X, 48))
    if settings is None or settings.right_chibi_enabled:
        character = _character("" if settings is None else settings.right_chibi_image)
        composite(character, (image.width - character.width - CONTENT_MARGIN_X, 48))
