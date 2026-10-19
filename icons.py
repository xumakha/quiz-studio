"""Consistent 24-unit outline icons; supersampling keeps small strokes smooth."""
from PIL import Image, ImageDraw
import customtkinter as ctk


def icon(name, color="#7c8793", size=18):
    scale = 4
    im = Image.new("RGBA", (24*scale, 24*scale))
    d = ImageDraw.Draw(im)
    stroke = 2*scale
    def line(points):
        points = [(round(x*scale), round(y*scale)) for x,y in points]
        d.line(points, fill=color, width=stroke, joint="curve")
        for x,y in points:
            d.ellipse((x-scale,y-scale,x+scale,y+scale),fill=color)
    def circle(x,y,r):
        d.ellipse(((x-r)*scale,(y-r)*scale,(x+r)*scale,(y+r)*scale),outline=color,width=stroke)
    def rect(l,t,r,b,radius=2):
        d.rounded_rectangle((l*scale,t*scale,r*scale,b*scale),radius=radius*scale,outline=color,width=stroke)
    if name == "audio":
        for x,t,b in [(4,9,15),(8,5,19),(12,2,22),(16,6,18),(20,9,15)]: line([(x,t),(x,b)])
    elif name == "settings":
        for y,x in [(5,8),(12,16),(19,10)]:
            line([(3,y),(x-3,y)]); line([(x+3,y),(21,y)]); circle(x,y,3)
    elif name == "folder":
        line([(3,8),(3,5),(9,5),(11,8),(20,8),(21,10),(18,20),(3,20),(1,10),(16,10)])
    elif name == "file-json":
        line([(14,2),(6,2),(4,4),(4,20),(6,22),(18,22),(20,20),(20,8),(14,2),(14,8),(20,8)])
        line([(9,12),(8,12),(8,14),(7,15),(8,16),(8,18),(9,18)])
        line([(15,12),(16,12),(16,14),(17,15),(16,16),(16,18),(15,18)])
    elif name == "save":
        line([(5,3),(17,3),(21,7),(21,20),(20,21),(4,21),(3,20),(3,4),(5,3)])
        rect(7,3,16,9,0); rect(7,14,17,21,1)
    elif name == "film":
        rect(3,7,21,21,2); line([(3,7),(3,3),(21,3),(21,7)])
        for x in (6,12,18): line([(x,3),(x-2,7)])
        line([(10,11),(15,14),(10,17),(10,11)])
    elif name == "play":
        line([(8,4),(20,12),(8,20),(8,4)])
    elif name == "stop":
        rect(6,6,18,18,2)
    elif name == "plus":
        line([(12,5),(12,19)]); line([(5,12),(19,12)])
    elif name == "edit":
        line([(14,4),(20,10),(10,20),(4,21),(5,15),(17,3),(20,6)])
    elif name == "copy":
        rect(8,8,21,21,2); line([(16,4),(4,4),(4,16)])
    elif name == "trash":
        line([(4,6),(20,6)]); line([(9,3),(15,3)]); line([(6,6),(7,21),(17,21),(18,6)])
        line([(10,10),(10,17)]); line([(14,10),(14,17)])
    elif name in ("up", "down"):
        line([(6,15),(12,9),(18,15)] if name == "up" else [(6,9),(12,15),(18,9)])
    elif name == "speaker":
        line([(3,9),(7,9),(12,5),(12,19),(7,15),(3,15),(3,9)])
        d.arc((9*scale,6*scale,21*scale,18*scale),-50,50,fill=color,width=stroke)
        d.arc((9*scale,2*scale,25*scale,22*scale),-50,50,fill=color,width=stroke)
    elif name == "mic":
        rect(9,2,15,15,3)
        d.arc((5*scale,7*scale,19*scale,20*scale),0,180,fill=color,width=stroke)
        line([(5,10),(5,13)]); line([(19,10),(19,13)]); line([(12,20),(12,23)]); line([(8,23),(16,23)])
    elif name == "image":
        rect(3,3,21,21,3); circle(8,8,1.4); line([(3,17),(9,11),(13,15),(16,12),(21,17)])
    elif name == "music":
        line([(9,18),(9,5),(20,3),(20,16)]); circle(6,18,3); circle(17,16,3)
    elif name == "phone":
        rect(6,2,18,22,3); line([(10,5),(14,5)]); line([(11,19),(13,19)])
    elif name == "check":
        circle(12,12,9); line([(8,12),(11,15),(16,9)])
    elif name == "x":
        line([(6,6),(18,18)]); line([(18,6),(6,18)])
    elif name in ("left","right"):
        line([(15,5),(8,12),(15,19)] if name=="left" else [(9,5),(16,12),(9,19)])
    elif name == "code":
        line([(8,6),(2,12),(8,18)]); line([(16,6),(22,12),(16,18)])
    elif name == "list":
        for y in (5,12,19): line([(8,y),(21,y)]); circle(3,y,0.5)
    else:
        raise ValueError(f"Unknown icon: {name}")
    return ctk.CTkImage(light_image=im, dark_image=im, size=(size,size))


class IconTabs(ctk.CTkFrame):
    """Tabs with actual image icons instead of font-dependent symbol characters."""
    def __init__(self, master, command=None, **kwargs):
        for key in list(kwargs):
            if key.startswith("segmented_button_") or key == "text_color":
                kwargs.pop(key)
        super().__init__(master, **kwargs)
        self.command, self.current = command, ""
        self.pages, self.buttons = {}, {}
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        self.nav = ctk.CTkFrame(self,fg_color="#f6f8fa",corner_radius=7)
        self.nav.grid(row=0,column=0,sticky="ew",padx=5,pady=(8,9))

    def add(self, name):
        index = len(self.pages)
        symbol = {"Giọng đọc":"mic","Nền":"image","Video":"phone","JSON":"code","Danh sách":"list"}[name]
        page = ctk.CTkFrame(self,fg_color="white",corner_radius=0)
        self.pages[name] = page
        self.nav.grid_columnconfigure(index,weight=1)
        btn = ctk.CTkButton(self.nav,text=name,image=icon(symbol,"#7c8793",14),compound="left",
            command=lambda: self.set(name),width=55,height=30,font=("Segoe UI",11),corner_radius=5,
            fg_color="transparent",hover_color="#eef4f3",text_color="#7c8793",border_spacing=3)
        btn.grid(row=0,column=index,sticky="ew",padx=3,pady=3)
        self.buttons[name] = btn
        if not self.current: self.set(name,notify=False)
        return page

    def set(self, name, notify=True):
        if name not in self.pages: raise ValueError(name)
        for key,page in self.pages.items():
            page.grid_remove()
            symbol = {"Giọng đọc":"mic","Nền":"image","Video":"phone","JSON":"code","Danh sách":"list"}[key]
            self.buttons[key].configure(fg_color="#e7f5f1" if key==name else "transparent",text_color="#218c7c" if key==name else "#7c8793",image=icon(symbol,"#218c7c" if key==name else "#7c8793",14))
        self.pages[name].grid(row=1,column=0,sticky="nsew",padx=5,pady=(0,5))
        self.current = name
        if notify and self.command: self.command()

    def get(self):
        return self.current
