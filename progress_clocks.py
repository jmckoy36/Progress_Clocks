#!/usr/bin/env python3
"""
Progress Clocks Application
"""

__version__ = "2.0.0"


import json
import math
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import tkinter.font as tkfont

# ---------------------------
# Config / constants
# ---------------------------
PADDING = 16
TITLE_SPACE = 56
LINE_W = 3
SEGMENT_CHOICES = (4, 6, 8, 12)
AUTOSAVE_MS = 5 * 60 * 1000  # 5 minutes

def get_app_dir() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", str(Path.home())))
        return base / "ProgressClocks"
    else:
        return Path.home() / ".progress_clocks"

APP_DIR = get_app_dir()
APP_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SESSION_PATH = APP_DIR / "session.json"
SETTINGS_PATH = APP_DIR / "settings.json"

# ---------------------------
# Utilities (shared)
# ---------------------------

# ---- Multi-monitor helpers (center on last-used monitor) ----
def _get_monitor_rect_from_point(x: int, y: int):
    """
    Windows: return (left, top, right, bottom) for the monitor containing point (x,y).
    Others: return primary screen rect using Tk's screen size.
    """
    try:
        import sys
        if sys.platform.startswith("win"):
            import ctypes
            from ctypes import wintypes

            MONITOR_DEFAULTTONEAREST = 2

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long),
                            ("top", ctypes.c_long),
                            ("right", ctypes.c_long),
                            ("bottom", ctypes.c_long)]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_ulong),
                            ("rcMonitor", RECT),
                            ("rcWork", RECT),
                            ("dwFlags", ctypes.c_ulong)]

            user32 = ctypes.windll.user32
            user32.MonitorFromPoint.restype = wintypes.HANDLE
            user32.MonitorFromPoint.argtypes = (wintypes.POINT, ctypes.c_ulong)

            pt = wintypes.POINT(x, y)
            hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
            if hmon:
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                    r = mi.rcWork  # use work area (excludes taskbar)
                    return (int(r.left), int(r.top), int(r.right), int(r.bottom))
    except Exception:
        pass

    # Fallback: center on primary screen using Tk (filled in by caller if needed)
    try:
        # We may not have a Tk root here; caller will handle fallback sizes.
        import tkinter as _tk
        _tmp = _tk.Tk()
        _tmp.update_idletasks()
        w = _tmp.winfo_screenwidth()
        h = _tmp.winfo_screenheight()
        _tmp.destroy()
        return (0, 0, int(w), int(h))
    except Exception:
        return (0, 0, 1920, 1080)  # hard fallback

def _center_geometry_on_rect(width: int, height: int, rect: tuple[int, int, int, int]) -> str:
    """Return a Tk geometry string WxH+X+Y centered in the given (l,t,r,b) rect."""
    l, t, r, b = rect
    mw = max(1, r - l)
    mh = max(1, b - t)
    x = l + max(0, (mw - width) // 2)
    y = t + max(0, (mh - height) // 2)
    return f"{int(width)}x{int(height)}+{int(x)}+{int(y)}"


def _hex_to_rgb(hex_color: str):
    s = hex_color.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch*2 for ch in s)
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return (0, 0, 0)

def _contrast_text_color(bg_hex: str) -> str:
    r, g, b = _hex_to_rgb(bg_hex)
    luminance = 0.2126*(r/255) + 0.7152*(g/255) + 0.0722*(b/255)
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

def load_settings() -> dict:
    """Read app settings from disk. Returns a dict with defaults if missing."""
    try:
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    # defaults
    return {
        "open_last_on_launch": False,    # user toggle
        "last_session_path": None,       # updated after a successful save/load
        "last_window_center": None,      # [cx, cy] in virtual screen coords
        "last_window_size": [900, 650],  # [w, h]
    }

def save_settings(data: dict) -> None:
    """Persist app settings to disk."""
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def center_window_over_parent(parent_widget, top, width=None, height=None):
    """Center Toplevel `top` over the toplevel window of `parent_widget`, on whatever monitor it's on."""
    root = parent_widget.winfo_toplevel()
    root.update_idletasks(); top.update_idletasks()

    # Parent window position/size in virtual screen coords (multi‑monitor aware)
    rx, ry = root.winfo_rootx(), root.winfo_rooty()
    rw, rh = root.winfo_width(), root.winfo_height()
    if rw <= 1 or rh <= 1:
        # fallback: parse geometry if width/height not realized yet
        try:
            g = root.geometry()
            size, x, y = g.split("+", 2)
            rw, rh = map(int, size.split("x"))
            rx, ry = int(x), int(y)
        except Exception:
            pass

    # Desired size: requested size unless explicitly given
    tw = width  or max(top.winfo_reqwidth(),  320)
    th = height or max(top.winfo_reqheight(), 200)

    px = rx + max(0, (rw - tw)//2)
    py = ry + max(0, (rh - th)//2)
    top.geometry(f"{tw}x{th}+{px}+{py}")


# ---------------------------
# Modal Notes (shared)
# ---------------------------
def open_notes_modal(parent, initial_text: str, title_text: str) -> str | None:
    root = parent.winfo_toplevel()
    root.update_idletasks()

    top = tk.Toplevel(root)
    top.title(f"{title_text} — Notes")
    top.transient(root)
    top.grab_set()
    top.minsize(420, 260)

    # center
    rx, ry = root.winfo_rootx(), root.winfo_rooty()
    rw, rh = root.winfo_width(), root.winfo_height()
    if rw <= 1 or rh <= 1:
        try:
            geom = root.geometry()
            parts = geom.split("+")
            size = parts[0].split("x")
            rw, rh = int(size[0]), int(size[1])
            rx, ry = int(parts[1]), int(parts[2])
        except Exception:
            pass
    pw, ph = 560, 360
    px = rx + max(0, (rw - pw)//2)
    py = ry + max(0, (rh - ph)//2)
    top.geometry(f"{pw}x{ph}+{px}+{py}")

    frm = ttk.Frame(top, padding=8)
    frm.pack(fill="both", expand=True)
    txt = tk.Text(frm, wrap="word", height=12)
    txt.pack(fill="both", expand=True)
    if initial_text:
        txt.insert("1.0", initial_text)

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(8,0))
    result = {"val": None}

    def do_save():
        result["val"] = txt.get("1.0", "end-1c")
        top.destroy()

    def do_cancel():
        result["val"] = None
        top.destroy()

    ttk.Button(btns, text="Save Notes", command=do_save).pack(side="left")
    ttk.Button(btns, text="Cancel", command=do_cancel).pack(side="right")

    top.after(50, lambda: (txt.focus_set(), txt.see("end")))
    parent.wait_window(top)
    return result["val"]

class SimpleSettingsDialog(tk.Toplevel):
    """Reusable modal with a vertical list of checkboxes and OK/Cancel."""
    def __init__(self, parent, title, items: list[tuple[str, tk.Variable]]):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        # Checkboxes
        for text, var in items:
            ttk.Checkbutton(frm, text=text, variable=var).pack(anchor="w", pady=2)

        # Buttons
        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(10,0))
        ttk.Button(btns, text="OK", command=self._ok).pack(side="right")
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(side="right", padx=(0,8))

        # Close handlers
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.result = None
        self._parent = parent

        # Center over parent
        self.update_idletasks()
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _ok(self):
        self.result = True
        self.destroy()

    def _cancel(self):
        self.result = False
        self.destroy()


# ---------------------------
# Shared ClockBase (very small)
#     The ClockBase(ttk.Frame) class is a base class that holds shared logic for all clock types.
#     It sets up common things like a title box, segment selector, etc.
# ---------------------------
class ClockBase(ttk.Frame):
    """Shared bits: title, invert, notes button, canvas, basic (de)serialize contract."""
    TYPE = "base"

    def __init__(self, master, initial_title="Clock", inverted=False, notes="", shared_inverted_var=None):
        super().__init__(master)
        self.title_var = tk.StringVar(value=initial_title)

        self.notes = notes or ""

        # Support shared dark-mode var (used by Racing container later)
        self._uses_shared_inverted = shared_inverted_var is not None
        self.inverted = shared_inverted_var or tk.BooleanVar(value=bool(inverted))

        # Always listen for changes to redraw, regardless of shared/non-shared.
        # (Dark Mode checkbox removed; toggled via the Settings dialog.)
        self._inv_trace_id = self.inverted.trace_add("write", lambda *_: self._on_theme_changed())

        ttk.Button(self, text="Notes", command=self.open_notes).grid(row=0, column=5, padx=6, pady=(8,0))

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.grid(row=1, column=0, columnspan=8, sticky="nsew", padx=8, pady=8)
        self.canvas.bind("<Configure>", lambda e: self.draw())

    def destroy(self):
        # detach shared dark-mode trace if any
        try:
            if getattr(self, "_uses_shared_inverted", False) and getattr(self, "_inv_trace_id", None):
                self.inverted.trace_remove("write", self._inv_trace_id)
                self._inv_trace_id = None
        except Exception:
            pass
        super().destroy()

    def _on_theme_changed(self):
        """Hook for subclasses when theme flips; default just redraws."""
        self.draw()

    def _colors(self):
        return {"bg":"black","fg":"white"} if self.inverted.get() else {"bg":"white","fg":"black"}

    def open_notes(self):
        res = open_notes_modal(self, self.notes, self.title_var.get() or "Clock")
        if res is not None:
            self.notes = res

    # to be implemented by subclasses
    def draw(self): ...
    def to_dict(self): ...
    def from_dict(self, data: dict): ...

# ---------------------------
# Danger Clock (circular fill)
#     The DangerClockFrame(ClockBase): class this is where your circular drawing lives.
# ---------------------------
class DangerClockFrame(ClockBase):
    TYPE = "danger"

    def __init__(self, master, initial_title="Danger Clock", segments=4, filled=0,
                 inverted=False, fill_color=None, notes="",
                 shared_segments_var=None, shared_inverted_var=None,
                 # NEW:
                 enable_label_ui=True,
                 click_mode="normal"   # "normal" (pick segment), "serial_next" (always next), "disabled"
                 ):
        super().__init__(master, initial_title=initial_title, inverted=inverted, notes=notes,
                         shared_inverted_var=shared_inverted_var)

        # --- Title controls (per-clock editable name) ---
        ttk.Label(self, text="Clock Name:").grid(row=0, column=0, padx=6, pady=(8, 0), sticky="w")
        title_entry = ttk.Entry(self, textvariable=self.title_var, width=20, justify="left")
        title_entry.grid(row=0, column=1, padx=(0, 12), pady=(8, 0), sticky="w")
        # Redraw the canvas whenever the title changes
        self.title_var.trace_add("write", lambda *_: self.draw())
        # OPTIONAL: live-update on each keystroke as well
        title_entry.bind("<KeyRelease>", lambda e: self.draw())
        # Settings button on the top bar
        ttk.Button(self, text="Settings", command=self.open_settings).grid(row=0, column=4, padx=(6, 6), pady=(8, 0),
                                                                           sticky="w")
        # --- Segments: allow a shared IntVar (used by Racing container later) ---
        self._uses_shared_segments = shared_segments_var is not None
        self.segments = shared_segments_var or tk.IntVar(value=int(segments))
        self._seg_trace_id = None

        if not self._uses_shared_segments:
            ttk.Label(self, text="Segments:").grid(row=0, column=6, sticky="e", padx=6, pady=(8, 0))
            seg_box = ttk.Combobox(self, state="readonly", values=SEGMENT_CHOICES, width=6, textvariable=self.segments)
            seg_box.grid(row=0, column=7, padx=6, pady=(8, 0), sticky="w")
            seg_box.bind("<<ComboboxSelected>>", lambda e: self._clamp_and_draw())
        else:
            # When segments are shared, listen for changes to resize/redraw
            self._seg_trace_id = self.segments.trace_add("write", lambda *_: self._clamp_and_draw())

        # ---- Initialize state that the controls depend on ----
        seg_count = int(self.segments.get())

        # filled pattern: first `filled` True, rest False
        self.filled = [False] * seg_count
        for i in range(min(int(filled), seg_count)):
            self.filled[i] = True

        # labels + toggle
        self.labels = [""] * seg_count
        self.show_labels = tk.BooleanVar(value=False)

        # default fill color: black in Light Mode, white in Dark Mode, unless a color was passed
        self.fill_color = fill_color or ("#FFFFFF" if self.inverted.get() else "#000000")

        # (RE)BIND CLICKS based on click_mode
        for seq in ("<Button-1>", "<Button-3>", "<Double-1>"):
            try:
                self.canvas.unbind(seq)
            except Exception:
                pass

        self._click_mode = click_mode
        if click_mode == "normal":
            self.canvas.bind("<Button-1>", self._on_left_click)
            self.canvas.bind("<Button-3>", self._on_right_click)
            self.canvas.bind("<Double-1>", self._on_double_click)
        elif click_mode == "serial_next":
            # Always advance one segment on any left click; ignore right/double
            self.canvas.bind("<Button-1>", lambda e: (self.increase(), None))
        elif click_mode == "disabled":
            pass  # no interactions

        # --- Controls (two rows so they don't get cut off when width is tight) ---
        # Give the buttons row a little guaranteed height
        self.rowconfigure(2, minsize=56)

        # Ensure the canvas row expands even with the second controls row present
        self.rowconfigure(1, weight=1)
        for col in range(8):
            self.columnconfigure(col, weight=1)

        # --- Controls row(s) ---
        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, columnspan=8, pady=(0, 10), sticky="we")

        # First line: +/- , Reset, Color, swatch
        line1 = ttk.Frame(btns)
        line1.pack(side="top", fill="x")

        ttk.Button(line1, text="−1", width=6, command=self.decrease).pack(side="left", padx=6)
        ttk.Button(line1, text="+1", width=6, command=self.increase).pack(side="left", padx=6)
        ttk.Button(line1, text="Reset", width=8, command=self.reset_with_prompt).pack(side="left", padx=6)

        ttk.Button(line1, text="Fill Color", command=self.choose_fill_color).pack(side="left", padx=12)
        self.fill_preview = tk.Label(line1, width=8, bg=self.fill_color, relief="sunken")
        self.fill_preview.pack(side="left")

        # line2: labels UI becomes optional
        line2 = ttk.Frame(btns)
        line2.pack(side="top", fill="x", pady=(4, 0))

        if enable_label_ui:
            ttk.Checkbutton(line2, text="Show Labels",
                            variable=self.show_labels,
                            command=self.draw).pack(side="left", padx=6)
            ttk.Button(line2, text="Edit Labels", command=self.edit_labels).pack(side="left", padx=6)

        # Keyboard shortcuts
        self.bind_all("+", lambda e: self.increase())
        self.bind_all("-", lambda e: self.decrease())
        self.bind_all("<r>", lambda e: self.reset())
        self.bind_all("<R>", lambda e: self.reset())

        # Defer the first draw until after the widget has a real size
        self.after_idle(self.draw)

    def is_complete(self) -> bool:
        return sum(self.filled) >= int(self.segments.get())

    def last_filled_index(self) -> int | None:
        """Return the highest index currently filled, or None if none."""
        n = sum(self.filled)
        return (n - 1) if n > 0 else None

    def destroy(self):
        # detach shared segments trace if any, then let base remove its trace, then destroy
        try:
            if getattr(self, "_uses_shared_segments", False) and getattr(self, "_seg_trace_id", None):
                self.segments.trace_remove("write", self._seg_trace_id)
                self._seg_trace_id = None
        except Exception:
            pass
        super().destroy()

    def _on_left_click(self, event):
        """Fill the clicked segment (turn it on)."""
        idx = self._pos_to_segment(event.x, event.y)
        if idx is not None:
            self.filled[idx] = True
            self._redraw_circle()

    def _on_right_click(self, event):
        """Un-fill the clicked segment (turn it off)."""
        idx = self._pos_to_segment(event.x, event.y)
        if idx is not None:
            self.filled[idx] = False
            self._redraw_circle()

    def _pos_to_segment(self, x, y):
        """
        Given a canvas (x,y) click, return the segment index 0..N-1,
        or None if the click is outside the circle.
        """
        import math

        seg_count = int(self.segments.get())
        if seg_count <= 0:
            return None

        # Use the exact center/radius computed in draw()
        cx = getattr(self, "center_x", None)
        cy = getattr(self, "center_y", None)
        r = getattr(self, "radius", None)

        # Fallback (shouldn't be needed once draw() has run)
        if cx is None or cy is None or r is None:
            w = int(self.canvas.winfo_width() or self.canvas.cget("width"))
            h = int(self.canvas.winfo_height() or self.canvas.cget("height"))
            size = min(w, h)
            pad = size * 0.05
            cx, cy = w / 2, h / 2
            r = (size / 2) - pad

        # Outside the circle? Ignore.
        dx, dy = x - cx, y - cy
        if (dx * dx + dy * dy) > (r * r):
            return None

        # Angle from +X axis with Y flipped (so "up" is positive)
        angle_deg = math.degrees(math.atan2(-dy, dx)) % 360

        # Our wedges are drawn CLOCKWISE from 12 o'clock:
        #   start_deg = 90 - i*seg_span, extent = -seg_span
        # So measure CLOCKWISE from top:
        angle_clockwise_from_top = (90 - angle_deg) % 360

        seg_span = 360 / seg_count
        idx = int(angle_clockwise_from_top // seg_span)

        # Clamp (safety)
        if idx < 0: idx = 0
        if idx >= seg_count: idx = seg_count - 1
        return idx

    def choose_fill_color(self):
        (rgb, hexv) = colorchooser.askcolor(
            color=self.fill_color,
            title="Choose fill color",
            parent=self.winfo_toplevel()  # NEW
        )

        if hexv:
            self.fill_color = hexv
            try: self.fill_preview.configure(bg=hexv)
            except Exception: pass
            self.draw()

    def _clamp_and_draw(self):
        # Ensure the lists match the new segments value (from the combobox).
        target = int(self.segments.get())
        self._resize_filled_to(target)
        self._resize_labels_to(target)
        self.draw()

    def increase(self):
        # Increase count of filled segments by 1
        current = sum(self.filled)
        if current < int(self.segments.get()):
            self._set_fill_count(current + 1)
            self.draw()

    def decrease(self):
        # Decrease count of filled segments by 1
        current = sum(self.filled)
        if current > 0:
            self._set_fill_count(current - 1)
            self.draw()

    def reset(self):
        # Clear all segments
        self._set_fill_count(0)
        self.draw()

    def reset_with_prompt(self):
        """Ask whether to also clear labels when resetting this single clock."""
        ans = messagebox.askquestion(
            "Reset Clock",
            "Reset this clock?\n\nAlso clear segment labels?",
            icon="question",
            parent=self.winfo_toplevel()
        )
        # 'yes' means also clear labels; 'no' means leave labels
        if ans == "yes":
            self.labels = [""] * int(self.segments.get())
            self.show_labels.set(self.show_labels.get())  # keep toggle state
        self.reset()

    def draw(self):
        # Bail out cleanly if widget/canvas is gone (during teardown)
        if not self.winfo_exists():
            return
        c = getattr(self, "canvas", None)
        if not c or not c.winfo_exists():
            return

        # If the canvas is still tiny (e.g., first layout pass), wait and redraw later
        w = int(c.winfo_width() or 0)
        h = int(c.winfo_height() or 0)
        if w < 120 or h < 120:
            self.after(50, self.draw)
            return

        c = self.canvas
        c.delete("all")
        colors = self._colors()
        c.configure(bg=colors["bg"])
        w = max(1, c.winfo_width()); h = max(1, c.winfo_height())

        # ----- Title (auto-fit to width, wrap if still too long) -----
        title_text = self.title_var.get()
        avail_w = max(1, w - 2 * PADDING)

        size = 16
        try:
            f = tkfont.Font(family="Arial", size=size, weight="bold")
            while f.measure(title_text) > avail_w and size > 9:
                size -= 1
                f.configure(size=size)
        except Exception:
            f = ("Arial", 12, "bold")

        extra = {}
        try:
            # If even the smallest font is still too wide, allow wrapping
            if isinstance(f, tkfont.Font) and f.measure(title_text) > avail_w:
                extra["width"] = avail_w
                extra["justify"] = "center"
        except Exception:
            pass

        # Draw from the very top (anchor north) so it doesn’t overlap the circle
        c.create_text(w / 2, 8, text=title_text, font=f, fill=colors["fg"], anchor="n", **extra)

        usable_h = max(1, h - TITLE_SPACE)
        r = max(1, min((w - 2*PADDING), (usable_h - 2*PADDING)) / 2)
        cx, cy = w/2, TITLE_SPACE + usable_h/2
        x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r

        segs = max(1, int(self.segments.get()))
        extent = 360 / segs
        start_base = 90

        # per-segment wedges (fill = True/False)
        seg_count = max(1, int(self.segments.get()))
        seg_span = 360 / seg_count

        # store center/radius for click detection
        self.center_x, self.center_y = cx, cy
        self.radius = r

        # clear any previously tagged arcs (if you ever redraw without clearing all)
        # (Not strictly needed since we did c.delete("all") above, but harmless.)
        c.delete("clock_arc")

        for i in range(seg_count):
            start_deg = 90 - (i * seg_span)           # put segment 0 at 12 o’clock
            is_filled = (i < len(self.filled)) and self.filled[i]
            fill_color = self.fill_color if is_filled else ""

            c.create_arc(
                x0, y0, x1, y1,
                start=start_deg,
                extent=-seg_span,                     # clockwise
                style=tk.PIESLICE,
                fill=fill_color,
                outline="#111111",
                width=2,
                tags=("clock_arc",),
            )

        # spokes
        for i in range(segs):
            ang = math.radians(start_base - i*extent)
            x_end = cx + r*math.cos(ang)
            y_end = cy - r*math.sin(ang)
            c.create_line(cx, cy, x_end, y_end, width=2, fill=colors["bg"])
            c.create_line(cx, cy, x_end, y_end, width=1, fill=colors["fg"])

        # border + dot
        c.create_oval(x0, y0, x1, y1, width=LINE_W, outline=colors["fg"])
        c.create_oval(cx-3, cy-3, cx+3, cy+3, fill=colors["fg"], outline=colors["fg"])

        # ----- Labels (on top) -----
        if self.show_labels.get():
            seg_count = max(1, int(self.segments.get()))
            seg_span = 360 / seg_count
            label_r = r * 0.60  # distance from center for text

            for i in range(seg_count):
                text = (self.labels[i] if i < len(self.labels) else "").strip()
                if not text:
                    continue

                # mid-angle of the wedge (drawing is clockwise)
                start_deg = 90 - (i * seg_span)
                mid_deg = start_deg - (seg_span / 2)
                ang = math.radians(mid_deg)

                tx = cx + label_r * math.cos(ang)
                ty = cy - label_r * math.sin(ang)

                # Choose a readable text color:
                # - if the segment is filled, contrast against the fill color
                # - otherwise, use the normal foreground color
                if (i < len(self.filled)) and self.filled[i]:
                    tcolor = _contrast_text_color(self.fill_color)
                else:
                    tcolor = colors["fg"]

                self.canvas.create_text(
                    tx, ty,
                    text=text,
                    fill=tcolor,
                    font=("Arial", 11, "bold"),
                    justify="center",
                )
        overlay = getattr(self, "_overlay_text", None)
        overlay_color = getattr(self, "_overlay_color", "#000000")
        if overlay:
            try:
                r = getattr(self, "radius", 60)
                size = max(12, int(r * 0.28))
                self.canvas.create_text(
                    self.center_x, self.center_y,
                    text=overlay,
                    font=("Consolas", size, "bold"),
                    fill=overlay_color
                )
            except Exception:
                pass

    def _on_theme_changed(self):
        """
        When toggling Dark Mode:
        - If fill is still the default (black), switch to white for visibility.
        - When switching back to Light Mode:
          If fill is white (the dark-mode default), switch back to black.
        Custom colors are left untouched.
        """
        fill = (self.fill_color or "").lower()

        if self.inverted.get():
            # Dark Mode ON: background becomes black
            if fill in ("#000000", "black"):
                self.fill_color = "#FFFFFF"
                try:
                    self.fill_preview.configure(bg=self.fill_color)
                except Exception:
                    pass
        else:
            # Dark Mode OFF: background becomes white
            if fill in ("#ffffff", "white"):
                self.fill_color = "#000000"
                try:
                    self.fill_preview.configure(bg=self.fill_color)
                except Exception:
                    pass

        self.draw()

    def open_settings(self):
        items = [("Dark Mode", self.inverted)]
        dlg = SimpleSettingsDialog(self.winfo_toplevel(), "Danger Clock Settings", items)
        self.wait_window(dlg)
        if dlg.result:
            self._on_theme_changed()

    # serialization
    def to_dict(self):
        return {
            "type": self.TYPE,
            "title": self.title_var.get(),
            "segments": int(self.segments.get()),
            "filled": int(sum(self.filled)),  # keep for backward compatibility
            "filled_list": list(bool(v) for v in self.filled),  # NEW: exact pattern
            "labels": list(self.labels),  # NEW
            "show_labels": bool(self.show_labels.get()),  # NEW
            "inverted": bool(self.inverted.get()),
            "fill_color": self.fill_color,
            "notes": self.notes,
        }

    def from_dict(self, data: dict):
        # basic fields
        self.title_var.set(data.get("title", "Danger Clock"))
        self.segments.set(int(data.get("segments", 4)))
        self.inverted.set(bool(data.get("inverted", False)))
        self.fill_color = data.get("fill_color", self.fill_color)
        self.notes = data.get("notes", "")

        # ensure list lengths match segments
        segs = int(self.segments.get())
        self._resize_filled_to(segs)
        self._resize_labels_to(segs)

        # prefer exact fill pattern if present
        flist = data.get("filled_list")
        if isinstance(flist, list) and len(flist) > 0:
            pattern = [bool(v) for v in flist][:segs]
            if len(pattern) < segs:
                pattern += [False] * (segs - len(pattern))
            self.filled = pattern
        else:
            count = int(data.get("filled", 0))
            self._set_fill_count(count)

        # labels + toggle
        lbls = data.get("labels")
        if isinstance(lbls, list):
            lbls = [str(v) if v is not None else "" for v in lbls][:segs]
            if len(lbls) < segs:
                lbls += [""] * (segs - len(lbls))
            self.labels = lbls
        else:
            self.labels = [""] * segs

        self.show_labels.set(bool(data.get("show_labels", False)))

        try:
            self.fill_preview.configure(bg=self.fill_color)
        except Exception:
            pass
        self.draw()


    def _resize_filled_to(self, new_count: int):
        """Keep self.filled list the same length as self.segments."""
        new_count = int(new_count)
        cur = len(self.filled)
        if new_count > cur:
            self.filled += [False] * (new_count - cur)
        elif new_count < cur:
            self.filled = self.filled[:new_count]

    def _set_fill_count(self, n: int):
        """Fill the first n segments True, rest False."""
        n = max(0, min(int(n), int(self.segments.get())))
        self.filled = [True]*n + [False]*(int(self.segments.get()) - n)

    def _redraw_circle(self):
        self.draw()

    def _resize_labels_to(self, new_count: int):
        new_count = int(new_count)
        cur = len(self.labels)
        if new_count > cur:
            self.labels += [""] * (new_count - cur)
        elif new_count < cur:
            self.labels = self.labels[:new_count]

    def edit_labels(self):
        """Simple modal to edit all segment labels at once."""
        segs = int(self.segments.get())
        self._resize_labels_to(segs)

        top = tk.Toplevel(self)
        top.title("Edit Segment Labels")
        top.transient(self.winfo_toplevel())
        top.grab_set()
        # NEW: center it over the app window
        center_window_over_parent(self, top)

        frm = ttk.Frame(top, padding=8)
        frm.pack(fill="both", expand=True)

        entries = []
        for i in range(segs):
            row = ttk.Frame(frm)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"Segment {i}").pack(side="left", padx=(0,8))
            e = ttk.Entry(row, width=32)
            e.pack(side="left", fill="x", expand=True)
            e.insert(0, self.labels[i] or "")
            entries.append(e)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(8, 0))

        def do_save():
            for i, e in enumerate(entries):
                self.labels[i] = e.get().strip()
            top.destroy()
            self.draw()

        def do_cancel():
            top.destroy()

        def do_clear_all():
            # Clear widgets immediately, and also clear labels on the clock
            for i, e in enumerate(entries):
                e.delete(0, "end")
                self.labels[i] = ""
            self.draw()

        ttk.Button(btns, text="Save Labels", command=do_save).pack(side="left")
        ttk.Button(btns, text="Clear All", command=do_clear_all).pack(side="left", padx=8)  # <— NEW
        ttk.Button(btns, text="Cancel", command=do_cancel).pack(side="right")

        # focus first entry
        top.after(50, lambda: (entries[0].focus_set(), entries[0].select_range(0, 'end')))
        self.wait_window(top)

    def _on_double_click(self, event):
        idx = self._pos_to_segment(event.x, event.y)
        if idx is None:
            return
        # quick prompt
        top = tk.Toplevel(self)
        top.title(f"Label for Segment {idx}")
        top.transient(self.winfo_toplevel()); top.grab_set()
        # NEW:
        center_window_over_parent(self, top)
        frm = ttk.Frame(top, padding=8); frm.pack(fill="both", expand=True)
        ent = ttk.Entry(frm, width=36)
        ent.pack(fill="x"); ent.insert(0, self.labels[idx] or "")
        btns = ttk.Frame(frm); btns.pack(fill="x", pady=(8,0))
        def ok():
            self.labels[idx] = ent.get().strip()
            top.destroy(); self.draw()
        def cancel():
            top.destroy()
        ttk.Button(btns, text="OK", command=ok).pack(side="left")
        ttk.Button(btns, text="Cancel", command=cancel).pack(side="right")
        top.after(50, lambda: (ent.focus_set(), ent.select_range(0, 'end')))
        self.wait_window(top)

class RacingClocksFrame(ttk.Frame):
    """
    A tab that holds 2..6 circular dials which all share the same segments count and dark mode.
    Each dial is a DangerClockFrame wired to shared vars.
    """
    TYPE = "racing"
    MAX_DIALS = 6

    def __init__(self, master, initial_title="Racing Clock", initial_dials=2, notes=""):
        super().__init__(master)

        # ---- Shared state for the whole tab ----
        self.title_var = tk.StringVar(value=initial_title)
        self.segments_var = tk.IntVar(value=4)
        self.inverted_var = tk.BooleanVar(value=False)
        self.notes = notes or ""

        # ---- Top bar (define 'top' BEFORE using it) ----
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=(8, 0))

        ttk.Label(top, text="Tab Title:").pack(side="left")
        ent = ttk.Entry(top, textvariable=self.title_var, width=28, justify="center")
        ent.pack(side="left", padx=(6, 12))

        ttk.Label(top, text="Segments:").pack(side="left", padx=(0,4))
        seg_box = ttk.Combobox(top, state="readonly", values=SEGMENT_CHOICES, width=6, textvariable=self.segments_var)
        seg_box.pack(side="left")

        ttk.Button(top, text="Notes", command=self.open_notes).pack(side="left", padx=(6, 12))

        self.add_btn = ttk.Button(top, text="Add Dial", command=self._add_dial)
        self.add_btn.pack(side="left", padx=(0, 6))

        self.remove_btn = ttk.Button(top, text="Remove Dial", command=self._remove_dial)
        self.remove_btn.pack(side="left", padx=(0, 12))

        ttk.Button(top, text="Reset All", command=self.reset_all).pack(side="left")
        ttk.Button(top, text="Settings", command=self.open_settings).pack(side="left", padx=(6, 0))

        # ---- Dials area ----
        self.dials_frame = ttk.Frame(self)
        self.dials_frame.pack(fill="both", expand=True, padx=8, pady=8)

        for c in range(3):
            self.dials_frame.columnconfigure(c, weight=1)
        for r in range(2):
            self.dials_frame.rowconfigure(r, weight=1)

        self.dials: list[DangerClockFrame] = []  # define BEFORE using in _update_dial_buttons

        # At least two dials to start
        count = max(2, min(int(initial_dials or 2), self.MAX_DIALS))
        for _ in range(count):
            self._add_dial()

        # Now that dials exist, set initial button states
        self._update_dial_buttons()

        # React to shared var changes
        self.segments_var.trace_add("write", lambda *_: self._on_segments_changed())
        self.inverted_var.trace_add("write", lambda *_: self._on_theme_changed_all())

    # ---- UI actions ----

    def open_notes(self):
        res = open_notes_modal(self, self.notes, self.title_var.get() or "Racing Clock")
        if res is not None:
            self.notes = res

    def reset_all(self):
        for d in self.dials:
            d.reset()

    # ---- Internal helpers ----

    def _add_dial(self):
        if len(self.dials) >= self.MAX_DIALS:
            return
        dial = DangerClockFrame(
            self.dials_frame,
            initial_title=f"Clock {len(self.dials)+1}",
            segments=self.segments_var.get(),
            inverted=self.inverted_var.get(),
            shared_segments_var=self.segments_var,
            shared_inverted_var=self.inverted_var,
        )
        self.dials.append(dial)
        self._relayout()
        self._update_dial_buttons()

    def _relayout(self):
        # place dials in rows of 3 (up to 6 total = 3x2)
        for w in self.dials:
            w.grid_forget()
        for idx, w in enumerate(self.dials):
            r, c = divmod(idx, 3)
            w.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)

    def _on_segments_changed(self):
        # Each dial is already bound to shared IntVar; just ask them to resize/redraw
        for d in self.dials:
            d._clamp_and_draw()

    def _on_theme_changed_all(self):
        # Each dial’s _on_theme_changed handles fill-color contrast swap
        for d in self.dials:
            d._on_theme_changed()

    def open_settings(self):
        items = [("Dark Mode", self.inverted_var)]
        dlg = SimpleSettingsDialog(self.winfo_toplevel(), "Racing Clocks Settings", items)
        self.wait_window(dlg)
        if dlg.result:
            self._on_theme_changed_all()

    # --- MOVE THESE INSIDE THE CLASS (indent them) ---
    def _update_dial_buttons(self):
        add_state = "disabled" if len(self.dials) >= self.MAX_DIALS else "normal"
        rm_state  = "disabled" if len(self.dials) <= 2 else "normal"
        try:
            self.add_btn.configure(state=add_state)
            self.remove_btn.configure(state=rm_state)
        except Exception:
            pass

    def _remove_dial(self):
        if len(self.dials) <= 2:
            return
        dial = self.dials.pop()
        try:
            dial.destroy()
        except Exception:
            pass
        self._relayout()
        self._update_dial_buttons()

    # ---- Persistence ----
    def to_dict(self) -> dict:
        return {
            "type": self.TYPE,
            "title": self.title_var.get(),
            "segments": int(self.segments_var.get()),
            "inverted": bool(self.inverted_var.get()),
            "notes": self.notes,
            # Save each dial using its own serializer
            "dials": [d.to_dict() for d in self.dials],
        }

    def from_dict(self, data: dict):
        # Tab-level fields first (so shared vars are set before dials read)
        self.title_var.set(data.get("title", "Racing Clock"))
        self.segments_var.set(int(data.get("segments", 4)))
        self.inverted_var.set(bool(data.get("inverted", False)))
        self.notes = data.get("notes", "")

        # Rebuild dials from saved data
        dials_data = data.get("dials") or []
        self._rebuild_from_dials(dials_data)

    def _rebuild_from_dials(self, dials_data: list):
        # Clear old dials
        for d in self.dials:
            try:
                d.destroy()
            except Exception:
                pass
        self.dials.clear()

        # Build new dials; ensure at least two
        target = max(2, min(len(dials_data) or 2, self.MAX_DIALS))
        for i in range(target):
            self._add_dial()

        # Feed dicts into dials, but remove per-dial "segments" and "inverted"
        # so they don't fight with the shared tab-level vars
        for dial, dd in zip(self.dials, dials_data):
            if not isinstance(dd, dict):
                continue
            dd = dict(dd)  # shallow copy
            dd.pop("segments", None)
            dd.pop("inverted", None)
            dial.from_dict(dd)

        # If there were fewer saved dials than current, clear extras (shouldn’t happen with target calc)
        self._relayout()
        self._update_dial_buttons()

class LinkedClocksFrame(ttk.Frame):
    """
    Linked series of 2..6 circular dials.
    - Only the first incomplete dial is "active".
    - Master Start/Stop drive a per-dial countdown (if timers are set).
    - Clicking a dial fills the NEXT segment (no arbitrary segment picking).
    - If ANY timer is specified, ALL timers must be specified to Start.
    """
    TYPE = "linked"
    MAX_DIALS = 6

    TICK_MS = 250  # update resolution for timers

    def __init__(self, master, initial_title="Linked Clocks", initial_dials=2, notes=""):
        super().__init__(master)

        # --- Shared/tab state ---
        self.title_var = tk.StringVar(value=initial_title)
        self.segments_var = tk.IntVar(value=4)
        self.inverted_var = tk.BooleanVar(value=False)
        self.notes = notes or ""

        self._show_overlay = tk.BooleanVar(value=False)
        self.overlay_color = tk.StringVar(value="#000000")  # default black; flips in dark mode

        # Timer engine state
        self._is_running = False
        self._job = None

        # --- Top bar (2-row grid to avoid clipping) ---
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=(8, 0))
        for c in range(8):
            top.columnconfigure(c, weight=1)
        # Make row 1 a bit taller; prevent control clipping
        top.grid_rowconfigure(1, minsize=44)

        # Give some columns minimum width so text like "Dark Mode" and buttons don't truncate
        top.grid_columnconfigure(0, minsize=90)  # "Tab Title:" label
        top.grid_columnconfigure(1, minsize=160)  # title entry
        top.grid_columnconfigure(2, minsize=90)  # "Segments:" label
        top.grid_columnconfigure(3, minsize=110)  # segments combobox / overlay cb
        top.grid_columnconfigure(4, minsize=110)  # "Dark Mode" / "Overlay Color"
        top.grid_columnconfigure(5, minsize=90)  # "Notes" / "Beep on dial complete"

        # Row 0: title / segments / dark / notes
        ttk.Label(top, text="Tab Title:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(top, textvariable=self.title_var, width=28, justify="center").grid(row=0, column=1, sticky="we",
                                                                                     padx=(6, 12))

        ttk.Label(top, text="Segments:").grid(row=0, column=2, sticky="e", padx=(0, 6))
        seg_box = ttk.Combobox(top, state="readonly", values=SEGMENT_CHOICES, width=6, textvariable=self.segments_var)
        seg_box.grid(row=0, column=3, sticky="w")
        seg_box.bind("<<ComboboxSelected>>", lambda e: self._on_segments_changed())

        ttk.Button(top, text="Notes", command=self.open_notes).grid(row=0, column=5, sticky="w", padx=(6, 12))
        ttk.Button(top, text="Settings", command=self.open_settings).grid(row=0, column=6, sticky="w", padx=(0, 6))

        # Row 1: add/remove/reset/overlay + (Commit C) overlay color + master controls at right
        ttk.Button(top, text="Add Dial", command=self._add_dial).grid(row=1, column=0, sticky="w", padx=(0, 6))
        ttk.Button(top, text="Remove Dial", command=self._remove_dial).grid(row=1, column=1, sticky="w", padx=(0, 12))
        ttk.Button(top, text="Reset All", command=self.reset_all).grid(row=1, column=2, sticky="w", padx=(0, 12))

        def _choose_overlay_color():
            (rgb, hexv) = colorchooser.askcolor(
                color=self.overlay_color.get(),
                title="Choose overlay text color",
                parent=self.winfo_toplevel()
            )
            if hexv:
                self.overlay_color.set(hexv)
                self._redraw_overlays()

        ttk.Button(top, text="Overlay Color", command=_choose_overlay_color) \
            .grid(row=1, column=4, sticky="w", padx=(0, 12))
        self.beep_on_complete = tk.BooleanVar(value=False)  # default unchecked; Settings dialog controls it

        # (Commit C will insert an "Overlay Color" button into column 4 here)

        # Master controls aligned right
        right = ttk.Frame(top);
        right.grid(row=1, column=7, sticky="e")
        self.start_btn = ttk.Button(right, text="Start", command=self.start);
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(right, text="Stop", command=self.stop, state="disabled");
        self.stop_btn.pack(side="left", padx=4)
        # Inline hint shown when Start is disabled due to partial timers
        self._start_hint = ttk.Label(right, text="Enter all HH:MM:SS to enable Start", foreground="#a00")
        self._start_hint.pack_forget()

        # --- Dial grid ---
        self.dials_frame = ttk.Frame(self); self.dials_frame.pack(fill="both", expand=True, padx=8, pady=8)
        for c in range(3): self.dials_frame.columnconfigure(c, weight=1)
        for r in range(2): self.dials_frame.rowconfigure(r, weight=1)
        self.dials_frame.bind("<Configure>", lambda e: self._relayout())

        self.dials: list[DangerClockFrame] = []
        self.timer_secs: list[tk.IntVar] = []      # per-dial configured countdown seconds
        self.elapsed_ms: list[int] = []  # NEW: runtime elapsed per dial (ms)

        # Build initial 2..6
        count = max(2, min(int(initial_dials or 2), self.MAX_DIALS))
        for _ in range(count): self._add_dial()

        # Watch shared vars
        self.segments_var.trace_add("write", lambda *_: self._on_segments_changed())
        self.inverted_var.trace_add("write", lambda *_: self._on_theme_changed_all())

        self._validate_start_button()
        self._redraw_overlays()
        self._bind_serial_clicks()


    # ------------- Public-ish actions -------------
    def open_notes(self):
        res = open_notes_modal(self, self.notes, self.title_var.get() or "Linked Clocks")
        if res is not None: self.notes = res

    def reset_all(self):
        self.stop()

        # Ask about clearing labels
        ans = messagebox.askquestion(
            "Reset All",
            "Reset all clocks on this tab?\n\nAlso clear ALL segment labels and timers?",
            icon="question",
            parent=self.winfo_toplevel()
        )
        clear_labels_and_timers = (ans == "yes")

        for d in self.dials:
            if clear_labels_and_timers:
                d.labels = [""] * int(d.segments.get())
            d.reset()

        if clear_labels_and_timers:
            # Timers back to 00:00:00 for all
            for v in self.timer_secs:
                v.set(0)
            # Also zero out elapsed so overlays show 00:00:00
            self.elapsed_ms = [0 for _ in self.dials]

        self._reset_all_remaining()
        self._redraw_overlays()
        self._validate_start_button()
        self._bind_serial_clicks()

    def start(self):
        # Validate timers (guard against partial entries)
        if not self._validate_timers():
            return

        # If all dials complete, nothing to do
        if all(d.is_complete() for d in self.dials):
            return

        # Start or resume
        self._is_running = True
        self._schedule_tick()
        self._sync_master_buttons()

    def stop(self):
        self._is_running = False
        self._cancel_tick()
        self._sync_master_buttons()

    # ------------- Internal helpers -------------

    def _sync_master_buttons(self):
        # Start is enabled only when not running (it also acts as resume)
        self.start_btn.configure(state="normal" if not self._is_running else "disabled")
        self.stop_btn.configure(state="normal" if self._is_running else "disabled")

    def _schedule_tick(self):
        self._cancel_tick()
        self._job = self.after(self.TICK_MS, self._on_tick)

    def _cancel_tick(self):
        if self._job:
            try: self.after_cancel(self._job)
            except Exception: pass
            self._job = None

    def _on_tick(self):
        if not self._is_running:
            return

        # find active dial (first incomplete)
        idx = next((i for i, d in enumerate(self.dials) if not d.is_complete()), None)
        if idx is None:
            self.stop()
            self._redraw_overlays()
            self._bind_serial_clicks()  # <-- NEW
            return

        # If timers are not used, do nothing (user advances by clicks)
        if not self._timers_in_use():
            self._redraw_overlays()
            self._bind_serial_clicks()  # <-- NEW
            self._schedule_tick()
            return

        # ---- proportional timing branch ----
        total_ms = max(0, self.timer_secs[idx].get() * 1000)
        if total_ms == 0:
            # no timer on this dial (shouldn't happen if validation passed)
            self._redraw_overlays()
            self._bind_serial_clicks()
            self._schedule_tick()
            return

        # advance elapsed for the active dial
        self.elapsed_ms[idx] = min(total_ms, self.elapsed_ms[idx] + self.TICK_MS)

        # compute how many segments should be filled by now
        segs = int(self.segments_var.get())
        target_fill = int((self.elapsed_ms[idx] / total_ms) * segs)

        # apply (idempotent)
        self.dials[idx]._set_fill_count(min(target_fill, segs))
        self.dials[idx].draw()

        # if we’ve reached total time, ensure filled; next tick will move to next dial
        if self.elapsed_ms[idx] >= total_ms:
            self.dials[idx]._set_fill_count(segs)
            self.dials[idx].draw()
            if getattr(self, "beep_on_complete", None) and self.beep_on_complete.get():
                self._beep_once()

        self._redraw_overlays()
        self._bind_serial_clicks()  # <-- NEW
        self._schedule_tick()

    def _timers_in_use(self) -> bool:
        # any positive configured time?
        return any(v.get() > 0 for v in self.timer_secs)

    def _validate_timers(self) -> bool:
        """If ANY time is set, ALL must be set > 0."""
        vals = [v.get() for v in self.timer_secs]
        any_set = any(v > 0 for v in vals)
        if not any_set:  # manual-click mode ok
            return True
        if all(v > 0 for v in vals):
            return True
        messagebox.showerror("Timers incomplete",
                             "You’ve enabled timers on some clocks.\nPlease enter a countdown for ALL clocks (HH:MM:SS).",
                             parent=self.winfo_toplevel())
        return False

    def _validate_start_button(self):
        timers = [v.get() for v in self.timer_secs]
        any_set = any(t > 0 for t in timers)
        all_set = all(t > 0 for t in timers) if timers else False
        can_start = (not any_set) or (all_set)
        self.start_btn.configure(state="normal" if can_start and not self._is_running else "disabled")

        # Toggle the inline hint if it exists (created in D2)
        if hasattr(self, "_start_hint"):
            if can_start:
                self._start_hint.pack_forget()
            else:
                self._start_hint.pack(side="left", padx=(0, 8))

    def _reset_all_remaining(self):
        # Proportional timing uses elapsed; remaining is derived
        self.elapsed_ms = [0 for _ in self.dials]  # NEW
        # If you’re keeping `remaining` around for overlay compatibility elsewhere, you can also refresh it:
        # self.remaining = [v.get() * 1000 for v in self.timer_secs]

    def _redraw_overlays(self):
        show = bool(self._show_overlay.get())
        timers = self._timers_in_use()
        active = next((i for i,d in enumerate(self.dials) if not d.is_complete()), None)

        for i, d in enumerate(self.dials):
            text = ""
            if show and self._timers_in_use() and self.timer_secs[i].get() > 0:
                total = self.timer_secs[i].get() * 1000
                rem_ms = max(0, total - (self.elapsed_ms[i] if i < len(self.elapsed_ms) else 0))
                s = rem_ms // 1000
                h, rem = divmod(s, 3600)
                m, s = divmod(rem, 60)
                text = f"{h:02d}:{m:02d}:{s:02d}"
            d._overlay_text = text
            d._overlay_color = self.overlay_color.get()
            d.draw()

    def _active_index(self) -> int | None:
        return next((i for i, d in enumerate(self.dials) if not d.is_complete()), None)

    def _bind_serial_clicks(self):
        """Only the active dial gets clicks. Left=advance. Right=unfill (only when timers are NOT used)."""
        active = self._active_index()
        timers = self._timers_in_use()

        for i, d in enumerate(self.dials):
            # clear our binds
            for seq in ("<Button-1>", "<Button-3>"):
                # Additionally, prevent accidental interactions on inactive canvases
                # by ignoring clicks. We only rebind for the active dial below.
                d.canvas.bind("<Button-1>", lambda e: None)
                d.canvas.bind("<Button-3>", lambda e: None)
                try:
                    d.canvas.unbind(seq)
                except Exception:
                    pass

            if active is None:
                continue  # everything complete

            if i == active:
                # left click always advances one
                d.canvas.bind("<Button-1>", lambda e, di=d: (
                    getattr(di, "_parse_timer", lambda *a, **k: None)(),  # commit HH:MM:SS if user just typed
                    di.increase(),
                    self._redraw_overlays(),
                    self._bind_serial_clicks()
                ))

                # right click: only in manual mode (no timers anywhere)
                if not timers:
                    def _unfill(_e, di=d):
                        # Use the public API so any future side‑effects stay consistent
                        di.decrease()
                        self._redraw_overlays()
                        self._bind_serial_clicks()

                    d.canvas.bind("<Button-3>", _unfill)

    # ------------- Layout / building -------------

    def _add_dial(self):
        if len(self.dials) >= self.MAX_DIALS: return

        idx = len(self.dials)
        dial = DangerClockFrame(
            self.dials_frame,
            initial_title=f"Clock {idx+1}",
            segments=self.segments_var.get(),
            inverted=self.inverted_var.get(),
            shared_segments_var=self.segments_var,
            shared_inverted_var=self.inverted_var,
            enable_label_ui=False,     # per spec: no objective labels
            click_mode="serial_next",  # per spec: click anywhere => fill next segment
        )

        # Per-dial timer UI under each dial
        ctrl = ttk.Frame(dial); ctrl.grid(row=3, column=0, columnspan=8, sticky="we", pady=(0,6))
        ttk.Label(ctrl, text="Countdown (HH:MM:SS):").pack(side="left")
        var = tk.IntVar(value=0)  # store seconds
        ent = ttk.Entry(ctrl, width=10, justify="center")
        ent.pack(side="left", padx=(4, 8))
        ttk.Label(ctrl, text="ⓘ fills segments evenly over total time", foreground="#666") \
            .pack(side="left", padx=(8, 0))

        def parse_and_set(*_):
            txt = ent.get().strip()
            if not txt:
                var.set(0)
            else:
                try:
                    parts = txt.split(":")
                    if len(parts) == 1:
                        total = int(parts[0])
                    elif len(parts) == 2:
                        mm, ss = parts
                        total = int(mm) * 60 + int(ss)
                    else:
                        hh, mm, ss = parts[-3], parts[-2], parts[-1]
                        total = int(hh) * 3600 + int(mm) * 60 + int(ss)
                    var.set(max(0, total))
                except Exception:
                    # keep old; lightly notify?
                    pass
            self._reset_all_remaining()
            self._validate_start_button()
            self._redraw_overlays()

        dial._parse_timer = parse_and_set  # <— NEW: stash parser for this dial

        ent.insert(0, "00:00:00")
        ent.bind("<FocusOut>", parse_and_set)
        ent.bind("<Return>", parse_and_set)

        # Notes button (already on dial top bar), Fill Color already present
        # Store & place dial
        self.timer_secs.append(var)
        self.dials.append(dial)
        self.elapsed_ms.append(0)

        self._relayout()
        self._bind_serial_clicks()
        self._validate_start_button()

    def _remove_dial(self):
        if len(self.dials) <= 2: return
        d = self.dials.pop()
        try: d.destroy()
        except Exception: pass
        self.timer_secs.pop()
        if self.elapsed_ms:
            self.elapsed_ms.pop()
        self._relayout()
        self._validate_start_button()
        self._redraw_overlays()
        self._bind_serial_clicks()

    def _relayout(self):
        # Determine columns based on available width
        try:
            w = max(1, int(self.dials_frame.winfo_width()))
        except Exception:
            w = 900
        # Simple breakpoints; tweak as you like
        if w < 760:
            cols = 1
        elif w < 1100:
            cols = 2
        else:
            cols = 3

        # Configure grid
        for c in range(3):
            self.dials_frame.columnconfigure(c, weight=0)
        for r in range(2):
            self.dials_frame.rowconfigure(r, weight=0)

        for c in range(cols):
            self.dials_frame.columnconfigure(c, weight=1)
        rows = (len(self.dials) + cols - 1) // cols
        for r in range(rows):
            self.dials_frame.rowconfigure(r, weight=1)

        # Place widgets
        for wgt in self.dials:
            wgt.grid_forget()
        for i, wgt in enumerate(self.dials):
            r, c = divmod(i, cols)
            wgt.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)

    def _beep_once(self):
        """Play a single ding when a dial completes (original behavior)."""
        root = self.winfo_toplevel()
        try:
            import platform
            if platform.system().lower().startswith("win"):
                try:
                    import winsound
                    winsound.Beep(880, 180)
                    return
                except Exception:
                    pass
            root.bell()
        except Exception:
            pass

    def _on_segments_changed(self):
        for d in self.dials: d._clamp_and_draw()
        self._bind_serial_clicks()

    def _on_theme_changed_all(self):
        for d in self.dials: d._on_theme_changed()
        # Flip default overlay text color when theme changes (only if user hasn't picked a custom one)
        if self.inverted_var.get():
            if self.overlay_color.get().lower() in ("#000000", "black"):
                self.overlay_color.set("#FFFFFF")
        else:
            if self.overlay_color.get().lower() in ("#ffffff", "white"):
                self.overlay_color.set("#000000")

        self._redraw_overlays()

    def open_settings(self):
        items = [
            ("Show Countdown Overlay", self._show_overlay),
            ("Enable Timer Alarms", self.beep_on_complete),
            ("Dark Mode", self.inverted_var),
        ]

        dlg = SimpleSettingsDialog(self.winfo_toplevel(), "Linked Clocks Settings", items)
        self.wait_window(dlg)
        if dlg.result:
            # Apply any visual/behavior side‑effects from toggles
            self._on_theme_changed_all()
            self._redraw_overlays()
            self._bind_serial_clicks()

    # ------------- Persistence -------------

    def to_dict(self) -> dict:
        return {
            "type": self.TYPE,
            "title": self.title_var.get(),
            "segments": int(self.segments_var.get()),
            "inverted": bool(self.inverted_var.get()),
            "notes": self.notes,
            "show_overlay": bool(self._show_overlay.get()),
            "beep_on_complete": bool(self.beep_on_complete.get()),
            "dials": [
                {
                    **d.to_dict(),
                    "timer_seconds": int(self.timer_secs[i].get())
                }
                for i, d in enumerate(self.dials)
            ],
        }

    def from_dict(self, data: dict):
        self.title_var.set(data.get("title", "Linked Clocks"))
        self.segments_var.set(int(data.get("segments", 4)))
        self.inverted_var.set(bool(data.get("inverted", False)))
        self.notes = data.get("notes", "")
        self._show_overlay.set(bool(data.get("show_overlay", False)))
        self.beep_on_complete.set(bool(data.get("beep_on_complete", False)))

        # Rebuild dials
        for d in self.dials:
            try:
                d.destroy()
            except Exception:
                pass
        self.dials.clear();
        self.timer_secs.clear();
        self.elapsed_ms.clear()


        dials_data = data.get("dials") or []
        target = max(2, min(len(dials_data) or 2, self.MAX_DIALS))
        for _ in range(target): self._add_dial()

        for i, dd in enumerate(dials_data[:len(self.dials)]):
            # feed dial state; strip conflicting fields
            if isinstance(dd, dict):
                dd = dict(dd)
                dd.pop("segments", None); dd.pop("inverted", None)
                self.dials[i].from_dict(dd)

                tsec = int(dd.get("timer_seconds", 0))
                self.timer_secs[i].set(max(0, tsec))

        self._reset_all_remaining()
        self._redraw_overlays()
        self._validate_start_button()
        self._bind_serial_clicks()

    def destroy(self):
        self._cancel_tick()
        super().destroy()


# ---------------------------
# App shell (minimal)
#     This is the main window class.  It manages the overall application.
# ---------------------------
class MultiClockApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Progress Clocks")
        self.minsize(700, 500)

        # Load settings first
        self.settings = load_settings()

        # Position window: center on the monitor that contained the app last time.
        try:
            # Get preferred size from settings (fallback to default)
            w, h = self.settings.get("last_window_size") or [900, 650]
            w = int(w); h = int(h)

            last_center = self.settings.get("last_window_center")
            if isinstance(last_center, (list, tuple)) and len(last_center) == 2:
                cx, cy = int(last_center[0]), int(last_center[1])
                rect = _get_monitor_rect_from_point(cx, cy)
                geom = _center_geometry_on_rect(w, h, rect)
                self.geometry(geom)
            else:
                # No prior center—use default size; Tk will place it; optionally center on primary
                rect = _get_monitor_rect_from_point(0, 0)
                self.geometry(_center_geometry_on_rect(w, h, rect))
        except Exception:
            # Absolute fallback
            self.geometry("900x650")


        # Remember last save/load file path for autosave to use.
        # (If we auto-load, we'll set this below.)
        self.current_session_path: Path | None = None

        # Tk "after" job handle for autosave loop.
        self._autosave_job = None

        # Build menus AFTER we have self.settings
        self._build_menu()

        # ---- Bottom toolbar (add/remove tabs) ----
        self.toolbar = ttk.Frame(self)
        self.toolbar.pack(side="bottom", fill="x")
        ttk.Button(self.toolbar, text="Add Danger Clock", command=self.add_danger_clock).pack(side="left", padx=6,
                                                                                              pady=6)
        ttk.Button(self.toolbar, text="Add Racing Clocks", command=self.add_racing_clocks).pack(side="left", padx=6,
                                                                                                pady=6)
        ttk.Button(self.toolbar, text="Add Linked Clocks", command=self.add_linked_clocks).pack(side="left", padx=6,
                                                                                                pady=6)
        ttk.Button(self.toolbar, text="Remove Current", command=self.remove_current).pack(side="left", padx=6, pady=6)

        # ---- Notebook in the middle ----
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        # Decide how to start
        opened_from_settings = False
        if self.settings.get("open_last_on_launch"):
            last_path = self.settings.get("last_session_path")
            if last_path:
                try:
                    self._load_from_path(Path(last_path))
                    self.current_session_path = Path(last_path)  # remember for autosave
                    opened_from_settings = True
                except Exception:
                    # fall back to a fresh tab
                    opened_from_settings = False

        if not opened_from_settings:
            # start with one empty tab
            self.add_danger_clock()

        # Save-on-exit hook
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Start the autosave loop.
        self._start_autosave()

    # ---------- Autosave & Exit ----------

    def _collect_tabs(self) -> list[dict]:
        """Gather JSON-serializable dicts from each tab via to_dict()."""
        items = []
        for tab_id in self.nb.tabs():
            frame = self._frame_from_tab(tab_id)
            if hasattr(frame, "to_dict"):
                items.append(frame.to_dict())
        return items

    def _save_to_path(self, path: Path):
        """Save current session to JSON at `path`."""
        items = self._collect_tabs()
        if not items:
            return  # nothing to save is fine (esp. for autosave)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"items": items}, f, ensure_ascii=False, indent=2)

    def _start_autosave(self):
        """Kick off autosave loop."""
        self._schedule_next_autosave()

    def _schedule_next_autosave(self):
        """(Re)schedule next autosave tick."""
        if self._autosave_job:
            try:
                self.after_cancel(self._autosave_job)
            except Exception:
                pass
            self._autosave_job = None
        self._autosave_job = self.after(AUTOSAVE_MS, self._autosave_tick)

    def _autosave_tick(self):
        """Do one autosave, then reschedule."""
        try:
            target = self.current_session_path or DEFAULT_SESSION_PATH
            self._save_to_path(Path(target))
            # record the autosave path as last session, too (optional)
            self.settings["last_session_path"] = str(Path(target))
            save_settings(self.settings)

        except Exception:
            # silent on autosave errors
            pass
        finally:
            self._schedule_next_autosave()

    def _on_close(self):
        """Final best-effort save, store window position, stop autosave, then close app."""
        try:
            # Save session
            target = self.current_session_path or DEFAULT_SESSION_PATH
            self._save_to_path(Path(target))
        except Exception:
            pass
        finally:
            # Capture window size + center point in virtual screen coords
            try:
                self.update_idletasks()
                geom = self.geometry()  # e.g., "900x650+123+456"
                size, x, y = geom.split("+", 2)
                w, h = map(int, size.split("x"))
                x, y = int(x), int(y)
                cx = x + (w // 2)
                cy = y + (h // 2)

                self.settings["last_window_size"] = [w, h]
                self.settings["last_window_center"] = [cx, cy]
                save_settings(self.settings)
            except Exception:
                pass

            # Stop autosave
            if self._autosave_job:
                try:
                    self.after_cancel(self._autosave_job)
                except Exception:
                    pass
                self._autosave_job = None

            self.destroy()

    # ---------- Menu ----------

    def _build_menu(self):
        menubar = tk.Menu(self)

        # File menu
        filemenu = tk.Menu(menubar, tearoff=False)
        filemenu.add_command(label="Save Session", command=self.save_session)
        filemenu.add_command(label="Load Session", command=self.load_session)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=filemenu)

        # Settings menu
        self.open_last_var = tk.BooleanVar(value=bool(self.settings.get("open_last_on_launch", False)))
        settings_menu = tk.Menu(menubar, tearoff=False)
        settings_menu.add_checkbutton(
            label="Open last session on launch",
            variable=self.open_last_var,
            command=self._on_toggle_open_last
        )
        menubar.add_cascade(label="Settings", menu=settings_menu)

        self.config(menu=menubar)

    def _on_toggle_open_last(self):
        self.settings["open_last_on_launch"] = bool(self.open_last_var.get())
        save_settings(self.settings)

    # ---------- Tabs ----------

    def add_danger_clock(self, title=None, segments=4, filled=0, inverted=False, fill_color=None, notes=""):
        # auto-number default titles
        if title is None or not title.strip() or title.strip().startswith("Danger Clock"):
            existing = [self._frame_from_tab(t).title_var.get()
                        for t in self.nb.tabs()
                        if isinstance(self._frame_from_tab(t), DangerClockFrame)]
            if not title or not title.strip() or title.strip() == "Danger Clock":
                title = _next_numbered_title(existing, "Danger Clock")

        frame = DangerClockFrame(self.nb, initial_title=title, segments=segments, filled=filled,
                                 inverted=inverted, fill_color=fill_color, notes=notes)
        self.nb.add(frame, text=self._short_title(title))

        def sync(*_):
            idx = self.nb.index(frame)
            self.nb.tab(idx, text=self._short_title(frame.title_var.get()))
        frame.title_var.trace_add("write", lambda *_: sync())
        self.nb.select(frame)
        return frame

    def remove_current(self):
        if self.nb.index("end") == 0:
            return
        current = self.nb.select()
        if current:
            self.nb.forget(current)

    def add_racing_clocks(self, title=None, notes="", initial_dials=2):
        # Auto-number default titles "Racing Clock n"
        existing = []
        for tab_id in self.nb.tabs():
            frame = self._frame_from_tab(tab_id)
            if hasattr(frame, "title_var") and getattr(frame, "TYPE", "") == "racing":
                existing.append(frame.title_var.get())
        base = "Racing Clock"
        default_title = _next_numbered_title(existing, base)
        title = (title or default_title).strip()

        # pass initial_dials through (not used on load; only for user-created tabs)
        frame = RacingClocksFrame(self.nb, initial_title=title, notes=notes, initial_dials=initial_dials)
        self.nb.add(frame, text=self._short_title(title))

        def sync(*_):
            try:
                idx = self.nb.index(frame)
                self.nb.tab(idx, text=self._short_title(frame.title_var.get()))
            except Exception:
                pass

        frame.title_var.trace_add("write", lambda *_: sync())

        self.nb.select(frame)
        return frame

    # ---------- Save / Load ----------

    def save_session(self):
        """Manual save with file chooser; remembers path for autosave."""
        items = self._collect_tabs()
        if not items:
            messagebox.showinfo("Nothing to save", "There are no tabs.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="Save session as JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            parent=self,
        )
        if not path:
            return
        try:
            self._save_to_path(Path(path))
            self.current_session_path = Path(path)  # remember for autosave
            # NEW:
            self.settings["last_session_path"] = str(self.current_session_path)
            save_settings(self.settings)
            messagebox.showinfo("Saved", f"Saved to:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Save failed", f"{e}", parent=self)

    def load_session(self):
        """Manual load; rebuilds tabs; remembers path for autosave."""
        path = filedialog.askopenfilename(title="Load session JSON",
                                          filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            self._load_from_path(Path(path))
            self.current_session_path = Path(path)  # remember for autosave
            # record for Settings
            self.settings["last_session_path"] = str(self.current_session_path)
            save_settings(self.settings)
            messagebox.showinfo("Loaded", f"Loaded from:\n{path}")
        except Exception as e:
            messagebox.showerror("Load failed", f"{e}")

    def _load_from_path(self, path: Path):
        """Load a session JSON from a specific path (no file chooser)."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Clear existing tabs
        for tab_id in self.nb.tabs():
            self.nb.forget(tab_id)

        # Rebuild from saved items
        for item in data.get("items", []):
            t = item.get("type")
            if t == DangerClockFrame.TYPE:
                # Create a tab (title will be corrected by from_dict)
                frame = self.add_danger_clock(title=item.get("title", "Danger Clock"))
                if hasattr(frame, "from_dict"):
                    frame.from_dict(item)

            elif t == getattr(RacingClocksFrame, "TYPE", "racing"):
                frame = self.add_racing_clocks(title=item.get("title", "Racing Clock"))
                if hasattr(frame, "from_dict"):
                    frame.from_dict(item)

            elif t == getattr(LinkedClocksFrame, "TYPE", "linked"):
                frame = self.add_linked_clocks(title=item.get("title", "Linked Clocks"))
                if hasattr(frame, "from_dict"): frame.from_dict(item)

            else:
                # Unknown tab type; skip gracefully
                continue

    # ---------- Helpers ----------

    def _frame_from_tab(self, tab_id):
        return self.nametowidget(tab_id)

    @staticmethod
    def _short_title(title: str) -> str:
        title = (title or "Clock").strip()
        return (title[:18] + "…") if len(title) > 18 else title

    def add_linked_clocks(self, title=None, notes="", initial_dials=2):
        existing = []
        for tab_id in self.nb.tabs():
            frame = self._frame_from_tab(tab_id)
            if hasattr(frame, "title_var") and getattr(frame, "TYPE", "") == "linked":
                existing.append(frame.title_var.get())
        base = "Linked Clocks"
        default_title = _next_numbered_title(existing, base)
        title = (title or default_title).strip()

        frame = LinkedClocksFrame(self.nb, initial_title=title, notes=notes, initial_dials=initial_dials)
        self.nb.add(frame, text=self._short_title(title))

        def sync(*_):
            try:
                idx = self.nb.index(frame)
                self.nb.tab(idx, text=self._short_title(frame.title_var.get()))
            except Exception:
                pass

        frame.title_var.trace_add("write", lambda *_: sync())

        self.nb.select(frame)
        return frame


if __name__ == "__main__":
    app = MultiClockApp()
    app.mainloop()
