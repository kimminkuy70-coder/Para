"""현대적인 플랫 UI 테마 (추가 패키지 없이 ttk 스타일만 사용).

색상은 밝은 톤의 플랫 디자인, 폰트는 한글이 깔끔한 '맑은 고딕'을 우선 사용한다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# 팔레트 (light / flat)
PALETTE = {
    "bg":        "#eef1f5",   # 앱 배경
    "surface":   "#ffffff",   # 카드/그리드 표면
    "primary":   "#2563eb",   # 강조(파랑)
    "primary_dk": "#1d4ed8",
    "primary_lt": "#dbeafe",
    "text":      "#1f2937",   # 본문 글자
    "muted":     "#6b7280",   # 보조 글자
    "border":    "#dfe3e8",
    "stripe":    "#f7f9fc",   # 짝수행 줄무늬
    "select":    "#dbeafe",   # 선택행
    "head_bg":   "#f1f4f8",   # 헤더 배경
    "header_bar": "#1e293b",  # 상단 타이틀 바
    "header_fg": "#f8fafc",
    "danger":    "#dc2626",
    "ok":        "#16a34a",
    # 비교 탭 강조
    "missing":   "#fef3c7",
    "diff":      "#fee2e2",
    "common":    "#dcfce7",
}


def _pick_family(root: tk.Misc) -> str:
    fams = set(tkfont.families(root))
    for cand in ("맑은 고딕", "Malgun Gothic", "Noto Sans CJK KR", "Segoe UI", "Apple SD Gothic Neo"):
        if cand in fams:
            return cand
    return "TkDefaultFont"


def apply_theme(root: tk.Tk) -> dict:
    """루트에 테마를 적용하고 팔레트+폰트 dict 를 반환."""
    p = dict(PALETTE)
    fam = _pick_family(root)

    fonts = {
        "base":   tkfont.Font(family=fam, size=10),
        "bold":   tkfont.Font(family=fam, size=10, weight="bold"),
        "head":   tkfont.Font(family=fam, size=10, weight="bold"),
        "title":  tkfont.Font(family=fam, size=15, weight="bold"),
        "sub":    tkfont.Font(family=fam, size=9),
        "grid":   tkfont.Font(family=fam, size=10),
    }
    p["family"] = fam
    p["fonts"] = fonts

    # tk(비 ttk) 위젯 기본 폰트/색
    root.option_add("*Font", fonts["base"])
    root.option_add("*Menu.Font", fonts["base"])
    root.configure(bg=p["bg"])

    style = ttk.Style(root)
    try:
        style.theme_use("clam")  # 가장 커스터마이즈가 자유로운 기본 테마
    except tk.TclError:
        pass

    # 전역
    style.configure(".", background=p["bg"], foreground=p["text"],
                    font=fonts["base"], borderwidth=0, focuscolor=p["bg"])
    style.configure("TFrame", background=p["bg"])
    style.configure("Surface.TFrame", background=p["surface"])
    style.configure("Header.TFrame", background=p["header_bar"])
    style.configure("TLabel", background=p["bg"], foreground=p["text"])
    style.configure("Surface.TLabel", background=p["surface"], foreground=p["text"])
    style.configure("Muted.TLabel", background=p["bg"], foreground=p["muted"], font=fonts["sub"])
    style.configure("Title.TLabel", background=p["header_bar"], foreground=p["header_fg"], font=fonts["title"])
    style.configure("HeaderInfo.TLabel", background=p["header_bar"], foreground="#cbd5e1", font=fonts["sub"])

    # 버튼 (플랫)
    style.configure("TButton", background=p["surface"], foreground=p["text"],
                    font=fonts["base"], padding=(12, 7), relief="flat", borderwidth=1)
    style.map("TButton",
              background=[("active", p["head_bg"]), ("pressed", p["border"])],
              bordercolor=[("!disabled", p["border"])])

    style.configure("Primary.TButton", background=p["primary"], foreground="#ffffff",
                    font=fonts["bold"], padding=(14, 7), relief="flat", borderwidth=0)
    style.map("Primary.TButton",
              background=[("active", p["primary_dk"]), ("pressed", p["primary_dk"])],
              foreground=[("disabled", "#e5e7eb")])

    style.configure("Ghost.TButton", background=p["header_bar"], foreground=p["header_fg"],
                    font=fonts["base"], padding=(10, 6), relief="flat", borderwidth=0)
    style.map("Ghost.TButton", background=[("active", "#334155")])

    # 노트북 탭
    style.configure("TNotebook", background=p["bg"], borderwidth=0, tabmargins=(8, 6, 8, 0))
    style.configure("TNotebook.Tab", background=p["bg"], foreground=p["muted"],
                    font=fonts["base"], padding=(18, 9), borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", p["surface"])],
              foreground=[("selected", p["primary"])],
              font=[("selected", fonts["bold"])])

    # Treeview (그리드)
    style.configure("Treeview", background=p["surface"], fieldbackground=p["surface"],
                    foreground=p["text"], font=fonts["grid"], rowheight=30,
                    borderwidth=0, relief="flat")
    style.configure("Treeview.Heading", background=p["head_bg"], foreground=p["muted"],
                    font=fonts["head"], relief="flat", padding=(8, 8), borderwidth=0)
    style.map("Treeview.Heading", background=[("active", p["border"])])
    style.map("Treeview",
              background=[("selected", p["select"])],
              foreground=[("selected", p["text"])])

    # Entry / Combobox
    style.configure("TEntry", fieldbackground=p["surface"], bordercolor=p["border"],
                    borderwidth=1, relief="flat", padding=5)
    style.configure("TCombobox", fieldbackground=p["surface"], background=p["surface"],
                    bordercolor=p["border"], borderwidth=1, padding=4)
    style.configure("TSeparator", background=p["border"])

    # 스크롤바 (슬림 플랫)
    style.configure("Vertical.TScrollbar", background=p["border"], troughcolor=p["bg"],
                    borderwidth=0, arrowsize=12, width=12)
    style.configure("Horizontal.TScrollbar", background=p["border"], troughcolor=p["bg"],
                    borderwidth=0, arrowsize=12)

    return p
