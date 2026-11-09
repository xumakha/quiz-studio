"""Exam, military and computing layouts on the shared portrait canvas."""
from PIL import Image, ImageDraw, ImageOps
from background_media import open_background
from branding import CONTENT_MARGIN_X, add_branding, compose_content, draw_text_watermark


PALETTES = {
    "easy_pass": dict(background="#D9EDF7", ink="#17394d", muted="#527487", accent="#247ba0", panel="#ffffff", soft="#c4e3f2", heading="EASY-PASS.APP", hint="REVIEW · TEST YOUR KNOWLEDGE"),
    "exam": dict(background="#edf1f7", ink="#172b4d", muted="#60718c", accent="#275caa", panel="#ffffff", soft="#e0e9f7", heading="EXAM PRACTICE", hint="REVIEW · TEST YOUR KNOWLEDGE"),
    "military": dict(background="#e7e9df", ink="#27362a", muted="#66705b", accent="#596b38", panel="#f7f8ef", soft="#dce2cc", heading="ASVAB PREP", hint="TRAIN · PREPARE FOR TEST DAY"),
    "tech": dict(background="#e8f1f5", ink="#133346", muted="#567586", accent="#007e92", panel="#f8fdff", soft="#d5eaf0", heading="TECH PRACTICE", hint="COMPUTING · TECHNOLOGY · CERTIFICATION"),
}


def render_frame(row, number, total, title, settings, reveal=False, countdown=None, countdown_remaining=None):
    from engine import fitted, font, draw_option_text
    from video_themes import detect_template
    from content_timeline import thinking_seconds
    theme = detect_template(row, title, settings.template)
    palette = PALETTES[theme]
    ink, muted, accent = (palette[key] for key in ("ink", "muted", "accent"))
    background = Image.new("RGB", (1080, 1920), palette["background"])
    if settings.background and not settings.background_overlay:
        with open_background(settings.background) as source:
            background = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), background.size)
        background = Image.blend(background, Image.new("RGB", background.size, "#081022"), settings.background_dim / 100)
    image = Image.new("RGBA", background.size)
    draw = ImageDraw.Draw(image)
    left, right = CONTENT_MARGIN_X, 1080-CONTENT_MARGIN_X

    def text(value, rect, size=42, color=ink, bold=True, align="left"):
        x, y, r, b = rect
        face, lines, step = fitted(draw, value, size, r-x, b-y, bold)
        top = y + (b-y-len(lines)*step)/2
        for line in lines:
            draw.text(((x+r)/2 if align == "center" else x, top), line, font=face, fill=color,
                      anchor="mt" if align == "center" else "lt")
            top += step

    draw.rounded_rectangle((left, 178, right, 246), 10, fill=accent)
    text(palette["heading"], (left+24, 188, right-190, 236), 31, "white")
    draw.text((right-24, 212), f"{number:02d} / {total:02d}", font=font(30, True), anchor="rm", fill="white")
    text(title, (left, 270, right, 382), 54, align="center" if theme in ("exam", "military", "easy_pass") else "left")
    draw.line((left, 401, right, 401), fill=accent, width=4)
    text(palette["hint"], (left, 416, right, 459), 25, muted)
    draw.rounded_rectangle((left, 478, right, 672), 14, fill=palette["panel"])
    text(row["question"], (left+26, 496, right-26, 654), 53)
    count = len(row["options"])
    gap = 12
    height = min(108, (444-gap*(count-1))//count)
    for index, option in enumerate(row["options"]):
        y = 698+index*(height+gap)
        correct = reveal and index == row["answer_index"]
        tone = "#287348" if correct else accent
        draw.rounded_rectangle((left, y, right, y+height), 10, fill=tone if correct else palette["panel"], outline=tone, width=3 if correct else 1)
        draw.rounded_rectangle((left+12, y+10, left+67, y+height-10), 6, fill=palette["panel"] if correct else palette["soft"])
        draw.text((left+40, y+height/2), chr(65+index), font=font(29, True), anchor="mm", fill=tone)
        draw_option_text(draw, option, (left+88, y+9, right-22, y+height-9), min(41, height-24), "white" if correct else ink)
    if reveal:
        draw.rounded_rectangle((left, 1164, right, 1394), 12, fill=palette["panel"], outline="#287348", width=2)
        text(f"ANSWER {chr(65+row['answer_index'])} · EXPLANATION", (left+24, 1180, right-24, 1226), 29, "#287348")
        text(row["explanation"] or row["options"][row["answer_index"]], (left+24, 1240, right-24, 1376), 36, bold=False)
    elif countdown is not None:
        draw.rounded_rectangle((left, 1170, right, 1328), 12, fill=palette["panel"])
        text(f"{countdown:02d} SEC", (left+24, 1180, left+260, 1252), 42, accent)
        text("CHOOSE YOUR ANSWER", (left+290, 1194, right-24, 1242), 28, muted)
        draw.rounded_rectangle((left+24, 1280, right-24, 1292), 6, fill=palette["soft"])
        remaining = countdown if countdown_remaining is None else countdown_remaining
        fraction = max(0, min(1, remaining/max(1, thinking_seconds(row, settings))))
        if fraction:
            draw.rounded_rectangle((left+24, 1280, left+24+(right-left-48)*fraction, 1292), 6, fill=accent)
    draw_text_watermark(draw, settings, ink)
    add_branding(image, settings)
    return compose_content(background, image, settings)
