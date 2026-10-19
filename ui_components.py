"""Shared desktop controls for the workspace and its editor dialogs."""
import customtkinter as ctk
from icons import icon

BG, INK, MUTED, ACCENT, LINE = "#f6f8fa", "#25333d", "#7c8793", "#218c7c", "#e3e8ed"


def box(parent, color="transparent", **kwargs):
    return ctk.CTkFrame(parent, fg_color=color, **kwargs)


def label(parent, text, size=13, color=INK, bold=False, **kwargs):
    return ctk.CTkLabel(parent, text=text, text_color=color,
                       font=("Segoe UI", size, "bold" if bold else "normal"),
                       anchor=kwargs.pop("anchor", "w"), **kwargs)


def button(parent, text, command, primary=False, symbol=None, **kwargs):
    return ctk.CTkButton(parent, text=text, command=command, height=kwargs.pop("height", 36), corner_radius=7,
                        fg_color=ACCENT if primary else "white",
                        hover_color="#187b6c" if primary else "#eef7f4",
                        text_color="white" if primary else INK, text_color_disabled="#a8b3bd",
                        border_width=0 if primary else 1, border_color=LINE, font=("Segoe UI", 12),
                        image=icon(symbol, "white" if primary else MUTED, 16) if symbol else None,
                        compound="left", **kwargs)


def dropdown(parent, variable, values, command=None, **kwargs):
    return ctk.CTkComboBox(parent, variable=variable, values=values, command=command, state="readonly",
                           height=36, corner_radius=6, fg_color="white", border_color=LINE,
                           button_color="#f0f4f5", button_hover_color="#e2eee9", text_color=INK,
                           dropdown_fg_color="white", dropdown_text_color=INK, dropdown_hover_color="#e7f5f1",
                           font=("Segoe UI", 11), dropdown_font=("Segoe UI", 12), **kwargs)


def entry(parent, variable, **kwargs):
    return ctk.CTkEntry(parent, textvariable=variable, height=36, corner_radius=6, fg_color="white",
                        text_color=INK, border_color=LINE, font=("Segoe UI", 12), **kwargs)
