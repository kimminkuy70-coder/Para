"""tkinter GUI — 화면 계층.

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
    META_FIELDS,
    ParamRepository,
)

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".pi_param_manager.json")
HEARTBEAT_MS = 5 * 60 * 1000  # 5분마다 잠금 갱신


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
    def __init__(self, master, columns, editable=True, on_edit=None, **kw):
        super().__init__(master, **kw)
        self.columns = columns
        self.editable = editable
        self.on_edit = on_edit  # 콜백(item_id, col_name, new_value)
        self._editor: tk.Entry | None = None

        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        ysb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        for col in columns:
            self.tree.heading(col, text=col)
            width = 130 if col in ("Parameter", "비고", "누락 호기", "초기 추천값") else 80
            self.tree.column(col, width=width, anchor="w", stretch=False)

        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # 줄무늬 + 강조 태그
        self.tree.tag_configure("odd", background="#f4f6f8")
        self.tree.tag_configure("missing", background="#fff3cd")
        self.tree.tag_configure("diff", background="#f8d7da")
        self.tree.tag_configure("common", background="#d4edda")

        if editable:
            self.tree.bind("<Double-1>", self._begin_edit)

    def clear(self):
        self._cancel_editor()
        for i in self.tree.get_children():
            self.tree.delete(i)

    def insert_row(self, iid, values, tags=()):
        self.tree.insert("", "end", iid=iid, values=values, tags=tags)

    # ---- 셀 편집 ----------------------------------------------------------

    def _begin_edit(self, event):
        if not self.editable:
            return
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col_id = self.tree.identify_column(event.x)  # '#n'
        row_id = self.tree.identify_row(event.y)
        if not row_id or not col_id:
            return
        col_index = int(col_id[1:]) - 1
        col_name = self.columns[col_index]

        x, y, w, h = self.tree.bbox(row_id, col_id)
        value = self.tree.set(row_id, col_name)
        self._cancel_editor()
        self._editor = tk.Entry(self.tree)
        self._editor.insert(0, value)
        self._editor.select_range(0, "end")
        self._editor.focus_set()
        self._editor.place(x=x, y=y, width=w, height=h)
        self._editor.bind("<Return>", lambda e: self._commit_editor(row_id, col_name))
        self._editor.bind("<Escape>", lambda e: self._cancel_editor())
        self._editor.bind("<FocusOut>", lambda e: self._commit_editor(row_id, col_name))

    def _commit_editor(self, row_id, col_name):
        if self._editor is None:
            return
        new_value = self._editor.get()
        self._cancel_editor()
        old = self.tree.set(row_id, col_name)
        if new_value != old:
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
        self.geometry("1280x720")

        self.repo: ParamRepository | None = None
        self.path: str | None = None
        self.read_only = False
        self.user = engine.current_user()
        self.dirty = False
        self._cfg = load_config()

        self._build_menu()
        self._build_body()
        self._build_statusbar()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(HEARTBEAT_MS, self._heartbeat)

        last = self._cfg.get("last_path")
        if last and os.path.exists(last):
            self.open_file(last)
        else:
            self._set_status("파일을 열어 시작하세요. (파일 메뉴 > 열기 / 엑셀 가져오기)")

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
        m.add_command(label="저장 (Ctrl+S)", command=self.save)
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

    def _build_body(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(side="top", fill="x", padx=6, pady=4)
        ttk.Button(toolbar, text="저장", command=self.save).pack(side="left", padx=2)
        ttk.Button(toolbar, text="새로고침", command=self._menu_reload).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(toolbar, text="행 추가", command=self._add_row).pack(side="left", padx=2)
        ttk.Button(toolbar, text="선택 행 삭제", command=self._delete_row).pack(side="left", padx=2)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=4)

        # 탭1: 파라미터 편집
        self.edit_cols = EDITABLE_FIELDS
        self.tab_edit = EditableTree(self.nb, self.edit_cols, editable=True, on_edit=self._on_cell_edit)
        self.nb.add(self.tab_edit, text="파라미터 편집")

        # 탭2: 호기 비교/누락
        self.cmp_cols = ["PI", "Recipe", "Zone", "Alg", "Parameter", "공통", "값차이", "누락 호기"] + AOI_UNITS
        self.tab_cmp = EditableTree(self.nb, self.cmp_cols, editable=False)
        self.nb.add(self.tab_cmp, text="호기 비교 / 누락")

        # 탭3: 변경 이력
        self.tab_hist = ttk.Frame(self.nb)
        self._build_history_tab(self.tab_hist)
        self.nb.add(self.tab_hist, text="변경 이력")

        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_changed())

    def _build_history_tab(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(side="top", fill="x", padx=4, pady=4)
        ttk.Label(bar, text="검색:").pack(side="left")
        self.hist_query = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.hist_query, width=30)
        e.pack(side="left", padx=4)
        e.bind("<KeyRelease>", lambda ev: self._refresh_history())
        ttk.Label(bar, text="PI:").pack(side="left", padx=(10, 0))
        self.hist_pi = tk.StringVar(value="(전체)")
        self.hist_pi_cb = ttk.Combobox(bar, textvariable=self.hist_pi, width=10, state="readonly")
        self.hist_pi_cb.pack(side="left", padx=4)
        self.hist_pi_cb.bind("<<ComboboxSelected>>", lambda ev: self._refresh_history())
        ttk.Label(bar, text="호기:").pack(side="left", padx=(10, 0))
        self.hist_aoi = tk.StringVar(value="(전체)")
        self.hist_aoi_cb = ttk.Combobox(bar, textvariable=self.hist_aoi, width=10,
                                        state="readonly", values=["(전체)"] + AOI_UNITS)
        self.hist_aoi_cb.pack(side="left", padx=4)
        self.hist_aoi_cb.bind("<<ComboboxSelected>>", lambda ev: self._refresh_history())

        self.hist_view_cols = ["Update Date", "Updated By", "Recipe", "Zone", "Alg",
                               "Parameter", "AOI", "Old Value", "New Value", "Change Type"]
        self.hist_tree = EditableTree(parent, self.hist_view_cols, editable=False)
        self.hist_tree.pack(fill="both", expand=True, padx=4, pady=4)

    def _build_statusbar(self):
        self.status = tk.StringVar()
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x")
        ttk.Label(bar, textvariable=self.status, anchor="w", relief="sunken").pack(fill="x")

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
        # 기존 잠금 해제
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
        self._update_title()

    def _menu_reload(self):
        if not self.path:
            return
        if self.dirty and not messagebox.askyesno("새로고침", "저장하지 않은 변경이 있습니다. 버리고 다시 읽을까요?"):
            return
        self.open_file(self.path)

    def save(self):
        if not self.repo or not self.path:
            return
        if self.read_only:
            messagebox.showwarning("읽기 전용", "읽기 전용으로 열려 있어 저장할 수 없습니다.")
            return
        self._check_conflicts()
        try:
            engine.write_lock(self.path, self.user)  # 잠금 갱신
            stats = self.repo.save(user=self.user)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("저장 실패", str(e))
            return
        self.dirty = False
        self._refresh_all()
        self._set_status(
            f"저장 완료 — 변경 {stats['changes']}건, 추가 {stats['added']}건, 삭제 {stats['deleted']}건")

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
            tags = ("odd",) if i % 2 else ()
            self.tab_edit.insert_row(pr.row_id, vals, tags)

    def _refresh_compare(self):
        self.tab_cmp.clear()
        if not self.repo:
            return
        for i, v in enumerate(self.repo.comparison_view()):
            base = [v["PI"], v["Recipe"], v["Zone"], v["Alg"], v["Parameter"],
                    "O" if v["common"] else "", "차이" if v["value_diff"] else "",
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
                tag = "odd" if i % 2 else ""
            self.tab_cmp.insert_row(v["row_id"], row, (tag,) if tag else ())

    def _refresh_history_filters(self):
        if not self.repo:
            return
        pis = sorted({engine._s(r.get("Recipe")) for r in self.repo.history if r.get("Recipe")})
        # 이력에는 PI 컬럼이 없으므로 PI_ALL 의 PI 목록을 사용
        pis = sorted({engine._s(p.get("PI")) for p in self.repo.rows if p.get("PI")})
        self.hist_pi_cb["values"] = ["(전체)"] + pis

    def _refresh_history(self):
        if not self.repo:
            return
        self.hist_tree.clear()
        q = self.hist_query.get().strip().lower()
        aoi_f = self.hist_aoi.get()
        # PI 필터는 이력에 PI 컬럼이 없어 Parameter/Recipe 기준 텍스트 매칭으로 대체
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
            self.hist_tree.insert_row(f"h{i}", vals, ("odd",) if shown % 2 else ())
            shown += 1
            if shown >= 2000:  # 과도한 렌더 방지
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
        self.tab_edit.tree.see(pr.row_id)
        self.tab_edit.tree.selection_set(pr.row_id)
        self._update_title()

    def _delete_row(self):
        if not self.repo or self.read_only:
            return
        sel = self.tab_edit.tree.selection()
        if not sel:
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
            "1) 파일 > '기존 엑셀(.xlsm) 가져오기' 로 처음 한 번 변환하거나,\n"
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
        mark = "*" if self.dirty else ""
        ro = " [읽기전용]" if self.read_only else ""
        self.title(f"PI_ALL 장비 파라미터 관리 — {name}{mark}{ro}  |  사용자: {self.user}")
        self._set_status(
            f"파일: {self.path or '-'}  |  사용자: {self.user}"
            f"{'  |  읽기전용' if self.read_only else ''}"
            f"{'  |  저장 안 됨' if self.dirty else ''}")

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
