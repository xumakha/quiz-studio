"""Road-inspired DMV practice cards on the shared mobile-safe canvas."""
from PIL import Image, ImageDraw, ImageOps

from background_media import open_background
from branding import CONTENT_MARGIN_X, add_branding, compose_content, draw_text_watermark
from prep_themes import PALETTES


def render_frame(row, number, total, title, settings, reveal=False, countdown=None, countdown_remaining=None):
    from engine import fitted, font, draw_option_text
    from content_timeline import thinking_seconds

    palette = PALETTES["dmv"]
    accent, ink, muted = (palette[key] for key in ("accent", "ink", "muted"))
    background = Image.new("RGB", (1080, 1920), palette["background"])
    if settings.background and not settings.background_overlay:
        with open_background(settings.background) as source:
            background = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), background.size)
        background = Image.blend(background, Image.new("RGB", background.size, "#081022"), settings.background_dim / 100)
    image = Image.new("RGBA", background.size)
    draw = ImageDraw.Draw(image)
    left, right = CONTENT_MARGIN_X, 1080-CONTENT_MARGIN_X

    def text(value, rect, size=42, color=ink, bold=True):
        x, y, r, b = rect
        face, lines, step = fitted(draw, value, size, r-x, b-y, bold)
        top = y + (b-y-len(lines)*step)/2
        for line in lines:
            draw.text((x, top), line, font=face, fill=color, anchor="lt")
            top += step

    # A narrow road edge keeps the question area clear of decoration.
    draw.rounded_rectangle((28, 178, 52, 1394), 12, fill=ink)
    for y in range(204, 1380, 76):
        draw.rectangle((38, y, 42, y+32), fill="white")
    draw.rounded_rectangle((left, 178, right, 374), 24, fill=accent)
    draw.rounded_rectangle((left+24, 204, left+100, 280), 14, fill="white")
    draw.line((left+44, 262, left+50, 221, left+74, 221, left+80, 262), fill=accent, width=5)
    draw.line((left+62, 231, left+62, 240), fill=accent, width=4)
    draw.line((left+62, 250, left+62, 259), fill=accent, width=4)
    text("DMV-PREP.ORG", (left+122, 205, right-180, 253), 38, "white")
    text("DRIVER KNOWLEDGE PRACTICE", (left+122, 258, right-24, 300), 24, "white")
    draw.text((right-26, 228), f"{number:02d} / {total:02d}", font=font(29, True), anchor="rm", fill="white")
    draw.rounded_rectangle((left+26, 334, right-26, 342), 4, fill="#7597FF")
    progress = max(0, min(1, number/max(1, total)))
    if progress:
        draw.rounded_rectangle((left+26, 334, left+26+(right-left-52)*progress, 342), 4, fill="white")
    text(title, (left, 398, right, 488), 43)
    draw.rounded_rectangle((left, 510, right, 758), 20, fill="white")
    text("KNOWLEDGE CHECK", (left+26, 528, right-26, 566), 24, accent)
    text(row["question"], (left+26, 580, right-26, 736), 49)
    count, gap = len(row["options"]), 12
    height = min(100, (360-gap*(count-1))//count)
    for index, option in enumerate(row["options"]):
        y = 760+index*(height+gap)
        correct = reveal and index == row["answer_index"]
        tone = "#21804F" if correct else accent
        draw.rounded_rectangle((left, y, right, y+height), 16,
                               fill="#EAF7EF" if correct else "white", outline=tone if correct else "#D8E2FF", width=3 if correct else 2)
        draw.ellipse((left+16, y+(height-46)/2, left+62, y+(height+46)/2), fill=tone if correct else palette["soft"])
        draw.text((left+39, y+height/2), chr(65+index), font=font(26, True), anchor="mm", fill="white" if correct else accent)
        draw_option_text(draw, option, (left+84, y+8, right-24, y+height-8), min(39, height-24), ink)
    if reveal:
        draw.rounded_rectangle((left, 1144, right, 1394), 16, fill="white", outline="#21804F", width=2)
        text(f"ANSWER {chr(65+row['answer_index'])} · EXPLANATION", (left+22, 1158, right-22, 1200), 25, "#21804F")
        text(row.get("explanation") or row["options"][row["answer_index"]], (left+22, 1212, right-22, 1378), 35, bold=False)
    elif countdown is not None:
        text(f"{countdown:02d} SEC", (left, 1274, left+220, 1340), 42, accent)
        text("CHOOSE YOUR ANSWER", (left+240, 1285, right, 1331), 27, muted)
        draw.rounded_rectangle((left, 1362, right, 1374), 6, fill=palette["soft"])
        remaining = countdown if countdown_remaining is None else countdown_remaining
        fraction = max(0, min(1, remaining/max(1, thinking_seconds(row, settings))))
        if fraction:
            draw.rounded_rectangle((left, 1362, left+(right-left)*fraction, 1374), 6, fill=accent)
    draw_text_watermark(draw, settings, ink)
    add_branding(image, settings)
    return compose_content(background, image, settings)
