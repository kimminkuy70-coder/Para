"""tkinter GUI — 화면 계층 (현대적 플랫 UI).

표준 라이브러리 tkinter 만 사용한다(추가 설치/네트워크 없음).
실제 로직은 engine 모듈에 있고, 이 파일은 화면과 사용자 조작만 담당한다.

탭 구성
  1) 파라미터 편집 : PI_ALL 그리드(셀 더블클릭 편집)
  2) 호기 비교/누락 : 파라미터별 호기 값 차이·누락 호기 강조
  3) 변경 이력      : 자동 기록된 변경 로그 검색/필터
"""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import engine
from .engine import (
    AOI_UNITS,
    EDITABLE_FIELDS,
    LOG_HEADERS,
    ParamRepository,
)
from .theme import apply_theme

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".pi_param_manager.json")
HEARTBEAT_MS = 5 * 60 * 1000  # 5분마다 잠금 갱신

# 컬럼별 권장 폭
_WIDE = {"Parameter": 180, "비고": 200, "누락 호기": 190, "초기 추천값": 120,
         "Recipe": 120, "Zone": 150, "Alg": 150, "Old Value": 110, "New Value": 110,
         "Change Type": 110, "Update Date": 100, "Updated By": 90}


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


# --------------------------------------------------------------------------
# 편집 가능한 Treeview (셀 더블클릭 -> Entry 오버레이)
# --------------------------------------------------------------------------

class EditableTree(ttk.Frame):
    def __init__(self, master, columns, palette, editable=True, on_edit=None, **kw):
        super().__init__(master, style="Surface.TFrame", **kw)
        self.columns = columns
        self.editable = editable
        self.on_edit = on_edit
        self.p = palette
        self._editor: tk.Entry | None = None

        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        ysb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=_WIDE.get(col, 84), anchor="w", stretch=False)

        self.tree.grid(row=0, column=0, sticky="nsew", padx=(2, 0), pady=2)
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree.tag_configure("odd", background=palette["stripe"])
        self.tree.tag_configure("even", background=palette["surface"])
        self.tree.tag_configure("missing", background=palette["missing"])
        self.tree.tag_configure("diff", background=palette["diff"])
        self.tree.tag_configure("common", background=palette["common"])

        if editable:
            self.tree.bind("<Double-1>", self._begin_edit)

    def clear(self):
        self._cancel_editor()
        self.tree.delete(*self.tree.get_children())

    def insert_row(self, iid, values, tags=()):
        self.tree.insert("", "end", iid=iid, values=values, tags=tags)

    def autosize(self, sample=60):
        """헤더/내용 길이에 맞춰 컬럼 폭 간단 자동 조정."""
        f = self.p["fonts"]["grid"]
        hf = self.p["fonts"]["head"]
        items = self.tree.get_children()[:sample]
        for col in self.columns:
            w = hf.measure(col) + 24
            for it in items:
                txt = str(self.tree.set(it, col))
                w = max(w, f.measure(txt) + 20)
            self.tree.column(col, width=min(max(w, 60), 320))

    # ---- 셀 편집 ----------------------------------------------------------

    def _begin_edit(self, event):
        if not self.editable:
            return
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        col_id = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id or not col_id:
            return
        col_name = self.columns[int(col_id[1:]) - 1]
        bbox = self.tree.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        value = self.tree.set(row_id, col_name)
        self._cancel_editor()
        ed = tk.Entry(self.tree, relief="flat", bg="#fffbe6",
                      highlightthickness=2, highlightcolor=self.p["primary"],
                      font=self.p["fonts"]["grid"])
        ed.insert(0, value)
        ed.select_range(0, "end")
        ed.focus_set()
        ed.place(x=x, y=y, width=w, height=h)
        ed.bind("<Return>", lambda e: self._commit_editor(row_id, col_name))
        ed.bind("<Escape>", lambda e: self._cancel_editor())
        ed.bind("<FocusOut>", lambda e: self._commit_editor(row_id, col_name))
        self._editor = ed

    def _commit_editor(self, row_id, col_name):
        if self._editor is None:
            return
        new_value = self._editor.get()
        self._cancel_editor()
        if new_value != self.tree.set(row_id, col_name):
            self.tree.set(row_id, col_name, new_value)
            if self.on_edit:
                self.on_edit(row_id, col_name, new_value)

    def _cancel_editor(self):
        if self._editor is not None:
            self._editor.destroy()
            self._editor = None


# --------------------------------------------------------------------------
# 메인 애플리케이션
# --------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PI_ALL 장비 파라미터 관리")
        self.geometry("1320x780")
        self.minsize(960, 600)

        self.p = apply_theme(self)

        self.repo: ParamRepository | None = None
        self.path: str | None = None
        self.read_only = False
        self.user = engine.current_user()
        self.dirty = False
        self._cfg = load_config()

        self._build_menu()
        self._build_header()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(HEARTBEAT_MS, self._heartbeat)

        last = self._cfg.get("last_path")
        if last and os.path.exists(last):
            self.after(50, lambda: self.open_file(last))
        else:
            self._set_status("파일을 열어 시작하세요 — 파일 메뉴 ▸ 열기 / 엑셀 가져오기")

    # ---- UI 구성 ----------------------------------------------------------

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

    def _build_body(self):
        wrap = ttk.Frame(self, padding=(10, 6))
        wrap.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(wrap)
        self.nb.pack(fill="both", expand=True)

        self.edit_cols = EDITABLE_FIELDS
        self.tab_edit = EditableTree(self.nb, self.edit_cols, self.p, editable=True,
                                     on_edit=self._on_cell_edit)
        self.nb.add(self.tab_edit, text="  파라미터 편집  ")

        self.cmp_cols = ["PI", "Recipe", "Zone", "Alg", "Parameter", "공통", "값차이", "누락 호기"] + AOI_UNITS
        self.tab_cmp = EditableTree(self.nb, self.cmp_cols, self.p, editable=False)
        self.nb.add(self.tab_cmp, text="  호기 비교 / 누락  ")

        self.tab_hist = ttk.Frame(self.nb, style="Surface.TFrame")
        self._build_history_tab(self.tab_hist)
        self.nb.add(self.tab_hist, text="  변경 이력  ")

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

        self.hist_view_cols = ["Update Date", "Updated By", "Recipe", "Zone", "Alg",
                               "Parameter", "AOI", "Old Value", "New Value", "Change Type"]
        self.hist_tree = EditableTree(parent, self.hist_view_cols, self.p, editable=False)
        self.hist_tree.pack(fill="both", expand=True)

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
            ans = messagebox.askyesno(
                "편집 잠금",
                f"현재 '{lock.user}' 님이 편집 중입니다 (시작 {lock.time}).\n\n"
                "읽기 전용으로 열까요?\n(아니오 = 잠금을 무시하고 편집 — 충돌 위험)")
            self.read_only = ans

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
        self.tab_edit.autosize()
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

    # ---- 그리드 새로고침 --------------------------------------------------

    def _refresh_all(self):
        self._refresh_edit()
        self._refresh_compare()
        self._refresh_history_filters()
        self._refresh_history()

    def _refresh_edit(self):
        self.tab_edit.clear()
        if not self.repo:
            return
        for i, pr in enumerate(self.repo.rows):
            vals = [engine._s(pr.get(f)) for f in self.edit_cols]
            self.tab_edit.insert_row(pr.row_id, vals, ("odd",) if i % 2 else ("even",))

    def _refresh_compare(self):
        self.tab_cmp.clear()
        if not self.repo:
            return
        for i, v in enumerate(self.repo.comparison_view()):
            base = [v["PI"], v["Recipe"], v["Zone"], v["Alg"], v["Parameter"],
                    "●" if v["common"] else "", "▲" if v["value_diff"] else "",
                    ", ".join(v["missing"])]
            aoi_vals = [engine._s(v["values"][u]) for u in AOI_UNITS]
            row = [engine._s(x) for x in base] + aoi_vals
            if v["value_diff"]:
                tag = "diff"
            elif v["missing"]:
                tag = "missing"
            elif v["common"]:
                tag = "common"
            else:
                tag = "odd" if i % 2 else "even"
            self.tab_cmp.insert_row(v["row_id"], row, (tag,))

    def _refresh_history_filters(self):
        if not self.repo:
            return
        pis = sorted({engine._s(p.get("PI")) for p in self.repo.rows if p.get("PI")})
        self.hist_pi_cb["values"] = ["(전체)"] + pis

    def _refresh_history(self):
        if not self.repo:
            return
        self.hist_tree.clear()
        q = self.hist_query.get().strip().lower()
        aoi_f = self.hist_aoi.get()
        pi_f = self.hist_pi.get()
        pi_params = None
        if pi_f and pi_f != "(전체)":
            pi_params = {engine._s(p.get("Parameter")) for p in self.repo.rows
                         if engine._s(p.get("PI")) == pi_f}
        shown = 0
        for i, rec in enumerate(reversed(self.repo.history)):
            if aoi_f and aoi_f != "(전체)" and engine._s(rec.get("AOI")) != aoi_f:
                continue
            if pi_params is not None and engine._s(rec.get("Parameter")) not in pi_params:
                continue
            if q:
                blob = " ".join(engine._s(rec.get(h)) for h in LOG_HEADERS).lower()
                if q not in blob:
                    continue
            vals = [engine._s(rec.get(c)) for c in self.hist_view_cols]
            self.hist_tree.insert_row(f"h{i}", vals, ("odd",) if shown % 2 else ("even",))
            shown += 1
            if shown >= 2000:
                break
        self._set_status(f"이력 {shown}건 표시")

    # ---- 편집 이벤트 ------------------------------------------------------

    def _on_cell_edit(self, row_id, col_name, new_value):
        if not self.repo:
            return
        pr = next((p for p in self.repo.rows if p.row_id == row_id), None)
        if pr is None:
            return
        pr.set(col_name, new_value)
        self.dirty = True
        self._update_title()

    def _add_row(self):
        if not self.repo or self.read_only:
            return
        pr = self.repo.add_row()
        self.dirty = True
        self._refresh_edit()
        self.nb.select(0)
        self.tab_edit.tree.see(pr.row_id)
        self.tab_edit.tree.selection_set(pr.row_id)
        self._update_title()

    def _delete_row(self):
        if not self.repo or self.read_only:
            return
        sel = self.tab_edit.tree.selection()
        if not sel:
            messagebox.showinfo("행 삭제", "삭제할 행을 먼저 선택하세요.")
            return
        if not messagebox.askyesno("행 삭제", "선택한 행을 삭제할까요? (저장 시 반영)"):
            return
        for iid in sel:
            self.repo.remove_row(iid)
        self.dirty = True
        self._refresh_edit()
        self._update_title()

    def _on_tab_changed(self):
        idx = self.nb.index(self.nb.select())
        if idx == 1:
            self._refresh_compare()
            self.tab_cmp.autosize()
        elif idx == 2:
            self._refresh_history()

    # ---- 기타 -------------------------------------------------------------

    def _show_aoi_ip(self):
        if not self.repo or not self.repo.aoi_ip:
            messagebox.showinfo("호기 IP", "호기 IP 정보가 없습니다.")
            return
        lines = [f"{k}\t{v}" for k, v in sorted(self.repo.aoi_ip.items())]
        messagebox.showinfo("호기 IP 매핑", "\n".join(lines))

    def _show_help(self):
        messagebox.showinfo(
            "사용 안내",
            "1) 파일 ▸ '기존 엑셀(.xlsm) 가져오기' 로 처음 한 번 변환하거나,\n"
            "   '공용 파일 열기' 로 OneDrive 폴더의 .xlsx 를 엽니다.\n"
            "2) '파라미터 편집' 탭에서 셀을 더블클릭해 값을 고칩니다.\n"
            "3) [저장]을 누르면 변경이 이력에 자동 기록되고,\n"
            "   디스크 최신본과 행 단위로 병합되어 저장됩니다.\n"
            "4) 다른 사람이 편집 중이면 잠금 안내가 뜹니다.\n\n"
            "※ 실행 중 네트워크 접속은 없습니다. OneDrive 폴더의 파일만 사용합니다.")

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
