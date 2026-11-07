"""Desktop app for Jarvis (tkinter - ships with Python, no extra installs).

Run:  python -m jarvis.gui     or double-click Jarvis.pyw
"""
from __future__ import annotations

import math
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

from .core import Jarvis
from .text import is_arabic

# ---- palette (HUD style) ------------------------------------------------
BG = "#060b14"
PANEL = "#0b1422"
PANEL_EDGE = "#12304a"
CYAN = "#3fd0ff"
CYAN_DIM = "#1b6f8f"
ICE = "#d8f3ff"
MUTED = "#6b8aa3"
USER = "#ffd27a"
OK = "#4be3a0"
WARN = "#ffb84d"
BAD = "#ff5d6c"
INPUT_BG = "#0e1b2c"

QUICK = [
    ("🩺  فحص ذاتي", "افحص نفسك"),
    ("🔧  إصلاح ذاتي", "اصلح نفسك"),
    ("🧠  وش تعلمت", "وش تعلمت"),
    ("📝  ملاحظاتي", "ملاحظاتي"),
    ("💾  نسخة احتياطية", "نسخة احتياطية"),
    ("⚠️  الأعطال", "الأعطال"),
    ("❔  المساعدة", "مساعدة"),
]


def pick_font(root, candidates, size, weight="normal"):
    families = set(tkfont.families(root))
    for name in candidates:
        if name in families:
            return (name, size, weight)
    return ("TkDefaultFont", size, weight)


class Reactor(tk.Canvas):
    """Animated arc-reactor that spins faster while Jarvis is thinking."""

    def __init__(self, master, size=150):
        super().__init__(master, width=size, height=size, bg=PANEL, highlightthickness=0)
        self.size, self.angle, self.busy, self.t0 = size, 0.0, False, time.time()
        self._tick()

    def _tick(self):
        self.delete("all")
        s, c = self.size, self.size / 2
        speed = 9 if self.busy else 2.2
        self.angle = (self.angle + speed) % 360
        pulse = (math.sin((time.time() - self.t0) * (6 if self.busy else 2)) + 1) / 2
        for r, w, col in ((c - 6, 2, CYAN_DIM), (c - 22, 1, PANEL_EDGE)):
            self.create_oval(c - r, c - r, c + r, c + r, outline=col, width=w)
        for i in range(3):   # outer rotating segments
            r = c - 12
            self.create_arc(c - r, c - r, c + r, c + r, start=self.angle + i * 120, extent=70,
                            style="arc", outline=CYAN, width=4)
        for i in range(6):   # inner counter-rotating ticks
            r = c - 34
            self.create_arc(c - r, c - r, c + r, c + r, start=-self.angle * 1.6 + i * 60, extent=22,
                            style="arc", outline=CYAN_DIM, width=6)
        core = 20 + 5 * pulse
        glow = 36 + 8 * pulse
        self.create_oval(c - glow, c - glow, c + glow, c + glow, outline="#0f3d55", width=8)
        self.create_oval(c - core, c - core, c + core, c + core, fill="#9fe9ff" if self.busy else "#62d8ff",
                         outline=ICE, width=2)
        self.create_text(c, c, text="J", fill=BG, font=("Helvetica", 20, "bold"))
        self.after(33, self._tick)


class JarvisApp:
    def __init__(self, root: tk.Tk, home=None):
        self.root = root
        self.home = home
        self.jarvis: Jarvis | None = None
        self.results: queue.Queue = queue.Queue()
        self.lock = threading.Lock()

        root.title("J.A.R.V.I.S")
        root.configure(bg=BG)
        root.geometry("1080x700")
        root.minsize(820, 540)
        self.f_title = pick_font(root, ["Segoe UI Semibold", "SF Pro Display", "Helvetica Neue", "DejaVu Sans"], 18, "bold")
        self.f_body = pick_font(root, ["Segoe UI", "SF Pro Text", "Noto Sans Arabic", "Noto Sans", "DejaVu Sans"], 12)
        self.f_small = pick_font(root, ["Segoe UI", "SF Pro Text", "Noto Sans", "DejaVu Sans"], 9)
        self.f_mono = pick_font(root, ["Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono"], 10)

        self._build()
        self.write_system("جاري تشغيل الأنظمة…  Initializing systems…")
        threading.Thread(target=self._boot, daemon=True).start()
        root.after(100, self._poll)
        root.protocol("WM_DELETE_WINDOW", self._quit)

    # ---- layout ------------------------------------------------------------
    def _build(self):
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=18, pady=(14, 6))
        tk.Label(top, text="J.A.R.V.I.S", fg=CYAN, bg=BG, font=self.f_title).pack(side="left")
        tk.Label(top, text="  Just A Rather Very Intelligent System", fg=MUTED, bg=BG, font=self.f_small).pack(side="left", pady=(8, 0))
        self.status_var = tk.StringVar(value="● starting")
        self.status = tk.Label(top, textvariable=self.status_var, fg=WARN, bg=BG, font=self.f_small)
        self.status.pack(side="right")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        # side panel
        side = tk.Frame(body, bg=PANEL, highlightbackground=PANEL_EDGE, highlightthickness=1, width=250)
        side.pack(side="left", fill="y", padx=(0, 12))
        side.pack_propagate(False)
        self.reactor = Reactor(side)
        self.reactor.pack(pady=(12, 2))
        tk.Label(side, text="العقول  ·  BRAINS", fg=MUTED, bg=PANEL, font=self.f_small).pack(anchor="w", padx=14, pady=(8, 2))
        self.brains_box = tk.Frame(side, bg=PANEL)
        self.brains_box.pack(fill="x", padx=14)
        tk.Label(side, text="أوامر سريعة  ·  QUICK", fg=MUTED, bg=PANEL, font=self.f_small).pack(anchor="w", padx=14, pady=(10, 2))
        for label, cmd in QUICK:
            b = tk.Label(side, text=label, fg=ICE, bg=PANEL, font=self.f_body, anchor="e", padx=10, pady=2, cursor="hand2")
            b.pack(fill="x", padx=8)
            b.bind("<Enter>", lambda e, w=b: w.configure(bg=PANEL_EDGE))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg=PANEL))
            b.bind("<Button-1>", lambda e, c=cmd: self.send(c))

        # chat
        main = tk.Frame(body, bg=PANEL, highlightbackground=PANEL_EDGE, highlightthickness=1)
        main.pack(side="left", fill="both", expand=True)
        wrap = tk.Frame(main, bg=PANEL)
        self.chat = tk.Text(wrap, bg=PANEL, fg=ICE, insertbackground=CYAN, relief="flat", wrap="word",
                            font=self.f_body, padx=18, pady=14, spacing1=2, spacing3=6, state="disabled",
                            highlightthickness=0, cursor="arrow")
        scroll = tk.Scrollbar(wrap, command=self.chat.yview, bg=PANEL, troughcolor=PANEL, relief="flat",
                              highlightthickness=0, bd=0, width=10)
        self.chat.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.chat.pack(side="left", fill="both", expand=True)
        # Arabic lines are right-aligned, English left-aligned; colour tells who is speaking.
        for who, color, head in (("user", USER, USER), ("jarvis", ICE, CYAN)):
            for d, just in (("rtl", "right"), ("ltr", "left")):
                self.chat.tag_configure(f"{who}_{d}", foreground=color, justify=just, lmargin1=8, lmargin2=8, rmargin=8)
                self.chat.tag_configure(f"{who}_head_{d}", foreground=head, font=self.f_small, justify=just,
                                        spacing1=12, lmargin1=8, rmargin=8)
        self.chat.tag_configure("system", foreground=MUTED, font=self.f_small, justify="center", spacing1=6)

        # input (packed at the bottom so the chat can never push it off-screen)
        bar = tk.Frame(main, bg=PANEL)
        bar.pack(side="bottom", fill="x", padx=12, pady=(4, 12))
        holder = tk.Frame(bar, bg=INPUT_BG, highlightbackground=CYAN_DIM, highlightthickness=1)
        holder.pack(side="left", fill="x", expand=True)
        self.entry = tk.Entry(holder, bg=INPUT_BG, fg=ICE, insertbackground=CYAN, relief="flat",
                              font=self.f_body, highlightthickness=0, justify="right")
        self.entry.pack(fill="x", padx=12, ipady=9)
        self.entry.bind("<Return>", lambda e: self.send())
        self.entry.bind("<KeyRelease>", self._align_entry)
        self.send_btn = tk.Label(bar, text="  إرسال ➤  ", fg=BG, bg=CYAN, font=self.f_body, cursor="hand2", pady=9)
        self.send_btn.pack(side="left", padx=(8, 0))
        self.send_btn.bind("<Button-1>", lambda e: self.send())
        wrap.pack(fill="both", expand=True, padx=2, pady=2)
        self.entry.focus_set()

    def _align_entry(self, _=None):
        txt = self.entry.get()
        self.entry.configure(justify="right" if (not txt or is_arabic(txt)) else "left")

    # ---- chat output -------------------------------------------------------
    def _append(self, text, tag):
        self.chat.configure(state="normal")
        self.chat.insert("end", text + "\n", tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def write_system(self, text):
        self._append(text, "system")

    def write(self, who, text, source=""):
        d = "rtl" if is_arabic(text) else "ltr"
        name = "أنت" if who == "user" else "Jarvis"
        head = f"{name}  ·  {time.strftime('%H:%M')}" + (f"  ·  {source}" if source else "")
        self._append(head, f"{who}_head_{d}")
        self._append(text, f"{who}_{d}")

    # ---- background work ---------------------------------------------------
    def _boot(self):
        try:
            j = Jarvis(home=self.home)
            self.results.put(("booted", j))
        except Exception as exc:  # pragma: no cover - shown in the window
            self.results.put(("fatal", exc))

    def send(self, text=None):
        text = (text if text is not None else self.entry.get()).strip()
        if not text:
            return
        if self.jarvis is None:
            self.write_system("لحظة، الأنظمة لم تكتمل بعد…")
            return
        self.entry.delete(0, "end")
        self._align_entry()
        self.write("user", text)
        self._busy(True)
        threading.Thread(target=self._ask, args=(text,), daemon=True).start()

    def _ask(self, text):
        with self.lock:
            try:
                reply = self.jarvis.handle(text)
                self.results.put(("reply", reply))
            except Exception as exc:  # handle() already heals; this is a last resort
                self.results.put(("error", exc))

    def _poll(self):
        try:
            while True:
                kind, value = self.results.get_nowait()
                if kind == "booted":
                    self.jarvis = value
                    self.root.title(f"J.A.R.V.I.S  —  {value.config.home}")
                    for note in value.startup_notes:
                        self.write_system(f"🔧 {note}")
                    title = value.config["user_title"]
                    self.write("jarvis", f"مرحباً {title}. كل الأنظمة جاهزة، كيف أقدر أخدمك؟", "system")
                    self._busy(False)
                elif kind == "reply":
                    self.write("jarvis", value.text, value.source)
                    self._busy(False)
                elif kind == "error":
                    self.write("jarvis", f"حصل عطل غير متوقع: {value}", "error")
                    self._busy(False)
                elif kind == "fatal":
                    self.write_system(f"تعذّر التشغيل: {value}")
                    self.status_var.set("● offline")
                    self.status.configure(fg=BAD)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _busy(self, on):
        self.reactor.busy = on
        if on:
            self.status_var.set("● يفكر…  thinking")
            self.status.configure(fg=WARN)
        else:
            brain = (self.jarvis.router.last_used if self.jarvis else None) or "ready"
            self.status_var.set(f"● online  ·  brain: {brain}")
            self.status.configure(fg=OK)
            self._refresh_brains()

    def _refresh_brains(self):
        if not self.jarvis:
            return
        for w in self.brains_box.winfo_children():
            w.destroy()
        for name, status in self.jarvis.router.status():
            ready = status.startswith("ready") and "cooling" not in status
            color = OK if ready else (WARN if "cooling" in status else MUTED)
            row = tk.Frame(self.brains_box, bg=PANEL)
            row.pack(fill="x", pady=1)
            tk.Label(row, text="●", fg=color, bg=PANEL, font=self.f_small).pack(side="left")
            tk.Label(row, text=f" {name}", fg=ICE, bg=PANEL, font=self.f_mono).pack(side="left")
            short = "ready" if ready else ("cooling" if "cooling" in status else "off")
            tk.Label(row, text=short, fg=color, bg=PANEL, font=self.f_small).pack(side="right")

    def _quit(self):
        if self.jarvis:
            self.jarvis.close()
        self.root.destroy()


def main(home=None):
    root = tk.Tk()
    if sys.platform == "win32":
        try:  # crisp text on high-DPI Windows screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    JarvisApp(root, home=home)
    root.mainloop()


if __name__ == "__main__":
    main()
