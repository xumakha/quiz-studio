"""Shared, non-modal history of successfully exported videos."""
from datetime import datetime
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from content_types import LABELS
from platform_support import open_in_file_manager
from ui_components import ACCENT, BG, INK, LINE, MUTED, box, button, entry, label


def display_time(value):
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError, OverflowError):
        return value or "—"


class VideoHistoryWindow(ctk.CTkToplevel):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.records = []
        self._records_by_id = {}
        self.title("Lịch sử video")
        self.geometry("1120x780")
        self.minsize(880, 660)
        self.configure(fg_color=BG)
        self.transient(host.winfo_toplevel())
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=2)
        self.grid_rowconfigure(3, weight=3)

        heading = box(self)
        heading.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 12))
        label(heading, "Lịch sử video", 23, bold=True).pack(anchor="w")
        label(heading, "Các video đã xuất thành công từ tất cả các kênh. Chọn một video để xem caption.",
              12, MUTED).pack(anchor="w", pady=(4, 0))

        toolbar = box(self)
        toolbar.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        label(toolbar, "Tìm kiếm", 12).pack(side="left", padx=(0, 10))
        self.search = tk.StringVar(master=self)
        self.search_field = entry(toolbar, self.search,
                                  placeholder_text="Tên video, loại, kênh hoặc caption…")
        self.search_field.pack(side="left", fill="x", expand=True)
        button(toolbar, "Làm mới", self.refresh, width=100).pack(side="right", padx=(10, 0))

        table_panel = box(self, "white", corner_radius=8, border_width=1, border_color=LINE)
        table_panel.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 12))
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(0, weight=1)
        style = ttk.Style(self)
        style.configure("History.Treeview", background="white", fieldbackground="white", foreground=INK,
                        rowheight=38, font=("Segoe UI", 10), borderwidth=0)
        style.configure("History.Treeview.Heading", background=BG, foreground=MUTED,
                        font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("History.Treeview", background=[("selected", "#e7f5f1")],
                  foreground=[("selected", ACCENT)])
        columns = ("time", "channel", "type", "title", "caption")
        self.table = ttk.Treeview(table_panel, columns=columns, show="headings", selectmode="browse",
                                  height=6, style="History.Treeview")
        for key, title, width in (("time", "Thời gian xuất", 135), ("channel", "Kênh", 130),
                                  ("type", "Loại video", 190), ("title", "Tên video", 230),
                                  ("caption", "Caption", 270)):
            self.table.heading(key, text=title, anchor="w")
            self.table.column(key, width=width, minwidth=width if key == "time" else 110,
                              stretch=key != "time", anchor="w")
        self.table.grid(row=0, column=0, sticky="nsew", padx=(1, 0), pady=(1, 0))
        vertical = ttk.Scrollbar(table_panel, orient="vertical", command=self.table.yview)
        vertical.grid(row=0, column=1, sticky="ns", pady=(1, 0))
        horizontal = ttk.Scrollbar(table_panel, orient="horizontal", command=self.table.xview)
        horizontal.grid(row=1, column=0, sticky="ew", padx=(1, 0))
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.table.bind("<<TreeviewSelect>>", self._show_selection)
        self.empty_message = label(table_panel, "", 13, MUTED, justify="center", anchor="center")

        details = box(self, "white", corner_radius=8, border_width=1, border_color=LINE)
        details.grid(row=3, column=0, sticky="nsew", padx=24)
        details.grid_columnconfigure(0, weight=1)
        details.grid_rowconfigure(6, weight=1)
        label(details, "Tên video", 12, bold=True).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 3))
        self.title_text = ctk.CTkTextbox(details, height=48, fg_color=BG, text_color=INK,
                                         font=("Segoe UI", 12), wrap="word", state="disabled")
        self.title_text.grid(row=1, column=0, sticky="ew", padx=16)
        self.metadata = label(details, "Chọn một video trong danh sách.", 11, MUTED,
                              justify="left", wraplength=980)
        self.metadata.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 4))
        self.output_path = tk.StringVar(master=self)
        path_row = box(details)
        path_row.grid(row=3, column=0, sticky="ew", padx=16)
        label(path_row, "File video", 11, MUTED).pack(side="left", padx=(0, 8))
        ttk.Entry(path_row, textvariable=self.output_path, state="readonly").pack(side="left", fill="x", expand=True)
        caption_heading = box(details)
        caption_heading.grid(row=5, column=0, sticky="ew", padx=16, pady=(10, 6))
        label(caption_heading, "Caption", 12, bold=True).pack(side="left")
        self.copy_button = button(caption_heading, "Copy caption", self.copy_caption, width=138,
                                  height=30, primary=True, symbol="copy", state="disabled")
        self.copy_button.pack(side="right")
        self.folder_button = button(caption_heading, "Mở thư mục", self.open_output_folder, width=115,
                                    height=30, state="disabled")
        self.folder_button.pack(side="right", padx=(0, 8))
        self.caption_text = ctk.CTkTextbox(details, height=110, fg_color=BG, text_color=INK,
                                           font=("Segoe UI", 12), wrap="word", state="disabled")
        self.caption_text.grid(row=6, column=0, sticky="nsew", padx=16, pady=(0, 14))
        details.bind("<Configure>", lambda event: self.metadata.configure(wraplength=max(320, event.width - 32)))
        self.status = label(self, "", 11, MUTED, wraplength=1020, justify="left")
        self.status.grid(row=4, column=0, sticky="ew", padx=24, pady=(8, 12))
        self.search.trace_add("write", lambda *_: self._populate())
        self.refresh()

    def destroy(self):
        # CustomTkinter leaves delayed titlebar/scrollbar callbacks behind when
        # destroying widgets. Cancel this window's callbacks, keeping shared
        # appearance/scaling and the main app's render polling timers alive.
        commands = set()
        pending = [self]
        while pending:
            widget = pending.pop()
            commands.update(getattr(widget, "_tclCommands", None) or ())
            pending.extend(widget.winfo_children())
        for timer in self.tk.call("after", "info"):
            script = self.tk.call("after", "info", timer)[0]
            if script in commands:
                # The owning widget removes its Tcl command during destroy.
                self.tk.call("after", "cancel", timer)
        super().destroy()

    def refresh(self):
        """Reload while keeping the current selection, including on read failure."""
        try:
            records = self.host.history_store.load()
        except (OSError, ValueError, sqlite3.Error) as error:
            self.status.configure(text=f"Không đọc được lịch sử video: {error}", text_color="#b44535")
            return False
        self.records = records
        self._records_by_id = {record["id"]: record for record in records}
        self._populate()
        return True

    def _populate(self):
        selected = self.table.selection()
        selected_id = selected[0] if selected else None
        query = self.search.get().strip().casefold()
        visible = []
        for record in self.records:
            kind = LABELS.get(record["video_type"], record["video_type"])
            searchable = "\n".join((record["title"], record["caption"], record["tab_name"],
                                     record["video_type"], kind))
            if not query or query in searchable.casefold():
                visible.append(record)
        children = self.table.get_children()
        if children:
            self.table.delete(*children)
        for record in visible:
            summary = " ".join(record["caption"].split())
            self.table.insert("", "end", iid=record["id"], values=(
                display_time(record["created_at"]), record["tab_name"],
                LABELS.get(record["video_type"], record["video_type"]), record["title"], summary))
        if visible:
            self.empty_message.place_forget()
            selection = selected_id if selected_id and self.table.exists(selected_id) else visible[0]["id"]
            self.table.selection_set(selection)
            self.table.focus(selection)
            self.table.see(selection)
        else:
            text = ("Không có video phù hợp với từ khóa." if self.records else
                    "Chưa có lịch sử video.\nVideo sẽ được lưu ở đây sau khi xuất thành công.")
            self.empty_message.configure(text=text)
            self.empty_message.place(relx=0.5, rely=0.55, anchor="center")
        self._show_selection()
        self.status.configure(text=f"{len(visible)} / {len(self.records)} video", text_color=MUTED)

    def _selected_record(self):
        selection = self.table.selection()
        return self._records_by_id.get(selection[0]) if selection else None

    @staticmethod
    def _set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _show_selection(self, event=None):
        record = self._selected_record()
        self._set_text(self.title_text, record["title"] if record else "")
        self._set_text(self.caption_text, record["caption"] if record else "")
        self.output_path.set(record["output_path"] if record else "")
        if record:
            kind = LABELS.get(record["video_type"], record["video_type"])
            metadata = f"Kênh: {record['tab_name']}  ·  Loại: {kind}  ·  {display_time(record['created_at'])}"
            if record.get("duration") is not None:
                metadata += f"  ·  {record['duration']:.1f} giây"
            self.metadata.configure(text=metadata)
        else:
            self.metadata.configure(text="Chọn một video trong danh sách.")
        self.copy_button.configure(state="normal" if record and record["caption"] else "disabled")
        self.folder_button.configure(state="normal" if record and record["output_path"] else "disabled")

    def copy_caption(self):
        record = self._selected_record()
        if record and record["caption"]:
            self.clipboard_clear()
            self.clipboard_append(record["caption"])
            self.status.configure(text="Đã sao chép caption.", text_color=ACCENT)

    def open_output_folder(self):
        record = self._selected_record()
        if not record or not record["output_path"]:
            return
        try:
            path = Path(record["output_path"])
            if not path.is_file():
                messagebox.showwarning("Không tìm thấy video",
                                       f"File video đã được di chuyển hoặc xóa:\n{path}", parent=self)
                return
            open_in_file_manager(path, select=True)
        except OSError as error:
            messagebox.showerror("Không mở được thư mục", str(error), parent=self)
