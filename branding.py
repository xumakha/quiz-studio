"""Shared logo placement for video frames and previews."""
from functools import lru_cache
from pathlib import Path

from PIL import Image

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


@lru_cache(maxsize=1)
def _character():
    with Image.open(Path(__file__).resolve().parent / "assets" / "chibi.png") as source:
        character = source.convert("RGBA")
    bounds = character.getbbox()
    if bounds:
        character = character.crop(bounds)
    character.thumbnail((124, 124), Image.Resampling.LANCZOS)
    return character


def add_logo(image, *, watermark=False):
    """Place branding on the 1080 x 1920 design canvas."""
    logo = _logo(800, 800, 0.07) if watermark else _logo(132, 118, 1.0)
    position = ((image.width - logo.width) // 2, (image.height - logo.height) // 2) if watermark else (CONTENT_MARGIN_X, 48)
    if image.mode == "RGBA":
        # Preserve the logo alpha: paste with a mask would apply opacity twice
        # when this transparent layer is later composited onto the background.
        image.alpha_composite(logo, position)
    else:
        image.paste(logo, position, logo)
    if not watermark:
        character = _character()
        image.paste(character, (image.width - character.width - CONTENT_MARGIN_X, 48), character)
