"""Rounded desktop workspace following the supplied Lovable visual design."""
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from engine import VOICES
from video_themes import TEMPLATES
from icons import icon, IconTabs
from preferences import USER_DEFAULTS

BG, INK, MUTED, ACCENT, LINE = "#f6f8fa", "#25333d", "#7c8793", "#218c7c", "#e3e8ed"


def build_ui(app, saved):
    ctk.set_appearance_mode("light")
    ctk.set_widget_scaling(1)
    app.configure(bg=BG)
    style = ttk.Style(app)
    style.theme_use("clam")
    style.configure("TLabel", background="white", foreground=INK, font=("Segoe UI", 9))
    style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor="#edf2f4", borderwidth=0, thickness=5)
    style.configure("Treeview", background="white", fieldbackground="white", foreground=INK, rowheight=38, font=("Segoe UI", 10), borderwidth=0)
    style.configure("Treeview.Heading", background=BG, foreground=MUTED, font=("Segoe UI", 9, "bold"), relief="flat")
    style.map("Treeview", background=[("selected", "#e7f5f1")], foreground=[("selected", ACCENT)])

    def box(parent, color="transparent", **kw):
        return ctk.CTkFrame(parent, fg_color=color, **kw)

    def label(parent, text, size=13, color=INK, bold=False, **kw):
        return ctk.CTkLabel(parent, text=text, text_color=color, font=("Segoe UI", size, "bold" if bold else "normal"), anchor=kw.pop("anchor", "w"), **kw)

    def button(parent, text, command, primary=False, symbol=None, **kw):
        return ctk.CTkButton(parent, text=text, command=command, height=36, corner_radius=7,
            fg_color=ACCENT if primary else "white", hover_color="#187b6c" if primary else "#eef7f4",
            text_color="white" if primary else INK, text_color_disabled="#a8b3bd",
            border_width=0 if primary else 1, border_color=LINE, font=("Segoe UI", 12),
            image=icon(symbol,"white" if primary else MUTED,16) if symbol else None,compound="left", **kw)

    def divider(parent):
        box(parent, LINE, height=1, corner_radius=0).pack(fill="x", pady=10)

    def section(parent, text):
        label(parent, text.upper(), 10, MUTED, True).pack(anchor="w", pady=(14, 6))

    def combo(parent, text, variable, values):
        label(parent, text, 12).pack(anchor="w", pady=(9, 6))
        ctk.CTkComboBox(parent, variable=variable, values=values, state="readonly", height=36, corner_radius=6,
            fg_color="white", border_color=LINE, button_color="#f0f4f5", button_hover_color="#e2eee9",
            text_color=INK, dropdown_fg_color="white", dropdown_text_color=INK, dropdown_hover_color="#e7f5f1",
            font=("Segoe UI", 11), dropdown_font=("Segoe UI", 12)).pack(fill="x")

    def slider(parent, text, variable, low, high, suffix=""):
        label(parent, text, 12).pack(anchor="w", pady=(14, 5))
        row = box(parent)
        row.pack(fill="x", pady=(0, 6))
        control = ctk.CTkSlider(row, from_=low, to=high, number_of_steps=high-low, variable=variable,
            height=18, fg_color="#e7edef", progress_color=ACCENT, button_color=ACCENT, button_hover_color="#166c60")
        control.pack(side="left", fill="x", expand=True, padx=(0, 10))
        value = label(row, f"{variable.get()}{suffix}", 11, MUTED, width=48, fg_color=BG, corner_radius=5)
        value.pack(side="right")
        variable.trace_add("write", lambda *args: value.configure(text=f"{variable.get()}{suffix}"))

    def toggle(parent, text, variable, command=None):
        ctk.CTkSwitch(parent, text=text, variable=variable, command=command, font=("Segoe UI", 11),
            text_color=INK, progress_color=ACCENT, fg_color="#dfe5e9", button_color="white",
            button_hover_color="#f7fbfa", switch_width=32, switch_height=18).pack(anchor="w", pady=9)

    app.voice = tk.StringVar(value="Việt • Google (HTTP)")
    app.en_voice = tk.StringVar(value="English • Google (HTTP)")
    app.rate, app.pitch, app.countdown = tk.IntVar(value=0), tk.IntVar(value=0), tk.IntVar(value=5)
    app.resolution = tk.StringVar(value="1080 × 1920")
    app.video_template = tk.StringVar(value="Tự động theo môn học")
    app.brand = tk.StringVar(value="QUIZ STUDIO")
    app.watermark_enabled = tk.BooleanVar(value=True)
    app.read_options, app.speech = tk.BooleanVar(value=True), tk.BooleanVar(value=True)
    app.read_explanation = tk.BooleanVar(value=True)
    app.music_volume = tk.IntVar(value=12)
    app.background_dim = tk.IntVar(value=saved["background_dim"])
    app.selected, app.reveal = tk.IntVar(value=1), tk.BooleanVar(value=False)
    for name, default in USER_DEFAULTS.items():
        getattr(app, name).set(saved.get(name, default))

    header = box(app, "white", corner_radius=0, height=76)
    header.pack(fill="x")
    header.pack_propagate(False)
    ctk.CTkLabel(header,text="",image=icon("audio","white",24),width=40,height=40,fg_color=ACCENT,corner_radius=10).pack(side="left",padx=(28,12))
    identity = box(header)
    identity.pack(side="left")
    label(identity, "Quiz Studio", 20, bold=True).pack(anchor="w")
    label(identity, "Không gian sáng tạo video trắc nghiệm", 10, MUTED).pack(anchor="w")
    label(header, "DESKTOP", 9, MUTED, fg_color=BG, corner_radius=4, width=68, height=22).pack(side="left", padx=16)
    breadcrumb = box(header)
    breadcrumb.pack(side="left", padx=20)
    ctk.CTkLabel(breadcrumb,text="Dự án của tôi",image=icon("folder",MUTED,15),compound="left",font=("Segoe UI",11),text_color=MUTED).pack(side="left")
    ctk.CTkLabel(breadcrumb,text="",image=icon("right",MUTED,13),width=25).pack(side="left")
    label(breadcrumb,"Trình biên tập",11,MUTED).pack(side="left")
    app.export_button = button(header, "Xuất video", app.export, primary=True, symbol="film", width=138)
    app.export_button.pack(side="right", padx=(10, 28))
    button(header, "Lưu JSON", app.save_json, symbol="save", width=110).pack(side="right")

    footer = box(app, "white", corner_radius=0)
    footer.pack(side="bottom", fill="x")
    foot = box(footer)
    foot.pack(fill="x", padx=28, pady=12)
    app.folder_button = button(foot, "Mở trong thư mục", app.open_output_folder, symbol="folder", width=166, state="disabled")
    app.folder_button.pack(side="right", padx=(12, 0))
    button(foot, "Hủy tác vụ", app.cancel.set, symbol="x", width=112).pack(side="right", padx=(12, 0))
    app.progress_label = ttk.Label(foot, text="0%", width=6)
    app.progress_label.pack(side="right", padx=12)
    area = box(foot)
    area.pack(fill="both", expand=True)
    app.status = ttk.Label(area, text="Sẵn sàng tạo video", foreground=MUTED, wraplength=770)
    app.status.pack(anchor="w", pady=(0, 7))
    app.progress = ttk.Progressbar(area, mode="determinate", maximum=100)
    app.progress.pack(fill="x")

    intro = box(app)
    intro.pack(fill="x", padx=28, pady=(19, 17))
    label(intro, "Trình biên tập video", 23, bold=True).pack(anchor="w")
    label(intro, "Biến những câu hỏi thú vị thành video của riêng bạn.", 12, MUTED).pack(anchor="w", pady=(2, 0))
    workspace = box(app)
    workspace.pack(fill="both", expand=True, padx=28, pady=(0, 22))
    workspace.columnconfigure(0, minsize=282)
    workspace.columnconfigure(1, weight=1, minsize=380)
    workspace.columnconfigure(2, minsize=290)
    workspace.rowconfigure(0, weight=1)

    def panel(column, title, symbol, caption=""):
        card = box(workspace, "white", corner_radius=10, border_width=1, border_color=LINE)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column==0 else 18, 0))
        heading = box(card)
        heading.pack(fill="x", padx=18, pady=(15, 12))
        ctk.CTkLabel(heading,text="",image=icon(symbol,MUTED,18),width=18,height=20).pack(side="left",padx=(0,9))
        label(heading, title, 14, bold=True).pack(side="left")
        if caption:
            label(heading, caption, 10, MUTED, fg_color=BG, corner_radius=4, width=45).pack(side="right")
        box(card, LINE, height=1, corner_radius=0).pack(fill="x", padx=1)
        return card

    left = panel(0, "Tùy chỉnh video", "settings")
    tabs = IconTabs(left, fg_color="white", corner_radius=8, height=100,
        segmented_button_fg_color=BG, segmented_button_selected_color="#e7f5f1",
        segmented_button_selected_hover_color="#dcefe9", segmented_button_unselected_color=BG,
        segmented_button_unselected_hover_color="#edf2f4", text_color=ACCENT)
    tabs.pack(fill="both", expand=True, padx=12, pady=(5, 12))
    def tab(name):
        parent = tabs.add(name)
        inner = ctk.CTkScrollableFrame(parent, fg_color="white", corner_radius=0, width=232,
            scrollbar_button_color="#dbe3e7", scrollbar_button_hover_color="#b8ccc8")
        inner.pack(fill="both", expand=True)
        return inner
    voice, background, video = tab("Giọng đọc"), tab("Nền"), tab("Video")
    section(voice, "Giọng đọc & ngôn ngữ")
    combo(voice, "Giọng đọc chính", app.voice, list(VOICES))
    combo(voice, "Giọng cho đoạn tiếng Anh", app.en_voice, [k for k,v in VOICES.items() if v.startswith("en") or v=="google:en"])
    slider(voice, "Tốc độ giọng đọc", app.rate, -50, 100, "%")
    slider(voice, "Cao độ", app.pitch, -50, 50)
    button(voice, "Nghe thử giọng đọc", app.voice_preview, symbol="speaker").pack(fill="x", pady=14)
    divider(voice)
    section(voice, "Cách đọc nội dung")
    toggle(voice, "Đọc các lựa chọn A, B, C…", app.read_options)
    toggle(voice, "Đọc giải thích đáp án", app.read_explanation)
    toggle(voice, "Tạo giọng đọc cho video", app.speech)
    label(voice, "Giọng online cần kết nối Internet.", 10, MUTED).pack(anchor="w", pady=5)
    divider(voice)
    section(voice, "Thời gian câu hỏi")
    slider(voice, "Thời gian suy nghĩ", app.countdown, 1, 30, "s")
    section(background, "Ảnh nền")
    upload = box(background, BG, border_width=1, border_color=LINE, corner_radius=8)
    upload.pack(fill="x", pady=10)
    ctk.CTkLabel(upload,text="",image=icon("image",MUTED,32),height=40).pack(pady=(16,4))
    label(upload, "Ảnh nền của bạn", 12, MUTED).pack()
    button(upload, "Chọn ảnh nền", lambda: app.choose_media("background"),symbol="image").pack(fill="x", padx=16, pady=16)
    label(background, "Ảnh được tự lưu cho lần mở sau.", 10, MUTED).pack(anchor="w", pady=5)
    slider(background, "Làm tối ảnh nền", app.background_dim, 0, 70, "%")
    divider(background)
    section(background, "Nhạc nền")
    button(background, "Chọn nhạc nền", lambda: app.choose_media("music"),symbol="music").pack(fill="x", pady=10)
    label(background, "Nhạc được sao chép và tự lưu cho lần mở sau.", 10, MUTED, wraplength=220).pack(anchor="w", pady=5)
    slider(background, "Âm lượng nhạc", app.music_volume, 0, 100, "%")
    app.media_label = ttk.Label(background, wraplength=220, foreground=MUTED)
    app.media_label.pack(anchor="w", pady=12)
    app.update_media_label()
    button(background, "Bỏ ảnh / nhạc nền", app.clear_media,symbol="x").pack(fill="x", pady=10)
    section(video, "Thông tin video")
    combo(video, "Giao diện cho toàn bộ video", app.video_template, list(TEMPLATES))
    label(video, "Mỗi video chỉ dùng một giao diện.\nTự động chọn theo môn của câu đầu tiên; bạn có thể đổi mẫu tại đây.", 10, MUTED, wraplength=220).pack(anchor="w", pady=8)
    toggle(video, "Hiện watermark ở đáy video", app.watermark_enabled, app.update_watermark)
    label(video, "Chữ watermark", 12).pack(anchor="w", pady=(12, 6))
    app.watermark_entry = ctk.CTkEntry(video, textvariable=app.brand, height=36, corner_radius=6,
        fg_color="white", text_color=INK, border_color=LINE, font=("Segoe UI", 12))
    app.watermark_entry.pack(fill="x")
    label(video, "Tắt để ẩn cả chữ và khung watermark.", 10, MUTED, wraplength=220).pack(anchor="w", pady=10)
    combo(video, "Độ phân giải", app.resolution, ["1080 × 1920", "720 × 1280"])
    format_card = box(video, BG, corner_radius=7)
    format_card.pack(fill="x", pady=18)
    ctk.CTkLabel(format_card,text="Video dọc · 9:16",image=icon("phone",ACCENT,18),compound="left",text_color=INK,font=("Segoe UI",12,"bold")).pack(anchor="w",padx=12,pady=(12,2))
    label(format_card, "30 fps · MP4 · Shorts / TikTok / Reels", 10, MUTED).pack(anchor="w", padx=12, pady=(0, 12))

    center = panel(1, "Nội dung câu hỏi", "file-json")
    toolbar = box(center)
    toolbar.pack(fill="x", padx=16, pady=12)
    app.question_count = ttk.Label(toolbar, foreground=MUTED)
    app.question_count.pack(side="left")
    button(toolbar, "Lưu JSON", app.save_json,symbol="save", width=105).pack(side="right")
    button(toolbar, "Mở JSON", app.open_json,symbol="folder", width=105).pack(side="right", padx=7)
    bottom = box(center)
    bottom.pack(side="bottom", fill="x", padx=18, pady=16)
    button(bottom, "Kiểm tra & xem trước", app.validate,symbol="check", width=185).pack(side="right")
    label(bottom, "A–F · [en]…[/en]", 10, MUTED).pack(side="left")
    app.validation = ttk.Label(center, text="", wraplength=480)
    app.validation.pack(side="bottom", anchor="w", padx=20, pady=8)
    content = IconTabs(center, fg_color="white", corner_radius=8, command=lambda: app.validate() if content.get()=="Danh sách" else None,
        segmented_button_fg_color=BG, segmented_button_selected_color="#e7f5f1", segmented_button_selected_hover_color="#dcefe9",
        segmented_button_unselected_color=BG, segmented_button_unselected_hover_color="#edf2f4", text_color=ACCENT)
    content.pack(fill="both", expand=True, padx=12)
    editor, listing = content.add("JSON"), content.add("Danh sách")
    surface = box(editor, "#192430", corner_radius=8)
    surface.pack(fill="both", expand=True)
    app.text = tk.Text(surface, bg="#192430", fg="#e3ebef", insertbackground="#72d4ba", font=("Consolas", 10), wrap="none", undo=True,
        relief="flat", highlightthickness=0, padx=12, pady=12, spacing1=2, spacing3=2)
    vertical = ctk.CTkScrollbar(surface, command=app.text.yview, fg_color="#192430", button_color="#455565", button_hover_color="#718b97")
    horizontal = ctk.CTkScrollbar(surface, orientation="horizontal", command=app.text.xview, fg_color="#192430", button_color="#455565", button_hover_color="#718b97")
    app.text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    vertical.pack(side="right", fill="y", pady=8)
    horizontal.pack(side="bottom", fill="x", padx=8)
    app.text.pack(fill="both", expand=True, padx=(6, 0), pady=(6, 0))
    app.text.tag_configure("json_key", foreground="#97c8ec")
    app.text.tag_configure("json_string", foreground="#a6d3ad")
    app.text.bind("<<Modified>>", app.json_changed)
    app.question_list = ttk.Treeview(listing, columns=("question", "answer"), show="headings", selectmode="browse")
    for key, text in [("question", "Câu hỏi"), ("answer", "Đáp án")]:
        app.question_list.heading(key, text=text)
    app.question_list.column("question", width=300, stretch=True)
    app.question_list.column("answer", width=65, stretch=False)
    scroller = ctk.CTkScrollbar(listing, command=app.question_list.yview)
    app.question_list.configure(yscrollcommand=scroller.set)
    scroller.pack(side="right", fill="y")
    app.question_list.pack(fill="both", expand=True)
    app.question_list.bind("<<TreeviewSelect>>", app.select_list_question)

    right = panel(2, "Xem trước", "play", "9:16")
    app.template_label = label(right, "TỰ ĐỘNG THEO MÔN HỌC", 10, ACCENT, True)
    app.template_label.pack(pady=(16, 8))
    stage = box(right, BG, corner_radius=8)
    stage.pack(fill="x", padx=18, pady=10)
    app.preview = ttk.Label(stage, background=BG)
    app.preview.pack(padx=14, pady=14)
    label(right, "Câu hỏi đang xem", 11, MUTED).pack(anchor="w", padx=20, pady=(8, 7))
    controls = box(right)
    controls.pack(fill="x", padx=18)
    button(controls, "", lambda: app.move_question(-1),symbol="left", width=36).pack(side="left")
    question_entry = ctk.CTkEntry(controls, textvariable=app.selected, width=100, height=36, corner_radius=6,
        border_color=LINE, fg_color="white", text_color=INK, justify="center")
    question_entry.pack(side="left", fill="x", expand=True, padx=8)
    question_entry.bind("<Return>", lambda e: app.show_preview())
    question_entry.bind("<FocusOut>", lambda e: app.show_preview())
    button(controls, "", lambda: app.move_question(1),symbol="right", width=36).pack(side="right")
    reveal_area = box(right)
    reveal_area.pack(fill="x", padx=18, pady=6)
    toggle(reveal_area, "Hiện đáp án & giải thích", app.reveal, app.show_preview)
    label(right, "30 fps · MP4 · Video dọc", 10, MUTED).pack(pady=(2, 12))
    app.background_dim.trace_add("write", app.background_dim_changed)
    app.brand.trace_add("write", lambda *args: app.show_preview())
    app.video_template.trace_add("write", lambda *args: app.show_preview())
    app.update_watermark()
