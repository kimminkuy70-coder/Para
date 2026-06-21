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
from tkinter import filedialog, messagebox, ttk

from tksheet import Sheet

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
        self.title("PI_ALL 장비 파라미터 관리")
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
        self._cfg = load_config()
        self.edit_ids: list[str] = []      # tab1 표시행 -> row_id
        # 파라미터 편집/값 수정 공통 열 구성(메타 + 호기 값)
        self.full_cols = META_FIELDS + AOI_UNITS

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
        s.set_options(table_wrap="w", header_wrap="w", table_grid_fg="#cfd6df",
                      show_vertical_grid=True, show_horizontal_grid=True)
        if editable:
            s.enable_bindings("single_select", "drag_select", "row_select", "column_select",
                              "arrowkeys", "copy", "paste", "cut", "delete", "edit_cell",
                              "rc_select", "double_click_column_resize")
        else:
            s.enable_bindings("single_select", "drag_select", "row_select", "column_select",
                              "arrowkeys", "copy", "double_click_column_resize")
        return s

    def _set_widths(self, sheet, headers):
        for i, h in enumerate(headers):
            w = WIDTHS.get(h, AOI_W if h in AOI_UNITS else 100)
            sheet.column_width(column=i, width=w)

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
        ttk.Label(bar, text="PI_ALL 장비 파라미터 관리", style="Title.TLabel").pack(side="left")
        right = ttk.Frame(bar, style="Header.TFrame")
        right.pack(side="right")
        self.hdr_file = ttk.Label(right, text="파일 없음", style="HeaderInfo.TLabel")
        self.hdr_file.pack(side="top", anchor="e")
        self.hdr_user = ttk.Label(right, text=f"사용자: {self.user}", style="HeaderInfo.TLabel")
        self.hdr_user.pack(side="top", anchor="e")

    def _build_toolbar(self):
        tb = ttk.Frame(self, style="Surface.TFrame", padding=(12, 9))
        tb.pack(side="top", fill="x")
        ttk.Button(tb, text="💾  저장", style="Primary.TButton", command=self.save).pack(side="left")
        ttk.Button(tb, text="↻  새로고침", command=self._menu_reload).pack(side="left", padx=(8, 0))
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=12, pady=2)
        ttk.Button(tb, text="＋  행 추가", command=self._add_row).pack(side="left")
        ttk.Button(tb, text="🗑  선택 행 삭제", command=self._delete_row).pack(side="left", padx=(8, 0))
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=12, pady=2)
        ttk.Button(tb, text="↧  엑셀 가져오기", command=self._menu_import).pack(side="left")
        ttk.Button(tb, text="↥  내보내기", command=self._menu_export).pack(side="left", padx=(8, 0))

    # ---- 본문(탭) ----------------------------------------------------------

    def _build_body(self):
        wrap = ttk.Frame(self, padding=(10, 6))
        wrap.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(wrap)
        self.nb.pack(fill="both", expand=True)

        # 탭1: 파라미터 편집(메타 + 호기 값 전부 편집)
        f1 = ttk.Frame(self.nb)
        self.sh_edit = self._make_sheet(f1, self.full_cols, frozen=5, editable=True)
        self.sh_edit.pack(fill="both", expand=True)
        self.sh_edit.extra_bindings([("end_edit_cell", self._on_edit_full),
                                     ("end_paste", self._on_edit_full)])
        self.nb.add(f1, text="  파라미터 편집  ")

        # 탭2: 파라미터 값 수정(편집과 동일 열 + 접기 화살표, 호기 값만 편집)
        f2 = ttk.Frame(self.nb)
        self.sh_val = self._make_sheet(f2, self.full_cols, frozen=5, editable=True)
        self.sh_val.pack(fill="both", expand=True)
        self.sh_val.extra_bindings([("end_edit_cell", self._on_value_edit),
                                    ("end_paste", self._on_value_edit)])
        self.nb.add(f2, text="  파라미터 값 수정  ")

        # 탭3: 호기 비교/누락
        f3 = ttk.Frame(self.nb)
        self.cmp_cols = ["PI", "Recipe", "Zone", "Alg", "Parameter"] + AOI_UNITS + ["누락 호기"]
        self.sh_cmp = self._make_sheet(f3, self.cmp_cols, frozen=5, editable=False)
        self.sh_cmp.pack(fill="both", expand=True)
        self.nb.add(f3, text="  호기 비교 / 누락  ")

        # 탭4: 변경 이력
        f4 = ttk.Frame(self.nb, style="Surface.TFrame")
        self._build_history_tab(f4)
        self.nb.add(f4, text="  변경 이력  ")

        # 탭5: 특이사항
        f5 = ttk.Frame(self.nb)
        self.sh_spec = self._make_sheet(f5, SPECIAL_HEADERS, frozen=2, editable=True)
        self.sh_spec.pack(fill="both", expand=True)
        self.sh_spec.extra_bindings([("end_edit_cell", self._on_special_edit),
                                     ("end_paste", self._on_special_edit)])
        self.nb.add(f5, text="  특이사항  ")

        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_changed())

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
                                        state="readonly", values=["(전체)"] + AOI_UNITS)
        self.hist_aoi_cb.pack(side="left", padx=6)
        self.hist_aoi_cb.bind("<<ComboboxSelected>>", lambda ev: self._refresh_history())

        self.hist_cols = ["Update Date", "Updated By", "Recipe", "Zone", "Alg",
                          "Parameter", "AOI", "Old Value", "New Value", "Change Type"]
        self.sh_hist = self._make_sheet(parent, self.hist_cols, frozen=6, editable=False)
        self.sh_hist.pack(fill="both", expand=True)

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

    def open_file(self, path: str):
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
        if not self.read_only:
            engine.write_lock(path, self.user)
        self._cfg["last_path"] = path
        save_config(self._cfg)
        self._check_conflicts()
        self._refresh_all()
        self._update_title()

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

    def _refresh_edit(self):
        if not self.repo:
            return
        self.edit_ids = [pr.row_id for pr in self.repo.rows]
        data = [[engine._s(pr.get(f)) for f in self.full_cols] for pr in self.repo.rows]
        self.sh_edit.set_sheet_data(data, reset_col_positions=False, redraw=False)
        self._set_widths(self.sh_edit, self.full_cols)
        self._fit_heights(self.sh_edit, len(self.full_cols))
        self.sh_edit.redraw()

    def _refresh_values(self):
        """편집 탭과 동일한 열 구성 + 접기 화살표(트리). 호기 값만 편집 가능."""
        if not self.repo:
            return
        ncol = len(self.full_cols)
        blank = [""] * ncol
        idx = {h: i for i, h in enumerate(self.full_cols)}
        rows = sorted(self.repo.rows, key=lambda p: (engine.pi_order(p.get("PI")), p.display_order or 0))

        tree: list[list] = []          # [iid, parent, *full_cols]
        texts: list[str] = []          # 인덱스(트리) 라벨
        seen: set[str] = set()
        open_ids: list[str] = []
        self.val_leaf_ids: set[str] = set()

        def add_node(iid, parent, label, col_name, col_val):
            if iid in seen:
                return
            seen.add(iid)
            row = [iid, parent] + list(blank)
            if col_name and col_val:
                row[2 + idx[col_name]] = col_val   # 그룹 값은 해당 열에 표시
            tree.append(row)
            texts.append(label)
            open_ids.append(iid)

        for pr in rows:
            pi = engine._s(pr.get("PI")) or "(빈 PI)"
            rc = engine._s(pr.get("Recipe"))
            zn = engine._s(pr.get("Zone"))
            al = engine._s(pr.get("Alg"))
            i_pi = f"PI::{pi}"
            i_rc = f"R::{pi}|{rc}"
            i_zn = f"Z::{pi}|{rc}|{zn}"
            i_al = f"A::{pi}|{rc}|{zn}|{al}"
            add_node(i_pi, "", pi, "PI", pi)
            add_node(i_rc, i_pi, f"└ {rc or '(빈 Recipe)'}", "Recipe", rc)
            add_node(i_zn, i_rc, f"  └ {zn or '(빈 Zone)'}", "Zone", zn)
            add_node(i_al, i_zn, f"    └ {al or '(빈 Alg)'}", "Alg", al)
            # leaf = 파라미터 (iid = row_id) — 전체 열을 편집 탭과 동일하게 채움
            leaf = [pr.row_id, i_al] + [engine._s(pr.get(c)) for c in self.full_cols]
            tree.append(leaf)
            texts.append(f"      {engine._s(pr.get('Parameter')) or '(빈 파라미터)'}")
            self.val_leaf_ids.add(pr.row_id)

        self.sh_val.tree_build(data=tree, iid_column=0, parent_column=1, text_column=texts,
                               open_ids=open_ids, include_iid_column=False,
                               include_parent_column=False)
        # 호기(AOI) 열만 편집 가능, 메타 열은 읽기 전용
        try:
            ro = [i for i, h in enumerate(self.full_cols) if h not in AOI_UNITS]
            self.sh_val.readonly_columns(columns=ro, readonly=True)
            self.sh_val.readonly_columns(columns=[i for i, h in enumerate(self.full_cols)
                                                  if h in AOI_UNITS], readonly=False)
        except Exception:
            pass
        try:
            self.sh_val.set_index_width(240)
            self.sh_val.set_options(index_align="left")
        except Exception:
            pass
        self._set_widths(self.sh_val, self.full_cols)
        self.sh_val.redraw()

    def _refresh_compare(self):
        if not self.repo:
            return
        data = []
        tags = []  # (row_index, color)
        for i, v in enumerate(self.repo.comparison_view()):
            base = [v["PI"], v["Recipe"], v["Zone"], v["Alg"], v["Parameter"]]
            aoi = [engine._s(v["values"][u]) for u in AOI_UNITS]
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
        data = []
        for rec in self.repo.special:
            row = []
            for h in SPECIAL_HEADERS:
                v = rec.get(h)
                if h == SPECIAL_BOOL_COL:
                    v = bool(v)
                else:
                    v = engine._s(v)
                row.append(v)
            data.append(row)
        self.sh_spec.set_sheet_data(data, reset_col_positions=False, redraw=False)
        self._set_widths(self.sh_spec, SPECIAL_HEADERS)
        bcol = SPECIAL_HEADERS.index(SPECIAL_BOOL_COL)
        try:
            self.sh_spec.checkbox_column(bcol, checked=False)
            for r, rec in enumerate(self.repo.special):
                self.sh_spec.set_cell_data(r, bcol, bool(rec.get(SPECIAL_BOOL_COL)))
        except Exception:
            pass
        self._fit_heights(self.sh_spec, len(SPECIAL_HEADERS))
        self.sh_spec.redraw()

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
        if col >= len(self.full_cols):
            return
        field = self.full_cols[col]
        if field not in AOI_UNITS:   # 메타 열은 읽기 전용
            return
        iid = self.sh_val.rowitem(row)
        pr = self._row_by_id(iid)
        if pr is None:               # 그룹 헤더 행은 무시
            return
        val = self.sh_val.get_cell_data(row, col)
        pr.set(field, (val if val not in (None, "") else None))
        self._mark_dirty()

    def _on_special_edit(self, event=None):
        if not self.repo:
            return
        data = self.sh_spec.get_sheet_data()
        new_special = []
        bcol = SPECIAL_HEADERS.index(SPECIAL_BOOL_COL)
        for row in data:
            rec = {}
            for j, h in enumerate(SPECIAL_HEADERS):
                v = row[j] if j < len(row) else None
                if j == bcol:
                    v = bool(v)
                rec[h] = v
            new_special.append(rec)
        self.repo.special = new_special
        self._mark_dirty()

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
        if tab == 4:  # 특이사항
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
        if tab == 4:
            sel = sorted({c[0] for c in self.sh_spec.get_selected_cells()} |
                         set(self.sh_spec.get_selected_rows()), reverse=True)
            if not sel:
                messagebox.showinfo("행 삭제", "삭제할 특이사항 행을 선택하세요.")
                return
            if not messagebox.askyesno("행 삭제", f"선택한 {len(sel)}개 특이사항 행을 삭제할까요?"):
                return
            for r in sel:
                if 0 <= r < len(self.repo.special):
                    del self.repo.special[r]
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

    # ---- 탭/기타 ----------------------------------------------------------

    def _on_tab_changed(self):
        idx = self._current_tab()
        if idx == 1:
            self._refresh_values()
        elif idx == 2:
            self._refresh_compare()
        elif idx == 3:
            self._refresh_history()

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
        self.title(f"PI_ALL 장비 파라미터 관리 — {name}{mark}{ro}")
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
