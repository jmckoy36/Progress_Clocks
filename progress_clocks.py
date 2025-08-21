#!/usr/bin/env python3
"""
Progress Clocks — Clean restart
Step 1: Danger Clock only, minimal features (title, segments, fill, invert, notes).
"""

import json
import math
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

# ---------------------------
# Config / constants
# ---------------------------
PADDING = 16
TITLE_SPACE = 44
LINE_W = 3
SEGMENT_CHOICES = (4, 6, 8, 12)
# How often to auto-save the whole session (in milliseconds).
# 5 minutes = 5 * 60 * 1000
AUTOSAVE_MS = 5 * 60 * 1000


def get_app_dir() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", str(Path.home())))
        return base / "ProgressClocks"
    else:
        return Path.home() / ".progress_clocks"

APP_DIR = get_app_dir()
APP_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_SESSION_PATH = APP_DIR / "session.json"

# ---------------------------
# Utilities (shared)
# ---------------------------
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

# ---------------------------
# Shared ClockBase (very small)
#     The ClockBase(ttk.Frame) class is a base class that holds shared logic for all clock types.
#     It sets up common things like a title box, segment selector, etc.
# ---------------------------
class ClockBase(ttk.Frame):
    """Shared bits: title, invert, notes button, canvas, basic (de)serialize contract."""
    TYPE = "base"

    def __init__(self, master, initial_title="Clock", inverted=False, notes=""):
        super().__init__(master)
        self.title_var = tk.StringVar(value=initial_title)
        self.inverted = tk.BooleanVar(value=bool(inverted))
        self.notes = notes or ""

        for c in range(8):
            self.columnconfigure(c, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text="Title:").grid(row=0, column=0, sticky="e", padx=6, pady=(8,0))
        ent = ttk.Entry(self, textvariable=self.title_var, width=28, justify="center")
        ent.grid(row=0, column=1, columnspan=3, sticky="we", padx=6, pady=(8,0))
        ent.bind("<KeyRelease>", lambda e: self.draw())

        inv = ttk.Checkbutton(self, text="Dark Mode", variable=self.inverted, command=self._on_theme_changed)
        inv.grid(row=0, column=4, padx=(6, 10), pady=(8,0), sticky="w")

        ttk.Button(self, text="Notes", command=self.open_notes).grid(row=0, column=5, padx=6, pady=(8,0))

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.grid(row=1, column=0, columnspan=8, sticky="nsew", padx=8, pady=8)
        self.canvas.bind("<Configure>", lambda e: self.draw())

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
                 inverted=False, fill_color=None, notes=""):
        super().__init__(master, initial_title=initial_title, inverted=inverted, notes=notes)
        self.segments = tk.IntVar(value=int(segments))
        # Track each segment as filled (True) or empty (False)
        self.filled = [False] * int(segments)
        for i in range(min(int(filled), int(segments))):
            self.filled[i] = True
        self.fill_color = fill_color or ("#000000" if not inverted else "#FFFFFF")
        # Click bindings: left = fill, right = un-fill
        self.canvas.bind("<Button-1>", self._on_left_click)   # left click
        self.canvas.bind("<Button-3>", self._on_right_click)  # right click (Windows/Linux)

        ttk.Label(self, text="Segments:").grid(row=0, column=6, sticky="e", padx=6, pady=(8,0))
        seg_box = ttk.Combobox(self, state="readonly", values=SEGMENT_CHOICES, width=6, textvariable=self.segments)
        seg_box.grid(row=0, column=7, padx=6, pady=(8,0), sticky="w")
        seg_box.bind("<<ComboboxSelected>>", lambda e: self._clamp_and_draw())

        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, columnspan=8, pady=(0,10))
        ttk.Button(btns, text="−1", width=6, command=self.decrease).pack(side="left", padx=6)
        ttk.Button(btns, text="+1", width=6, command=self.increase).pack(side="left", padx=6)
        ttk.Button(btns, text="Reset", width=8, command=self.reset).pack(side="left", padx=6)

        # Fill color
        ttk.Button(btns, text="Fill Color", command=self.choose_fill_color).pack(side="left", padx=12)
        self.fill_preview = tk.Label(btns, width=10, bg=self.fill_color, relief="sunken")
        self.fill_preview.pack(side="left")

        self.bind_all("+", lambda e: self.increase())
        self.bind_all("-", lambda e: self.decrease())
        self.bind_all("<r>", lambda e: self.reset())
        self.bind_all("<R>", lambda e: self.reset())

        self.draw()

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
        (rgb, hexv) = colorchooser.askcolor(color=self.fill_color, title="Choose fill color")
        if hexv:
            self.fill_color = hexv
            try: self.fill_preview.configure(bg=hexv)
            except Exception: pass
            self.draw()

    def _clamp_and_draw(self):
        # Ensure the boolean list matches the new segments value (from the combobox).
        self._resize_filled_to(int(self.segments.get()))
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

    def draw(self):
        c = self.canvas
        c.delete("all")
        colors = self._colors()
        c.configure(bg=colors["bg"])
        w = max(1, c.winfo_width()); h = max(1, c.winfo_height())

        c.create_text(w/2, 16, text=self.title_var.get(), font=("Arial", 16, "bold"), fill=colors["fg"])

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

    # serialization
    def to_dict(self):
        return {
            "type": self.TYPE,
            "title": self.title_var.get(),
            "segments": int(self.segments.get()),
            "filled": int(sum(self.filled)),          # save count of filled segments
            "inverted": bool(self.inverted.get()),
            "fill_color": self.fill_color,
            "notes": self.notes,
        }

    def from_dict(self, data: dict):
        self.title_var.set(data.get("title", "Danger Clock"))
        self.segments.set(int(data.get("segments", 4)))
        count = int(data.get("filled", 0))
        self._resize_filled_to(int(self.segments.get()))
        self._set_fill_count(count)
        self.inverted.set(bool(data.get("inverted", False)))
        self.fill_color = data.get("fill_color", self.fill_color)
        self.notes = data.get("notes", "")
        try: self.fill_preview.configure(bg=self.fill_color)
        except Exception: pass
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


# ---------------------------
# App shell (minimal)
#     This is the main window class.  It manages the overall application.
# ---------------------------
class MultiClockApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Progress Clocks")
        self.geometry("900x650")
        self.minsize(700, 500)

        self._build_menu()

        # Remember last save/load file path for autosave to use.
        self.current_session_path: Path | None = None

        # Tk "after" job handle for autosave loop.
        self._autosave_job = None

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Add Danger Clock", command=self.add_danger_clock).pack(side="left", padx=6, pady=6)
        ttk.Button(toolbar, text="Remove Current", command=self.remove_current).pack(side="left", padx=6, pady=6)

        # start with one tab
        self.add_danger_clock()

        # Save-on-exit hook: IMPORTANT — this needs a *callable*, not a string.
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
        except Exception:
            # silent on autosave errors
            pass
        finally:
            self._schedule_next_autosave()

    def _on_close(self):
        """Final best-effort save, stop autosave, then close app."""
        try:
            target = self.current_session_path or DEFAULT_SESSION_PATH
            self._save_to_path(Path(target))
        except Exception:
            pass
        finally:
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
        filemenu = tk.Menu(menubar, tearoff=False)
        filemenu.add_command(label="Save Session", command=self.save_session)
        filemenu.add_command(label="Load Session", command=self.load_session)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=filemenu)
        self.config(menu=menubar)

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

    def remove_current(self):
        if self.nb.index("end") == 0:
            return
        current = self.nb.select()
        if current:
            self.nb.forget(current)

    # ---------- Save / Load ----------

    def save_session(self):
        """Manual save with file chooser; remembers path for autosave."""
        items = self._collect_tabs()
        if not items:
            messagebox.showinfo("Nothing to save", "There are no tabs.")
            return
        path = filedialog.asksaveasfilename(title="Save session as JSON",
                                            defaultextension=".json",
                                            filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            self._save_to_path(Path(path))
            self.current_session_path = Path(path)  # remember for autosave
            messagebox.showinfo("Saved", f"Saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save failed", f"{e}")

    def load_session(self):
        """Manual load; rebuilds tabs; remembers path for autosave."""
        path = filedialog.askopenfilename(title="Load session JSON",
                                          filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Load failed", f"{e}")
            return

        # Clear existing tabs
        for tab_id in self.nb.tabs():
            self.nb.forget(tab_id)

        # Rebuild from saved items
        for item in data.get("items", []):
            if item.get("type") == DangerClockFrame.TYPE:
                self.add_danger_clock(title=item.get("title", "Danger Clock"),
                                      segments=int(item.get("segments", 4)),
                                      filled=int(item.get("filled", 0)),
                                      inverted=bool(item.get("inverted", False)),
                                      fill_color=item.get("fill_color"),
                                      notes=item.get("notes", ""))

        self.current_session_path = Path(path)  # remember for autosave
        messagebox.showinfo("Loaded", f"Loaded from:\n{path}")

    # ---------- Helpers ----------

    def _frame_from_tab(self, tab_id):
        return self.nametowidget(tab_id)

    @staticmethod
    def _short_title(title: str) -> str:
        title = (title or "Clock").strip()
        return (title[:18] + "…") if len(title) > 18 else title


if __name__ == "__main__":
    app = MultiClockApp()
    app.mainloop()
