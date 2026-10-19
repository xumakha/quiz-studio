"""Text-first learning layouts sharing exactly the export scene representation."""
from PIL import Image, ImageDraw, ImageOps
from content_types import plain


def render_ending(settings):
    from pathlib import Path
    with Image.open(Path(__file__).resolve().parent / "assets" / "ending-img.png") as source:
        artwork = ImageOps.exif_transpose(source).convert("RGB")
        return ImageOps.pad(artwork, (settings.width, settings.height), method=Image.Resampling.LANCZOS,
                            color=artwork.getpixel((0, 0)))


def render_scene(row, scene, number, total, title, settings):
    from engine import fitted, font, wrap
    from branding import add_logo
    if row.get("type", "multiple_choice") == "multiple_choice":
        from video_themes import render_frame
        return render_frame(row, number, total, title, settings, scene.phase == "answer", scene.countdown)
    image = Image.new("RGB", (1080, 1920), "#fff6d7")
    if settings.background:
        with Image.open(settings.background) as source:
            image = ImageOps.fit(source.convert("RGB"), image.size)
        image = Image.blend(image, Image.new("RGB", image.size, "#081022"), settings.background_dim / 100)
    draw = ImageDraw.Draw(image)
    def block(text, y, height, size=58, color="#112c50", background=None, highlight=None, field="nội dung"):
        if not plain(text).strip():
            return
        if background:
            draw.rounded_rectangle((64, y, 1016, y + height), radius=24, fill=background)
        try:
            face, lines, step = fitted(draw, text, size, 884, height-32, True)
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
                x = 540 - draw.textlength(line, font=face)/2
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
                draw.text((540, top), line, font=face, anchor="mt", fill=color)
            cursor = max(cursor, offset+len(line))
            top += step
    block(title, 170, 140, 52, background="#ffdc65", field="tiêu đề")
    heading = f"{number}/{total} - {scene.label}"
    heading_height = min(300, max(90, len(wrap(draw, heading, font(32, True), 884))*44+32))
    block(heading, 330, heading_height, 32, field="hướng dẫn")
    content_top = max(450, 330 + heading_height + 30)
    kind = row["type"]
    if kind == "dialogue":
        turns = scene.text.split("\n")
        height = min(180, min(640, 1130-content_top) // max(1, len(turns)) - 10)
        for i, turn in enumerate(turns):
            block(turn, content_top+i*(height+10), height, 42, background="#dceeff" if i % 2 == 0 else "#ffecaa")
    elif kind == "word_order" and scene.phase in ("question", "countdown", "arrange"):
        tokens = row["tokens"]
        height = min(160, min(640, 1130-content_top) // max(1, len(tokens)) - 8)
        for i, token in enumerate(tokens):
            target = row["answer_order"].index(token["id"])
            position = i + (target-i)*scene.progress
            block(token["text"], content_top+position*(height+8), height, 44, background="#dceeff")
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
        block(scene.text, content_top, 840-content_top, 68, highlight=highlight, field="câu hỏi/đáp án")
    if scene.detail:
        block(scene.detail, 910, 220, 44, background="#e0efff", field="phần bật mí")
    if scene.phase == "answer" and row.get("explanation"):
        block(row["explanation"], 1160, 230, 40, background="#fffdf4", field="giải thích")
    if scene.countdown is not None:
        block(f"{scene.countdown} giây", 1190, 150, 70, background="#ffdc65")
    if settings.watermark_enabled:
        add_logo(image, watermark=True)
        block(settings.brand, 1430, 90, 30)
    return image.resize((settings.width, settings.height), Image.Resampling.LANCZOS)


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
