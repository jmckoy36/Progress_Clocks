#!/usr/bin/env python3
"""
Danger Clocks + Tug-of-War Clock (Linear)
- Notes windows titled with the clock name (e.g., "Danger Clock 1 — Notes").
- Auto-save every 5 minutes (enabled by default). Toggle in File menu.
- Tug-of-War tabs auto-number; Danger Clock has selectable fill color.
- Notes button on both clocks -> modal text area, saved in session.
- Tug-of-War labels draw only if the segment is owned AND the label is non-default ("Objective N").
- Popup tally appears when all objectives are owned (fires once per all-owned state).
"""

import json
import math
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from datetime import datetime

# Optional export dependency (gracefully handled if missing)
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# ---- Appearance / geometry constants ----
PADDING = 16
TITLE_SPACE = 44
LINE_W = 3
SEGMENT_CHOICES = (4, 6, 8, 12)

# Divider "gutters"
SEP_W_BG = 8
SEP_W_FG = 2

# Tug-of-War defaults
DEFAULT_TEAM_COLORS = ["#2E86DE", "#E74C3C", "#27AE60", "#F1C40F"]  # blue, red, green, gold

# Autosave interval (ms)
AUTOSAVE_MS = 5 * 60 * 1000  # 5 minutes


def get_app_dir() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", str(Path.home())))
        return base / "MultiProgressClocks"
    else:
        return Path.home() / ".multi_progress_clocks"


APP_DIR = get_app_dir()
APP_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_SESSION_PATH = APP_DIR / "session.json"


# ---------------------------
# Utilities
# ---------------------------

def _text_size(draw: "ImageDraw.ImageDraw", text: str, font):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        return max(6, len(text)) * 7, 12  # fallback estimate


def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(ch * 2 for ch in hex_color)
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except Exception:
        return (0, 0, 0)


def _contrast_text_color(bg_hex: str) -> str:
    r, g, b = _hex_to_rgb(bg_hex)
    luminance = 0.2126 * (r / 255) + 0.7152 * (g / 255) + 0.0722 * (b / 255)
    return "#000000" if luminance > 0.6 else "#FFFFFF"


def _next_numbered_title(existing_titles, base):
    used = set()
    for t in existing_titles:
        t = (t or "").strip()
        if t == base:
            used.add(1)
        elif t.startswith(base + " "):
            tail = t[len(base) + 1:].strip()
            if tail.isdigit():
                used.add(int(tail))
    n = 1
    while n in used:
        n += 1
    return f"{base} {n}"


def _default_labels(n: int):
    """Return ['Objective 1', ..., 'Objective n']"""
    return [f"Objective {i+1}" for i in range(n)]


# ---------------------------
# Modal Notes helper
# ---------------------------

def open_notes_modal(parent, initial_text: str, title_text: str) -> str | None:
    """Open a modal Notes window centered over the app's current window."""
    # Resolve the real toplevel (root window) for correct monitor placement
    root = parent.winfo_toplevel()
    root.update_idletasks()  # ensure geometry info is current

    # Create the modal
    top = tk.Toplevel(root)
    top.title(f"{title_text} — Notes")
    top.transient(root)
    top.grab_set()
    top.minsize(420, 260)

    # ---- Center over the root window (same monitor as app) ----
    # Root's absolute position on the virtual screen (across monitors)
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    if rw <= 1 or rh <= 1:  # first open edge case: use geometry string
        try:
            geom = root.geometry()  # e.g., "980x720+2560+120"
            parts = geom.split("+")
            size = parts[0].split("x")
            rw = int(size[0]); rh = int(size[1])
            rx = int(parts[1]); ry = int(parts[2])
        except Exception:
            pass

    # Desired popup size (initial)
    pw, ph = 560, 360
    px = rx + max(0, (rw - pw) // 2)
    py = ry + max(0, (rh - ph) // 2)
    top.geometry(f"{pw}x{ph}+{px}+{py}")
    top.lift()
    top.focus_force()

    # ---- UI ----
    frm = ttk.Frame(top, padding=8)
    frm.pack(fill="both", expand=True)

    txt = tk.Text(frm, wrap="word", height=12)
    txt.pack(fill="both", expand=True)
    if initial_text:
        txt.insert("1.0", initial_text)

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(8, 0))
    saved_text = {"val": None}

    def do_save():
        saved_text["val"] = txt.get("1.0", "end-1c")
        top.destroy()

    def do_cancel():
        saved_text["val"] = None
        top.destroy()

    ttk.Button(btns, text="Save Notes", command=do_save).pack(side="left")
    ttk.Button(btns, text="Cancel", command=do_cancel).pack(side="right")

    # Put caret in the text box
    top.after(50, lambda: (txt.focus_set(), txt.see("end")))
    parent.wait_window(top)
    return saved_text["val"]



# ---------------------------
# Danger Clock (circular fill) with fill color + notes
# ---------------------------

class ClockFrame(ttk.Frame):
    TYPE = "clock"

    def __init__(self, master, initial_title="Danger Clock", segments=4, filled=0, inverted=False,
                 fill_color=None, notes=""):
        super().__init__(master)

        self.segments = tk.IntVar(value=segments)
        self.filled = int(filled)
        self.inverted = tk.BooleanVar(value=bool(inverted))
        self.title_var = tk.StringVar(value=initial_title)
        # default fill based on theme if not provided
        self.fill_color = fill_color or ("#000000" if not inverted else "#FFFFFF")
        self.notes = notes or ""

        for col in range(8):
            self.columnconfigure(col, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text="Clock Title:").grid(row=0, column=0, sticky="e", padx=6, pady=(8, 0))
        title_entry = ttk.Entry(self, textvariable=self.title_var, width=32, justify="center")
        title_entry.grid(row=0, column=1, columnspan=2, padx=6, pady=(8, 0), sticky="we")
        title_entry.bind("<KeyRelease>", lambda e: self.draw())

        ttk.Label(self, text="Segments:").grid(row=0, column=3, sticky="e", padx=6, pady=(8, 0))
        seg_box = ttk.Combobox(self, state="readonly", values=SEGMENT_CHOICES, width=6, textvariable=self.segments)
        seg_box.grid(row=0, column=4, padx=6, pady=(8, 0), sticky="w")
        seg_box.bind("<<ComboboxSelected>>", self.on_segments_changed)

        inv_chk = ttk.Checkbutton(self, text="Invert colors", variable=self.inverted, command=self.draw)
        inv_chk.grid(row=0, column=5, padx=(6, 10), pady=(8, 0), sticky="w")

        # Fill color picker
        ttk.Button(self, text="Fill Color", command=self.choose_fill_color).grid(row=0, column=6, padx=(6, 2), pady=(8, 0))
        self.fill_preview = tk.Label(self, width=10, bg=self.fill_color, relief="sunken")
        self.fill_preview.grid(row=0, column=7, padx=(0, 10), pady=(8, 0), sticky="w")

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.grid(row=1, column=0, columnspan=8, sticky="nsew", padx=8, pady=8)
        self.canvas.bind("<Configure>", lambda e: self.draw())

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=8, pady=(0, 10))
        ttk.Button(btn_frame, text="−1", width=6, command=self.decrease).grid(row=0, column=0, padx=6)
        ttk.Button(btn_frame, text="+1", width=6, command=self.increase).grid(row=0, column=1, padx=6)
        ttk.Button(btn_frame, text="Reset", width=8, command=self.reset).grid(row=0, column=2, padx=6)
        self.value_var = tk.StringVar(value=str(self.filled))
        ttk.Label(btn_frame, text="Filled:").grid(row=0, column=3, padx=(16, 0))
        ttk.Label(btn_frame, textvariable=self.value_var, width=3).grid(row=0, column=4, padx=(4, 12))
        ttk.Button(btn_frame, text="Save PNG", width=10, command=self.save_png).grid(row=0, column=5, padx=6)
        ttk.Button(btn_frame, text="Notes", width=10, command=self.open_notes).grid(row=0, column=6, padx=6)

        self.canvas.bind("<Button-1>", lambda e: self.increase())
        self.canvas.bind("<Button-3>", lambda e: self.decrease())
        self.bind_all("+", lambda e: self.increase())
        self.bind_all("-", lambda e: self.decrease())
        self.bind_all("<r>", lambda e: self.reset())
        self.bind_all("<R>", lambda e: self.reset())

        self.draw()

    def choose_fill_color(self):
        initial = self.fill_color
        (rgb, hexv) = colorchooser.askcolor(color=initial, title=f"Choose Danger fill color")
        if hexv:
            self.fill_color = hexv
            try:
                self.fill_preview.configure(bg=hexv)
            except Exception:
                pass
            self.draw()

    def on_segments_changed(self, _=None):
        if self.filled > self.segments.get():
            self.filled = self.segments.get()
        self.draw()

    def increase(self):
        if self.filled < self.segments.get():
            self.filled += 1
            self.draw()

    def decrease(self):
        if self.filled > 0:
            self.filled -= 1
            self.draw()

    def reset(self):
        self.filled = 0
        self.draw()

    def _colors(self):
        return {"bg": "black", "fg": "white"} if self.inverted.get() else {"bg": "white", "fg": "black"}

    def draw(self):
        c = self.canvas
        c.delete("all")
        colors = self._colors()
        c.configure(bg=colors["bg"])

        w = max(1, c.winfo_width())
        h = max(1, c.winfo_height())

        c.create_text(w / 2, 16, text=self.title_var.get(), font=("Arial", 16, "bold"), fill=colors["fg"])

        usable_h = max(1, h - TITLE_SPACE)
        r = max(1, min((w - 2 * PADDING), (usable_h - 2 * PADDING)) / 2)
        cx, cy = w / 2, TITLE_SPACE + usable_h / 2
        x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r

        segs = max(1, int(self.segments.get()))
        extent = 360 / segs
        start_base = 90

        for i in range(self.filled):
            start = start_base - i * extent
            c.create_arc(x0, y0, x1, y1, start=start, extent=-extent,
                         style=tk.PIESLICE, outline="", fill=self.fill_color)

        for i in range(segs):
            ang = math.radians(start_base - i * extent)
            x_end = cx + r * math.cos(ang)
            y_end = cy - r * math.sin(ang)
            c.create_line(cx, cy, x_end, y_end, width=SEP_W_BG, fill=colors["bg"])
            c.create_line(cx, cy, x_end, y_end, width=SEP_W_FG, fill=colors["fg"])

        c.create_oval(x0, y0, x1, y1, width=LINE_W, outline=colors["fg"])
        c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=colors["fg"], outline=colors["fg"])
        self.value_var.set(str(self.filled))

    def save_png(self):
        if not PIL_AVAILABLE:
            messagebox.showerror("Pillow not installed", "PNG export requires Pillow.\n\npip install pillow")
            return

        path = filedialog.asksaveasfilename(title="Save Danger Clock as PNG", defaultextension=".png",
                                            filetypes=[("PNG image", "*.png")])
        if not path:
            return

        w = max(200, self.canvas.winfo_width())
        h = max(200, self.canvas.winfo_height())
        colors = self._colors()

        img = Image.new("RGB", (w, h), color=colors["bg"])
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        title = self.title_var.get()
        tw, th = _text_size(draw, title, font)
        draw.text(((w - tw) / 2, 8), title, fill=colors["fg"], font=font)

        usable_h = max(1, h - TITLE_SPACE)
        r = max(1, min((w - 2 * PADDING), (usable_h - 2 * PADDING)) / 2)
        cx, cy = w / 2, TITLE_SPACE + usable_h / 2
        x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r

        segs = max(1, int(self.segments.get()))
        extent = 360 / segs
        start_base = 90

        for i in range(self.filled):
            start = start_base - i * extent
            # PIL expects degrees CCW from 3 o'clock; map our 12 o'clock CW angles:
            start_pil = (360 - start) % 360
            end_pil = (360 - (start - extent)) % 360
            draw.pieslice([x0, y0, x1, y1], start=start_pil, end=end_pil,
                          fill=self.fill_color, outline=None)

        for i in range(segs):
            ang = math.radians(start_base - i * extent)
            x_end = cx + r * math.cos(ang)
            y_end = cy - r * math.sin(ang)
            draw.line([cx, cy, x_end, y_end], fill=colors["bg"], width=SEP_W_BG)
            draw.line([cx, cy, x_end, y_end], fill=colors["fg"], width=SEP_W_FG)

        draw.ellipse([x0, y0, x1, y1], outline=colors["fg"], width=LINE_W)
        draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=colors["fg"], outline=colors["fg"])

        try:
            img.save(path, format="PNG")
            messagebox.showinfo("Saved", f"Saved Danger Clock PNG to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save PNG:\n{e}")

    # --- Notes ---
    def open_notes(self):
        result = open_notes_modal(self, self.notes, self.title_var.get() or "Danger Clock")
        if result is not None:
            self.notes = result

    # Serialization
    def to_dict(self):
        return {
            "type": self.TYPE,
            "title": self.title_var.get(),
            "segments": int(self.segments.get()),
            "filled": int(self.filled),
            "inverted": bool(self.inverted.get()),
            "fill_color": self.fill_color,
            "notes": self.notes,
        }

    def from_dict(self, data: dict):
        self.title_var.set(data.get("title", "Danger Clock"))
        self.segments.set(int(data.get("segments", 4)))
        self.filled = int(data.get("filled", 0))
        self.inverted.set(bool(data.get("inverted", False)))
        self.fill_color = data.get("fill_color", self.fill_color)
        self.notes = data.get("notes", "")
        try:
            self.fill_preview.configure(bg=self.fill_color)
        except Exception:
            pass
        self.draw()


# ---------------------------
# Tug-of-War Clock (Linear) — labels only if owned & non-default, tally popup, notes
# ---------------------------

class TugOfWarLinearFrame(ttk.Frame):
    TYPE = "tug_linear"

    def __init__(self, master, initial_title="Tug-of-War Clock", segments=6, team_count=2,
                 teams=None, ownership=None, labels=None, inverted=False, notes=""):
        super().__init__(master)

        self.title_var = tk.StringVar(value=initial_title)
        self.segments = tk.IntVar(value=segments)
        self.inverted = tk.BooleanVar(value=bool(inverted))
        self.notes = notes or ""

        if teams is None:
            teams = [{"name": f"Team {i+1}", "color": DEFAULT_TEAM_COLORS[i % len(DEFAULT_TEAM_COLORS)]}
                     for i in range(max(2, min(4, int(team_count))))]
        self.teams = teams

        segs = max(1, int(segments))
        self.ownership = list(ownership) if ownership and len(ownership) == segs else [-1] * segs
        self.labels = list(labels) if labels and len(labels) == segs else _default_labels(segs)

        self._tally_shown = False

        for col in range(10):
            self.columnconfigure(col, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text="Title:").grid(row=0, column=0, sticky="e", padx=6, pady=(8, 0))
        title_entry = ttk.Entry(self, textvariable=self.title_var, width=28, justify="center")
        title_entry.grid(row=0, column=1, columnspan=3, padx=6, pady=(8, 0), sticky="we")
        title_entry.bind("<KeyRelease>", lambda e: self.draw())

        ttk.Label(self, text="Segments:").grid(row=0, column=4, sticky="e", padx=6, pady=(8, 0))
        seg_box = ttk.Combobox(self, state="readonly", values=SEGMENT_CHOICES, width=6, textvariable=self.segments)
        seg_box.grid(row=0, column=5, padx=6, pady=(8, 0), sticky="w")
        seg_box.bind("<<ComboboxSelected>>", self.on_segments_changed)

        ttk.Label(self, text="Teams:").grid(row=0, column=6, sticky="e", padx=6, pady=(8, 0))
        self.team_count = tk.IntVar(value=len(self.teams))
        team_box = ttk.Combobox(self, state="readonly", values=(2, 3, 4), width=4, textvariable=self.team_count)
        team_box.grid(row=0, column=7, padx=6, pady=(8, 0), sticky="w")
        team_box.bind("<<ComboboxSelected>>", self.on_team_count_changed)

        inv_chk = ttk.Checkbutton(self, text="Invert colors", variable=self.inverted, command=self.draw)
        inv_chk.grid(row=0, column=8, padx=(6, 10), pady=(8, 0), sticky="w")

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0, cursor="hand2")
        self.canvas.grid(row=1, column=0, columnspan=10, sticky="nsew", padx=8, pady=8)
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<Button-1>", self.on_click_cycle)
        self.canvas.bind("<Button-3>", self.on_click_unclaim)

        bottom = ttk.Frame(self)
        bottom.grid(row=2, column=0, columnspan=10, pady=(0, 10), sticky="we")
        for i in range(10):
            bottom.columnconfigure(i, weight=1)

        # Team editors
        self._team_rows = []
        self._rebuild_team_rows(bottom)

        # Label editors
        ttk.Label(bottom, text="Objective Labels (render only if owned AND non-default):").grid(
            row=2, column=0, sticky="w", padx=6, pady=(8, 4), columnspan=10
        )
        self.labels_frame = ttk.Frame(bottom)
        self.labels_frame.grid(row=3, column=0, columnspan=10, sticky="we", padx=6)
        self._label_vars = []
        self._rebuild_label_rows()

        ttk.Button(bottom, text="Reset Ownership", command=self.reset).grid(row=4, column=0, padx=6, pady=(8, 0), sticky="w")
        ttk.Button(bottom, text="Save PNG", command=self.save_png).grid(row=4, column=1, padx=6, pady=(8, 0), sticky="w")
        ttk.Button(bottom, text="Notes", command=self.open_notes).grid(row=4, column=2, padx=6, pady=(8, 0), sticky="w")

        self.draw()

    # Colors / theme
    def _colors(self):
        return {"bg": "black", "fg": "white"} if self.inverted.get() else {"bg": "white", "fg": "black"}

    # Team rows
    def _rebuild_team_rows(self, parent):
        for row in getattr(self, "_team_rows", []):
            for w in row: w.destroy()
        self._team_rows = []

        for i, team in enumerate(self.teams):
            name_var = tk.StringVar(value=team["name"])
            color_var = tk.StringVar(value=team["color"])

            def save_name(var=name_var, idx=i):
                self.teams[idx]["name"] = var.get().strip() or f"Team {idx+1}"
                self.draw()

            def choose_color(idx=i, cvar=color_var):
                initial = cvar.get()
                (rgb, hexv) = colorchooser.askcolor(color=initial, title=f"Choose color for {self.teams[idx]['name']}")
                if hexv:
                    self.teams[idx]["color"] = hexv
                    cvar.set(hexv)
                    self.draw()

            ttk.Label(parent, text=f"Team {i+1}:").grid(row=0, column=i*2, sticky="e", padx=(6, 2))
            entry = ttk.Entry(parent, textvariable=name_var, width=14)
            entry.grid(row=0, column=i*2+1, padx=(0, 4))
            entry.bind("<FocusOut>", lambda e, s=save_name: s())
            entry.bind("<Return>", lambda e, s=save_name: s())

            color_btn = ttk.Button(parent, text="Color", width=8, command=choose_color)
            color_btn.grid(row=1, column=i*2, padx=(6, 2), pady=(4, 0), sticky="e")
            color_lbl = tk.Label(parent, textvariable=color_var, width=10, bg=team["color"], fg="black", relief="sunken")
            color_lbl.grid(row=1, column=i*2+1, padx=(0, 4), pady=(4, 0), sticky="w")

            def sync_bg(lbl=color_lbl, cvar=color_var):
                try: lbl.configure(bg=cvar.get())
                except Exception: pass
                self.after(100, sync_bg)
            self.after(0, sync_bg)

            self._team_rows.append((entry, color_btn, color_lbl))

    # Labels grid
    def _rebuild_label_rows(self):
        for child in self.labels_frame.winfo_children(): child.destroy()
        self._label_vars = []
        cols = int(self.segments.get())
        # enforce correct defaults 1..N
        while len(self.labels) < cols:
            self.labels.append(f"Objective {len(self.labels)+1}")
        self.labels = self.labels[:cols]

        for i in range(cols):
            var = tk.StringVar(value=self.labels[i])
            ent = ttk.Entry(self.labels_frame, textvariable=var, width=18)
            ent.grid(row=0, column=i, padx=4, pady=2, sticky="we")
            ent.bind("<FocusOut>", lambda e, idx=i, v=var: self._save_label(idx, v))
            ent.bind("<Return>",  lambda e, idx=i, v=var: self._save_label(idx, v))
            self.labels_frame.columnconfigure(i, weight=1)
            self._label_vars.append(var)

    def _save_label(self, idx, var):
        txt = var.get().strip() or f"Objective {idx+1}"
        var.set(txt)
        if idx < len(self.labels):
            self.labels[idx] = txt
        self.draw()

    # Events
    def on_segments_changed(self, _=None):
        new_segs = int(self.segments.get())
        old_own = list(self.ownership)
        old_labels = list(self.labels)
        self.ownership = (old_own[:new_segs] + [-1] * new_segs)[:new_segs]
        defaults = _default_labels(new_segs)
        merged = []
        for i in range(new_segs):
            merged.append(old_labels[i] if i < len(old_labels) else defaults[i])
        self.labels = merged
        self._rebuild_label_rows()
        self.draw()

    def on_team_count_changed(self, _=None):
        count = int(self.team_count.get())
        if count > len(self.teams):
            for i in range(len(self.teams), count):
                self.teams.append({"name": f"Team {i+1}", "color": DEFAULT_TEAM_COLORS[i % len(DEFAULT_TEAM_COLORS)]})
        else:
            self.teams = self.teams[:count]
        for i, v in enumerate(self.ownership):
            if v >= count:
                self.ownership[i] = -1
        parent = self.children[next(k for k in self.children if isinstance(self.children[k], ttk.Frame))]
        self._rebuild_team_rows(parent)
        self.draw()

    def reset(self):
        self.ownership = [-1] * int(self.segments.get())
        self._tally_shown = False
        self.draw()

    def _segment_at(self, x, y):
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        top = TITLE_SPACE + PADDING
        bottom = h - PADDING - 40
        if bottom <= top + 10: return None
        left, right = PADDING, w - PADDING
        segs = max(1, int(self.segments.get()))
        seg_w = (right - left) / segs
        if x < left or x > right or y < top or y > bottom: return None
        idx = int((x - left) // seg_w)
        return min(max(idx, 0), segs - 1)

    def on_click_cycle(self, e):
        idx = self._segment_at(e.x, e.y)
        if idx is None: return
        current = self.ownership[idx]
        count = len(self.teams)
        self.ownership[idx] = -1 if current == count - 1 else current + 1
        self.draw()
        self._maybe_show_tally()

    def on_click_unclaim(self, e):
        idx = self._segment_at(e.x, e.y)
        if idx is None: return
        self.ownership[idx] = -1
        self._tally_shown = False  # leaving all-owned state
        self.draw()

    # Tally popup logic
    def _maybe_show_tally(self):
        if -1 in self.ownership:
            self._tally_shown = False
            return
        if self._tally_shown:
            return
        counts = [0] * len(self.teams)
        for owner in self.ownership:
            if 0 <= owner < len(counts):
                counts[owner] += 1
        lines = [f"{self.teams[i]['name']}: {counts[i]}" for i in range(len(self.teams))]
        messagebox.showinfo("Tug-of-War Tally", "All objectives are owned.\n\n" + "\n".join(lines))
        self._tally_shown = True

    # Drawing
    def draw(self):
        c = self.canvas
        c.delete("all")
        colors = self._colors()
        c.configure(bg=colors["bg"])

        w = max(1, c.winfo_width())
        h = max(1, c.winfo_height())

        c.create_text(w/2, 16, text=self.title_var.get(), font=("Arial", 16, "bold"), fill=colors["fg"])

        track_top = TITLE_SPACE + PADDING
        track_bottom = h - PADDING - 40
        track_left, track_right = PADDING, w - PADDING
        segs = max(1, int(self.segments.get()))
        seg_w = max(10, (track_right - track_left) / segs)
        track_height = max(40, (track_bottom - track_top))

        # Segments
        for i in range(segs):
            x0 = track_left + i * seg_w
            x1 = track_left + (i + 1) * seg_w
            y0, y1 = track_top, track_top + track_height
            owner = self.ownership[i] if i < len(self.ownership) else -1
            fill_color = colors["bg"] if owner == -1 else self.teams[owner]["color"]
            c.create_rectangle(x0, y0, x1, y1, outline="", fill=fill_color)

            # Label ONLY if owned AND not default "Objective N"
            default_label = f"Objective {i+1}"
            label = self.labels[i] if i < len(self.labels) else default_label
            if owner != -1 and label.strip() and label.strip() != default_label:
                text_color = _contrast_text_color(fill_color)
                c.create_text((x0 + x1)/2, y0 + track_height/2,
                              text=label, fill=text_color, font=("Arial", 12, "bold"))

        # Dividers
        for i in range(1, segs):
            x = track_left + i * seg_w
            c.create_line(x, track_top, x, track_top + track_height, width=SEP_W_BG, fill=colors["bg"])
            c.create_line(x, track_top, x, track_top + track_height, width=SEP_W_FG, fill=colors["fg"])

        # Border
        c.create_rectangle(track_left, track_top, track_right, track_top + track_height,
                           outline=colors["fg"], width=LINE_W)

        # Legend
        legend_y = h - 20
        x = 10
        for t in self.teams:
            sw = 18
            c.create_rectangle(x, legend_y-10, x+sw, legend_y+10, fill=t["color"], outline=colors["fg"])
            c.create_text(x + sw + 6, legend_y, text=t["name"], anchor="w", fill=colors["fg"])
            x += sw + 6 + (len(t["name"]) * 8) + 12

        # Win banner if same team owns all
        winner = self._check_winner()
        if winner is not None:
            msg = f"{self.teams[winner]['name']} wins!"
            c.create_text(w/2, track_top + track_height/2, text=msg, font=("Arial", 18, "bold"), fill=colors["fg"])

    def _check_winner(self):
        segs = max(1, int(self.segments.get()))
        if len(self.ownership) < segs or segs == 0: return None
        first = self.ownership[0]
        if first == -1: return None
        for i in range(1, segs):
            if self.ownership[i] != first:
                return None
        return first

    # Export
    def save_png(self):
        if not PIL_AVAILABLE:
            messagebox.showerror("Pillow not installed", "PNG export requires Pillow.\n\npip install pillow")
            return

        path = filedialog.asksaveasfilename(title="Save Tug-of-War Clock as PNG",
                                            defaultextension=".png",
                                            filetypes=[("PNG image", "*.png")])
        if not path:
            return

        w = max(500, self.canvas.winfo_width())
        h = max(260, self.canvas.winfo_height())
        colors = self._colors()

        img = Image.new("RGB", (w, h), color=colors["bg"])
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        title = self.title_var.get()
        tw, th = _text_size(draw, title, font)
        draw.text(((w - tw) / 2, 8), title, fill=colors["fg"], font=font)

        track_top = TITLE_SPACE + PADDING
        track_bottom = h - PADDING - 40
        track_left, track_right = PADDING, w - PADDING
        segs = max(1, int(self.segments.get()))
        seg_w = max(10, (track_right - track_left) / segs)
        track_height = max(40, (track_bottom - track_top))

        # Segments & labels (labels ONLY if owned AND not default)
        for i in range(segs):
            x0 = int(track_left + i * seg_w)
            x1 = int(track_left + (i + 1) * seg_w)
            y0 = int(track_top)
            y1 = int(track_top + track_height)
            owner = self.ownership[i] if i < len(self.ownership) else -1
            fill_color = colors["bg"] if owner == -1 else self.teams[owner]["color"]
            draw.rectangle([x0, y0, x1, y1], fill=fill_color, outline=None)

            default_label = f"Objective {i+1}"
            label = self.labels[i] if i < len(self.labels) else default_label
            if owner != -1 and label.strip() and label.strip() != default_label:
                text_color = _contrast_text_color(fill_color)
                lw, lh = _text_size(draw, label, font)
                draw.text((x0 + (x1 - x0 - lw) / 2, y0 + (track_height - lh) / 2),
                          label, fill=text_color, font=font)

        # Dividers
        for i in range(1, segs):
            x = int(track_left + i * seg_w)
            draw.line([x, track_top, x, track_top + track_height], fill=colors["bg"], width=SEP_W_BG)
            draw.line([x, track_top, x, track_top + track_height], fill=colors["fg"], width=SEP_W_FG)

        # Border
        draw.rectangle([track_left, track_top, track_right, track_top + track_height],
                       outline=colors["fg"], width=LINE_W)

        # Legend
        legend_y = h - 20
        x = 10
        for t in self.teams:
            sw = 18
            draw.rectangle([x, legend_y-10, x+sw, legend_y+10], fill=t["color"], outline=colors["fg"])
            name = t["name"]
            nw, nh = _text_size(draw, name, font)
            draw.text((x + sw + 6, legend_y - nh / 2), name, fill=colors["fg"], font=font)
            x += sw + 6 + nw + 12

        # Win banner
        winner = self._check_winner()
        if winner is not None:
            msg = f"{self.teams[winner]['name']} wins!"
            mw, mh = _text_size(draw, msg, font)
            draw.text(((w - mw) / 2, track_top + (track_height - mh) / 2), msg, fill=colors["fg"], font=font)

    # --- Notes ---
    def open_notes(self):
        result = open_notes_modal(self, self.notes, self.title_var.get() or "Tug-of-War Clock")
        if result is not None:
            self.notes = result

    # Serialization
    def to_dict(self):
        return {
            "type": self.TYPE,
            "title": self.title_var.get(),
            "segments": int(self.segments.get()),
            "inverted": bool(self.inverted.get()),
            "teams": [{"name": t["name"], "color": t["color"]} for t in self.teams],
            "ownership": list(self.ownership),
            "labels": list(self.labels),
            "notes": self.notes,
        }

    def from_dict(self, data: dict):
        self.title_var.set(data.get("title", "Tug-of-War Clock"))
        segs = int(data.get("segments", 6))
        self.segments.set(segs)
        self.inverted.set(bool(data.get("inverted", False)))
        self.teams = list(data.get("teams", self.teams))
        self.ownership = list(data.get("ownership", [-1] * segs))[:segs] + [-1] * max(0, segs - len(data.get("ownership", [])))
        lbls = list(data.get("labels", _default_labels(segs)))
        lbls = (lbls[:segs] + _default_labels(segs))[:segs]
        for i in range(segs):
            if not lbls[i].strip():
                lbls[i] = f"Objective {i+1}"
        self.labels = lbls
        self.notes = data.get("notes", "")
        self.team_count = tk.IntVar(value=len(self.teams))
        parent = self.children[next(k for k in self.children if isinstance(self.children[k], ttk.Frame))]
        self._rebuild_team_rows(parent)
        self._rebuild_label_rows()
        self._tally_shown = False
        self.draw()


# ---------------------------
# App shell (Danger + Tug-of-War Clock) — with auto-numbering & auto-save
# ---------------------------

class MultiClockApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Danger & Tug-of-War Clocks")
        self.geometry("980x720")
        self.minsize(700, 500)
        self.current_session_path: Path | None = None

        # Autosave state
        self.autosave_enabled = tk.BooleanVar(value=True)
        self._autosave_job = None

        self._build_menu()

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Add Danger Clock", command=self.add_danger_clock).pack(side="left", padx=6, pady=6)
        ttk.Button(toolbar, text="Add Tug-of-War Clock", command=self.add_tug_clock).pack(side="left", padx=6, pady=6)
        ttk.Button(toolbar, text="Remove Current", command=self.remove_current).pack(side="left", padx=6, pady=6)

        # Hotkeys
        self.bind_all("<Control-s>", lambda e: self.quick_save())
        self.bind_all("<Control-S>", lambda e: self.save_session_as())
        self.bind_all("<Control-Shift-S>", lambda e: self.save_session_as())
        self.bind_all("<Control-o>", lambda e: self.load_session())
        self.bind_all("<Control-O>", lambda e: self.load_session())
        self.bind_all("<Control-n>", lambda e: self.new_session())
        self.bind_all("<Control-N>", lambda e: self.new_session())

        self._auto_load_default()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if not self.nb.tabs():
            self.add_danger_clock()

        # Start autosave loop
        self._start_autosave()

    def _build_menu(self):
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=False)
        filemenu.add_command(label="New Session\tCtrl+N", command=self.new_session)
        filemenu.add_command(label="Load Session…\tCtrl+O", command=self.load_session)
        filemenu.add_separator()
        filemenu.add_command(label="Save Session\tCtrl+S", command=self.quick_save)
        filemenu.add_command(label="Save Session As…\tCtrl+Shift+S", command=self.save_session_as)
        filemenu.add_checkbutton(label="Enable Auto-Save (5 min)", variable=self.autosave_enabled,
                                 command=self._toggle_autosave)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=filemenu)
        self.config(menu=menubar)

    # Tabs
    def add_danger_clock(self, title=None, segments=4, filled=0, inverted=False, fill_color=None, notes=""):
        # Auto-number default Danger Clock titles
        if title is None or not title.strip() or title.strip().startswith("Danger Clock"):
            existing = [self._frame_from_tab(t).title_var.get() for t in self.nb.tabs()
                        if isinstance(self._frame_from_tab(t), ClockFrame)]
            if not title or not title.strip() or title.strip() == "Danger Clock":
                title = _next_numbered_title(existing, "Danger Clock")

        frame = ClockFrame(self.nb, initial_title=title, segments=segments, filled=filled,
                           inverted=inverted, fill_color=fill_color, notes=notes)
        self.nb.add(frame, text=self._short_title(title))

        def sync_label(*_):
            idx = self.nb.index(frame); self.nb.tab(idx, text=self._short_title(frame.title_var.get()))
        frame.title_var.trace_add("write", lambda *_: sync_label())
        self.nb.select(frame)

    def add_tug_clock(self, title=None, segments=6, team_count=2, teams=None, ownership=None, labels=None, inverted=False, notes=""):
        # Auto-number default Tug-of-War Clock titles
        if title is None or not title.strip() or title.strip().startswith("Tug-of-War Clock"):
            existing = [self._frame_from_tab(t).title_var.get() for t in self.nb.tabs()
                        if isinstance(self._frame_from_tab(t), TugOfWarLinearFrame)]
            if not title or not title.strip() or title.strip() == "Tug-of-War Clock":
                title = _next_numbered_title(existing, "Tug-of-War Clock")

        frame = TugOfWarLinearFrame(self.nb, initial_title=title, segments=segments, team_count=team_count,
                                    teams=teams, ownership=ownership, labels=labels,
                                    inverted=inverted, notes=notes)
        self.nb.add(frame, text=self._short_title(title))

        def sync_label(*_):
            idx = self.nb.index(frame); self.nb.tab(idx, text=self._short_title(frame.title_var.get()))
        frame.title_var.trace_add("write", lambda *_: sync_label())
        self.nb.select(frame)

    def remove_current(self):
        if self.nb.index("end") == 0: return
        current = self.nb.select()
        if current: self.nb.forget(current)

    def new_session(self, *_):
        for tab_id in self.nb.tabs(): self.nb.forget(tab_id)
        self.current_session_path = None
        self.add_danger_clock()

    # Save/Load
    def _auto_load_default(self):
        if DEFAULT_SESSION_PATH.exists():
            try:
                with open(DEFAULT_SESSION_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._load_from_data(data)
                self.current_session_path = DEFAULT_SESSION_PATH
            except Exception:
                pass

    def _on_close(self):
        try:
            self._save_to_path(DEFAULT_SESSION_PATH)
        except Exception:
            pass
        # cancel autosave job
        if self._autosave_job:
            try:
                self.after_cancel(self._autosave_job)
            except Exception:
                pass
        self.destroy()

    def _collect_tabs(self):
        items = []
        for tab_id in self.nb.tabs():
            frame = self._frame_from_tab(tab_id)
            if hasattr(frame, "to_dict"):
                items.append(frame.to_dict())
        return items

    def _save_to_path(self, path: Path):
        items = self._collect_tabs()
        if not items:
            raise RuntimeError("There are no tabs to save.")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"items": items}, f, ensure_ascii=False, indent=2)

    def quick_save(self, *_):
        target = self.current_session_path or DEFAULT_SESSION_PATH
        try:
            self._save_to_path(Path(target))
            messagebox.showinfo("Session saved", f"Saved to:\n{target}")
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save session:\n{e}")

    def save_session_as(self, *_):
        path = filedialog.asksaveasfilename(title="Save session as JSON",
                                            defaultextension=".json",
                                            filetypes=[("JSON files", "*.json")])
        if not path: return
        try:
            self._save_to_path(Path(path))
            self.current_session_path = Path(path)
            messagebox.showinfo("Session saved", f"Saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save session:\n{e}")

    def load_session(self, *_):
        path = filedialog.askopenfilename(title="Load session JSON", filetypes=[("JSON files", "*.json")])
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Load failed", f"Could not read session:\n{e}")
            return
        self._load_from_data(data)
        self.current_session_path = Path(path)
        messagebox.showinfo("Session loaded", "Session loaded successfully.")

    def _load_from_data(self, data: dict):
        items = data.get("items")
        if items is None:
            clocks = data.get("clocks", [])
            items = [{"type": "clock", **c} for c in clocks]

        for tab_id in self.nb.tabs(): self.nb.forget(tab_id)

        for item in items:
            t = item.get("type")
            if t == ClockFrame.TYPE:
                self.add_danger_clock(title=item.get("title", "Danger Clock"),
                                      segments=int(item.get("segments", 4)),
                                      filled=int(item.get("filled", 0)),
                                      inverted=bool(item.get("inverted", False)),
                                      fill_color=item.get("fill_color"),
                                      notes=item.get("notes", ""))
            elif t == TugOfWarLinearFrame.TYPE:
                self.add_tug_clock(title=item.get("title", "Tug-of-War Clock"),
                                   segments=int(item.get("segments", 6)),
                                   team_count=len(item.get("teams", [])) or 2,
                                   teams=item.get("teams"),
                                   ownership=item.get("ownership"),
                                   labels=item.get("labels"),
                                   inverted=bool(item.get("inverted", False)),
                                   notes=item.get("notes", ""))
            else:
                continue

    def _frame_from_tab(self, tab_id):
        return self.nametowidget(tab_id)

    @staticmethod
    def _short_title(title: str) -> str:
        title = (title or "Clock").strip()
        return (title[:18] + "…") if len(title) > 18 else title

    # ---- Autosave logic ----
    def _toggle_autosave(self):
        if self.autosave_enabled.get():
            self._start_autosave()
        else:
            if self._autosave_job:
                try:
                    self.after_cancel(self._autosave_job)
                except Exception:
                    pass
                self._autosave_job = None

    def _start_autosave(self):
        # Kick off the autosave loop if enabled
        if not self.autosave_enabled.get():
            return
        # schedule first tick soon
        self._schedule_next_autosave()

    def _schedule_next_autosave(self):
        if self._autosave_job:
            try:
                self.after_cancel(self._autosave_job)
            except Exception:
                pass
        self._autosave_job = self.after(AUTOSAVE_MS, self._autosave_tick)

    def _autosave_tick(self):
        if not self.autosave_enabled.get():
            return
        target = self.current_session_path or DEFAULT_SESSION_PATH
        try:
            self._save_to_path(Path(target))
            # (silent) could also log to console:
            # print(f"[{datetime.now().strftime('%H:%M:%S')}] Autosaved to {target}")
        except Exception:
            # Stay silent; try again next cycle
            pass
        finally:
            # schedule the next tick
            self._schedule_next_autosave()


if __name__ == "__main__":
    app = MultiClockApp()
    app.mainloop()
