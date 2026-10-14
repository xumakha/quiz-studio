"""Subject detection and soft learning-video templates."""
import math
import re
import unicodedata
from PIL import Image, ImageDraw, ImageOps

TEMPLATES = {"Tự động theo môn học": "auto", "Toán · Xanh bạc hà": "math", "Tiếng Anh · Xanh sáng": "english", "Quiz nhiều màu · Mẫu trước": "classic"}

def video_template(rows, title="", selected="auto"):
    """Choose one template for the entire video, including its previews."""
    return detect_template(rows[0] if rows else {}, title, selected)

def detect_template(row, title="", selected="auto"):
    if selected not in TEMPLATES.values():
        raise ValueError("Mẫu video không hợp lệ.")
    if selected != "auto":
        return selected
    for source in (str(row.get("subject", ""))+" "+str(row.get("lesson", "")), title):
        source = "".join(c for c in unicodedata.normalize("NFD", source.lower()) if unicodedata.category(c)!="Mn").replace("đ","d")
        if re.search(r"\b(english|tieng anh|ngoai ngu|esl|ielts)\b", source):
            return "english"
        if re.search(r"\b(toan|math|mathematics|algebra|geometry)\b", source):
            return "math"
    text = str(row.get("question", ""))+" ".join(row.get("options", []))
    return "english" if "[en]" in text.lower() else "classic"

def render_frame(row, number, total, title, settings, reveal=False, countdown=None):
    from engine import fitted, font
    theme = detect_template(row, title, settings.template)
    if theme == "classic":
        from video_classic import render_frame as classic
        return classic(row, number, total, title, settings, reveal, countdown)
    is_math = theme=="math"
    ink, muted = ("#29443a", "#658477") if is_math else ("#2d4559", "#6b8297")
    image = Image.new("RGB", (1080,1920), "#e3f1e9" if is_math else "#e6f1f8")
    if settings.background:
        with Image.open(settings.background) as source:
            image = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), image.size, method=Image.Resampling.LANCZOS)
        shade = Image.new("RGBA", image.size, (8,15,34,round(255*settings.background_dim/100)))
        image = Image.alpha_composite(image.convert("RGBA"),shade).convert("RGB")
    draw = ImageDraw.Draw(image,"RGBA")
    if is_math and not settings.background:
        for y in range(0,1920,78): draw.line((0,y,1080,y),fill=(93,135,114,16))
        for x in range(0,1080,78): draw.line((x,0,x,1920),fill=(93,135,114,16))
    def text(text, rect, size, color=ink, bold=True, align="center"):
        l,t,r,b=rect
        face,lines,step=fitted(draw,text,size,r-l,b-t,bold)
        y=(t+b-len(lines)*step)/2
        for line in lines:
            draw.text(((l+r)/2 if align=="center" else l,y),line,anchor="mt" if align=="center" else "lt",font=face,fill=color)
            y+=step
    draw.rounded_rectangle((144,178,706,233),13,fill=(255,255,255,200))
    text("THỬ THÁCH TOÁN" if is_math else "ENGLISH QUIZ",(160,188,690,226),29,align="left")
    draw.rounded_rectangle((755,178,936,233),13,fill=(255,255,255,200))
    text(f"{number:02d} / {total:02d}",(767,186,924,226),31)
    draw.rounded_rectangle((144,260,936,390),25,fill=(173,146,100,55))
    draw.rounded_rectangle((144,250,936,380),25,fill="#f6dfad")
    text(title,(174,270,906,360),53,"#6a5432")
    draw.rounded_rectangle((320,428,760,471),12,fill=(255,255,255,175))
    text("BẠN CÓ BIẾT?" if is_math else "CHỌN ĐÁP ÁN ĐÚNG",(338,432,742,469),23,muted)
    # No enclosing board, question fill or question border.
    text(row["question"],(144,480,936,720),62)
    colors=["#56816c","#557da1","#a68446","#92779e","#ae747d","#528e94"]
    n=len(row["options"]); columns=1 if n==2 else 2; rows=math.ceil(n/columns)
    height=min(160,(360-(rows-1)*24)//rows); width=792 if columns==1 else 378
    for i,option in enumerate(row["options"]):
        x=144+(i%columns)*414; y=760+(i//columns)*(height+24)
        correct=reveal and i==row["answer_index"]; tone=colors[i]
        draw.rounded_rectangle((x,y+9,x+width,y+height+9),22,fill="#387a5a" if correct else tone)
        draw.rounded_rectangle((x,y,x+width,y+height),22,fill="#387a5a" if correct else (255,255,255,218),outline="#387a5a" if correct else tone,width=3)
        cy=y+height/2
        draw.ellipse((x+22,cy-38,x+98,cy+38),fill=(255,255,255,45) if correct else tone)
        draw.text((x+60,cy),chr(65+i),anchor="mm",font=font(38,True),fill="white")
        text(option,(x+119,y+20,x+width-20,y+height-20),47,"white" if correct else ink,align="left")
        if correct:
            draw.rounded_rectangle((x+width-57,y-12,x+width-4,y+31),12,fill="#2d654b")
            draw.line([(x+width-46,y+7),(x+width-34,y+19),(x+width-16,y-1)],fill="white",width=6,joint="curve")
    if reveal:
        draw.rounded_rectangle((144,1160,936,1400),22,fill=(255,255,255,223))
        draw.text((171,1180),f"ĐÁP ÁN {chr(65+row['answer_index'])} · GHI NHỚ",font=font(30,True),fill="#387a5a")
        text(row["explanation"] or "Đáp án đúng: "+row["options"][row["answer_index"]],(172,1230,908,1378),34,bold=False,align="left")
    elif countdown is not None:
        draw.rounded_rectangle((144,1160,936,1320),22,fill=(255,255,255,205))
        draw.text((174,1184),"Còn",font=font(31),fill=muted)
        draw.text((253,1174),str(countdown),font=font(55,True),fill=ink)
        draw.text((321,1184),"giây",font=font(31),fill=muted)
        draw.text((904,1190),"Bạn chọn đáp án nào?",anchor="rt",font=font(25),fill=muted)
        draw.rounded_rectangle((174,1265,906,1280),7,fill="#d3e2df")
        fraction=max(0,min(1,countdown/max(1,settings.countdown)))
        if fraction: draw.rounded_rectangle((174,1265,174+732*fraction,1280),7,fill="#387a5a")
    if settings.watermark_enabled and settings.brand.strip():
        draw.rounded_rectangle((144,1420,936,1470),15,fill=(255,255,255,185))
        text(settings.brand,(170,1428,910,1462),26,muted)
    return image.resize((settings.width,settings.height),Image.Resampling.LANCZOS)
