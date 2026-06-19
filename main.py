import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading, os, sys, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from symptom_matcher import predict_diseases, get_severity_score, get_severity_level
from chatbot_engine import (
    ask_question, give_conclusion, ask_groq, ask_followup,
    analyze_image_with_groq, start_image_qa,
    greet_patient, analyze_pdf_with_groq, parse_response,
    QUESTION_BANK
)
from pdf_reader import extract_text_from_pdf

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ══════════════════════════════════════════════════════════════════════════
#  BEAUTIFUL LIGHT THEME — WARM CLINICAL ELEGANCE
# ══════════════════════════════════════════════════════════════════════════
BG        = "#f1f5f9"      # cool slate mist
SIDEBAR   = "#f8fafc"     # ice white
CARD      = "#e2e8f0"     # slate cloud
BORDER    = "#94a3b8"     # slate border
FIELD_BG  = "#f1f5f9"     # slate ice field
HOVER     = "#cbd5e1"     # slate hover
GREEN     = "#0369a1"     # ocean blue (primary)
GREEN_H   = "#075985"
BLUE      = "#7c3aed"     # violet
BLUE_H    = "#6d28d9"
PURPLE    = "#0891b2"     # cyan
PURPLE_H  = "#0e7490"
AMBER     = "#ea580c"     # tangerine
AMBER_H   = "#c2410c"
RED       = "#dc2626"
RED_H     = "#b91c1c"
TEXT      = "#000000"      # pure black
SUB       = "#000000"
LABEL     = "#000000"      # pure black labels
MUTED     = "#334155"      # dark slate
USR_BG    = "#6366f1"   # soft indigo

# Section header colours (in conclusion report)
SEC_BLUE   = "#0c4a6e"
SEC_GREEN  = "#065f46"
SEC_AMBER  = "#9a3412"
SEC_PURPLE = "#155e75"
SEC_RED    = "#991b1b"

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROFILE_FILE = os.path.join(BASE_DIR, "profile.json")
HISTORY_DIR  = os.path.join(BASE_DIR, "chat_history")
os.makedirs(HISTORY_DIR, exist_ok=True)

MAX_QUESTIONS = 6

SECTIONS = [
    ("\U0001f50d ANALYSIS:",                        SEC_BLUE),
    ("\U0001f9a0 POSSIBLE CONDITIONS:",              SEC_GREEN),
    ("\u26a0\ufe0f SEVERITY ASSESSMENT:",             SEC_AMBER),
    ("\u2705 PRECAUTIONS & RECOMMENDATIONS:",    SEC_GREEN),
    ("\u2705 PRECAUTIONS:",                      SEC_GREEN),
    ("\u2705 RECOMMENDATIONS:",                 SEC_GREEN),
    ("\U0001f48a COMMON MEDICINES:",                 SEC_PURPLE),
    ("\U0001f6a8 WHEN TO SEE A DOCTOR IMMEDIATELY:", SEC_RED),
    ("\U0001f6a8 WHEN TO SEE A DOCTOR:",             SEC_RED),
    ("\u26a0\ufe0f DISCLAIMER:",                      SEC_AMBER),
]

OPT_COLORS = [
    ("#e0f2fe", "#0369a1", "#075985"),
    ("#ccfbf1", "#0891b2", "#0e7490"),
    ("#ede9fe", "#7c3aed", "#6d28d9"),
    ("#ffedd5", "#ea580c", "#c2410c"),
]

FONT_BODY  = ("Segoe UI", 14)
FONT_BODY_B = ("Segoe UI", 14, "bold")
FONT_HDR   = ("Georgia", 16, "bold")


# ── HELPERS ───────────────────────────────────────────────────────────────
def now_str(): return datetime.now().strftime("%I:%M %p")

def save_profile(data):
    with open(PROFILE_FILE, "w") as f: json.dump(data, f, indent=2)

def load_profile():
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE) as f: return json.load(f)
        except Exception: pass
    return {"name":"","age":"","gender":"Male","blood_pressure":"","known_conditions":""}

def list_chats():
    return sorted([f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")], reverse=True)

def load_chat(f):
    with open(os.path.join(HISTORY_DIR, f)) as fp: return json.load(fp)

def save_chat(cid, msgs):
    with open(os.path.join(HISTORY_DIR, f"{cid}.json"), "w") as f: json.dump(msgs, f, indent=2)

def del_chat(f):
    p = os.path.join(HISTORY_DIR, f)
    if os.path.exists(p): os.remove(p)


# ── TEXT BOX BUILDERS ─────────────────────────────────────────────────────

_CHAT_CANVAS = [None]

def _fwd_scroll(event):
    c = _CHAT_CANVAS[0]
    if not c: return "break"
    if event.delta:
        c.yview_scroll(int(-1 * (event.delta / 40)), "units")
    elif event.num == 4: c.yview_scroll(-6, "units")
    elif event.num == 5: c.yview_scroll(6, "units")
    return "break"


def _height(text, wrap=700, lh=21):
    cpl = max(40, wrap // 9)   # ~9px per char for bold font size 14
    lines = 0.0
    in_disc = False
    for line in text.split("\n"):
        s = line.strip()
        if s == "":
            lines += 0.3
        else:
            is_hdr = any(h.rstrip(":") in s for h,_ in SECTIONS)
            if is_hdr and "DISCLAIMER" in s:
                in_disc = True
            # Headers and disclaimer body are bold — use fewer chars
            if is_hdr:
                chars = min(48, cpl - 12)
            elif in_disc:
                chars = min(55, cpl - 8)
            else:
                chars = cpl
            lines += max(1, -(-len(s) // chars))
    return max(40, min(int(lines * lh) + 28, 5000))


def _bind_tb(tk):
    tk.bind("<MouseWheel>", _fwd_scroll)
    tk.bind("<Button-4>", _fwd_scroll)
    tk.bind("<Button-5>", _fwd_scroll)


def make_rich_box(parent, text):
    """Conclusion report — white card, bold dark section headers, dark body text."""
    tb = ctk.CTkTextbox(parent, height=_height(text, wrap=700),
                         fg_color="#f8fafc", border_color="#7dd3fc", border_width=2,
                         corner_radius=16, font=ctk.CTkFont(size=14),
                         text_color="#000000", wrap="word", activate_scrollbars=False)
    tb.pack(anchor="w", fill="x", pady=(0, 4))
    tk = tb._textbox
    tk.configure(bg="#ffffff", relief="flat")
    for hdr, col in SECTIONS:
        tk.tag_configure(f"h{abs(hash(hdr))%99999}",
                          foreground=col, font=FONT_HDR, spacing1=10, spacing3=3)
    tk.tag_configure("body", foreground="#000000", font=FONT_BODY,
                      lmargin1=14, lmargin2=14, spacing1=1, spacing3=2)
    tk.tag_configure("disc", foreground="#8B0000",
                      font=("Segoe UI", 14, "bold"), lmargin1=14, lmargin2=14,
                      spacing1=1, spacing3=2)
    in_disc = False
    for i, line in enumerate(text.split("\n")):
        m = next((hdr for hdr, _ in SECTIONS
                  if hdr.rstrip(":") in line or line.strip().startswith(hdr)), None)
        if m:
            if i > 0: tk.insert("end", "\n")
            tk.insert("end", f" {line.strip()}\n", f"h{abs(hash(m))%99999}")
            in_disc = "DISCLAIMER" in m
        elif line.strip() == "": tk.insert("end", "\n")
        else: tk.insert("end", f"  {line}\n", "disc" if in_disc else "body")
    tb.configure(state="disabled")
    _bind_tb(tk)
    return tb


def make_teal_box(parent, text):
    """Question / short-answer — soft mint card, dark text."""
    tb = ctk.CTkTextbox(parent, height=_height(text, wrap=600, lh=21),
                         fg_color="#f0f9ff", border_color="#38bdf8", border_width=2,
                         corner_radius=16, font=ctk.CTkFont(size=14),
                         text_color="#000000", wrap="word", activate_scrollbars=False)
    tb.pack(anchor="w", fill="x", pady=(0, 4))
    tk = tb._textbox
    tk.configure(bg="#f0f9ff", relief="flat")
    tk.tag_configure("q", foreground="#000000", font=FONT_BODY,
                      lmargin1=14, lmargin2=14, spacing1=2, spacing3=2)
    tk.insert("end", text, "q")
    tb.configure(state="disabled")
    _bind_tb(tk)
    return tb


def make_user_box(parent, text):
    """User bubble — soft lavender, auto-width, right-aligned."""
    # Calculate width based on text length — compact for short, wider for long
    char_w = 8.5  # approx pixels per char at size 14
    pad = 36       # internal padding
    max_w = 620    # max bubble width
    min_w = 120    # min bubble width
    raw_w = int(len(text) * char_w + pad)
    box_w = max(min_w, min(max_w, raw_w))
    # If text needs wrapping, use max width
    if len(text) > 65:
        box_w = max_w

    tb = ctk.CTkTextbox(parent, width=box_w,
                         height=_height(text, wrap=box_w-pad, lh=21),
                         fg_color="#ddd6f3", border_color="#b8a9e0", border_width=1,
                         corner_radius=14, font=ctk.CTkFont(size=14),
                         text_color="#1a1035", wrap="word", activate_scrollbars=False)
    tb.pack(anchor="e", padx=(10, 6), pady=(0, 4))
    tk = tb._textbox
    tk.configure(bg="#ddd6f3", relief="flat")
    tk.tag_configure("m", foreground="#1a1035", font=FONT_BODY,
                      lmargin1=14, lmargin2=14, spacing1=3, spacing3=3)
    tk.insert("end", text, "m")
    tb.configure(state="disabled")
    _bind_tb(tk)
    return tb


# ══════════════════════════════════════════════════════════════════════════
class HealthApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("MediAI \u2014 AI Health Consultation System")
        self.minsize(1024, 680)
        self.configure(fg_color=BG)

        # Force full screen
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")
        self.after(50, self._maximize)

        self.profile = load_profile()
        self.chat_log = []; self.chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._tw = None; self._last_dx = ""
        self._qa_on = False; self._qa_hist = []; self._qa_n = 0
        self._img_on = False; self._img_hist = []; self._img_n = 0
        self._p = {"type":"plain","text":"","opts":[],"sev":None,"img":False}

        self._build()
        self._bind_smooth_scroll()
        self._refresh_hist()
        self._welcome()

    def _maximize(self):
        try: self.state("zoomed"); return
        except: pass
        try: self.attributes("-zoomed", True); return
        except: pass

    def _build(self):
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_history()
        self._build_chat()

    # ── SIDEBAR ────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=268, fg_color=SIDEBAR, corner_radius=0,
                           border_width=1, border_color=BORDER)
        sb.grid(row=0, column=0, sticky="nsew"); sb.grid_propagate(False)

        # ═══ BOTTOM SECTION — severity + footer (packed FIRST so it stays visible) ═══
        bot = ctk.CTkFrame(sb, fg_color="transparent")
        bot.pack(side="bottom", fill="x")

        ctk.CTkFrame(bot, height=3, fg_color="#0c4a6e").pack(fill="x", padx=16)
        ctk.CTkLabel(bot, text="LAST SEVERITY",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=18, pady=(8, 0))
        sc = ctk.CTkFrame(bot, fg_color="#f1f5f9", corner_radius=10,
                           border_color=BORDER, border_width=1)
        sc.pack(fill="x", padx=18, pady=(4, 6))
        self.sev_ic = ctk.CTkLabel(sc, text="\u25c9",
                                    font=ctk.CTkFont(size=16), text_color=MUTED)
        self.sev_ic.pack(side="left", padx=(12, 6), pady=8)
        self.sev_lb = ctk.CTkLabel(sc, text="Not analyzed yet",
                                    font=ctk.CTkFont(size=13, weight="bold"),
                                    text_color=MUTED)
        self.sev_lb.pack(side="left", pady=8)

        ctk.CTkFrame(bot, height=1, fg_color=BORDER).pack(fill="x")

        # ═══ TOP SECTION — logo + profile (fills remaining space) ═══
        top = ctk.CTkFrame(sb, fg_color="transparent")
        top.pack(side="top", fill="both", expand=True)

        # Logo
        logo = ctk.CTkFrame(top, fg_color="transparent")
        logo.pack(fill="x", padx=16, pady=(18, 0))
        av = ctk.CTkFrame(logo, fg_color=GREEN, width=42, height=42, corner_radius=12)
        av.pack(side="left", padx=(0, 10)); av.pack_propagate(False)
        ctk.CTkLabel(av, text="\u2695", font=ctk.CTkFont(size=21),
                     text_color="#fff").pack(expand=True)
        nc = ctk.CTkFrame(logo, fg_color="transparent"); nc.pack(side="left", anchor="w")
        ctk.CTkLabel(nc, text="MediAI",
                     font=ctk.CTkFont(family="Georgia", size=21, weight="bold"),
                     text_color="#000000").pack(anchor="w")
        ctk.CTkLabel(nc, text="AI Health Consultation System",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color="#374151").pack(anchor="w")

        ctk.CTkFrame(top, height=3, fg_color="#0c4a6e").pack(fill="x", padx=16, pady=(14, 0))

        # Profile header
        ph = ctk.CTkFrame(top, fg_color="transparent")
        ph.pack(fill="x", padx=18, pady=(10, 4))
        ctk.CTkLabel(ph, text="PATIENT PROFILE",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#000000").pack(side="left")
        ctk.CTkLabel(ph, text="\u25cf live",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=GREEN).pack(side="right")

        # Fields — compact spacing
        def fld(lbl, ph_txt, val=""):
            ctk.CTkLabel(top, text=lbl,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="#000000").pack(anchor="w", padx=18, pady=(5, 0))
            e = ctk.CTkEntry(top, placeholder_text=ph_txt,
                             fg_color=FIELD_BG, border_color=BORDER,
                             text_color="#000000",
                             placeholder_text_color="#6b7280",
                             height=34, corner_radius=8,
                             font=ctk.CTkFont(size=13))
            e.pack(fill="x", padx=18, pady=(0, 0))
            if val: e.insert(0, val)
            return e

        p = self.profile
        self.e_name = fld("Full Name",       "e.g. Rahul Sharma",   p.get("name",""))
        self.e_age  = fld("Age",             "e.g. 25",             p.get("age",""))
        self.e_bp   = fld("Blood Pressure",  "e.g. 120/80",         p.get("blood_pressure",""))
        self.e_cond = fld("Known Conditions","e.g. Diabetes / None", p.get("known_conditions",""))

        ctk.CTkLabel(top, text="Gender",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#000000").pack(anchor="w", padx=18, pady=(5, 0))
        self.gvar = ctk.StringVar(value=p.get("gender", "Male"))
        ctk.CTkOptionMenu(top, values=["Male","Female","Other"], variable=self.gvar,
                          fg_color=FIELD_BG, button_color=BLUE, button_hover_color=BLUE_H,
                          text_color="#000000", dropdown_fg_color="#fff",
                          dropdown_text_color="#000000", dropdown_hover_color=HOVER,
                          height=34, corner_radius=8).pack(fill="x", padx=18)

        ctk.CTkButton(top, text="\U0001f4be  Save & Update Profile",
                      command=self._save_profile,
                      fg_color=GREEN, hover_color=GREEN_H, text_color="#fff",
                      height=40, corner_radius=10,
                      font=ctk.CTkFont(size=13, weight="bold")
                      ).pack(fill="x", padx=18, pady=(12, 0))

    # ── HISTORY PANEL ──────────────────────────────────────────────────────
    def _build_history(self):
        hp = ctk.CTkFrame(self, width=215, fg_color="#e2e8f0", corner_radius=0,
                           border_width=1, border_color=BORDER)
        hp.grid(row=0, column=1, sticky="nsew"); hp.grid_propagate(False)

        hdr = ctk.CTkFrame(hp, fg_color=SIDEBAR, height=56, corner_radius=0)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Chat History",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#080808").pack(side="left", padx=14, pady=14)

        br = ctk.CTkFrame(hp, fg_color="transparent")
        br.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkButton(br, text="\uff0b New Chat", command=self._new_chat,
                      fg_color=BLUE, hover_color=BLUE_H, text_color="#fff",
                      height=38, corner_radius=10,
                      font=ctk.CTkFont(size=12, weight="bold")
                      ).pack(fill="x", pady=(0, 4))
        ctk.CTkButton(br, text="\U0001f5d1 Clear Chat", command=self._clear_chat,
                      fg_color="#fef2f2", hover_color="#fecdd3",
                      text_color=RED, border_color="#e8b4b4", border_width=1,
                      height=38, corner_radius=10,
                      font=ctk.CTkFont(size=11, weight="bold")
                      ).pack(fill="x")

        ctk.CTkFrame(hp, height=1, fg_color=BORDER).pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(hp, text="PREVIOUS CHATS",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#000000").pack(anchor="w", padx=12, pady=(2, 4))

        self.hist_sf = ctk.CTkScrollableFrame(hp, fg_color="transparent",
                                                   corner_radius=0,
                                                   scrollbar_button_color="#94a3b8",
                                                   scrollbar_button_hover_color="#64748b")
        self.hist_sf.pack(fill="both", expand=True)

        ctk.CTkFrame(hp, height=1, fg_color=BORDER).pack(fill="x")
        ctk.CTkButton(hp, text="\U0001f4be Save Chat", command=self._save_chat_btn,
                      fg_color=PURPLE, hover_color=PURPLE_H, text_color="#fff",
                      height=36, corner_radius=10,
                      font=ctk.CTkFont(size=11, weight="bold")
                      ).pack(fill="x", padx=10, pady=8)

    def _refresh_hist(self):
        for w in self.hist_sf.winfo_children(): w.destroy()
        chats = list_chats()
        if not chats:
            ctk.CTkLabel(self.hist_sf, text="No saved chats yet",
                         font=ctk.CTkFont(size=11), text_color=MUTED).pack(pady=20)
            return
        for f in chats:
            try:
                dt = datetime.strptime(f.replace(".json",""), "%Y%m%d_%H%M%S")
                label = dt.strftime("%d %b  %I:%M %p")
            except: label = f.replace(".json","")
            row = ctk.CTkFrame(self.hist_sf, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=2)
            ctk.CTkButton(row, text=f"\U0001f4ac {label}",
                          command=lambda fn=f: self._load_chat(fn),
                          fg_color="#f8fafc", hover_color="#cbd5e1",
                          text_color="#080808", anchor="w",
                          height=34, corner_radius=8,
                          font=ctk.CTkFont(size=11)
                          ).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="\u2715", width=30, height=34,
                          fg_color="transparent", hover_color="#fecdd3",
                          text_color="#999", corner_radius=8,
                          font=ctk.CTkFont(size=10),
                          command=lambda fn=f: self._del_chat(fn)
                          ).pack(side="right", padx=(2, 0))

    # ── CHAT AREA ──────────────────────────────────────────────────────────
    def _build_chat(self):
        cc = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        cc.grid(row=0, column=2, sticky="nsew")
        cc.grid_rowconfigure(1, weight=1)
        cc.grid_columnconfigure(0, weight=1)

        # Header with accent bars top and bottom
        hdr = ctk.CTkFrame(cc, fg_color="#f8fafc", height=62, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew"); hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)
        # Dark teal accent lines — full width, bold visible
        ctk.CTkFrame(hdr, fg_color="#0c4a6e", height=4, corner_radius=0).place(x=0, y=0, relwidth=1)
        ctk.CTkFrame(hdr, fg_color="#0c4a6e", height=3, corner_radius=0).place(x=0, rely=1.0, relwidth=1, anchor="sw")
        ctk.CTkLabel(hdr, text="Health Consultation Chat",
                     font=ctk.CTkFont(family="Georgia", size=19, weight="bold"),
                     text_color="#000000").grid(row=0, column=0, padx=24, sticky="w")
        self.stat_lbl = ctk.CTkLabel(hdr, text="\u25cf Ready",
                                      font=ctk.CTkFont(size=12, weight="bold"),
                                      text_color=GREEN)
        self.stat_lbl.grid(row=0, column=1, padx=20)

        # Chat scroll — with subtle background pattern effect via bg color
        self.scroll = ctk.CTkScrollableFrame(cc, fg_color="#f1f5f9",
                                                 corner_radius=0,
                                                 scrollbar_button_color="#94a3b8",
                                                 scrollbar_button_hover_color="#64748b")
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        # Input bar
        ibar = ctk.CTkFrame(cc, fg_color="#f8fafc", height=74, corner_radius=0)
        ibar.grid(row=2, column=0, sticky="ew"); ibar.grid_propagate(False)
        ibar.grid_columnconfigure(0, weight=1)

        self.inp = ctk.CTkEntry(ibar,
            placeholder_text="Type your symptoms and press Enter...",
            fg_color="#f1f5f9", border_color="#94a3b8",
            text_color="#080808", placeholder_text_color="#999",
            height=48, corner_radius=24,
            font=ctk.CTkFont(size=14))
        self.inp.grid(row=0, column=0, padx=(18, 10), pady=13, sticky="ew")
        self.inp.bind("<Return>", lambda e: self._send())

        br = ctk.CTkFrame(ibar, fg_color="transparent")
        br.grid(row=0, column=1, padx=(0, 16), pady=13)
        for txt, cmd, fg, hv, w in [
            ("Send \u27a4",   self._send,         BLUE,   BLUE_H,   96),
            ("\U0001f5bc Image",  self._upload_image, PURPLE, PURPLE_H, 100),
            ("\U0001f4c4 PDF",    self._upload_pdf,   AMBER,  AMBER_H,  86),
        ]:
            ctk.CTkButton(br, text=txt, command=cmd,
                          fg_color=fg, hover_color=hv, text_color="#fff",
                          height=48, width=w, corner_radius=12,
                          font=ctk.CTkFont(size=12,
                                           weight="bold" if "Send" in txt else "normal")
                          ).pack(side="left", padx=(0, 6))

    # ── SMOOTH SCROLL ─────────────────────────────────────────────────────
    def _bind_smooth_scroll(self):
        canvas = self.scroll._parent_canvas
        _CHAT_CANVAS[0] = canvas
        canvas.configure(yscrollincrement=18)
        sp = str(self.scroll)
        def _on(event):
            try: wp = str(event.widget)
            except: return
            if not wp.startswith(sp): return
            if event.delta:
                u = int(-1 * (event.delta / 40))
                if u == 0: u = -1 if event.delta > 0 else 1
                canvas.yview_scroll(u, "units")
            elif event.num == 4: canvas.yview_scroll(-6, "units")
            elif event.num == 5: canvas.yview_scroll(6, "units")
            return "break"
        self.bind_all("<MouseWheel>", _on)
        self.bind_all("<Button-4>", _on)
        self.bind_all("<Button-5>", _on)

    # ── OPTION BUTTONS ─────────────────────────────────────────────────────
    def _add_opts(self, opts, is_q=False):
        if not opts: return
        lf = ctk.CTkFrame(self.scroll, fg_color="transparent")
        lf.pack(fill="x", padx=60, pady=(3, 4))
        ctk.CTkLabel(lf,
                     text="  \U0001f518 Select your answer:" if is_q else "  \U0001f4a1 More options:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#000000").pack(anchor="w")
        bf = ctk.CTkFrame(self.scroll, fg_color="transparent")
        bf.pack(fill="x", padx=60, pady=(0, 10))
        for i, opt in enumerate(opts):
            bg, brd, tc = OPT_COLORS[i % len(OPT_COLORS)]
            ctk.CTkButton(bf, text=f"  {opt}  ",
                          command=lambda o=opt: self._opt_click(o),
                          fg_color=bg, hover_color=brd, text_color=tc,
                          border_color=brd, border_width=1,
                          height=38, corner_radius=20,
                          font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
                          ).pack(side="left", padx=(0, 8), pady=3)
        self._scroll_end()

    def _opt_click(self, opt):
        self._bubble_user(opt)
        prof = self._get_prof()
        self._show_typing()
        self._set_status("\u23f3 Thinking...", AMBER)
        if self._img_on:
            self._img_hist.append({"role":"user","content":opt})
            threading.Thread(target=self._img_qa_next, args=(prof,), daemon=True).start()
        elif self._qa_on:
            self._qa_hist.append({"role":"user","content":opt})
            threading.Thread(target=self._qa_next, args=(prof,), daemon=True).start()
        else:
            threading.Thread(target=self._do_followup, args=(opt, self._last_dx, prof), daemon=True).start()

    def _do_followup(self, q, dx, prof):
        """Answer user's question. Works with or without prior diagnosis context."""
        if not dx or len(dx.strip()) < 20:
            # No diagnosis yet — use ask_groq for a direct helpful answer
            ctx = ""
            if prof:
                ctx = f"Patient: {prof.get('name','')}, Age: {prof.get('age','')}, "
                ctx += f"Conditions: {prof.get('known_conditions','')}\n"
            raw = ask_groq(ctx + f"Patient asks: {q}\n\n"
                          "Give a helpful, specific answer to their question. "
                          "If they ask about diet, give specific foods to eat and avoid. "
                          "If they ask about remedies, give practical home remedies. "
                          "Keep it concise — 5-6 sentences max.", prof)
        else:
            raw = ask_followup(q, dx, prof)
        _, text, opts = parse_response(raw)
        self._p = {"type":"plain","text":text,"opts":opts,"sev":None,"img":False}
        self.after(50, self._show_p)

    # ── BUBBLE HELPERS ─────────────────────────────────────────────────────
    def _av(self, parent, emoji="\u2695", color=None):
        av = ctk.CTkFrame(parent, fg_color=color or GREEN,
                           width=40, height=40, corner_radius=12)
        av.pack(side="left", anchor="n", padx=(0, 10), pady=2)
        av.pack_propagate(False)
        ctk.CTkLabel(av, text=emoji, font=ctk.CTkFont(size=18),
                     text_color="#fff").pack(expand=True)

    def _bubble_user(self, text):
        t = now_str()
        outer = ctk.CTkFrame(self.scroll, fg_color="transparent")
        outer.pack(fill="x", pady=(8, 2), padx=16)
        ctk.CTkLabel(outer, text=f"You  \u00b7  {t}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#5b21b6").pack(anchor="e", padx=10, pady=(0, 4))
        make_user_box(outer, text)
        self._scroll_end()
        self.chat_log.append({"role":"user","text":text,"time":t})

    def _bubble_question(self, question, opts, img=False):
        t = now_str()
        outer = ctk.CTkFrame(self.scroll, fg_color="transparent")
        outer.pack(fill="x", pady=(8, 2), padx=16)
        row = ctk.CTkFrame(outer, fg_color="transparent"); row.pack(anchor="w", fill="x")
        self._av(row, "\U0001f5bc" if img else "\u2753", BLUE)
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", anchor="nw", fill="x", expand=True)
        label = "Analyzing image..." if img else "Gathering your symptoms..."
        ctk.CTkLabel(col, text=f"MediAI  \u00b7  {t}  \u00b7  {label}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#0c4a6e").pack(anchor="w", pady=(2, 4))
        make_teal_box(col, question)
        self._add_opts(opts, is_q=True)
        self.chat_log.append({"role":"assistant","text":f"Q: {question}","time":t})

    def _bubble_conclusion(self, text, opts=None):
        t = now_str()
        outer = ctk.CTkFrame(self.scroll, fg_color="transparent")
        outer.pack(fill="x", pady=(8, 2), padx=16)
        row = ctk.CTkFrame(outer, fg_color="transparent"); row.pack(anchor="w", fill="x")
        self._av(row)
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", anchor="nw", fill="x", expand=True)
        ctk.CTkLabel(col, text=f"MediAI  \u00b7  {t}  \u00b7  Health Report",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#0c4a6e").pack(anchor="w", pady=(2, 4))
        make_rich_box(col, text)
        if opts: self._add_opts(opts, is_q=False)
        self.chat_log.append({"role":"assistant","text":text,"time":t})
        self._last_dx = text

    def _bubble_plain(self, text, opts=None):
        t = now_str()
        outer = ctk.CTkFrame(self.scroll, fg_color="transparent")
        outer.pack(fill="x", pady=(8, 2), padx=16)
        row = ctk.CTkFrame(outer, fg_color="transparent"); row.pack(anchor="w", fill="x")
        self._av(row)
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", anchor="nw", fill="x", expand=True)
        ctk.CTkLabel(col, text=f"MediAI  \u00b7  {t}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#0c4a6e").pack(anchor="w", pady=(2, 4))
        has_secs = any(h.rstrip(":") in text for h, _ in SECTIONS)
        if has_secs: make_rich_box(col, text)
        else: make_teal_box(col, text)
        if opts: self._add_opts(opts, is_q=False)
        self.chat_log.append({"role":"assistant","text":text,"time":t})

    def _show_typing(self):
        self._hide_typing()
        self._tw = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._tw.pack(fill="x", pady=(4, 2), padx=16)
        row = ctk.CTkFrame(self._tw, fg_color="transparent"); row.pack(anchor="w")
        self._av(row)
        ctk.CTkLabel(row, text="\u23f3  Analyzing...",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=LABEL, fg_color="#e2e8f0",
                     corner_radius=14, padx=18, pady=10).pack(side="left")
        self._scroll_end()

    def _hide_typing(self):
        if self._tw:
            try: self._tw.destroy()
            except: pass
            self._tw = None

    def _scroll_end(self):
        self.scroll.after(50, lambda: self.scroll._parent_canvas.yview_moveto(1.0))

    def _scroll_top(self):
        self.scroll.after(80, lambda: self.scroll._parent_canvas.yview_moveto(0.0))

    def _set_status(self, t, c=GREEN):
        self.stat_lbl.configure(text=t, text_color=c)

    def _set_sev(self, level):
        if not level: return
        c = GREEN if "Mild" in level else AMBER if "Moderate" in level else RED
        i = "\U0001f7e2" if "Mild" in level else "\U0001f7e1" if "Moderate" in level else "\U0001f534"
        self.sev_ic.configure(text=i, text_color=c)
        self.sev_lb.configure(text=level, text_color=c)

    def _queue(self, r_type, text, opts, sev=None, img=False):
        self._p = {"type":r_type,"text":text,"opts":opts or [],"sev":sev,"img":img}
        self.after(50, self._show_p)

    def _show_p(self):
        self._hide_typing(); p = self._p
        if p["sev"]: self._set_sev(p["sev"])
        t, text, opts, img = p["type"], p["text"], p["opts"], p["img"]
        if t == "question": self._bubble_question(text, opts, img=img)
        elif t == "conclusion": self._bubble_conclusion(text, opts)
        else: self._bubble_plain(text, opts)
        self._set_status("\u25cf Ready", GREEN)

    # ── PROFILE & CHAT CONTROLS ────────────────────────────────────────────
    def _get_prof(self):
        return {"name": self.e_name.get().strip(), "age": self.e_age.get().strip(),
                "gender": self.gvar.get(), "blood_pressure": self.e_bp.get().strip(),
                "known_conditions": self.e_cond.get().strip()}

    def _save_profile(self):
        data = self._get_prof(); save_profile(data); self.profile = data
        self._show_typing(); self._set_status("\u23f3 Saving...", AMBER)
        threading.Thread(target=lambda: self._queue("plain", greet_patient(dict(data)), []), daemon=True).start()

    def _reset_qa(self):  self._qa_on = False; self._qa_hist = []; self._qa_n = 0
    def _reset_img(self): self._img_on = False; self._img_hist = []; self._img_n = 0

    def _welcome(self):
        name = self.profile.get("name","").strip()
        self._bubble_plain(
            f"\U0001f44b {'Hello ' + name + '! ' if name else ''}Welcome to MediAI!\n\n"
            "Tell me your symptoms and I will ask you a few questions \u2014 "
            "just like a doctor \u2014 then give you a complete health report.\n\n"
            "\U0001f5bc  Image button \u2192 upload a medical image for analysis\n"
            "\U0001f4c4  PDF button   \u2192 upload a lab report for analysis\n\n"
            "\u26a0\ufe0f  This is for informational purposes only.\n"
            "Always consult a real doctor for medical advice.",
            opts=["I have fever","I have a skin problem","I have stomach pain","I have headache or cold"])
        self._scroll_top()

    def _new_chat(self):
        if self.chat_log: save_chat(self.chat_id, self.chat_log)
        self.chat_log = []; self.chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        for w in self.scroll.winfo_children(): w.destroy()
        self._tw = None; self._reset_qa(); self._reset_img(); self._last_dx = ""
        self.sev_ic.configure(text="\u25c9", text_color=MUTED)
        self.sev_lb.configure(text="Not analyzed yet", text_color=MUTED)
        self._set_status("\u25cf Ready", GREEN)
        self._refresh_hist(); self._welcome()

    def _clear_chat(self):
        if self.chat_log and not messagebox.askyesno("Clear", "Clear this chat?"): return
        self.chat_log = []
        for w in self.scroll.winfo_children(): w.destroy()
        self._tw = None; self._reset_qa(); self._reset_img(); self._last_dx = ""
        self.sev_ic.configure(text="\u25c9", text_color=MUTED)
        self.sev_lb.configure(text="Not analyzed yet", text_color=MUTED)
        self._bubble_plain("\U0001f5d1 Chat cleared! What symptoms do you have?",
                           opts=["Fever","Headache","Stomach pain","Cough / Cold"])
        self._scroll_top()

    def _save_chat_btn(self):
        if not self.chat_log: messagebox.showinfo("Nothing to save", "Start a conversation first!"); return
        save_chat(self.chat_id, self.chat_log); self._refresh_hist()
        messagebox.showinfo("\u2705 Saved", "Chat saved!")

    def _load_chat(self, fname):
        if self.chat_log: save_chat(self.chat_id, self.chat_log)
        self.chat_log = []
        for w in self.scroll.winfo_children(): w.destroy()
        self._tw = None; self._reset_qa(); self._reset_img()
        try:
            msgs = load_chat(fname); self.chat_id = fname.replace(".json","")
            for m in msgs:
                self.chat_log.append(m)
                if m["role"] == "user": self._rh_user(m["text"], m.get("time",""))
                else: self._rh_bot(m["text"], m.get("time",""))
        except Exception as e: self._bubble_plain(f"Could not load chat: {e}")

    def _del_chat(self, fname):
        if messagebox.askyesno("Delete", "Delete this chat?"):
            del_chat(fname); self._refresh_hist()

    def _rh_user(self, text, t):
        outer = ctk.CTkFrame(self.scroll, fg_color="transparent")
        outer.pack(fill="x", pady=(8, 2), padx=16)
        ctk.CTkLabel(outer, text=f"You  \u00b7  {t}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#5b21b6").pack(anchor="e", padx=10, pady=(0, 4))
        make_user_box(outer, text); self._scroll_end()

    def _rh_bot(self, text, t):
        outer = ctk.CTkFrame(self.scroll, fg_color="transparent")
        outer.pack(fill="x", pady=(8, 2), padx=16)
        row = ctk.CTkFrame(outer, fg_color="transparent"); row.pack(anchor="w", fill="x")
        self._av(row)
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", anchor="nw", fill="x", expand=True)
        ctk.CTkLabel(col, text=f"MediAI  \u00b7  {t}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#0c4a6e").pack(anchor="w", pady=(2, 4))
        if any(h.rstrip(":") in text for h, _ in SECTIONS): make_rich_box(col, text)
        else: make_teal_box(col, text)
        self._scroll_end()

    # ── SEND ──────────────────────────────────────────────────────────────
    def _is_user_question(self, text):
        """Detect if user is asking their own question instead of answering bot's Q."""
        t = text.lower().strip()
        # Starts with question words
        if any(t.startswith(w) for w in ["what ", "how ", "should ", "can ", "which ", "why ",
                                          "tell ", "give ", "suggest ", "recommend ", "is there ",
                                          "do i ", "will ", "when ", "where ", "so what", "so how"]):
            return True
        # Contains diet/food/remedy/medicine keywords
        if any(k in t for k in ["diet", "eat", "food", "remedy", "medicine", "prevent",
                                 "exercise", "doctor", "serious", "contagious", "cure",
                                 "treatment", "should i", "what to"]):
            return True
        return False

    def _send(self):
        text = self.inp.get().strip()
        if not text: return
        self.inp.delete(0, "end"); prof = self._get_prof()
        self._bubble_user(text); self._show_typing()
        self._set_status("\u23f3 Thinking...", AMBER)
        if self._img_on:
            self._img_hist.append({"role":"user","content":text})
            threading.Thread(target=self._img_qa_next, args=(prof,), daemon=True).start()
        elif self._qa_on:
            # Check if user is asking a question instead of answering
            if self._is_user_question(text):
                self._qa_hist.append({"role":"user","content":text})
                last_ctx = " | ".join(m.get("content","")[:80] for m in self._qa_hist[-6:] if m.get("role") in ("user","assistant"))
                self._reset_qa()
                threading.Thread(target=self._do_followup, args=(text, last_ctx, prof), daemon=True).start()
            else:
                self._qa_hist.append({"role":"user","content":text})
                threading.Thread(target=self._qa_next, args=(prof,), daemon=True).start()
        elif self._is_user_question(text) and self._last_dx:
            # User asking a follow-up after a previous diagnosis
            threading.Thread(target=self._do_followup, args=(text, self._last_dx, prof), daemon=True).start()
        else:
            # New symptom — start fresh QA
            self._reset_qa(); self._qa_on = True
            diseases = predict_diseases(text); score = get_severity_score(text)
            sev, _ = get_severity_level(score)
            ctx = f"Patient initial complaint: {text}\n"
            if diseases: ctx += f"Dataset suggests: {', '.join(d for d,_ in diseases[:3])}\n"
            ctx += f"Initial severity estimate: {sev}"
            self._qa_hist = [{"role":"system","content":ctx}, {"role":"user","content":text}]
            threading.Thread(target=self._qa_first, args=(prof,), daemon=True).start()

    # ── Q&A FLOWS ─────────────────────────────────────────────────────────
    def _qa_first(self, prof):
        raw = ask_question(self._qa_hist, prof, q_number=0); rt, txt, opts = parse_response(raw)
        if rt != "question": q, o = QUESTION_BANK[0]; txt, opts = q, o
        self._qa_n += 1; self._qa_hist.append({"role":"assistant","content":txt})
        self._queue("question", txt, opts)

    def _qa_next(self, prof):
        if self._qa_n >= MAX_QUESTIONS: self._qa_conclude(prof); return
        raw = ask_question(self._qa_hist, prof, q_number=self._qa_n); rt, txt, opts = parse_response(raw)
        if rt == "question":
            self._qa_n += 1; self._qa_hist.append({"role":"assistant","content":txt})
            self._queue("question", txt, opts)
        else:
            if self._qa_n >= 3: self._qa_conclude(prof)
            else:
                q, o = QUESTION_BANK[self._qa_n % len(QUESTION_BANK)]; self._qa_n += 1
                self._qa_hist.append({"role":"assistant","content":q}); self._queue("question", q, o)

    def _qa_conclude(self, prof):
        raw = give_conclusion(self._qa_hist, prof); _, txt, opts = parse_response(raw)
        sev = next((s for s in ["Severe","Moderate","Mild"] if s in txt), None)
        self._reset_qa(); self._queue("conclusion", txt, opts, sev=sev)

    def _img_qa_next(self, prof):
        if self._img_n >= 4:
            raw = give_conclusion(self._img_hist, prof); _, txt, opts = parse_response(raw)
            sev = next((s for s in ["Severe","Moderate","Mild"] if s in txt), None)
            self._reset_img(); self._queue("conclusion", txt, opts, sev=sev); return
        raw = ask_question(self._img_hist, prof, q_number=self._img_n); rt, txt, opts = parse_response(raw)
        if rt == "question":
            self._img_n += 1; self._img_hist.append({"role":"assistant","content":txt})
            self._queue("question", txt, opts, img=True)
        else:
            raw2 = give_conclusion(self._img_hist, prof); _, txt2, opts2 = parse_response(raw2)
            sev = next((s for s in ["Severe","Moderate","Mild"] if s in txt2), None)
            self._reset_img(); self._queue("conclusion", txt2, opts2, sev=sev)

    def _upload_image(self):
        path = filedialog.askopenfilename(title="Select Medical Image",
                      filetypes=[("Images","*.jpg *.jpeg *.png *.webp *.bmp *.gif")])
        if not path: return
        prof = self._get_prof()
        self._bubble_user(f"\U0001f4f7 Image: {os.path.basename(path)}")
        self._show_typing(); self._set_status("\u23f3 Analyzing image...", AMBER)
        threading.Thread(target=self._do_image, args=(path, prof), daemon=True).start()

    def _do_image(self, path, prof):
        rt, text, opts = analyze_image_with_groq(path, prof)
        if rt == "image_qa_start":
            self._reset_img(); self._img_on = True
            self._img_hist = [{"role":"system","content":"Patient uploaded a medical image. Ask questions to understand it."}]
            first = start_image_qa(prof); _, qtxt, qopts = parse_response(first)
            if not qtxt: qtxt = "What part of your body does the image show?"; qopts = ["Skin / rash","Eye","Throat / mouth","Wound","X-ray or scan"]
            self._img_n += 1; self._img_hist.append({"role":"assistant","content":qtxt})
            self._queue("question", qtxt, qopts, img=True)
        else: self._queue(rt, text, opts)

    def _upload_pdf(self):
        path = filedialog.askopenfilename(title="Select Medical PDF", filetypes=[("PDF","*.pdf")])
        if not path: return
        prof = self._get_prof()
        self._bubble_user(f"\U0001f4c4 Report: {os.path.basename(path)}")
        self._show_typing(); self._set_status("\u23f3 Reading PDF...", AMBER)
        threading.Thread(target=self._do_pdf, args=(path, prof), daemon=True).start()

    def _do_pdf(self, path, prof):
        txt = extract_text_from_pdf(path)
        if not txt or len(txt.strip()) < 20:
            raw = ask_groq("Patient uploaded a scanned PDF \u2014 text extraction failed. Ask them to type their test values manually in chat.", prof)
            rt, t, o = parse_response(raw); self._queue(rt, t, o); return
        raw = analyze_pdf_with_groq(txt, prof); rt, t, o = parse_response(raw); self._queue(rt, t, o)

    def on_close(self):
        if self.chat_log: save_chat(self.chat_id, self.chat_log)
        self.destroy()


if __name__ == "__main__":
    app = HealthApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()