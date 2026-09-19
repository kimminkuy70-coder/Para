"""현대적인 플랫 UI 테마 (추가 패키지 없이 ttk 스타일만 사용).

디자인 방향(2026-09, `claude/ux-bento-navy-lime`): **벤토 그리드 + 미니멀리즘**.
- **네이비 = 구조**(상단바·제목·기본 버튼), **선명한 라임 = 강조**(활성 탭·주요 CTA·
  히어로 숫자·선택). 라임 위 글자는 항상 네이비(`on_accent`)로 대비를 확보한다.
- **미니멀**: 아주 밝은 배경 + 흰 카드 + 얇은 hairline 테두리 + 넉넉한 여백.
- 폰트는 **맑은 고딕**을 우선(설치 보장). 역할별 크기·굵기로 위계만 준다.

주의: 값 확인의 2분할 tksheet('장비 화면')는 실제 장비처럼 어두운 회색을 쓰므로
이 팔레트와 별개다(equip_app 쪽에서 직접 지정, 여기서 바꾸지 않는다).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# 팔레트 — 네이비 + 라임(미니멀·플랫)
PALETTE = {
    "bg":        "#f4f6fa",   # 앱 배경(아주 밝은 쿨그레이)
    "surface":   "#ffffff",   # 카드/그리드 표면
    # 네이비(구조·기본 버튼: 흰 글자)
    "primary":   "#1b345f",   # 강조(네이비)
    "primary_dk": "#12244a",
    "primary_lt": "#e7edf7",  # 연한 네이비 틴트(호버/칩)
    # 라임(강조·주요 CTA·활성: 네이비 글자)
    "accent":    "#a3e635",   # 선명한 라임
    "accent_dk": "#84cc16",   # 라임(진하게, 호버/눌림)
    "accent_lt": "#ecf7cf",   # 아주 연한 라임 틴트(선택/배지 배경)
    "on_accent": "#12244a",   # 라임 위 글자(네이비)
    "text":      "#10203a",   # 본문(네이비 잉크)
    "muted":     "#6a7688",   # 보조 글자
    "border":    "#e4e8f0",   # hairline 테두리
    "stripe":    "#f6f8fc",   # 짝수행 줄무늬
    "select":    "#eaf5c9",   # 선택행(연한 라임)
    "head_bg":   "#eef1f6",   # 헤더/섹션 배경(밝은)
    "header_bar": "#0f1e3d",  # 상단 타이틀 바(딥 네이비)
    "header_fg": "#f2f5fb",
    "danger":    "#d64545",
    "ok":        "#3f9142",   # 성공/긍정 텍스트·보조 버튼(흰 글자 가독)
    # 비교 탭 강조
    "missing":   "#fef3c7",
    "diff":      "#fee2e2",
    "common":    "#dcfce7",
}


def _pick_family(root: tk.Misc) -> str:
    """맑은 고딕 우선(설치 보장). 없으면 한글 가능한 폴백을 차례로."""
    fams = set(tkfont.families(root))
    for cand in ("맑은 고딕", "Malgun Gothic", "Noto Sans CJK KR", "Segoe UI",
                 "Apple SD Gothic Neo"):
        if cand in fams:
            return cand
    return "TkDefaultFont"


def apply_theme(root: tk.Tk) -> dict:
    """루트에 테마를 적용하고 팔레트+폰트 dict 를 반환."""
    p = dict(PALETTE)
    fam = _pick_family(root)

    # 역할별 크기·굵기 위계(미니멀: 제목 크게·굵게, 보조 작게).
    fonts = {
        "base":   tkfont.Font(family=fam, size=10),
        "bold":   tkfont.Font(family=fam, size=10, weight="bold"),
        "head":   tkfont.Font(family=fam, size=10, weight="bold"),
        "title":  tkfont.Font(family=fam, size=16, weight="bold"),  # 화면 제목
        "h2":     tkfont.Font(family=fam, size=12, weight="bold"),  # 카드/섹션 제목
        "kpi":    tkfont.Font(family=fam, size=22, weight="bold"),  # 히어로 통계 숫자
        "sub":    tkfont.Font(family=fam, size=9),
        "micro":  tkfont.Font(family=fam, size=8),                  # 캡션/배지
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
    style.configure("HeaderInfo.TLabel", background=p["header_bar"], foreground="#c4d0e6", font=fonts["sub"])

    # 버튼 (플랫)
    style.configure("TButton", background=p["surface"], foreground=p["text"],
                    font=fonts["base"], padding=(12, 7), relief="flat", borderwidth=1)
    style.map("TButton",
              background=[("active", p["head_bg"]), ("pressed", p["border"])],
              bordercolor=[("!disabled", p["border"])])

    # 기본 강조 버튼 = 네이비(흰 글자)
    style.configure("Primary.TButton", background=p["primary"], foreground="#ffffff",
                    font=fonts["bold"], padding=(14, 7), relief="flat", borderwidth=0)
    style.map("Primary.TButton",
              background=[("active", p["primary_dk"]), ("pressed", p["primary_dk"])],
              foreground=[("disabled", "#e5e7eb")])

    # 주요 CTA = 라임(네이비 글자)
    style.configure("Accent.TButton", background=p["accent"], foreground=p["on_accent"],
                    font=fonts["bold"], padding=(14, 7), relief="flat", borderwidth=0)
    style.map("Accent.TButton",
              background=[("active", p["accent_dk"]), ("pressed", p["accent_dk"])],
              foreground=[("disabled", "#7c8aa0")])

    style.configure("Ghost.TButton", background=p["header_bar"], foreground=p["header_fg"],
                    font=fonts["base"], padding=(10, 6), relief="flat", borderwidth=0)
    style.map("Ghost.TButton", background=[("active", "#1c3358")])

    # 노트북 탭 — 선택 시 네이비 글자 + 라임 밑줄 느낌(굵게)
    style.configure("TNotebook", background=p["bg"], borderwidth=0, tabmargins=(8, 6, 8, 0))
    style.configure("TNotebook.Tab", background=p["bg"], foreground=p["muted"],
                    font=fonts["base"], padding=(18, 9), borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", p["surface"])],
              foreground=[("selected", p["primary"])],
              font=[("selected", fonts["bold"])])

    # Treeview (그리드) — 선택행은 연한 라임 틴트
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
