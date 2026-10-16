"""Colorful quiz board inspired by the supplied mobile-video reference."""
import math
import re
from PIL import Image, ImageDraw, ImageOps
from branding import add_logo, compose_content


def render_frame(row, number, total, title, settings, reveal=False, countdown=None):
    from engine import draw_option_text, fitted, font, plain
    ink, blue = "#28323d", "#147af4"
    image = Image.new("RGB", (1080, 1920), "#319fe9")
    if settings.background:
        with Image.open(settings.background) as source:
            image = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), image.size, method=Image.Resampling.LANCZOS)
        shade = Image.new("RGBA", image.size, (8, 15, 34, round(255 * settings.background_dim / 100)))
        image = Image.alpha_composite(image.convert("RGBA"), shade).convert("RGB")
    background = image
    image = Image.new("RGBA", background.size)
    if settings.watermark_enabled:
        add_logo(image, watermark=True)
    draw = ImageDraw.Draw(image, "RGBA")

    def centered(text, rectangle, size, color=ink, bold=True, stroke=0):
        left, top, right, bottom = rectangle
        face, lines, step = fitted(draw, text, size, right-left, bottom-top, bold)
        start_y = (top + bottom - len(lines)*step) / 2
        for index, line in enumerate(lines):
            draw.text(((left+right)/2, start_y + index*step), line, font=face,
                anchor="mt", fill=color, stroke_width=stroke, stroke_fill="white")

    draw.rounded_rectangle((48, 178, 1032, 322), 35, fill="#b9942b")
    draw.rounded_rectangle((48, 165, 1032, 309), 35, fill="#ffdb4f")
    centered(title.upper(), (88, 186, 992, 283), 70, "#ee633c", stroke=3)
    grade = row.get("grade", row.get("class", ""))
    if not grade:
        match = re.search(r"lớp\s*(\d+)", str(row.get("subject", "")) + " " + title, re.I)
        grade = "LỚP " + match.group(1) if match else ""
    elif isinstance(grade, (int, float)) or str(grade).isdigit():
        grade = f"LỚP {grade}"
    badge = str(grade or row.get("subject", "QUIZ VUI"))
    draw.rounded_rectangle((235, 341, 845, 432), 26, fill="#0c5fbb")
    draw.rounded_rectangle((235, 331, 845, 422), 26, fill=blue)
    centered(badge.upper(), (265, 346, 815, 403), 40, "white")
    draw.rounded_rectangle((425, 448, 655, 498), 15, fill=(255, 255, 255, 215))
    centered(f"CÂU {number:02d} / {total:02d}", (435, 457, 645, 492), 25, "#58748c")

    # Only text in the question area: no fill, shadow or surrounding border.
    centered(row["question"], (48, 515, 1032, 725), 64)

    colors = ["#198942", "#177af1", "#f09a05", "#8851ef", "#ed5876", "#139aa9"]
    count = len(row["options"])
    columns = 1 if count == 2 else 2
    rows = math.ceil(count / columns)
    height = min(160, (360 - (rows-1)*24) // rows)
    width = 984 if columns == 1 else 476
    for index, option in enumerate(row["options"]):
        x = 48 + (index % columns) * 508
        y = 760 + (index // columns) * (height + 24)
        color = colors[index]
        correct = reveal and index == row["answer_index"]
        draw.rounded_rectangle((x, y+14, x+width, y+height+14), 30, fill=color)
        draw.rounded_rectangle((x, y, x+width, y+height), 30,
            fill=(234, 250, 234, 248) if correct else (255, 255, 255, 232),
            outline=color, width=8 if correct else 5)
        radius = 48 if height > 170 else 36
        cx, cy = x+66, y+height/2
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=color)
        draw.text((cx, cy), chr(65+index), font=font(47 if height>170 else 36, True), anchor="mm", fill="white")
        draw_option_text(draw, option, (x+128, y+22, x+width-22, y+height-22), 60, ink)
        if correct:
            draw.rounded_rectangle((x+width-80, y-15, x+width-8, y+32), 14, fill="#198942")
            # Draw the checkmark geometrically: Arial may lack the tick glyph.
            points = [(x+width-62, y+7), (x+width-49, y+20), (x+width-27, y-3)]
            draw.line(points, fill="white", width=7, joint="curve")
            for px, py in points:
                draw.ellipse((px-3, py-3, px+3, py+3), fill="white")

    if reveal:
        draw.rounded_rectangle((48, 1160, 1032, 1400), 27, fill=(255, 255, 255, 240), outline="#8ac9a0", width=3)
        draw.text((78, 1180), "ĐÁP ÁN " + chr(65+row["answer_index"]) + " · GIẢI THÍCH", font=font(32, True), fill="#198942")
        explanation = row["explanation"] or "Đáp án đúng: " + row["options"][row["answer_index"]]
        centered(explanation, (78, 1235, 1002, 1378), 35, bold=False)
    elif countdown is not None:
        draw.rounded_rectangle((48, 1160, 1032, 1330), 28, fill=(255, 255, 255, 230))
        draw.ellipse((110, 1188, 222, 1300), fill="#ffdb4f")
        draw.text((166, 1244), str(countdown), font=font(65, True), anchor="mm", fill="#bf6515")
        draw.text((255, 1201), "BẠN CHỌN ĐÁP ÁN NÀO?", font=font(34, True), fill=ink)
        draw.rounded_rectangle((255, 1268, 957, 1284), 8, fill="#dfeaf5")
        fraction = max(0, min(1, countdown / max(1, settings.countdown)))
        if fraction:
            draw.rounded_rectangle((255, 1268, 255+702*fraction, 1284), 8, fill=blue)
    if settings.watermark_enabled and settings.brand.strip():
        draw.rounded_rectangle((48, 1420, 1032, 1470), 20, fill=(255, 255, 255, 225))
        centered(settings.brand, (78, 1428, 1002, 1462), 27, "#526d83")
    add_logo(image)
    return compose_content(background, image, settings)
