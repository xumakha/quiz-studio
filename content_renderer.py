from background_media import open_background
"""Text-first learning layouts sharing exactly the export scene representation."""
from PIL import Image, ImageDraw, ImageOps
from content_types import plain, LABELS


def ipa_font(size):
    """Use a Unicode font with IPA, combining marks and stress symbols."""
    import os
    from pathlib import Path
    from PIL import ImageFont
    directory = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ("segoeui.ttf", "arial.ttf"):
        if (directory / name).is_file():
            return ImageFont.truetype(str(directory / name), size)
    raise ValueError("Thiếu font Unicode hỗ trợ IPA (Segoe UI hoặc Arial).")


def render_ending(settings):
    from pathlib import Path
    with Image.open(Path(__file__).resolve().parent / "assets" / "ending-img.png") as source:
        artwork = ImageOps.exif_transpose(source).convert("RGB")
        return ImageOps.pad(artwork, (settings.width, settings.height), method=Image.Resampling.LANCZOS,
                            color=artwork.getpixel((0, 0)))


def render_scene(row, scene, number, total, title, settings):
    from engine import fitted, font, wrap
    from branding import add_logo, compose_content, CONTENT_MARGIN_X
    if row.get("type", "multiple_choice") == "multiple_choice":
        from video_themes import render_frame
        return render_frame(row, number, total, title, settings, scene.phase == "answer", scene.countdown)
    image = Image.new("RGB", (1080, 1920), "#e6f1f8")
    if settings.background and not settings.background_overlay:
        with open_background(settings.background) as source:
            image = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), image.size)
        image = Image.blend(image, Image.new("RGB", image.size, "#081022"), settings.background_dim / 100)
    background_image = image
    image = Image.new("RGBA", background_image.size)
    if settings.watermark_enabled:
        add_logo(image, watermark=True)
    draw = ImageDraw.Draw(image)
    margin = CONTENT_MARGIN_X
    def block(text, y, height, size=58, color="#112c50", background=None, highlight=None, field="nội dung", left=margin, right=1080-margin, align="center", bold=True):
        if not plain(text).strip():
            return
        if background:
            draw.rounded_rectangle((left, y+7, right, y+height+7), radius=24, fill=(28, 66, 103, 15))
            draw.rounded_rectangle((left, y, right, y + height), radius=24, fill=background, outline=(70, 120, 155, 24), width=2)
        width = right-left-56
        center = (left+right)/2
        try:
            face, lines, step = fitted(draw, text, size, width, height-32, bold)
        except ValueError as error:
            raise ValueError(f"Câu {number}: {field} quá dài để hiển thị rõ. Hãy rút gọn hoặc chia nội dung.") from error
        if face.size < 30:
            raise ValueError(f"Câu {number}: {field} quá dài để hiển thị rõ. Hãy rút gọn hoặc chia nội dung.")
        top = y + (height-len(lines)*step)/2
        cursor = 0
        source = plain(text)
        for line in lines:
            offset = source.find(line, cursor)
            selected_range = None
            if highlight and offset >= 0:
                start, end = highlight
                left, right = max(start, offset), min(end, offset+len(line))
                if left < right:
                    selected_range = (left-offset, right-offset)
            if selected_range:
                first, last = selected_range
                x = center - draw.textlength(line, font=face)/2 if align == "center" else left+28
                baseline = top - draw.textbbox((0, 0), line, font=face, anchor="ls")[1]
                tone = "#cc4534" if scene.phase == "wrong" else "#1267b1"
                # Draw every glyph once, using the same baseline for all three runs.
                # Overpainting with mt/lt anchors previously left two colored copies.
                for begin, end, fill in ((0, first, color), (first, last, tone), (last, len(line), color)):
                    if begin < end:
                        run_x = x + draw.textlength(line[:begin], font=face)
                        draw.text((run_x, baseline), line[begin:end], font=face, anchor="ls", fill=fill)
                left_x = x + draw.textlength(line[:first], font=face)
                right_x = x + draw.textlength(line[:last], font=face)
                underline_y = baseline + face.getmetrics()[1] + 3
                draw.line((left_x, underline_y, right_x, underline_y), fill=tone, width=4)
            else:
                draw.text((center if align == "center" else left+28, top), line, font=face, anchor="mt" if align == "center" else "lt", fill=color)
            cursor = max(cursor, offset+len(line))
            top += step
    kind = row["type"]
    draw.rounded_rectangle((margin, 178, 754, 238), radius=13, fill=(255, 255, 255, 220))
    draw.text((margin+20, 208), LABELS[kind].upper(), font=font(30, True), anchor="lm", fill="#42637f")
    draw.rounded_rectangle((787, 178, 1080-margin, 238), radius=13, fill=(255, 255, 255, 220))
    draw.text((893, 208), f"{number:02d} / {total:02d}", font=font(31, True), anchor="mm", fill="#42637f")
    block(title, 260, 130, 52, color="#665125", background="#ffdf7d", field="tiêu đề")
    heading = "" if kind == "guess_word" else scene.label
    heading_height = min(260, max(90, len(wrap(draw, heading, font(32, True), 864))*44+32))
    block(heading, 418, heading_height, 32, color="#58758c", field="hướng dẫn")
    content_top = max(530, 418 + heading_height + 22)
    if kind == "guess_word":
        block(row.get("level", ""), 410, 100, 32, color="#58758c")
        block(row["meaning_vi"], 535, 190, 76, field="nghĩa tiếng Việt")
        if row.get("context_hint", "").strip():
            block(row["context_hint"], 715, 100, 32, color="#58758c", field="chú thích nghĩa tiếng Việt", bold=False)
        # Fit the complete mask on one line, including twenty-letter words.
        word = plain(scene.text)
        size = 76
        while size > 30 and draw.textlength(word, font=font(size, True)) > 864:
            size -= 1
        if scene.phase in ("question", "countdown", "answer", "explanation"):
            block(word, 830 if row.get("context_hint", "").strip() else 750, 140, size, color="#1267b1", background="#f8fcff", field="từ cần đoán")
        else:
            block(word, 830 if row.get("context_hint", "").strip() else 750, 210, 52, field="ví dụ")
        if scene.phase in ("answer", "explanation") and row.get("ipa", "").strip():
            ipa = row["ipa"].strip()
            ipa_size = 48
            while ipa_size > 34 and draw.textlength(ipa, font=ipa_font(ipa_size)) > 864:
                ipa_size -= 1
            face = ipa_font(ipa_size)
            if draw.textlength(ipa, font=face) > 864:
                raise ValueError(f"Câu {number}: IPA quá dài để hiển thị rõ.")
            draw.text((540, 995 if row.get("context_hint", "").strip() else 915), ipa, font=face, anchor="mt", fill="#42637f")
        if scene.phase == "question":
            block("Chuẩn bị", 1160, 110, 48)
        elif scene.phase in ("explanation", "example"):
            block(scene.detail, 1080 if row.get("context_hint", "").strip() else 1040, 260 if row.get("context_hint", "").strip() else 300, 42, background="#fff8df", field="giải thích / ví dụ", bold=False)
    elif kind == "dialogue":
        turns = scene.text.split("\n")
        height = min(180, min(640, 1130-content_top) // max(1, len(turns)) - 10)
        for i, turn in enumerate(turns):
            block(turn, content_top+i*(height+10), height, 42, background="#f8fcff" if i % 2 == 0 else "#fff0b9",
                  left=margin if i % 2 == 0 else margin+56, right=1080-margin-56 if i % 2 == 0 else 1080-margin, align="left")
    elif kind == "word_order" and scene.phase in ("question", "countdown", "arrange"):
        tokens = row["tokens"]
        import math
        rows = math.ceil(len(tokens)/2)
        height = min(136, (1100-content_top)//max(1, rows)-20)
        for i, token in enumerate(tokens):
            target = row["answer_order"].index(token["id"])
            column = i % 2 + (target % 2-i % 2)*scene.progress
            line = i//2 + (target//2-i//2)*scene.progress
            left = margin+column*472
            block(token["text"], content_top+line*(height+20), height, 44, background="#f8fcff", left=left, right=left+448)
    else:
        highlight = None
        if kind == "error_correction" and scene.phase in ("wrong", "answer"):
            import re
            h = row["highlight"]
            starts = [m.start() for m in re.finditer(re.escape(h["wrong"]), plain(row["question"]))]
            start = h.get("start", starts[h.get("occurrence", 1)-1])
            highlight = (start, start+len(h["correct"] if scene.phase == "answer" else h["wrong"]))
        elif kind == "fill_blank" and scene.phase == "answer":
            start = plain(row["question"]).index("___")
            highlight = (start, start+len(plain(row["answer"])))
        block(scene.text, content_top, 950-content_top, 68, highlight=highlight, field="câu hỏi/đáp án")
    if scene.detail and kind != "guess_word":
        block(scene.detail, 990, 180, 54 if kind == "error_correction" else 44, color="#1267b1", background="#f8fcff", field="phần bật mí")
    if kind != "guess_word" and scene.phase == "answer" and row.get("explanation"):
        block(row["explanation"], 1190, 210, 40, background="#fff8df", field="giải thích", bold=False)
    if scene.countdown is not None:
        block(f"{scene.countdown} giây", 1160, 160, 64, background="#ffdf7d")
        draw.rounded_rectangle((margin+30, 1344, 1050-margin, 1356), radius=6, fill="#c9dce9")
        seconds = row.get("thinking_seconds", row.get("_default_thinking_seconds", settings.countdown))
        fraction = min(1, max(0, scene.countdown/max(1, seconds)))
        if fraction:
            draw.rounded_rectangle((margin+30, 1344, margin+30+(920-60)*fraction, 1356), radius=6, fill="#3887bb")
    if settings.watermark_enabled:
        block(settings.brand, 1400, 76, 30)
    add_logo(image)
    return compose_content(background_image, image, settings)


def validate_layout(title, rows, settings, check=lambda: None):
    """Check all layouts before spending time generating speech or video segments."""
    from content_timeline import plan_item
    for number, row in enumerate(rows, 1):
        seen = set()
        for scene in plan_item(row, settings):
            check()
            key = (scene.phase, scene.text, scene.label, scene.detail, scene.progress)
            if key not in seen:
                render_scene(row, scene, number, len(rows), title, settings)
                seen.add(key)
