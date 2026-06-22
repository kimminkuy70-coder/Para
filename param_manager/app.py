"""tkinter + tksheet GUI — 화면 계층 (스프레드시트형 UX).

표 위젯은 tksheet(MIT, 순수 파이썬, 네트워크 없음)를 사용한다.
실제 로직은 engine 모듈에 있고, 이 파일은 화면과 사용자 조작만 담당한다.

탭 구성
  1) 파라미터 편집   : 구조 정의(PI/Recipe/Zone/Alg/Parameter/초기추천값/비고) 평면 표
  2) 파라미터 값 수정 : PI▸Recipe▸Zone▸Alg▸파라미터 드릴다운 트리, leaf에서 호기 값 편집
  3) 호기 비교/누락  : 모든 호기 + 누락 호기 열, 값 차이/누락 강조
  4) 변경 이력       : 자동 기록된 변경 로그 검색/필터
  5) 특이사항        : 라트별 메모, 종료여부 체크박스

공통: 모든 시트 Parameter 열까지 열 고정, 셀 줄바꿈+행높이 자동, 셀 테두리 표시.
"""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from tksheet import Sheet

HIGHLIGHT_YELLOW = "#FFF24D"   # 강조(노란색)


class Tooltip:
    """위젯에 마우스를 올리면 안내(단축키 등)를 보여주는 간단한 툴팁."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg="#1e293b", fg="#f8fafc",
                 padx=8, pady=4, bd=0).pack()

    def _hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None

from . import engine
from .engine import (
    AOI_UNITS,
    LOG_HEADERS,
    META_FIELDS,
    SPECIAL_BOOL_COL,
    SPECIAL_HEADERS,
    ParamRepository,
)
from .theme import apply_theme

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".pi_param_manager.json")
HEARTBEAT_MS = 5 * 60 * 1000

# 컬럼 폭(헤더명 기준)
WIDTHS = {
    "＋／－": 50,
    "PI": 60, "Recipe": 120, "Zone": 150, "Alg": 150, "Parameter": 170,
    "초기 추천값": 110, "비고": 230, "누락 호기": 380,
    "Update Date": 100, "Updated By": 90, "AOI": 70,
    "Old Value": 120, "New Value": 120, "Change Type": 110,
    "일자": 95, "호기": 80, "라트 번호": 130, "S/M": 60, "Layer": 70,
    "목적": 110, "진행 상황": 150, "종료 여부": 70, "특이사항": 320,
}
AOI_W = 70


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False)
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Camtek AOI 장비 파라미터 관리")
        self.geometry("1360x800")
        self.minsize(1000, 640)

        self.p = apply_theme(self)
        self.fam = self.p["family"]
        self.sheet_font = (self.fam, 10, "normal")
        self.sheet_hfont = (self.fam, 10, "bold")
        self.sheet_ifont = (self.fam, 9, "normal")

        self.repo: ParamRepository | None = None
        self.path: str | None = None
        self.read_only = False
        self.user = engine.current_user()
        self.dirty = False
        self.active_kind: str | None = None   # 현재 연 장비 종류 "PI"/"RDL"
        self._cfg = load_config()
        self.edit_ids: list[str] = []      # tab1 표시행 -> row_id
        # 호기 목록(파일에서 자동 인식; 기본은 PI 13개)
        self.aoi = list(AOI_UNITS)
        # 파라미터 항목 수정 / 호기별 값 수정 공통 열(메타 + 호기 값)
        self.full_cols = META_FIELDS + self.aoi
        self.val_cols = list(self.full_cols)   # 호기별 값 수정: 동일 열 + 셀 안 +/- 토글
        self.collapsed: set[str] = set()   # 접힌 그룹 key 집합
        self.val_display: list[dict] = []  # 표시행 메타(헤더/leaf 매핑)
        self.val_toggles: dict[tuple, str] = {}  # (행,열)->그룹key (셀 안 +/- 위치)
        self._sized: set[int] = set()      # 기본 열너비 적용된 시트(사용자 조절 보존용)
        self.spec_shown_idx: list[int] = []
        # 탭 기본 이름(키->기본 표시명). 사용자가 더블클릭으로 바꾸면 config 에 저장.
        self.tab_keys = ["edit", "value", "compare", "history", "special", "reference"]
        self.tab_default = {
            "edit": "파라미터 항목 수정", "value": "호기별 값 수정",
            "compare": "호기 비교 / 누락", "history": "변경 이력",
            "special": "특이사항", "reference": "참고자료",
        }

        self._build_menu()
        self._build_header()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(HEARTBEAT_MS, self._heartbeat)

        last = self._cfg.get("last_path")
        if last and os.path.exists(last):
            self.after(60, lambda: self.open_file(last))
        else:
            self._set_status("파일을 열어 시작하세요 — 파일 메뉴 ▸ 열기 / 엑셀 가져오기")

    # ---- 공통 시트 생성 ----------------------------------------------------

    def _make_sheet(self, parent, headers, frozen=0, editable=True) -> Sheet:
        s = Sheet(parent, theme="light blue", frozen_columns=frozen,
                  show_x_scrollbar=True, show_y_scrollbar=True,
                  font=self.sheet_font, header_font=self.sheet_hfont, index_font=self.sheet_ifont)
        s.headers(headers)
        # edit_cell_return/tab = "" : Enter/Tab 입력 후 같은 셀에 머무름
        # (마지막 셀에서 (1,1)로 점프하던 동작 방지)
        s.set_options(table_wrap="w", header_wrap="w", table_grid_fg="#cfd6df",
                      show_vertical_grid=True, show_horizontal_grid=True,
                      edit_cell_return="", edit_cell_tab="")
        # column_width_resize: 열 경계 드래그로 너비 조절,
        # double_click_column_resize: 경계 더블클릭 시 내용에 맞춰 자동 너비,
        # row_height_resize: 행 경계 드래그로 높이 조절,
        # undo/redo: Ctrl+Z / Ctrl+Shift+Z(또는 Ctrl+Y)
        if editable:
            s.enable_bindings("single_select", "drag_select", "row_select", "column_select",
                              "arrowkeys", "copy", "paste", "cut", "delete", "edit_cell",
                              "rc_select", "column_width_resize", "double_click_column_resize",
                              "row_height_resize", "undo", "redo")
        else:
            s.enable_bindings("single_select", "drag_select", "row_select", "column_select",
                              "arrowkeys", "copy", "column_width_resize",
                              "double_click_column_resize", "row_height_resize")
        # 열 너비를 드래그로 바꾸면 줄바꿈에 맞춰 행 높이 재계산(글씨 잘림 방지)
        s.CH.bind("<ButtonRelease-1>", lambda e: self.after(15, lambda: self._refit(s)), add="+")
        return s

    def _refit(self, sheet):
        try:
            ncols = sheet.MT.total_data_cols()
        except Exception:
            data = sheet.get_sheet_data()
            ncols = len(data[0]) if data else 0
        if ncols:
            self._fit_heights(sheet, ncols)
            sheet.redraw()

    def _bind_undo(self, sheet, resync):
        """undo/redo 후 repo 를 시트 내용으로 재동기화."""
        sheet.bind("<<Undo>>", lambda e: resync())
        sheet.bind("<<Redo>>", lambda e: resync())

    def _set_widths(self, sheet, headers):
        # 최초 1회만 기본 너비 적용 -> 사용자가 드래그로 조절한 너비를 보존.
        # (새 파일을 열면 open_file 에서 _sized 를 비워 기본값 재적용)
        if id(sheet) in self._sized:
            return
        for i, h in enumerate(headers):
            w = WIDTHS.get(h, AOI_W if h in self.aoi else 100)
            sheet.column_width(column=i, width=w)
        self._sized.add(id(sheet))

    def _fit_heights(self, sheet, ncols, max_rows=350):
        n = sheet.get_total_rows()
        if n == 0:
            return
        limit = min(n, max_rows)
        heights = []
        for r in range(limit):
            try:
                h = max((sheet.MT.get_wrapped_cell_height(r, c) for c in range(ncols)), default=28)
            except Exception:
                h = 28
            heights.append(max(int(h), 26))
        if n > limit:
            heights += [28] * (n - limit)
        try:
            sheet.set_row_heights(heights)
        except Exception:
            pass

    # ---- 메뉴/헤더/툴바 ----------------------------------------------------

    def _build_menu(self):
        menubar = tk.Menu(self)
        m = tk.Menu(menubar, tearoff=0)
        m.add_command(label="공용 파일 열기 (.xlsx)", command=self._menu_open)
        m.add_command(label="새 공용 파일 만들기", command=self._menu_new)
        m.add_separator()
        m.add_command(label="기존 엑셀(.xlsm) 가져오기", command=self._menu_import)
        m.add_command(label="다른 이름으로 내보내기", command=self._menu_export)
        m.add_separator()
        m.add_command(label="저장  (Ctrl+S)", command=self.save)
        m.add_command(label="새로고침(디스크 다시 읽기)", command=self._menu_reload)
        m.add_separator()
        m.add_command(label="종료", command=self._on_close)
        menubar.add_cascade(label="파일", menu=m)
        h = tk.Menu(menubar, tearoff=0)
        h.add_command(label="호기 IP 보기", command=self._show_aoi_ip)
        h.add_command(label="사용 안내", command=self._show_help)
        menubar.add_cascade(label="도움말", menu=h)
        self.config(menu=menubar)
        self.bind("<Control-s>", lambda e: self.save())

    def _build_header(self):
        bar = ttk.Frame(self, style="Header.TFrame", padding=(18, 12))
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Camtek AOI 장비 파라미터 관리", style="Title.TLabel").pack(side="left")
        # 장비 종류 전환 버튼(PI / RDL)
        self.btn_pi = ttk.Button(bar, text="PI", width=6, command=lambda: self._switch_kind("PI"))
        self.btn_pi.pack(side="left", padx=(20, 0))
        self.btn_rdl = ttk.Button(bar, text="RDL", width=6, command=lambda: self._switch_kind("RDL"))
        self.btn_rdl.pack(side="left", padx=(8, 0))
        right = ttk.Frame(bar, style="Header.TFrame")
        right.pack(side="right")
        self.hdr_file = ttk.Label(right, text="파일 없음", style="HeaderInfo.TLabel")
        self.hdr_file.pack(side="top", anchor="e")
        self.hdr_user = ttk.Label(right, text=f"사용자: {self.user}", style="HeaderInfo.TLabel")
        self.hdr_user.pack(side="top", anchor="e")
        self._update_kind_buttons()

    def _build_toolbar(self):
        tb = ttk.Frame(self, style="Surface.TFrame", padding=(12, 9))
        tb.pack(side="top", fill="x")
        ttk.Button(tb, text="💾  저장", style="Primary.TButton", command=self.save).pack(side="left")
        ttk.Button(tb, text="↻  새로고침", command=self._menu_reload).pack(side="left", padx=(8, 0))
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=12, pady=2)
        ttk.Button(tb, text="＋  행 추가", command=self._add_row).pack(side="left")
        ttk.Button(tb, text="🗑  선택 행 삭제", command=self._delete_row).pack(side="left", padx=(8, 0))
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=12, pady=2)
        btn_hl = ttk.Button(tb, text="🟨  강조", command=lambda: self._fill_cells(None))
        btn_hl.pack(side="left")
        Tooltip(btn_hl, "선택한 셀을 노란색으로 강조 / 해제  (단축키 F4)")
        ttk.Button(tb, text="🎨  채우기 색", command=self._fill_cells_pick).pack(side="left", padx=(8, 0))
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=12, pady=2)
        ttk.Button(tb, text="↧  엑셀 가져오기", command=self._menu_import).pack(side="left")
        ttk.Button(tb, text="↥  내보내기", command=self._menu_export).pack(side="left", padx=(8, 0))
        self.bind("<F4>", lambda e: self._fill_cells(None))

    # ---- 본문(탭) ----------------------------------------------------------

    def _build_body(self):
        wrap = ttk.Frame(self, padding=(10, 6))
        wrap.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(wrap)
        self.nb.pack(fill="both", expand=True)

        # 탭1: 파라미터 항목 수정(메타 + 호기 값 전부 편집)
        f1 = ttk.Frame(self.nb)
        self.sh_edit = self._make_sheet(f1, self.full_cols, frozen=5, editable=True)
        self.sh_edit.pack(fill="both", expand=True)
        self.sh_edit.extra_bindings([("end_edit_cell", self._on_edit_full),
                                     ("end_paste", self._on_edit_full)])
        self._bind_undo(self.sh_edit, self._on_edit_full)
        self.nb.add(f1)

        # 탭2: 호기별 값 수정(셀 안 +/- 토글로 접기/펼치기, 호기 값만 편집)
        f2 = ttk.Frame(self.nb, style="Surface.TFrame")
        vbar = ttk.Frame(f2, style="Surface.TFrame", padding=(10, 8))
        vbar.pack(side="top", fill="x")
        ttk.Button(vbar, text="모두 펼치기", command=lambda: self._val_expand_all(True)).pack(side="left")
        ttk.Button(vbar, text="모두 접기", command=lambda: self._val_expand_all(False)).pack(side="left", padx=(8, 0))
        ttk.Label(vbar, text="  PI/Recipe/Zone/Alg 셀의 ＋／－ 를 클릭해 그 그룹을 접고 펼칩니다 (호기 값만 편집 가능)",
                  style="Muted.TLabel").pack(side="left", padx=8)
        self.sh_val = self._make_sheet(f2, self.val_cols, frozen=5, editable=True)
        self.sh_val.pack(fill="both", expand=True)
        self.sh_val.extra_bindings([("end_edit_cell", self._on_value_edit),
                                    ("end_paste", self._sync_value_all),
                                    ("cell_select", self._on_val_click)])
        self._bind_undo(self.sh_val, self._sync_value_all)
        self.nb.add(f2)

        # 탭3: 호기 비교/누락
        f3 = ttk.Frame(self.nb)
        self.cmp_cols = ["PI", "Recipe", "Zone", "Alg", "Parameter"] + self.aoi + ["누락 호기"]
        self.sh_cmp = self._make_sheet(f3, self.cmp_cols, frozen=5, editable=False)
        self.sh_cmp.pack(fill="both", expand=True)
        self.nb.add(f3)

        # 탭4: 변경 이력
        f4 = ttk.Frame(self.nb, style="Surface.TFrame")
        self._build_history_tab(f4)
        self.nb.add(f4)

        # 탭5: 특이사항(검색 + 종료여부 ☑/☐ 클릭 토글 + 일자 자동변환)
        f5 = ttk.Frame(self.nb, style="Surface.TFrame")
        sbar = ttk.Frame(f5, style="Surface.TFrame", padding=(10, 10))
        sbar.pack(side="top", fill="x")
        ttk.Label(sbar, text="검색", style="Surface.TLabel").pack(side="left")
        self.spec_query = tk.StringVar()
        se = ttk.Entry(sbar, textvariable=self.spec_query, width=30)
        se.pack(side="left", padx=(6, 0))
        se.bind("<KeyRelease>", lambda ev: self._refresh_special())
        ttk.Label(sbar, text="  (일자는 20260616 처럼 입력 → 자동 변환 · 종료 여부는 ☑/☐ 클릭)",
                  style="Muted.TLabel").pack(side="left", padx=8)
        self.sh_spec = self._make_sheet(f5, SPECIAL_HEADERS, frozen=2, editable=True)
        self.sh_spec.pack(fill="both", expand=True)
        self.sh_spec.extra_bindings([("end_edit_cell", self._on_special_edit),
                                     ("end_paste", self._sync_special_all),
                                     ("cell_select", self._on_spec_click)])
        self._bind_undo(self.sh_spec, self._sync_special_all)
        self.nb.add(f5)

        # 탭6: 참고자료(엑셀 '관련 자료' 기반 4개 표, 제목 칸은 사용자가 입력)
        f6 = ttk.Frame(self.nb, style="Surface.TFrame")
        rbar = ttk.Frame(f6, style="Surface.TFrame", padding=(10, 8))
        rbar.pack(side="top", fill="x")
        ttk.Button(rbar, text="＋  표 추가", command=self._ref_add_table).pack(side="left")
        ttk.Label(rbar, text="  표 제목/내용을 셀에서 직접 수정하세요 (제목 행은 파랑 강조)",
                  style="Muted.TLabel").pack(side="left", padx=8)
        self.sh_ref = self._make_sheet(f6, ["", "", "", ""], frozen=0, editable=True)
        self.sh_ref.pack(fill="both", expand=True)
        self.sh_ref.extra_bindings([("end_edit_cell", self._on_ref_edit),
                                    ("end_paste", self._on_ref_edit)])
        self._bind_undo(self.sh_ref, self._on_ref_edit)
        self.nb.add(f6)

        self._apply_tab_names()
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_changed())
        self.nb.bind("<Double-1>", self._on_tab_doubleclick)

    def _build_history_tab(self, parent):
        bar = ttk.Frame(parent, style="Surface.TFrame", padding=(10, 10))
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="검색", style="Surface.TLabel").pack(side="left")
        self.hist_query = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.hist_query, width=28)
        e.pack(side="left", padx=(6, 16))
        e.bind("<KeyRelease>", lambda ev: self._refresh_history())
        ttk.Label(bar, text="PI", style="Surface.TLabel").pack(side="left")
        self.hist_pi = tk.StringVar(value="(전체)")
        self.hist_pi_cb = ttk.Combobox(bar, textvariable=self.hist_pi, width=10, state="readonly")
        self.hist_pi_cb.pack(side="left", padx=(6, 16))
        self.hist_pi_cb.bind("<<ComboboxSelected>>", lambda ev: self._refresh_history())
        ttk.Label(bar, text="호기", style="Surface.TLabel").pack(side="left")
        self.hist_aoi = tk.StringVar(value="(전체)")
        self.hist_aoi_cb = ttk.Combobox(bar, textvariable=self.hist_aoi, width=10,
                                        state="readonly", values=["(전체)"] + self.aoi)
        self.hist_aoi_cb.pack(side="left", padx=6)
        self.hist_aoi_cb.bind("<<ComboboxSelected>>", lambda ev: self._refresh_history())

        self.hist_cols = ["Update Date", "Updated By", "Recipe", "Zone", "Alg",
                          "Parameter", "AOI", "Old Value", "New Value", "Change Type"]
        self.sh_hist = self._make_sheet(parent, self.hist_cols, frozen=6, editable=False)
        self.sh_hist.pack(fill="both", expand=True)

    # ---- 탭 이름(더블클릭 변경) -------------------------------------------

    def _tab_name(self, key: str) -> str:
        custom = (self._cfg.get("tab_names") or {}).get(key)
        return custom or self.tab_default[key]

    def _apply_tab_names(self):
        for i, key in enumerate(self.tab_keys):
            try:
                self.nb.tab(i, text=f"  {self._tab_name(key)}  ")
            except Exception:
                pass

    def _on_tab_doubleclick(self, event):
        try:
            idx = self.nb.index(f"@{event.x},{event.y}")
        except Exception:
            return
        if idx < 0 or idx >= len(self.tab_keys):
            return
        key = self.tab_keys[idx]
        cur = self._tab_name(key)
        top = tk.Toplevel(self)
        top.title("탭 이름 변경")
        top.transient(self)
        top.resizable(False, False)
        ttk.Label(top, text="새 탭 이름:", padding=(12, 10, 12, 4)).pack(anchor="w")
        var = tk.StringVar(value=cur)
        ent = ttk.Entry(top, textvariable=var, width=30)
        ent.pack(padx=12, fill="x")
        ent.focus_set()
        ent.select_range(0, "end")

        def commit(_=None):
            name = var.get().strip() or self.tab_default[key]
            names = dict(self._cfg.get("tab_names") or {})
            if name == self.tab_default[key]:
                names.pop(key, None)
            else:
                names[key] = name
            self._cfg["tab_names"] = names
            save_config(self._cfg)
            self._apply_tab_names()
            top.destroy()

        btns = ttk.Frame(top, padding=(12, 10))
        btns.pack(fill="x")
        ttk.Button(btns, text="확인", style="Primary.TButton", command=commit).pack(side="right")
        ttk.Button(btns, text="취소", command=top.destroy).pack(side="right", padx=(0, 6))
        ent.bind("<Return>", commit)
        ent.bind("<Escape>", lambda e: top.destroy())
        top.update_idletasks()
        top.geometry(f"+{self.winfo_rootx() + event.x}+{self.winfo_rooty() + event.y + 20}")
        return "break"

    def _build_statusbar(self):
        self.status = tk.StringVar()
        bar = ttk.Frame(self, style="Surface.TFrame", padding=(12, 6))
        bar.pack(side="bottom", fill="x")
        ttk.Label(bar, textvariable=self.status, style="Surface.TLabel",
                  font=self.p["fonts"]["sub"]).pack(side="left")
        self.lock_lbl = ttk.Label(bar, text="", style="Surface.TLabel", font=self.p["fonts"]["sub"])
        self.lock_lbl.pack(side="right")

    # ---- 파일 작업 --------------------------------------------------------

    def _menu_open(self):
        p = filedialog.askopenfilename(title="공용 파일 열기",
                                       filetypes=[("Excel", "*.xlsx"), ("모든 파일", "*.*")])
        if p:
            self.open_file(p)

    def _menu_new(self):
        p = filedialog.asksaveasfilename(title="새 공용 파일 만들기", defaultextension=".xlsx",
                                         filetypes=[("Excel", "*.xlsx")])
        if not p:
            return
        engine.create_empty_workbook(p)
        self.open_file(p)

    def _menu_import(self):
        src = filedialog.askopenfilename(title="기존 엑셀(.xlsm) 선택",
                                         filetypes=[("Excel 매크로", "*.xlsm"), ("Excel", "*.xlsx"),
                                                    ("모든 파일", "*.*")])
        if not src:
            return
        dest = filedialog.asksaveasfilename(title="가져온 데이터를 저장할 공용 파일(.xlsx)",
                                            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not dest:
            return
        try:
            engine.import_from_xlsm(src, dest)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("가져오기 실패", str(e))
            return
        messagebox.showinfo("가져오기 완료", f"기존 엑셀 데이터를 다음 파일로 변환했습니다:\n{dest}")
        self.open_file(dest)

    def _menu_export(self):
        if not self.path:
            return
        dest = filedialog.asksaveasfilename(title="다른 이름으로 내보내기", defaultextension=".xlsx",
                                            filetypes=[("Excel", "*.xlsx")])
        if dest:
            engine.export_copy(self.path, dest)
            messagebox.showinfo("내보내기 완료", f"내보냈습니다:\n{dest}")

    # ---- 장비 종류(PI / RDL) 전환 ----------------------------------------

    def _kind_of(self, repo) -> str | None:
        sn = getattr(repo, "sheet_name", "") if repo else ""
        if sn == "RDL_ALL":
            return "RDL"
        if sn == "PI_ALL":
            return "PI"
        return None

    def _update_kind_buttons(self):
        for kind, btn in (("PI", self.btn_pi), ("RDL", self.btn_rdl)):
            active = (self.active_kind == kind)
            btn.configure(style="Primary.TButton" if active else "Ghost.TButton")

    def _switch_kind(self, kind: str):
        if self.dirty and not messagebox.askyesno(
                "전환", "저장하지 않은 변경이 있습니다. 버리고 전환할까요?"):
            return
        path = self._cfg.get(f"{kind.lower()}_path")
        if path and os.path.exists(path):
            self.open_file(path, kind=kind)
        else:
            self._setup_kind(kind)

    def _setup_kind(self, kind: str):
        """해당 장비 파일이 아직 지정되지 않았을 때: 파일 선택/가져오기 후 기억."""
        if not messagebox.askyesno(
                f"{kind} 파일 지정",
                f"{kind} 장비 파라미터 파일이 아직 지정되지 않았습니다.\n\n"
                f"지금 지정하시겠습니까?\n"
                f"(공용 .xlsx 를 선택하거나, 기존 엑셀 .xlsm 을 가져옵니다)"):
            return
        src = filedialog.askopenfilename(
            title=f"{kind} 파일 선택 (.xlsx 공용 파일 또는 .xlsm)",
            filetypes=[("Excel", "*.xlsx *.xlsm"), ("모든 파일", "*.*")])
        if not src:
            return
        if src.lower().endswith(".xlsm"):
            dest = filedialog.asksaveasfilename(
                title=f"{kind} 공용 파일로 저장할 .xlsx 경로",
                defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
            if not dest:
                return
            try:
                engine.import_from_xlsm(src, dest)
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("가져오기 실패", str(e))
                return
            src = dest
        self.open_file(src, kind=kind)

    def open_file(self, path: str, kind: str | None = None):
        if self.path and not self.read_only:
            engine.release_lock(self.path, self.user)
        self.read_only = False
        lock = engine.read_lock(path)
        if lock and not lock.is_stale() and lock.user != self.user:
            self.read_only = messagebox.askyesno(
                "편집 잠금",
                f"현재 '{lock.user}' 님이 편집 중입니다 (시작 {lock.time}).\n\n"
                "읽기 전용으로 열까요?\n(아니오 = 잠금을 무시하고 편집 — 충돌 위험)")
        repo = ParamRepository(path)
        try:
            repo.load()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("열기 실패", str(e))
            return
        self.repo = repo
        self.path = path
        self.dirty = False
        self._sized.clear()   # 새 파일 -> 기본 열너비 재적용
        self._reconfigure_columns()   # 파일의 호기 목록/시트명에 맞춰 열 재구성
        if not self.read_only:
            engine.write_lock(path, self.user)
        # 장비 종류 결정/기억 (버튼으로 연 경우 우선, 아니면 시트명으로 추정)
        self.active_kind = kind or self._kind_of(repo)
        if self.active_kind:
            self._cfg[f"{self.active_kind.lower()}_path"] = path
        self._update_kind_buttons()
        self._cfg["last_path"] = path
        save_config(self._cfg)
        self._check_conflicts()
        self._refresh_all()
        self._update_title()

    def _reconfigure_columns(self):
        """로드한 파일의 호기 목록(repo.aoi_units)에 맞춰 열/헤더를 다시 구성."""
        self.aoi = list(self.repo.aoi_units) if (self.repo and self.repo.aoi_units) else list(AOI_UNITS)
        self.full_cols = META_FIELDS + self.aoi
        self.val_cols = list(self.full_cols)
        self.cmp_cols = ["PI", "Recipe", "Zone", "Alg", "Parameter"] + self.aoi + ["누락 호기"]
        try:
            self.sh_edit.headers(self.full_cols)
            self.sh_val.headers(self.val_cols)
            self.sh_cmp.headers(self.cmp_cols)
            self.hist_aoi_cb["values"] = ["(전체)"] + self.aoi
        except Exception:
            pass
        self._sized.clear()

    def _menu_reload(self):
        if not self.path:
            return
        if self.dirty and not messagebox.askyesno("새로고침", "저장하지 않은 변경이 있습니다. 버리고 다시 읽을까요?"):
            return
        self.open_file(self.path)

    def save(self):
        if not self.repo or not self.path:
            messagebox.showinfo("저장", "먼저 파일을 여세요.")
            return
        if self.read_only:
            messagebox.showwarning("읽기 전용", "읽기 전용으로 열려 있어 저장할 수 없습니다.")
            return
        self._check_conflicts()
        self._set_status("저장 중…")
        self.update_idletasks()
        try:
            engine.write_lock(self.path, self.user)
            stats = self.repo.save(user=self.user)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("저장 실패", str(e))
            return
        self.dirty = False
        self._refresh_all()
        self._update_title()
        self._set_status(
            f"✓ 저장 완료 — 변경 {stats['changes']}건 · 추가 {stats['added']}건 · 삭제 {stats['deleted']}건")

    def _check_conflicts(self):
        if not self.path:
            return
        conflicts = engine.find_conflict_copies(self.path)
        if conflicts:
            names = "\n".join(os.path.basename(c) for c in conflicts)
            messagebox.showwarning(
                "충돌본 감지",
                "OneDrive 동기화 충돌본으로 의심되는 파일이 있습니다:\n\n" + names +
                "\n\n동시 저장으로 생겼을 수 있습니다. 내용을 확인하고 정리하세요.")

    # ---- 새로고침 ----------------------------------------------------------

    def _refresh_all(self):
        self._refresh_edit()
        self._refresh_values()
        self._refresh_compare()
        self._refresh_history_filters()
        self._refresh_history()
        self._refresh_special()
        self._refresh_reference()

    def _refresh_edit(self):
        if not self.repo:
            return
        self.edit_ids = [pr.row_id for pr in self.repo.rows]
        data = [[engine._s(pr.get(f)) for f in self.full_cols] for pr in self.repo.rows]
        self.sh_edit.set_sheet_data(data, reset_col_positions=False, redraw=False)
        self._set_widths(self.sh_edit, self.full_cols)
        self._fit_heights(self.sh_edit, len(self.full_cols))
        self._apply_cell_colors(self.sh_edit, "edit")
        self.sh_edit.redraw()

    @staticmethod
    def _grp_keys(pr):
        pi = engine._s(pr.get("PI")) or "(빈 PI)"
        rc = engine._s(pr.get("Recipe")); zn = engine._s(pr.get("Zone")); al = engine._s(pr.get("Alg"))
        return [f"PI::{pi}", f"R::{pi}|{rc}", f"Z::{pi}|{rc}|{zn}", f"A::{pi}|{rc}|{zn}|{al}"], (pi, rc, zn, al)

    def _refresh_values(self):
        """편집과 동일한 열 구성. 별도 헤더 행 없이 PI/Recipe/Zone/Alg 셀 안에
        ＋／－ 토글을 넣어 그 그룹을 접고/펼친다. 호기 값만 편집 가능."""
        if not self.repo:
            return
        rows = sorted(self.repo.rows, key=lambda p: (engine.pi_order(p.get("PI")), p.display_order or 0))
        n = len(rows)
        ncol = len(self.val_cols)
        gcols = ["PI", "Recipe", "Zone", "Alg"]   # 토글이 들어가는 그룹 열
        data: list[list] = []
        self.val_display = []
        self.val_toggles = {}
        prev = None   # 직전에 '표시된' 행의 (pi,rc,zn,al)
        i = 0
        while i < n:
            pr = rows[i]
            keys, vals = self._grp_keys(pr)
            # 접힌 최상위 조상 레벨 찾기
            coll = next((L for L in range(4) if keys[L] in self.collapsed), None)
            if coll is not None:
                # 그룹 요약 행 1개만 표시하고 같은 그룹의 나머지 행은 건너뜀
                row = [""] * ncol
                for L in range(4):
                    col = self.full_cols.index(gcols[L])
                    same = prev is not None and prev[:L + 1] == vals[:L + 1]
                    if L < coll:
                        if not same:
                            row[col] = "－ " + (vals[L] or "")
                            self.val_toggles[(len(data), col)] = keys[L]
                    elif L == coll:
                        row[col] = "＋ " + (vals[L] or "")
                        self.val_toggles[(len(data), col)] = keys[L]
                self.val_display.append({"kind": "summary"})
                data.append(row)
                prefix = tuple(keys[:coll + 1])
                while i < n and tuple(self._grp_keys(rows[i])[0][:coll + 1]) == prefix:
                    i += 1
                prev = vals
                continue
            # 펼쳐진 leaf 행: 전체 값 표시 + 그룹 시작 셀에 '－' 토글
            row = [""] * ncol
            for fi, f in enumerate(self.full_cols):
                row[fi] = engine._s(pr.get(f))
            for L in range(4):
                col = self.full_cols.index(gcols[L])
                same = prev is not None and prev[:L + 1] == vals[:L + 1]
                if same:
                    row[col] = ""        # 반복 그룹 값은 비워 가독성↑(엑셀 병합 느낌)
                else:
                    row[col] = "－ " + (vals[L] or "")
                    self.val_toggles[(len(data), col)] = keys[L]
            self.val_display.append({"kind": "leaf", "rowid": pr.row_id})
            data.append(row)
            prev = vals
            i += 1

        self.sh_val.set_sheet_data(data, reset_col_positions=False, redraw=False)
        self._set_widths(self.sh_val, self.val_cols)
        try:
            ro_cols = [i for i, h in enumerate(self.val_cols) if h not in set(self.aoi)]
            self.sh_val.readonly_columns(columns=ro_cols, readonly=True)
        except Exception:
            pass
        # 토글 셀 강조(연한 파랑)
        try:
            self.sh_val.dehighlight_all()
            for (r, c) in self.val_toggles:
                self.sh_val.highlight_cells(row=r, column=c, bg="#e3edfb", fg="#1d4ed8")
        except Exception:
            pass
        self._apply_cell_colors(self.sh_val, "value")
        self._fit_heights(self.sh_val, len(self.val_cols))
        self.sh_val.redraw()

    def _on_val_click(self, event=None):
        """PI/Recipe/Zone/Alg 셀의 ＋／－ 클릭 시 해당 그룹 접기/펼치기."""
        if not self.repo:
            return
        sel = self.sh_val.get_currently_selected()
        if not sel:
            return
        key = self.val_toggles.get((sel.row, sel.column))
        if not key:
            return
        if key in self.collapsed:
            self.collapsed.discard(key)
        else:
            self.collapsed.add(key)
        self._refresh_values()

    def _val_expand_all(self, expand: bool):
        if not self.repo:
            return
        if expand:
            self.collapsed.clear()
        else:
            keys = set()
            for pr in self.repo.rows:
                keys.update(self._grp_keys(pr)[0])
            self.collapsed = keys
        self._refresh_values()

    def _refresh_compare(self):
        if not self.repo:
            return
        data = []
        tags = []  # (row_index, color)
        for i, v in enumerate(self.repo.comparison_view()):
            base = [v["PI"], v["Recipe"], v["Zone"], v["Alg"], v["Parameter"]]
            aoi = [engine._s(v["values"].get(u)) for u in self.aoi]
            data.append([engine._s(x) for x in base] + aoi + [", ".join(v["missing"])])
            if v["value_diff"]:
                tags.append((i, self.p["diff"]))
            elif v["missing"]:
                tags.append((i, self.p["missing"]))
            elif v["common"]:
                tags.append((i, self.p["common"]))
        self.sh_cmp.set_sheet_data(data, reset_col_positions=False, redraw=False)
        self._set_widths(self.sh_cmp, self.cmp_cols)
        try:
            self.sh_cmp.dehighlight_all()
            for r, color in tags:
                self.sh_cmp.highlight_rows(rows=[r], bg=color, fg="#1f2937", redraw=False)
        except Exception:
            pass
        self._fit_heights(self.sh_cmp, len(self.cmp_cols))
        self.sh_cmp.redraw()

    def _refresh_history_filters(self):
        if not self.repo:
            return
        pis = sorted({engine._s(p.get("PI")) for p in self.repo.rows if p.get("PI")})
        self.hist_pi_cb["values"] = ["(전체)"] + pis

    def _refresh_history(self):
        if not self.repo:
            return
        q = self.hist_query.get().strip().lower()
        aoi_f = self.hist_aoi.get()
        pi_f = self.hist_pi.get()
        pi_params = None
        if pi_f and pi_f != "(전체)":
            pi_params = {engine._s(p.get("Parameter")) for p in self.repo.rows
                         if engine._s(p.get("PI")) == pi_f}
        data = []
        for rec in reversed(self.repo.history):
            if aoi_f and aoi_f != "(전체)" and engine._s(rec.get("AOI")) != aoi_f:
                continue
            if pi_params is not None and engine._s(rec.get("Parameter")) not in pi_params:
                continue
            if q:
                blob = " ".join(engine._s(rec.get(h)) for h in LOG_HEADERS).lower()
                if q not in blob:
                    continue
            data.append([engine._s(rec.get(c)) for c in self.hist_cols])
            if len(data) >= 2000:
                break
        self.sh_hist.set_sheet_data(data, reset_col_positions=False, redraw=False)
        self._set_widths(self.sh_hist, self.hist_cols)
        self._fit_heights(self.sh_hist, len(self.hist_cols), max_rows=200)
        self.sh_hist.redraw()
        self._set_status(f"이력 {len(data)}건 표시")

    def _refresh_special(self):
        if not self.repo:
            return
        q = self.spec_query.get().strip().lower() if hasattr(self, "spec_query") else ""
        dcol = SPECIAL_HEADERS.index("일자")
        bcol = SPECIAL_HEADERS.index(SPECIAL_BOOL_COL)
        data = []
        self.spec_shown_idx = []   # 표시행 -> repo.special 원본 인덱스
        err_rows = []
        for orig, rec in enumerate(self.repo.special):
            row = []
            is_err = False
            for h in SPECIAL_HEADERS:
                v = rec.get(h)
                if h == SPECIAL_BOOL_COL:
                    v = "☑" if bool(v) else "☐"   # 클릭 토글되는 체크 기호
                elif h == "일자":
                    disp, ok = engine.format_kdate(v)
                    v = disp
                    is_err = not ok
                else:
                    v = engine._s(v)
                row.append(v)
            if q:
                blob = " ".join(str(x) for x in row).lower()
                if q not in blob:
                    continue
            self.spec_shown_idx.append(orig)
            if is_err:
                err_rows.append(len(data))
            data.append(row)
        self.sh_spec.set_sheet_data(data, reset_col_positions=False, redraw=False)
        self._set_widths(self.sh_spec, SPECIAL_HEADERS)
        try:
            self.sh_spec.readonly_columns(columns=[bcol], readonly=True)  # 기호 클릭만 허용
            self.sh_spec.align(rows="all", columns=[bcol], align="center", redraw=False)
        except Exception:
            pass
        try:
            self.sh_spec.dehighlight_all()
            for r in err_rows:        # 일자 오류 셀 강조
                self.sh_spec.highlight_cells(row=r, column=dcol, bg=self.p["diff"], fg="#b91c1c")
        except Exception:
            pass
        self._apply_cell_colors(self.sh_spec, "special")
        self._fit_heights(self.sh_spec, len(SPECIAL_HEADERS))
        self.sh_spec.redraw()
        self._set_status(f"특이사항 {len(data)}건 표시")

    def _on_spec_click(self, event=None):
        """종료 여부 열(☑/☐) 클릭 시 토글."""
        if not self.repo:
            return
        sel = self.sh_spec.get_currently_selected()
        if not sel:
            return
        bcol = SPECIAL_HEADERS.index(SPECIAL_BOOL_COL)
        if sel.column != bcol:
            return
        if sel.row >= len(self.spec_shown_idx):
            return
        orig = self.spec_shown_idx[sel.row]
        if 0 <= orig < len(self.repo.special):
            cur = bool(self.repo.special[orig].get(SPECIAL_BOOL_COL))
            self.repo.special[orig][SPECIAL_BOOL_COL] = not cur
            self.sh_spec.set_cell_data(sel.row, bcol, "☑" if not cur else "☐")
            self.sh_spec.redraw()
            self._mark_dirty()

    # ---- 참고자료 ----------------------------------------------------------

    def _refresh_reference(self):
        if not self.repo:
            return
        grid = [list(r) + [""] * (engine.REF_COLS - len(r)) for r in self.repo.reference]
        if not grid:
            grid = [["", "", "", ""]]
        self.sh_ref.set_sheet_data(grid, reset_col_positions=False, redraw=False)
        for i, w in enumerate((300, 220, 160, 160)):
            self.sh_ref.column_width(column=i, width=w)
        # 제목 행 강조: '표 제목' 또는 '표N 제목' 포함 셀
        try:
            self.sh_ref.dehighlight_all()
            for r, row in enumerate(grid):
                first = engine._s(row[0])
                if "제목" in first or (first and all(engine._s(c) == "" for c in row[1:]) and first not in ("항목",)):
                    self.sh_ref.highlight_rows(rows=[r], bg="#dbe7fb", fg="#1d4ed8", redraw=False)
        except Exception:
            pass
        self._apply_cell_colors(self.sh_ref, "reference")
        self._fit_heights(self.sh_ref, engine.REF_COLS, max_rows=400)
        self.sh_ref.redraw()

    def _on_ref_edit(self, event=None):
        if not self.repo:
            return
        self.repo.reference = [[engine._s(c) for c in row]
                               for row in self.sh_ref.get_sheet_data()]
        self._mark_dirty()

    def _ref_add_table(self):
        if not self.repo:
            return
        self.repo.reference = list(self.repo.reference) + [
            ["", "", "", ""],
            ["표 제목(여기에 입력)", "", "", ""],
            ["항목", "값", "", ""],
            ["", "", "", ""],
        ]
        self._refresh_reference()
        self._mark_dirty()

    # ---- 편집 콜백 ---------------------------------------------------------

    def _on_edit_full(self, event=None):
        """파라미터 편집 탭: 메타 + 호기 값 전부 repo 에 반영."""
        if not self.repo:
            return
        data = self.sh_edit.get_sheet_data()
        for i, row in enumerate(data):
            if i >= len(self.edit_ids):
                break
            pr = self._row_by_id(self.edit_ids[i])
            if pr is None:
                continue
            for j, field in enumerate(self.full_cols):
                pr.set(field, (row[j] if j < len(row) else "") or None)
        self._mark_dirty()

    def _on_value_edit(self, event=None):
        """파라미터 값 수정 탭: leaf(파라미터) 행의 호기 값만 반영."""
        if not self.repo:
            return
        sel = self.sh_val.get_currently_selected()
        if not sel:
            return
        row, col = sel.row, sel.column
        if col >= len(self.val_cols):
            return
        field = self.val_cols[col]
        if field not in set(self.aoi):   # 메타 열은 편집 불가
            return
        if row >= len(self.val_display) or self.val_display[row]["kind"] != "leaf":
            return               # 그룹 헤더 행은 무시
        pr = self._row_by_id(self.val_display[row]["rowid"])
        if pr is None:
            return
        val = self.sh_val.get_cell_data(row, col)
        pr.set(field, (val if val not in (None, "") else None))
        self._mark_dirty()

    def _sync_value_all(self, event=None):
        """undo/redo·붙여넣기 후: 보이는 leaf 행의 호기 값을 모두 repo 에 재반영."""
        if not self.repo:
            return
        data = self.sh_val.get_sheet_data()
        aoi_idx = {self.val_cols.index(u): u for u in self.aoi}
        for r, info in enumerate(self.val_display):
            if info.get("kind") != "leaf" or r >= len(data):
                continue
            pr = self._row_by_id(info.get("rowid"))
            if pr is None:
                continue
            for ci, u in aoi_idx.items():
                v = data[r][ci] if ci < len(data[r]) else ""
                pr.set(u, v if v not in (None, "") else None)
        self._mark_dirty()

    def _sync_special_all(self, event=None):
        """undo/redo·붙여넣기 후: 보이는 특이사항 행을 repo 에 재반영(종료여부 제외)."""
        if not self.repo:
            return
        data = self.sh_spec.get_sheet_data()
        bcol = SPECIAL_HEADERS.index(SPECIAL_BOOL_COL)
        for r, orig in enumerate(self.spec_shown_idx):
            if r >= len(data) or not (0 <= orig < len(self.repo.special)):
                continue
            rec = self.repo.special[orig]
            for j, h in enumerate(SPECIAL_HEADERS):
                if j == bcol:
                    continue
                rec[h] = data[r][j] if j < len(data[r]) else ""
        self._mark_dirty()

    def _on_special_edit(self, event=None):
        """편집된 셀만 원본 인덱스에 반영(종료여부 기호/재포맷된 일자 덮어쓰기 방지)."""
        if not self.repo:
            return
        sel = self.sh_spec.get_currently_selected()
        if not sel:
            return
        bcol = SPECIAL_HEADERS.index(SPECIAL_BOOL_COL)
        if sel.column == bcol:    # 종료여부는 클릭 핸들러가 처리
            return
        if sel.row >= len(self.spec_shown_idx) or sel.column >= len(SPECIAL_HEADERS):
            return
        orig = self.spec_shown_idx[sel.row]
        if not (0 <= orig < len(self.repo.special)):
            return
        field = SPECIAL_HEADERS[sel.column]
        self.repo.special[orig][field] = self.sh_spec.get_cell_data(sel.row, sel.column)
        self._mark_dirty()
        if field == "일자":       # 입력 즉시 자동 변환/오류 표시
            self._refresh_special()

    def _row_by_id(self, rid):
        return next((p for p in self.repo.rows if p.row_id == rid), None) if self.repo else None

    def _mark_dirty(self):
        if not self.dirty:
            self.dirty = True
            self._update_title()

    # ---- 행 추가/삭제(현재 탭 기준) ---------------------------------------

    def _current_tab(self):
        try:
            return self.nb.index(self.nb.select())
        except Exception:
            return 0

    def _add_row(self):
        if not self.repo or self.read_only:
            return
        tab = self._current_tab()
        if tab == 5:  # 참고자료: 빈 행 추가
            self.repo.reference = list(self.repo.reference) + [["", "", "", ""]]
            self._refresh_reference()
        elif tab == 4:  # 특이사항
            self.repo.special.append({h: (False if h == SPECIAL_BOOL_COL else "") for h in SPECIAL_HEADERS})
            self._refresh_special()
            self.nb.select(4)
        else:  # 파라미터 정의
            pr = self.repo.add_row()
            self._refresh_edit()
            self.nb.select(0)
            try:
                self.sh_edit.see(row=len(self.repo.rows) - 1, column=0)
            except Exception:
                pass
            self.edit_ids = [p.row_id for p in self.repo.rows]
            _ = pr
        self._mark_dirty()

    def _delete_row(self):
        if not self.repo or self.read_only:
            return
        tab = self._current_tab()
        if tab == 5:  # 참고자료
            sel = sorted({c[0] for c in self.sh_ref.get_selected_cells()} |
                         set(self.sh_ref.get_selected_rows()), reverse=True)
            if not sel:
                messagebox.showinfo("행 삭제", "삭제할 참고자료 행을 선택하세요.")
                return
            ref = list(self.repo.reference)
            for r in sel:
                if 0 <= r < len(ref):
                    del ref[r]
            self.repo.reference = ref
            self._refresh_reference()
            self._mark_dirty()
            return
        if tab == 4:
            sel = sorted({c[0] for c in self.sh_spec.get_selected_cells()} |
                         set(self.sh_spec.get_selected_rows()), reverse=True)
            if not sel:
                messagebox.showinfo("행 삭제", "삭제할 특이사항 행을 선택하세요.")
                return
            if not messagebox.askyesno("행 삭제", f"선택한 {len(sel)}개 특이사항 행을 삭제할까요?"):
                return
            shown = getattr(self, "spec_shown_idx", list(range(len(self.repo.special))))
            orig = sorted({shown[r] for r in sel if 0 <= r < len(shown)}, reverse=True)
            for o in orig:
                if 0 <= o < len(self.repo.special):
                    del self.repo.special[o]
            self._refresh_special()
        else:
            rows = set(self.sh_edit.get_selected_rows()) | {c[0] for c in self.sh_edit.get_selected_cells()}
            if not rows:
                messagebox.showinfo("행 삭제", "삭제할 파라미터 행을 선택하세요.")
                return
            if not messagebox.askyesno("행 삭제", f"선택한 {len(rows)}개 파라미터 행을 삭제할까요? (저장 시 반영)"):
                return
            for r in rows:
                if 0 <= r < len(self.edit_ids):
                    self.repo.remove_row(self.edit_ids[r])
            self._refresh_edit()
        self._mark_dirty()

    # ---- 셀 강조 / 채우기 색 ----------------------------------------------

    @staticmethod
    def _fg_for(bg: str) -> str:
        """배경색 밝기에 따라 글자색(검정/흰색) 자동 선택."""
        try:
            r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
            return "#1f2937" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"
        except Exception:
            return "#1f2937"

    def _color_target(self):
        """현재 탭의 (시트, 종류). 색칠 가능한 탭만 반환."""
        tab = self._current_tab()
        return {0: (self.sh_edit, "edit"), 1: (self.sh_val, "value"),
                4: (self.sh_spec, "special"), 5: (self.sh_ref, "reference")}.get(tab)

    def _cell_key(self, kind, r, c):
        if kind in ("edit", "value"):
            cols = self.full_cols if kind == "edit" else self.val_cols
            if c >= len(cols):
                return None
            if kind == "edit":
                if r >= len(self.edit_ids):
                    return None
                rid = self.edit_ids[r]
            else:
                if r >= len(self.val_display) or self.val_display[r].get("kind") != "leaf":
                    return None
                rid = self.val_display[r]["rowid"]
            return f"P|{rid}|{cols[c]}"
        if kind == "special":
            if r >= len(self.spec_shown_idx):
                return None
            return f"S|{self.spec_shown_idx[r]}|{c}"
        if kind == "reference":
            return f"R|{r}|{c}"
        return None

    def _selected_cells(self, sheet):
        cells = set(sheet.get_selected_cells())
        if not cells:
            sel = sheet.get_currently_selected()
            if sel:
                cells = {(sel.row, sel.column)}
        return cells

    def _fill_cells(self, color):
        """color=None 이면 노란색 토글(이미 노랑이면 해제), 아니면 해당 색으로 채움."""
        if not self.repo or self.read_only:
            return
        target = self._color_target()
        if not target:
            self._set_status("이 탭에서는 셀 색을 칠할 수 없습니다. (항목/값/특이사항/참고자료 탭에서 가능)")
            return
        sheet, kind = target
        cells = self._selected_cells(sheet)
        if not cells:
            return
        cc = self.repo.cell_colors
        keys = [k for (r, c) in cells if (k := self._cell_key(kind, r, c))]
        if not keys:
            return
        if color is None:  # 노란색 토글
            all_yellow = all(cc.get(k) == HIGHLIGHT_YELLOW for k in keys)
            for k in keys:
                if all_yellow:
                    cc.pop(k, None)
                else:
                    cc[k] = HIGHLIGHT_YELLOW
        else:
            for k in keys:
                cc[k] = color
        self._mark_dirty()
        self._refresh_color_tab(kind)

    def _fill_cells_pick(self):
        if not self.repo or self.read_only:
            return
        if not self._color_target():
            self._set_status("이 탭에서는 셀 색을 칠할 수 없습니다.")
            return
        rgb, hexv = colorchooser.askcolor(color=HIGHLIGHT_YELLOW, title="채우기 색 선택")
        if hexv:
            self._fill_cells(hexv.upper())

    def _refresh_color_tab(self, kind):
        {"edit": self._refresh_edit, "value": self._refresh_values,
         "special": self._refresh_special, "reference": self._refresh_reference}[kind]()

    def _apply_cell_colors(self, sheet, kind):
        """저장된 셀 색을 해당 탭에 다시 적용(refresh 끝에서 호출)."""
        if not self.repo or not self.repo.cell_colors:
            return
        cc = self.repo.cell_colors
        try:
            if kind in ("edit", "value"):
                cols = self.full_cols if kind == "edit" else self.val_cols
                col_idx = {h: i for i, h in enumerate(cols)}
                if kind == "edit":
                    row_idx = {rid: i for i, rid in enumerate(self.edit_ids)}
                else:
                    row_idx = {d["rowid"]: i for i, d in enumerate(self.val_display)
                               if d.get("kind") == "leaf"}
                for key, color in cc.items():
                    if not key.startswith("P|"):
                        continue
                    _, rid, field = key.split("|", 2)
                    r = row_idx.get(rid); c = col_idx.get(field)
                    if r is not None and c is not None:
                        sheet.highlight_cells(row=r, column=c, bg=color,
                                              fg=self._fg_for(color), redraw=False)
            elif kind == "special":
                pos = {orig: i for i, orig in enumerate(self.spec_shown_idx)}
                for key, color in cc.items():
                    if not key.startswith("S|"):
                        continue
                    _, o, c = key.split("|")
                    r = pos.get(int(o))
                    if r is not None:
                        sheet.highlight_cells(row=r, column=int(c), bg=color,
                                              fg=self._fg_for(color), redraw=False)
            elif kind == "reference":
                for key, color in cc.items():
                    if not key.startswith("R|"):
                        continue
                    _, r, c = key.split("|")
                    sheet.highlight_cells(row=int(r), column=int(c), bg=color,
                                          fg=self._fg_for(color), redraw=False)
        except Exception:
            pass

    # ---- 탭/기타 ----------------------------------------------------------

    def _on_tab_changed(self):
        idx = self._current_tab()
        if idx == 1:
            self._refresh_values()
        elif idx == 2:
            self._refresh_compare()
        elif idx == 3:
            self._refresh_history()
        elif idx == 5:
            self._refresh_reference()

    def _show_aoi_ip(self):
        if not self.repo or not self.repo.aoi_ip:
            messagebox.showinfo("호기 IP", "호기 IP 정보가 없습니다.")
            return
        lines = [f"{k}\t{v}" for k, v in sorted(self.repo.aoi_ip.items())]
        messagebox.showinfo("호기 IP 매핑", "\n".join(lines))

    def _show_help(self):
        messagebox.showinfo(
            "사용 안내",
            "· 파라미터 편집 : PI/Recipe/Zone/Alg/Parameter 등 '정의'를 추가·수정\n"
            "· 파라미터 값 수정 : PI▸…▸파라미터 트리에서 호기별 값을 편집(펼치기/접기)\n"
            "· 호기 비교/누락 : 호기 간 값 차이·누락을 한눈에\n"
            "· 변경 이력 : 값 변경 자동 기록 검색\n"
            "· 특이사항 : 라트별 메모, 종료여부 체크박스\n\n"
            "값을 고친 뒤 [저장]을 누르면 이력에 기록되고 디스크와 행 단위 병합됩니다.\n"
            "모든 표는 Parameter 열까지 고정되어 횡스크롤해도 보입니다.\n"
            "※ 실행 중 네트워크 접속 없음. OneDrive 폴더의 파일만 사용.")

    def _heartbeat(self):
        if self.path and not self.read_only:
            engine.write_lock(self.path, self.user)
        self.after(HEARTBEAT_MS, self._heartbeat)

    def _update_title(self):
        name = os.path.basename(self.path) if self.path else "(파일 없음)"
        mark = " ●" if self.dirty else ""
        ro = "  [읽기전용]" if self.read_only else ""
        self.title(f"Camtek AOI 장비 파라미터 관리 — {name}{mark}{ro}")
        self.hdr_file.configure(text=f"{name}{mark}{ro}")
        self.hdr_user.configure(text=f"사용자: {self.user}")
        if self.repo:
            self.lock_lbl.configure(
                text=("읽기 전용" if self.read_only else "편집 중 · 잠금 보유") +
                     f"   |   파라미터 {len(self.repo.rows)}행")

    def _set_status(self, text):
        self.status.set(text)

    def _on_close(self):
        if self.dirty and not messagebox.askyesno("종료", "저장하지 않은 변경이 있습니다. 그래도 종료할까요?"):
            return
        if self.path and not self.read_only:
            engine.release_lock(self.path, self.user)
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
