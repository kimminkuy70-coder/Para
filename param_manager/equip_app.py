"""장비 UI 모방형 GUI — 실제 Camtek 장비 파라미터 화면처럼 구성.

화면 흐름(뒤로/앞으로 가능)
  S0  호기 격자      : 보유 장비(33호기)를 네모칸 그리드로 표시 → 클릭
  S1  PI / RDL       : 종류 선택(시트/파일) → 클릭
  S2  PI2 / PI3 …    : PI 열의 고유값(파일에서 자동) → 클릭
  S3  Recipe         : 선택 PI 하위 Recipe 고유값(예: PI / PI_bubble) → 클릭
  S4  장비 화면       : Zone 가로탭 ▸ Alg 접이식 섹션 ▸ Parameter 행
                       (선택 호기 입력칸 + 다른 호기 값 옅게 + 색/강조 + 드래그 이동 + 파라미터 추가)

엔진(engine)이 엑셀 입출력·병합·이력·색/테두리·잠금을 담당하고,
이 파일은 화면과 사용자 조작만 담당한다. 실행 중 네트워크 접속은 없다.
"""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from tksheet import Sheet

from . import coef_detector
from . import coefstore
from . import collate
from . import collector
from . import downloader as dl
from . import engine
from . import extract_io
from . import formbuilder
from . import history as history_mod
from . import ini_parser
from . import refdata
from . import refresh as refresh_mod
from . import rtp_parser as rtp
from . import workdirs
from .engine import ParamRepository
from .theme import apply_theme

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".pi_param_manager.json")
HIGHLIGHT_YELLOW = "#FFF24D"   # 강조(노랑)

# 양식 만들기에서 고르는 레시피(레벨) — 스펙: PI2/PI3/PI4, RDL1~RDL4
RECIPE_LEVELS = {"PI": ["PI2", "PI3", "PI4"], "RDL": ["RDL1", "RDL2", "RDL3", "RDL4"]}


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


def _color_key(row_id: str) -> str:
    """파라미터 행 강조/색 저장 키(app.py 의 P|RowID|field 규약과 호환)."""
    return f"P|{row_id}|Parameter"


def _sanitize_name(s: str) -> str:
    import re
    return re.sub(r'[<>:"/\\|?*]+', "_", str(s)).strip().strip(".") or "item"


class EquipApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Camtek AOI 장비 파라미터 관리")
        self.geometry("1400x860")
        self.minsize(1080, 680)
        self.p = apply_theme(self)
        self.fonts = self.p["fonts"]
        self.user = engine.current_user()

        # 상태
        self._cfg = load_config()
        self.repo: ParamRepository | None = None
        self.path: str | None = None
        self.kind: str | None = None         # "PI" / "RDL"
        self.read_only = False
        self.dirty = False
        self.recent_colors: list = self._cfg.get("recent_colors", [])

        # 3차 재설계: 저장 폴더 + 3개 독립 파일(장비 IP / 참고자료 / 특이사항)
        self.save_dir: str | None = self._cfg.get("save_dir")
        self.ip_rows: list[dict] = []        # 장비 IP 주소 [{호기, IP}] — 호기 기준
        self.ref_grid: list[list] = []       # 참고자료(자유형 메모 그리드)
        self.ref_colors: dict = {}           # 참고자료 셀 색상 {(r,c): '#hex'}
        self.special_rows: list[dict] = []   # 특이사항 행들
        self.special_colors: dict = {}       # 특이사항 셀 색상
        self.coef_rows: list[dict] = []      # 변환계수.xlsx [호기,MAG,변형,계수,비고]

        # 상단 탭(파라미터 값 확인 / 양식 만들기 / 특이사항 / 참고자료)
        self.view = "param"
        # 스펙: '파라미터 값 확인' 화면에서 호기 값 '직접 수정' 기능 제거(읽기 전용).
        # 값은 '파라미터 값 업데이트'(장비 수집)로만 채운다. 이름/추천값/비고/색은 편집 유지.
        self.values_readonly = True

        # 내비게이션 스택(뒤로/앞으로) — 파라미터 탭 전용
        self.nav: list[dict] = [{"screen": "s0"}]
        self.nav_idx = 0

        # S4 보조 상태
        self.cur_zone: str | None = None
        self.collapsed: set = set()          # 접힌 Alg 키
        self._drag = None
        self._row_widgets: list = []         # [(param_row, frame, alg)]
        self._note_pop = None
        self._cur_sheet = None               # 특이사항/참고자료 tksheet
        self._cur_kind = None

        # 되돌리기/다시(동작 단위 스냅샷 스택)
        self._undo: list = []
        self._redo: list = []

        # 행 높이(좌/우 정렬용 픽셀) — 내용(입력칸)보다 크게 잡아 minsize 로 행높이 고정
        self.HDR_H = 30
        self.SEC_H = 34
        self.ROW_H = 34
        self.LINE_PX = 16          # 우측 줄바꿈 셀의 한 줄 높이
        self.CELL_CHARS = 10       # 우측 셀 한 줄에 들어가는 대략 글자수
        self.MAX_LINES = 5         # 우측 셀 최대 줄 수(행 높이 폭주 방지)
        self.COL_W = 84            # 우측 호기 셀 고정 폭(px) — 헤더/값 정렬용
        self.NAME_W = 210          # 좌측 파라미터 이름 열 폭(px) — 줄바꿈 기준
        self.VAL_W = 120           # 좌측 선택호기 값 열 폭(px) — 줄바꿈 기준

        self._build_chrome()
        self._render()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<F4>", lambda e: self._highlight_focused())
        self.after(200, self._startup)   # 저장폴더 지정 → 참고자료/특이사항 로드 → 최신 취합
        self.bind_all("<Control-z>", lambda e: self.undo())
        self.bind_all("<Control-y>", lambda e: self.redo())
        self.bind_all("<Control-Z>", lambda e: self.undo())
        self.bind_all("<Control-Shift-Z>", lambda e: self.redo())
        self.bind_all("<Control-Shift-z>", lambda e: self.redo())

    # ====================================================================
    #  상단 공통 크롬(뒤로/앞으로/브레드크럼/저장/파일)
    # ====================================================================
    def _build_chrome(self):
        bar = tk.Frame(self, bg=self.p["header_bar"], height=58)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)

        self.btn_back = tk.Button(bar, text="◀ 뒤로", relief="flat", bd=0,
                                  bg="#334155", fg="#f8fafc", padx=12, pady=6,
                                  activebackground="#475569", command=self.go_back)
        self.btn_back.pack(side="left", padx=(12, 4), pady=11)
        self.btn_fwd = tk.Button(bar, text="앞으로 ▶", relief="flat", bd=0,
                                 bg="#334155", fg="#f8fafc", padx=12, pady=6,
                                 activebackground="#475569", command=self.go_forward)
        self.btn_fwd.pack(side="left", padx=4, pady=11)
        self.btn_home = tk.Button(bar, text="⌂ 처음", relief="flat", bd=0,
                                  bg="#334155", fg="#f8fafc", padx=12, pady=6,
                                  activebackground="#475569",
                                  command=lambda: self.navigate(screen="s0"))
        self.btn_home.pack(side="left", padx=4, pady=11)

        self.btn_undo = tk.Button(bar, text="↶ 되돌리기", relief="flat", bd=0,
                                  bg="#334155", fg="#f8fafc", padx=10, pady=6,
                                  activebackground="#475569", command=self.undo)
        self.btn_undo.pack(side="left", padx=(12, 2), pady=11)
        self.btn_redo = tk.Button(bar, text="↷ 다시", relief="flat", bd=0,
                                  bg="#334155", fg="#f8fafc", padx=10, pady=6,
                                  activebackground="#475569", command=self.redo)
        self.btn_redo.pack(side="left", padx=2, pady=11)

        self.lbl_crumb = tk.Label(bar, text="", bg=self.p["header_bar"],
                                  fg="#cbd5e1", font=self.fonts["sub"])
        self.lbl_crumb.pack(side="left", padx=16)

        self.btn_file = tk.Button(bar, text="⋯ 파일", relief="flat", bd=0,
                                  bg="#334155", fg="#f8fafc", padx=12, pady=6,
                                  activebackground="#475569", command=self._file_menu)
        self.btn_file.pack(side="right", padx=(4, 12), pady=11)
        self.btn_save = tk.Button(bar, text="💾 저장", relief="flat", bd=0,
                                  bg=self.p["primary"], fg="#ffffff", padx=14, pady=6,
                                  activebackground=self.p["primary_dk"], command=self.save)
        self.btn_save.pack(side="right", padx=4, pady=11)

        self.title_lbl = tk.Label(bar, text="Camtek AOI 장비 파라미터 관리",
                                  bg=self.p["header_bar"], fg=self.p["header_fg"],
                                  font=self.fonts["title"])
        self.title_lbl.pack(side="right", padx=16)

        # 묶음: 파라미터 탭에서만 보이는 내비 위젯
        self._nav_widgets = [self.btn_back, self.btn_fwd, self.btn_home, self.lbl_crumb]

        # 상단 3탭(파라미터 / 특이사항 / 참고자료)
        self.tabbar = tk.Frame(self, bg=self.p["head_bg"], height=40)
        self.tabbar.pack(side="top", fill="x")
        self.tabbar.pack_propagate(False)
        self._tab_btns = {}
        for key, label in (("param", "파라미터 값 확인"), ("form", "양식 만들기"),
                           ("special", "특이사항"), ("reference", "참고자료"),
                           ("ip", "장비 IP")):
            b = tk.Button(self.tabbar, text=label, relief="flat", bd=0,
                          font=self.fonts["bold"], padx=22, pady=8, cursor="hand2",
                          command=lambda k=key: self._set_view(k))
            b.pack(side="left", padx=(8 if key == "param" else 2, 2), pady=4)
            self._tab_btns[key] = b

        # 상태바
        self.status = tk.Label(self, text="", anchor="w", bg=self.p["head_bg"],
                               fg=self.p["muted"], font=self.fonts["sub"], padx=10)
        self.status.pack(side="bottom", fill="x")

        # 본문 컨테이너
        self.body = tk.Frame(self, bg=self.p["bg"])
        self.body.pack(side="top", fill="both", expand=True)
        self._sync_tab_style()

    def _sync_tab_style(self):
        for k, b in self._tab_btns.items():
            on = (k == self.view)
            b.config(bg=(self.p["primary"] if on else self.p["head_bg"]),
                     fg=("#ffffff" if on else self.p["muted"]))

    def _set_view(self, key):
        self.view = key
        self._sync_tab_style()
        # 내비 위젯은 파라미터 탭에서만
        for w in self._nav_widgets:
            (w.pack(side="left") if key == "param" else w.pack_forget())
        self._render()

    def _set_status(self, msg: str):
        self.status.config(text=msg)
        self.update_idletasks()

    def _guard(self) -> bool:
        """읽기 전용이면 변경 동작 차단."""
        if self.read_only:
            self._set_status("읽기 전용 — 다른 사용자가 편집 중이라 수정할 수 없습니다.")
            return False
        return True

    # ====================================================================
    #  내비게이션
    # ====================================================================
    def _state(self) -> dict:
        return self.nav[self.nav_idx]

    def navigate(self, **changes):
        base = dict(self._state())
        if changes.get("screen") == "s0":
            base = {}
        base.update(changes)
        # 앞으로 기록 잘라내고 push
        self.nav = self.nav[: self.nav_idx + 1]
        self.nav.append(base)
        self.nav_idx = len(self.nav) - 1
        self._render()

    def go_back(self):
        if self.nav_idx > 0:
            self.nav_idx -= 1
            self._render()

    def go_forward(self):
        if self.nav_idx < len(self.nav) - 1:
            self.nav_idx += 1
            self._render()

    def _render(self):
        # 이전 화면의 휠 바인딩 잔재 제거(다른 창까지 스크롤되는 문제 방지)
        for seq in ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-6>", "<Button-7>"):
            try:
                self.unbind_all(seq)
            except tk.TclError:
                pass
        self.btn_undo.config(state=("normal" if self._undo and not self.read_only else "disabled"))
        self.btn_redo.config(state=("normal" if self._redo and not self.read_only else "disabled"))
        for w in self.body.winfo_children():
            w.destroy()
        if self.view == "special":
            self._view_special()
            return
        if self.view == "reference":
            self._view_reference()
            return
        if self.view == "ip":
            self._view_ip()
            return
        if self.view == "form":
            self._view_form()
            return
        st = self._state()
        self.btn_back.config(state=("normal" if self.nav_idx > 0 else "disabled"))
        self.btn_fwd.config(state=("normal" if self.nav_idx < len(self.nav) - 1 else "disabled"))
        self._update_crumb(st)
        self._param_actionbar()
        scr = st.get("screen", "s0")
        if scr == "s0":
            self._screen_machines()
        elif scr == "s1":
            self._screen_kind(st)
        elif scr == "s2":
            self._screen_pi(st)
        elif scr == "s3":
            self._screen_recipe(st)
        elif scr == "s4":
            self._screen_equipment(st)

    def _update_crumb(self, st):
        parts = []
        if st.get("machine"):
            parts.append(st["machine"])
        if st.get("kind"):
            parts.append(st["kind"])
        if st.get("pi"):
            parts.append(st["pi"])
        if st.get("recipe"):
            parts.append(st["recipe"])
        self.lbl_crumb.config(text="  ▸  ".join(parts))

    # ====================================================================
    #  S0 — 호기 격자
    # ====================================================================
    def _all_machines(self) -> list:
        """호기 목록 = '장비 IP 주소' 파일 기준. 비면 빈 목록."""
        return refdata.machines(self.ip_rows)

    def _coef_label_for(self, machine: str) -> str:
        """선택 호기의 변환계수(변형별 모두) 표시 문자열. 장비 렌즈 특성 = 호기+MAG."""
        rows = coefstore.machine_coefs(self.coef_rows, machine)
        if not rows:
            return "  · 변환계수 미등록(변환계수.xlsx)"
        parts = []
        for r in rows:
            tag = engine._s(r.get("변형")).strip() or (
                f"MAG {engine._s(r.get('MAG')).strip()}" if r.get("MAG") else "")
            val = engine._s(r.get("계수")).strip()
            try:
                val = f"{float(val):.4g}"
            except ValueError:
                pass
            parts.append(f"{tag}={val}" if tag else val)
        return "  · 변환계수  " + " · ".join(parts)

    def _screen_machines(self):
        wrap = tk.Frame(self.body, bg=self.p["bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=18)
        tk.Label(wrap, text="호기 선택", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", pady=(0, 4))
        tk.Label(wrap, text="관리할 장비(호기)를 선택하세요.", bg=self.p["bg"],
                 fg=self.p["muted"], font=self.fonts["sub"]).pack(anchor="w", pady=(0, 14))

        if not self._all_machines():
            tk.Label(wrap, text="참고자료에 등록된 호기가 없습니다. ‘＋ 호기 추가’로 호기와 "
                              "IP를 등록하세요(참고자료.xlsx에 저장됩니다).",
                     bg=self.p["bg"], fg=self.p["danger"],
                     font=self.fonts["sub"]).pack(anchor="w", pady=(0, 8))
        grid = tk.Frame(wrap, bg=self.p["bg"])
        grid.pack(fill="both", expand=True)
        cols = 8
        machines = self._all_machines()
        custom = set(machines)          # 모든 호기가 참고자료 기반(우클릭 삭제 가능)
        for i, m in enumerate(machines):
            r, c = divmod(i, cols)
            b = tk.Button(grid, text=m, width=10, height=3, relief="flat", bd=0,
                          bg=self.p["surface"], fg=self.p["text"],
                          activebackground=self.p["primary_lt"],
                          font=self.fonts["bold"], cursor="hand2",
                          command=lambda mm=m: self.navigate(screen="s1", machine=mm))
            b.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            b.bind("<Enter>", lambda e, w=b: w.config(bg=self.p["primary_lt"]))
            b.bind("<Leave>", lambda e, w=b: w.config(bg=self.p["surface"]))
            if m in custom:
                # 사용자가 추가한 호기 — 우클릭으로 삭제 메뉴
                b.bind("<Button-3>", lambda e, mm=m: self._machine_ctx(e, mm))
        # 맨 끝 칸: ＋ 호기 추가
        i = len(machines)
        r, c = divmod(i, cols)
        add = tk.Button(grid, text="＋ 호기 추가", width=10, height=3, relief="flat",
                        bd=0, bg=self.p["head_bg"], fg=self.p["text"],
                        activebackground=self.p["primary_lt"],
                        font=self.fonts["bold"], cursor="hand2",
                        command=self._add_machine_dialog)
        add.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
        for c in range(cols):
            grid.columnconfigure(c, weight=1)

    def _add_machine_dialog(self):
        """호기 추가 — 이름 + IP 를 입력받아 참고자료(참고자료.xlsx)에 기록."""
        if not self.save_dir:
            messagebox.showinfo("저장 폴더", "먼저 저장 폴더를 지정하세요.")
            return
        win = tk.Toplevel(self)
        win.title("호기 추가")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="추가할 호기와 IP를 입력하세요(참고자료에 저장됩니다).",
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["bold"]).pack(
                 anchor="w", padx=14, pady=(12, 6))
        frm = tk.Frame(win, bg=self.p["bg"])
        frm.pack(fill="x", padx=14)
        tk.Label(frm, text="호기(예: AOI-26):", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).grid(row=0, column=0, sticky="w", pady=3)
        name_var = tk.StringVar()
        tk.Entry(frm, textvariable=name_var, width=20, relief="solid", bd=1).grid(
            row=0, column=1, padx=6, pady=3)
        tk.Label(frm, text="IP:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).grid(row=1, column=0, sticky="w", pady=3)
        ip_var = tk.StringVar()
        tk.Entry(frm, textvariable=ip_var, width=20, relief="solid", bd=1).grid(
            row=1, column=1, padx=6, pady=3)

        def ok():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("입력", "호기 이름을 입력하세요.", parent=win)
                return
            added = refdata.add_machine(self.ip_rows, name, ip_var.get().strip())
            self._save_refdata()
            win.destroy()
            self._render()
            messagebox.showinfo(
                "호기 추가",
                (f"호기 '{name}' 를 '장비 IP 주소'에 추가했습니다." if added
                 else f"'{name}' 는 이미 있어 IP만 갱신했습니다.")
                + "\n다음 취합부터 이 호기 열이 포함됩니다.")
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=14, pady=12)
        tk.Button(bt, text="추가", relief="flat", bd=0, bg=self.p["primary"], fg="#ffffff",
                  padx=16, cursor="hand2", command=ok).pack(side="left")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=16,
                  cursor="hand2", command=win.destroy).pack(side="left", padx=6)

    def _machine_ctx(self, event, machine):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label=f"'{machine}' 호기 삭제(참고자료에서)",
                      command=lambda: self._remove_custom_machine(machine))
        m.tk_popup(event.x_root, event.y_root)

    def _remove_custom_machine(self, machine):
        if not messagebox.askyesno(
                "호기 삭제",
                f"'{machine}' 호기를 '장비 IP 주소'에서 제거할까요?\n"
                "(이미 만들어진 취합 파일의 열/값은 그대로 남습니다.)"):
            return
        self.ip_rows = [r for r in self.ip_rows
                        if engine._s(r.get("호기")).strip() != machine]
        self._save_refdata()
        self._render()

    # ====================================================================
    #  S1 — PI / RDL
    # ====================================================================
    def _screen_kind(self, st):
        wrap = self._choice_wrap(f"{st['machine']} — 종류 선택", "PI 또는 RDL 을 선택하세요.")
        for kind, desc in (("PI", "PI Core Parameter"), ("RDL", "RDL Parameter")):
            self._big_button(wrap, kind, desc,
                             lambda k=kind: self._enter_kind(k))

    def _enter_kind(self, kind):
        if not self.repo or not self.repo.rows:
            messagebox.showinfo("데이터 없음",
                                "표시할 취합 데이터가 없습니다.\n"
                                "먼저 ‘파라미터 값 업데이트’로 취합을 만드세요.")
            return
        self.navigate(screen="s2", kind=kind)

    # ====================================================================
    #  S2 — PI 값(PI2/PI3/PI4 …)
    # ====================================================================
    def _screen_pi(self, st):
        wrap = self._choice_wrap(f"{st['machine']} ▸ {st['kind']} — 레시피 선택",
                                 "취합 데이터에서 인식된 레시피(레벨)입니다.")
        kind = st.get("kind", "PI")
        vals = [v for v in self._distinct("PI")
                if (v.upper().startswith("RDL") if kind == "RDL"
                    else not v.upper().startswith("RDL"))]
        if not vals:
            tk.Label(wrap, text="데이터가 없습니다.", bg=self.p["bg"],
                     fg=self.p["muted"]).pack()
            return
        for v in vals:
            n = sum(1 for r in self.repo.rows if engine._s(r.get("PI")) == v)
            self._big_button(wrap, v, f"파라미터 {n}개",
                             lambda vv=v: self.navigate(screen="s3", pi=vv))

    # ====================================================================
    #  S3 — Recipe(PI / PI_bubble …)
    # ====================================================================
    def _screen_recipe(self, st):
        wrap = self._choice_wrap(f"{st['machine']} ▸ {st['kind']} ▸ {st['pi']} — Recipe 선택",
                                 "파일에서 자동 인식된 Recipe 입니다.")
        vals = self._distinct("Recipe", pi=st["pi"])
        if not vals:
            tk.Label(wrap, text="Recipe 데이터가 없습니다.", bg=self.p["bg"],
                     fg=self.p["muted"]).pack()
            return
        for v in vals:
            n = sum(1 for r in self.repo.rows
                    if engine._s(r.get("PI")) == st["pi"] and engine._s(r.get("Recipe")) == v)
            self._big_button(wrap, v or "(빈 Recipe)", f"파라미터 {n}개",
                             lambda vv=v: self.navigate(screen="s4", recipe=vv))

    # ---- 선택 화면 공통 위젯 ------------------------------------------
    def _choice_wrap(self, title, sub):
        wrap = tk.Frame(self.body, bg=self.p["bg"])
        wrap.pack(fill="both", expand=True, padx=28, pady=22)
        tk.Label(wrap, text=title, bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", pady=(0, 2))
        tk.Label(wrap, text=sub, bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(anchor="w", pady=(0, 18))
        inner = tk.Frame(wrap, bg=self.p["bg"])
        inner.pack(anchor="w")
        return inner

    def _big_button(self, parent, text, desc, cmd):
        card = tk.Frame(parent, bg=self.p["surface"], width=240, height=110,
                        highlightbackground=self.p["border"], highlightthickness=1,
                        cursor="hand2")
        card.pack(side="left", padx=8, pady=8)
        card.pack_propagate(False)
        tk.Label(card, text=text, bg=self.p["surface"], fg=self.p["primary"],
                 font=self.fonts["title"]).pack(anchor="w", padx=16, pady=(20, 2))
        tk.Label(card, text=desc, bg=self.p["surface"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(anchor="w", padx=16)
        for w in (card, *card.winfo_children()):
            w.bind("<Button-1>", lambda e: cmd())
            w.bind("<Enter>", lambda e: card.config(bg=self.p["primary_lt"]))
            w.bind("<Leave>", lambda e: card.config(bg=self.p["surface"]))
        return card

    def _distinct(self, field, pi=None) -> list:
        seen, out = set(), []
        for r in self.repo.rows:
            if pi is not None and engine._s(r.get("PI")) != pi:
                continue
            v = engine._s(r.get(field))
            if v not in seen:
                seen.add(v)
                out.append(v)
        return [v for v in out if v != ""] or ([""] if "" in seen else [])

    # ====================================================================
    #  S4 — 장비 화면
    # ====================================================================
    def _filtered_rows(self, st) -> list:
        return [r for r in self.repo.rows
                if engine._s(r.get("PI")) == st["pi"]
                and engine._s(r.get("Recipe")) == st["recipe"]]

    def _screen_equipment(self, st):
        rows = self._filtered_rows(st)
        zones = []
        for r in rows:
            z = engine._s(r.get("Zone"))
            if z not in zones:
                zones.append(z)
        if self.cur_zone not in zones:
            self.cur_zone = zones[0] if zones else None

        outer = tk.Frame(self.body, bg=self.p["bg"])
        outer.pack(fill="both", expand=True)

        # 제목줄: "AOI-25 : PI"
        head = tk.Frame(outer, bg=self.p["surface"],
                        highlightbackground=self.p["border"], highlightthickness=1)
        head.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(head, text=f"  {st['machine']} : {st['recipe'] or st['pi']}",
                 bg=self.p["surface"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(side="left", pady=8)
        # 변환계수(장비 렌즈 특성 = 호기+MAG) — 변형별 모두 표시
        coef_txt = self._coef_label_for(st["machine"])
        tk.Label(head, text=coef_txt, bg=self.p["surface"],
                 fg=(self.p["primary"] if "계수  " in coef_txt else self.p["muted"]),
                 font=self.fonts["bold"]).pack(side="left", padx=(6, 0))
        ro = "  [파일 읽기 전용]" if self.read_only else ""
        tk.Label(head, text=f"좌=선택 호기 · 우=다른 호기 · 값은 읽기 전용(‘값 업데이트’로 채움) "
                          f"· Shift+휠=가로스크롤{ro}   ",
                 bg=self.p["surface"], fg=(self.p["danger"] if self.read_only else self.p["muted"]),
                 font=self.fonts["sub"]).pack(side="right", pady=8)

        # Zone 가로 탭 + Zone/Alg 추가
        ztab = tk.Frame(outer, bg=self.p["bg"])
        ztab.pack(fill="x", padx=12, pady=(8, 0))
        for z in zones:
            sel = (z == self.cur_zone)
            b = tk.Button(ztab, text=z or "(Zone 없음)", relief="flat", bd=0,
                          bg=(self.p["primary"] if sel else self.p["surface"]),
                          fg=("#ffffff" if sel else self.p["text"]),
                          font=self.fonts["bold"], padx=16, pady=8, cursor="hand2",
                          command=lambda zz=z: self._set_zone(zz))
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-3>", lambda e, zz=z, w=b, s=st: self._zone_menu(e, s, zz, w))
        if not self.read_only:
            tk.Button(ztab, text="＋Zone", relief="flat", bd=0, bg=self.p["surface"],
                      fg=self.p["primary"], font=self.fonts["bold"], padx=12, pady=8,
                      cursor="hand2", command=lambda s=st: self._add_zone(s)).pack(side="left", padx=(8, 2))
            tk.Button(ztab, text="＋Alg", relief="flat", bd=0, bg=self.p["surface"],
                      fg=self.p["primary"], font=self.fonts["bold"], padx=12, pady=8,
                      cursor="hand2", command=lambda s=st: self._add_alg(s)).pack(side="left", padx=2)
        tk.Label(ztab, text="  (Zone/Alg 우클릭=이름수정·삭제)", bg=self.p["bg"],
                 fg=self.p["muted"], font=self.fonts["sub"]).pack(side="left")

        # ---- 2분할: 좌(선택호기, 고정폭) / 우(다른호기, 가로스크롤) ----
        LEFT_W = 540
        others = [m for m in self.repo.aoi_units if m != st["machine"]]

        mid = tk.Frame(outer, bg=self.p["bg"])
        mid.pack(fill="both", expand=True, padx=12, pady=10)

        # === 상단 고정 헤더(세로 스크롤해도 항상 보임) ===
        hdr_strip = tk.Frame(mid, bg=self.p["head_bg"], height=self.HDR_H)
        hdr_strip.pack(side="top", fill="x")
        hdr_strip.pack_propagate(False)
        lhdr = tk.Frame(hdr_strip, bg=self.p["head_bg"], width=LEFT_W)
        lhdr.pack(side="left", fill="y")
        lhdr.pack_propagate(False)
        hb = self.p["head_bg"]
        hfg = self.p["muted"]
        # 좌측 행 레이아웃(grip/chip/이름/값/비고)에 맞춰 컬럼 제목 정렬(추천값 열 제거)
        tk.Label(lhdr, text="", bg=hb, width=2, font=self.fonts["bold"]).pack(side="left")           # grip
        tk.Label(lhdr, text="", bg=hb, width=2).pack(side="left", padx=(2, 6))                       # chip
        nbox = tk.Frame(lhdr, bg=hb, width=self.NAME_W)
        nbox.pack(side="left", fill="y")
        nbox.pack_propagate(False)
        tk.Label(nbox, text="파라미터", bg=hb, fg=hfg, font=self.fonts["base"],
                 anchor="w").pack(side="left", fill="both", expand=True)
        vbox = tk.Frame(lhdr, bg=hb, width=self.VAL_W)
        vbox.pack(side="left", fill="y", padx=(4, 0))
        vbox.pack_propagate(False)
        tk.Label(vbox, text=f"{st['machine']} 값", bg=hb, fg=self.p["primary"],
                 font=self.fonts["sub"], anchor="center").pack(side="left", fill="both", expand=True)
        tk.Label(lhdr, text="비고", bg=hb, fg=hfg, font=self.fonts["sub"],
                 width=2).pack(side="left", padx=(6, 2))
        tk.Frame(hdr_strip, bg="#94a3b8", width=3).pack(side="left", fill="y")
        rhead = tk.Canvas(hdr_strip, bg=self.p["head_bg"], highlightthickness=0)
        rhead.pack(side="left", fill="both", expand=True)
        rhead_inner = tk.Frame(rhead, bg=self.p["head_bg"])
        rhead.create_window((0, 0), window=rhead_inner, anchor="nw")
        for m in others:
            cell = tk.Frame(rhead_inner, width=self.COL_W, height=self.HDR_H,
                            bg=self.p["head_bg"], highlightthickness=1,
                            highlightbackground="#b8c0cc")
            cell.pack_propagate(False)
            cell.pack(side="left")
            tk.Label(cell, text=m, bg=self.p["head_bg"], fg=self.p["text"],
                     font=self.fonts["sub"], anchor="center").pack(fill="both", expand=True)
        self._rhead = rhead

        # === 본문(스크롤) ===
        body = tk.Frame(mid, bg=self.p["bg"])
        body.pack(side="top", fill="both", expand=True)
        vbar = ttk.Scrollbar(body, orient="vertical", command=self._yview_both)
        vbar.pack(side="right", fill="y")
        self._vbar = vbar

        left_wrap = tk.Frame(body, bg=self.p["bg"], width=LEFT_W)
        left_wrap.pack(side="left", fill="y")
        left_wrap.pack_propagate(False)
        lcanvas = tk.Canvas(left_wrap, bg=self.p["bg"], highlightthickness=0)
        lcanvas.pack(side="left", fill="both", expand=True)
        linner = tk.Frame(lcanvas, bg=self.p["bg"])
        lcanvas.create_window((0, 0), window=linner, anchor="nw", tags="inner")
        lcanvas.bind("<Configure>", lambda e: lcanvas.itemconfig("inner", width=e.width))
        lcanvas.config(yscrollcommand=vbar.set)

        divider = tk.Frame(body, bg="#94a3b8", width=3)
        divider.pack(side="left", fill="y")

        right_wrap = tk.Frame(body, bg=self.p["bg"])
        right_wrap.pack(side="left", fill="both", expand=True)
        hbar = ttk.Scrollbar(right_wrap, orient="horizontal")
        hbar.pack(side="bottom", fill="x")
        rcanvas = tk.Canvas(right_wrap, bg=self.p["bg"], highlightthickness=0)
        rcanvas.pack(side="left", fill="both", expand=True)
        rinner = tk.Frame(rcanvas, bg=self.p["bg"])
        rcanvas.create_window((0, 0), window=rinner, anchor="nw")

        # 가로 스크롤: 본문 캔버스와 고정 헤더를 같은 위치로 동기화
        def _xsync(*a):
            hbar.set(*a)
            rhead.xview_moveto(rcanvas.xview()[0])
        rcanvas.config(xscrollcommand=_xsync)

        def _hcmd(*a):
            rcanvas.xview(*a)
            rhead.xview_moveto(rcanvas.xview()[0])
        hbar.config(command=_hcmd)

        self._left_canvas, self._right_canvas = lcanvas, rcanvas

        self._row_widgets = []
        self._build_panes(linner, rinner, st, others)

        def _upd(_=None):
            try:
                lcanvas.configure(scrollregion=lcanvas.bbox("all"))
                rcanvas.configure(scrollregion=rcanvas.bbox("all"))
                rhead.configure(scrollregion=rhead.bbox("all"))
            except tk.TclError:
                pass
        linner.bind("<Configure>", _upd)
        rinner.bind("<Configure>", _upd)
        self.after(60, _upd)
        # 줄바꿈으로 행 높이가 달라질 수 있어, 실제 높이를 측정해 좌우를 동일하게 맞춤
        self.after(70, self._equalize_panes)
        self._scope_wheel(mid, lcanvas, rcanvas, hcanvas=rcanvas)

    def _equalize_panes(self):
        """좌/우 각 행을 실제 요구 높이의 큰 쪽으로 맞춰 정렬(줄바꿈 대응)."""
        li, ri = getattr(self, "_pane_l", None), getattr(self, "_pane_r", None)
        if li is None or ri is None:
            return
        try:
            self.update_idletasks()
            for r in range(getattr(self, "_pane_n", 0)):
                lw = li.grid_slaves(row=r, column=0)
                rw = ri.grid_slaves(row=r, column=0)
                hl = lw[0].winfo_reqheight() if lw else 0
                hr = rw[0].winfo_reqheight() if rw else 0
                h = max(hl, hr, self.ROW_H)
                li.rowconfigure(r, minsize=h)
                ri.rowconfigure(r, minsize=h)
            self._left_canvas.configure(scrollregion=self._left_canvas.bbox("all"))
            self._right_canvas.configure(scrollregion=self._right_canvas.bbox("all"))
        except Exception:
            pass

    def _set_zone(self, z):
        self.cur_zone = z
        self._render()

    def _toggle_alg(self, key):
        if key in self.collapsed:
            self.collapsed.discard(key)
        else:
            self.collapsed.add(key)
        self._render()

    # ---- 2분할 행 빌더 -------------------------------------------------
    def _grid_row(self, linner, rinner, r, h):
        linner.rowconfigure(r, minsize=h)
        rinner.rowconfigure(r, minsize=h)
        linner.columnconfigure(0, weight=1)

    def _build_panes(self, linner, rinner, st, others):
        zrows = [x for x in self._filtered_rows(st)
                 if engine._s(x.get("Zone")) == self.cur_zone]
        r = 0   # 호기명 헤더는 상단 고정 스트립으로 분리됨

        algs = []
        for x in zrows:
            a = engine._s(x.get("Alg"))
            if a not in algs:
                algs.append(a)
        for a in algs:
            key = f"{self.cur_zone}|{a}"
            coll = key in self.collapsed
            prows = [x for x in zrows if engine._s(x.get("Alg")) == a]
            # 섹션 헤더
            self._grid_row(linner, rinner, r, self.SEC_H)
            hdr = tk.Frame(linner, bg="#e2e8f0", cursor="hand2")
            hdr.grid(row=r, column=0, sticky="nsew")
            arrow = "▶" if coll else "▼"
            alg_lbl = tk.Label(hdr, text=f" {arrow}  {a or '(Alg 없음)'}", bg="#e2e8f0",
                               fg=self.p["text"], font=self.fonts["bold"], anchor="w")
            alg_lbl.pack(side="left", fill="x", expand=True)
            tk.Label(hdr, text=f"{len(prows)}개  ", bg="#e2e8f0", fg=self.p["muted"],
                     font=self.fonts["sub"]).pack(side="right")
            hdr.bind("<Button-1>", lambda e, k=key: self._toggle_alg(k))
            alg_lbl.bind("<Button-1>", lambda e, k=key: self._toggle_alg(k))
            hdr.bind("<Button-3>", lambda e, aa=a, w=alg_lbl, s=st: self._alg_menu(e, s, aa, w))
            alg_lbl.bind("<Button-3>", lambda e, aa=a, w=alg_lbl, s=st: self._alg_menu(e, s, aa, w))
            rsec = tk.Frame(rinner, bg="#e2e8f0")
            rsec.grid(row=r, column=0, sticky="nsew")
            r += 1
            if coll:
                continue
            for pr in prows:
                lines = self._row_lines(pr, others)
                rh = max(self.ROW_H, lines * self.LINE_PX + 10)
                self._grid_row(linner, rinner, r, rh)
                self._build_left_row(linner, r, st, pr, a)
                self._build_right_row(rinner, r, pr, others, lines)
                r += 1
            if not self.read_only:
                self._grid_row(linner, rinner, r, self.ROW_H)
                tk.Button(linner, text="＋ 파라미터 추가", relief="flat", bd=0,
                          bg=self.p["surface"], fg=self.p["primary"], font=self.fonts["bold"],
                          cursor="hand2", anchor="w", padx=12,
                          command=lambda s=st, aa=a: self._add_param(s, aa)).grid(
                    row=r, column=0, sticky="nsew")
                tk.Frame(rinner, bg=self.p["surface"]).grid(row=r, column=0, sticky="nsew")
                r += 1

        if not zrows:
            self._grid_row(linner, rinner, r, self.ROW_H)
            tk.Label(linner, text="이 Zone에 파라미터가 없습니다. ＋Alg / ＋파라미터로 추가하세요.",
                     bg=self.p["bg"], fg=self.p["muted"]).grid(row=r, column=0, sticky="w")
            r += 1
        # 줄바꿈 후 좌우 행 높이 정렬용 참조 저장
        self._pane_l, self._pane_r, self._pane_n = linner, rinner, r

    def _build_left_row(self, linner, r, st, pr, alg):
        machine = st["machine"]
        # grid 로 열 폭 고정 + 이름/값은 wraplength 로 줄바꿈(잘림 방지). 행 높이는
        # _equalize_panes 가 좌/우 실제 높이의 큰 쪽으로 맞춰 정렬한다.
        row = tk.Frame(linner, bg=self.p["surface"])
        row.grid(row=r, column=0, sticky="nsew")
        row.columnconfigure(2, minsize=self.NAME_W)
        row.columnconfigure(3, minsize=self.VAL_W)
        self._row_widgets.append((pr, row, alg))

        grip = tk.Label(row, text="⋮⋮", bg=self.p["surface"], fg=self.p["muted"],
                        font=self.fonts["bold"], cursor="fleur", width=2)
        grip.grid(row=0, column=0, sticky="n")
        grip.bind("<ButtonPress-1>", lambda e, p=pr: self._drag_start(e, p))
        grip.bind("<B1-Motion>", self._drag_move)
        grip.bind("<ButtonRelease-1>", lambda e, s=st: self._drag_drop(e, s))

        col = self.repo.cell_colors.get(_color_key(pr.row_id), "")
        chip = tk.Label(row, text=" ", bg=(col or self.p["border"]), width=2,
                        cursor="hand2", relief="flat")
        chip.grid(row=0, column=1, sticky="n", padx=(2, 6), pady=2)
        chip.bind("<Button-1>", lambda e, p=pr, w=chip: self._color_popup(p, w))
        chip.bind("<Button-3>", lambda e, p=pr: self._clear_color(p))

        name = engine._s(pr.get("Parameter")) or "(이름 없음)"
        # 이름 셀: 줄바꿈(잘림 방지). 색은 색칩으로만 표시.
        lbl = tk.Label(row, text=name, bg=self.p["surface"], fg=self.p["text"],
                       font=self.fonts["base"], anchor="nw", justify="left",
                       wraplength=self.NAME_W - 10)
        lbl.grid(row=0, column=2, sticky="nsew")
        lbl.bind("<Double-Button-1>",
                 lambda e, p=pr, w=lbl: self._edit_popup(
                     w, engine._s(p.get("Parameter")),
                     lambda new, pp=p: self._rename_param(pp, new)))
        for w in (row, lbl):
            w.bind("<Button-3>", lambda e, p=pr: self._param_menu(e, p))

        # 선택 호기 값 — 읽기 전용(스펙), 줄바꿈 표시
        valtext = engine._s(pr.get(machine))
        val = tk.Label(row, text=valtext, bg="#f8fafc", fg=self.p["text"],
                       font=self.fonts["base"], anchor="nw", justify="left",
                       wraplength=self.VAL_W - 10, relief="solid", bd=1)
        val.grid(row=0, column=3, sticky="nsew", padx=2, pady=1)

        has_note = bool(engine._s(pr.get("비고")))
        qbtn = tk.Button(row, text="?", width=2, relief="flat", bd=0, cursor="hand2",
                         font=self.fonts["bold"],
                         bg=(self.p["primary_lt"] if has_note else self.p["head_bg"]),
                         fg=(self.p["primary"] if has_note else self.p["muted"]))
        qbtn.config(command=lambda p=pr, w=qbtn: self._show_note(p, w))
        qbtn.grid(row=0, column=4, sticky="n", padx=(4, 2))

    def _build_right_row(self, rinner, r, pr, others, lines=1):
        f = tk.Frame(rinner, bg=self.p["surface"])
        f.grid(row=r, column=0, sticky="nsew")
        for m in others:
            # 고정폭 셀(헤더와 동일 COL_W) + 자동 줄바꿈 + 직접 수정. 엑셀형 격자
            v = engine._s(pr.get(m))
            cell = tk.Frame(f, width=self.COL_W, bg=self.p["surface"],
                            highlightthickness=1, highlightbackground="#d4dae2")
            cell.pack_propagate(False)
            cell.pack(side="left", fill="y")
            t = tk.Text(cell, wrap="word", font=self.fonts["sub"], fg="#6b7280",
                        bg=self.p["surface"], relief="flat", bd=0,
                        highlightthickness=0, padx=2, pady=1)
            if v:
                t.insert("1.0", v)
            if self.read_only or self.values_readonly:
                t.config(state="disabled")   # 값 확인은 읽기 전용(스펙)
            t.pack(fill="both", expand=True)
            t.bind("<FocusOut>",
                   lambda ev, p=pr, mm=m, w=t: self._set_value_str(p, mm, w.get("1.0", "end")))
            t._param = pr

    # ---- 스크롤 동기/스코프 -------------------------------------------
    def _yview_both(self, *args):
        # 좌측을 마스터로 스크롤하고 우측은 같은 위치(fraction)로 맞춤.
        # (우측은 가로 스크롤바 때문에 뷰포트가 더 짧아 units 스크롤이 어긋나므로 moveto 로 동기화)
        l = getattr(self, "_left_canvas", None)
        r = getattr(self, "_right_canvas", None)
        if l is not None:
            l.yview(*args)
            if r is not None:
                r.yview_moveto(l.yview()[0])

    def _scope_wheel(self, widget, *canvases, hcanvas=None):
        """포인터가 widget 위에 있을 때만 휠 스크롤(다른 창/빈영역 영향 차단).
        세로: 내용이 화면보다 짧으면 무시. 가로(hcanvas): Shift+휠 / 가로 휠."""
        def on_v(e):
            ref = canvases[0]
            bbox = ref.bbox("all")
            if not bbox or (bbox[3] - bbox[1]) <= ref.winfo_height():
                return
            n = int(-e.delta / 120) or (-1 if e.delta > 0 else 1)
            ref.yview_scroll(n, "units")
            top = ref.yview()[0]
            for c in canvases[1:]:   # 나머지 캔버스는 마스터 위치로 동기화
                c.yview_moveto(top)
            return "break"

        def on_h(e):
            if hcanvas is None:
                return
            n = int(-e.delta / 120) or (-1 if e.delta > 0 else 1)
            hcanvas.xview_scroll(n, "units")
            return "break"

        def on_h_linux(e):
            if hcanvas is None:
                return
            hcanvas.xview_scroll(-1 if e.num == 6 else 1, "units")
            return "break"

        def enter(_=None):
            self.bind_all("<MouseWheel>", on_v)
            if hcanvas is not None:
                self.bind_all("<Shift-MouseWheel>", on_h)
                # 리눅스 가로 휠(Button-6/7) — 일부 X 서버엔 없으므로 예외 무시
                for seq in ("<Button-6>", "<Button-7>"):
                    try:
                        self.bind_all(seq, on_h_linux)
                    except tk.TclError:
                        pass

        def leave(_=None):
            for seq in ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-6>", "<Button-7>"):
                try:
                    self.unbind_all(seq)
                except tk.TclError:
                    pass

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    # ====================================================================
    #  되돌리기 / 다시 (동작 단위 스냅샷)
    # ====================================================================
    def _snapshot_state(self) -> dict:
        rp = self.repo
        return {
            "rows": [(r.row_id, dict(r.values), r.display_order, list(r.aoi_units))
                     for r in rp.rows],
            "colors": dict(rp.cell_colors),
            "borders": dict(rp.cell_borders),
            "special": [dict(s) for s in rp.special],
            "reference": [list(x) for x in rp.reference],
            "aoi_units": list(rp.aoi_units),
        }

    def _restore_state(self, snap: dict) -> None:
        from .engine import ParamRow
        rp = self.repo
        rp.aoi_units = list(snap["aoi_units"])
        rp.rows = [ParamRow(values=dict(v), row_id=rid, display_order=do, aoi_units=list(au))
                   for (rid, v, do, au) in snap["rows"]]
        rp.cell_colors = dict(snap["colors"])
        rp.cell_borders = dict(snap["borders"])
        rp.special = [dict(s) for s in snap["special"]]
        rp.reference = [list(x) for x in snap["reference"]]

    def _push_undo(self) -> None:
        """변경 직전 상태를 되돌리기 스택에 저장."""
        if not self.repo:
            return
        self._undo.append(self._snapshot_state())
        self._undo = self._undo[-60:]
        self._redo.clear()

    def undo(self):
        if self.read_only or not self.repo or not self._undo:
            self._set_status("되돌릴 동작이 없습니다.")
            return
        self._redo.append(self._snapshot_state())
        self._restore_state(self._undo.pop())
        self.dirty = True
        self._close_note()
        self._set_status("되돌리기 완료")
        self._render()

    def redo(self):
        if self.read_only or not self.repo or not self._redo:
            self._set_status("다시 실행할 동작이 없습니다.")
            return
        self._undo.append(self._snapshot_state())
        self._restore_state(self._redo.pop())
        self.dirty = True
        self._close_note()
        self._set_status("다시 실행 완료")
        self._render()

    # ====================================================================
    #  추천값 / 색 팝업 / Zone·Alg 추가·삭제
    # ====================================================================
    def _color_popup(self, pr, anchor):
        """최근 사용자 지정 색 팔레트(껐다 켜도 유지) + 색 선택/해제."""
        if not self._guard():
            return
        self._close_note()
        pop = tk.Toplevel(self)
        self._note_pop = pop
        pop.wm_overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.wm_geometry(f"+{anchor.winfo_rootx()}+{anchor.winfo_rooty() + anchor.winfo_height() + 2}")
        frame = tk.Frame(pop, bg=self.p["surface"], highlightbackground=self.p["border"],
                         highlightthickness=1)
        frame.pack()
        tk.Label(frame, text="최근 색", bg=self.p["surface"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(anchor="w", padx=6, pady=(6, 0))
        sw = tk.Frame(frame, bg=self.p["surface"])
        sw.pack(padx=6, pady=4)
        palette = self.recent_colors or [HIGHLIGHT_YELLOW, "#fee2e2", "#dcfce7",
                                         "#dbeafe", "#fde68a"]
        for hx in palette[:10]:
            tk.Button(sw, bg=hx, width=2, height=1, relief="flat", bd=1, cursor="hand2",
                      command=lambda c=hx, p=pr: self._apply_color(p, c, pop)).pack(side="left", padx=2)
        bar = tk.Frame(frame, bg=self.p["surface"])
        bar.pack(fill="x", padx=6, pady=(0, 6))
        tk.Button(bar, text="강조(노랑)", relief="flat", bd=0, bg=HIGHLIGHT_YELLOW,
                  fg="#5a4b00", cursor="hand2",
                  command=lambda p=pr: self._apply_color(p, HIGHLIGHT_YELLOW, pop)).pack(side="left", padx=2)
        tk.Button(bar, text="다른 색…", relief="flat", bd=0, bg=self.p["head_bg"],
                  fg=self.p["text"], cursor="hand2",
                  command=lambda p=pr: self._pick_color(p, pop)).pack(side="left", padx=2)
        tk.Button(bar, text="색 없음", relief="flat", bd=0, bg=self.p["head_bg"],
                  fg=self.p["danger"], cursor="hand2",
                  command=lambda p=pr: (self._clear_color(p), pop.destroy())).pack(side="left", padx=2)
        pop.bind("<Escape>", lambda e: pop.destroy())

    def _apply_color(self, pr, hx, pop=None):
        if not self._guard():
            return
        self._push_undo()
        self.repo.cell_colors[_color_key(pr.row_id)] = hx
        self._remember_color(hx)
        self.dirty = True
        if pop is not None:
            pop.destroy()
        self._render()

    def _zone_menu(self, e, st, zone, anchor=None):
        m = tk.Menu(self, tearoff=0)
        st_ = "disabled" if self.read_only else "normal"
        m.add_command(label="Zone 이름 수정", state=st_,
                      command=lambda: self._edit_popup(
                          anchor or self, zone,
                          lambda new: self._rename_zone(st, zone, new)))
        m.add_command(label=f"Zone '{zone}' 삭제", state=st_,
                      command=lambda: self._delete_zone(st, zone))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _alg_menu(self, e, st, alg, anchor=None):
        m = tk.Menu(self, tearoff=0)
        st_ = "disabled" if self.read_only else "normal"
        m.add_command(label="Alg 이름 수정", state=st_,
                      command=lambda: self._edit_popup(
                          anchor or self, alg,
                          lambda new: self._rename_alg(st, alg, new)))
        m.add_command(label=f"Alg '{alg}' 삭제", state=st_,
                      command=lambda: self._delete_alg(st, alg))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _add_zone(self, st):
        if not self._guard():
            return
        name = simpledialog_safe(self, "새 Zone 이름")
        if not name:
            return
        self._push_undo()
        pr = self.repo.add_row({"PI": st["pi"], "Recipe": st["recipe"], "Zone": name,
                                "Alg": "", "Parameter": ""})
        self.cur_zone = name
        self.dirty = True
        self._set_status(f"Zone 추가: {name}")
        self._render()

    def _add_alg(self, st):
        if not self._guard():
            return
        if not self.cur_zone:
            messagebox.showinfo("Alg 추가", "먼저 Zone을 선택/추가하세요.")
            return
        name = simpledialog_safe(self, "새 Alg 이름")
        if not name:
            return
        self._push_undo()
        # 현재 Zone 마지막 행 아래에 삽입
        idx = -1
        for i, r in enumerate(self.repo.rows):
            if (engine._s(r.get("PI")) == st["pi"]
                    and engine._s(r.get("Recipe")) == st["recipe"]
                    and engine._s(r.get("Zone")) == self.cur_zone):
                idx = i
        vals = {"PI": st["pi"], "Recipe": st["recipe"], "Zone": self.cur_zone,
                "Alg": name, "Parameter": ""}
        if idx >= 0:
            self.repo.insert_row_after(idx, vals)
        else:
            self.repo.add_row(vals)
        self.dirty = True
        self._set_status(f"Alg 추가: {name}")
        self._render()

    def _delete_zone(self, st, zone):
        if not self._guard():
            return
        if not messagebox.askyesno("Zone 삭제",
                                   f"Zone '{zone}'의 모든 파라미터를 삭제할까요? (현재 Recipe)"):
            return
        self._push_undo()
        ids = [r.row_id for r in self._filtered_rows(st)
               if engine._s(r.get("Zone")) == zone]
        for rid in ids:
            self.repo.remove_row(rid)
        if self.cur_zone == zone:
            self.cur_zone = None
        self.dirty = True
        self._set_status(f"Zone 삭제: {zone} ({len(ids)}개 파라미터)")
        self._render()

    def _delete_alg(self, st, alg):
        if not self._guard():
            return
        if not messagebox.askyesno("Alg 삭제",
                                   f"현재 Zone의 Alg '{alg}' 파라미터를 삭제할까요?"):
            return
        self._push_undo()
        ids = [r.row_id for r in self._filtered_rows(st)
               if engine._s(r.get("Zone")) == self.cur_zone
               and engine._s(r.get("Alg")) == alg]
        for rid in ids:
            self.repo.remove_row(rid)
        self.dirty = True
        self._set_status(f"Alg 삭제: {alg} ({len(ids)}개 파라미터)")
        self._render()

    # ---- 값/색/추가/삭제 ----------------------------------------------
    def _set_value(self, pr, machine, var):
        self._set_value_str(pr, machine, var.get())

    def _set_value_str(self, pr, machine, new):
        if self.read_only:
            return
        new = engine._s(new)
        if engine._s(pr.get(machine)) != new:
            self._push_undo()
            pr.set(machine, new if new != "" else None)
            self.dirty = True
            self._set_status(f"변경됨: {engine._s(pr.get('Parameter'))} [{machine}] = {new}")

    def _row_lines(self, pr, others) -> int:
        """좌측 파라미터명/값 + 우측 셀들 중 가장 긴 것 기준 필요한 줄 수(초기 추정).
        최종 행 높이는 _equalize_panes 가 실제 위젯 높이로 다시 맞춘다."""
        import math
        mx = 1
        name = engine._s(pr.get("Parameter"))
        if name:
            mx = max(mx, math.ceil(len(name) / 16))     # 좌측 이름 줄바꿈 반영
        for m in others:
            v = engine._s(pr.get(m))
            if v:
                mx = max(mx, math.ceil(len(v) / self.CELL_CHARS))
        return min(mx, self.MAX_LINES)

    # ---- 인라인 편집 팝업(셀 위 떠있는 Entry) -------------------------
    def _edit_popup(self, widget, current, on_commit):
        if not self._guard():
            return
        top = tk.Toplevel(self)
        top.wm_overrideredirect(True)
        top.attributes("-topmost", True)
        top.wm_geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty()}")
        var = tk.StringVar(value=current)
        ent = tk.Entry(top, textvariable=var, font=self.fonts["base"],
                       width=max(20, len(current) + 6), relief="solid", bd=1)
        ent.pack()
        ent.focus_set()
        ent.select_range(0, "end")

        def commit(_=None):
            val = var.get().strip()
            top.destroy()
            on_commit(val)

        ent.bind("<Return>", commit)
        ent.bind("<Escape>", lambda e: top.destroy())
        ent.bind("<FocusOut>", lambda e: top.destroy())

    def _rename_zone(self, st, old, new):
        if not new or new == old:
            return
        self._push_undo()
        for r in self._filtered_rows(st):
            if engine._s(r.get("Zone")) == old:
                r.set("Zone", new)
        if self.cur_zone == old:
            self.cur_zone = new
        self.dirty = True
        self._set_status(f"Zone 이름 변경: {old} → {new} (현재 Recipe)")
        self._render()

    def _rename_alg(self, st, old, new):
        if not new or new == old:
            return
        self._push_undo()
        for r in self._filtered_rows(st):
            if engine._s(r.get("Zone")) == self.cur_zone and engine._s(r.get("Alg")) == old:
                r.set("Alg", new)
        # 접힘 상태 키 이동
        ok, nk = f"{self.cur_zone}|{old}", f"{self.cur_zone}|{new}"
        if ok in self.collapsed:
            self.collapsed.discard(ok)
            self.collapsed.add(nk)
        self.dirty = True
        self._set_status(f"Alg 이름 변경: {old} → {new} (현재 Zone)")
        self._render()

    def _rename_param(self, pr, new):
        if not new or new == engine._s(pr.get("Parameter")):
            return
        self._push_undo()
        pr.set("Parameter", new)
        self.dirty = True
        self._set_status(f"파라미터 이름 변경: {new}")
        self._render()

    # ---- 우클릭 메뉴 + 변경 내역 창 -----------------------------------
    def _param_menu(self, e, pr):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="변경 내역 보기", command=lambda: self._show_history(pr))
        m.add_separator()
        if not self.read_only:
            m.add_command(label="이 파라미터 삭제", command=lambda: self._delete_param(pr))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _delete_param(self, pr):
        if not self._guard():
            return
        if not messagebox.askyesno("삭제",
                                   f"'{engine._s(pr.get('Parameter'))}' 파라미터를 삭제할까요?"):
            return
        self._push_undo()
        self.repo.remove_row(pr.row_id)
        self.dirty = True
        self._render()

    def _show_history(self, pr):
        recipe = engine._s(pr.get("Recipe"))
        zone = engine._s(pr.get("Zone"))
        alg = engine._s(pr.get("Alg"))
        param = engine._s(pr.get("Parameter"))
        recs = [h for h in self.repo.history
                if engine._s(h.get("Parameter")) == param
                and engine._s(h.get("Recipe")) == recipe
                and engine._s(h.get("Zone")) == zone
                and engine._s(h.get("Alg")) == alg]
        recs.reverse()  # 최신순

        win = tk.Toplevel(self)
        win.title(f"변경 내역 — {param}")
        win.geometry("820x460")
        win.configure(bg=self.p["bg"])
        tk.Label(win, text=f"{recipe} ▸ {zone} ▸ {alg} ▸ {param}",
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["bold"],
                 anchor="w").pack(fill="x", padx=12, pady=(10, 4))

        cols = ("일시", "호기", "이전값", "새값", "변경자", "유형")
        tv = ttk.Treeview(win, columns=cols, show="headings")
        widths = (140, 70, 130, 130, 90, 110)
        for c, w in zip(cols, widths):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor="w")
        for h in recs:
            tv.insert("", "end", values=(
                engine._s(h.get("Update Date")), engine._s(h.get("AOI")),
                engine._s(h.get("Old Value")), engine._s(h.get("New Value")),
                engine._s(h.get("Updated By")), engine._s(h.get("Change Type"))))
        vsb = ttk.Scrollbar(win, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vsb.set)
        tv.bind("<MouseWheel>", lambda e: tv.yview_scroll(int(-e.delta / 120), "units"))
        tv.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        vsb.pack(side="right", fill="y", pady=(0, 12), padx=(0, 12))
        if not recs:
            tk.Label(win, text="이 파라미터의 변경 내역이 없습니다.",
                     bg=self.p["bg"], fg=self.p["muted"]).place(relx=0.5, rely=0.5, anchor="center")

    # ---- 비고 메모 팝업(엑셀 메모처럼) --------------------------------
    def _close_note(self):
        pop = getattr(self, "_note_pop", None)
        if pop is not None:
            try:
                pop.destroy()
            except Exception:
                pass
            self._note_pop = None

    def _show_note(self, pr, anchor):
        # 이미 열린 비고 팝업이 있으면 먼저 닫는다(하나만 유지)
        self._close_note()
        note = engine._s(pr.get("비고"))
        pop = tk.Toplevel(self)
        self._note_pop = pop
        pop.wm_overrideredirect(True)
        pop.attributes("-topmost", True)
        # ? 버튼 바로 아래에 위치
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 2
        pop.wm_geometry(f"+{x}+{y}")
        frame = tk.Frame(pop, bg="#fff8c4", highlightbackground="#caa500",
                         highlightthickness=1)
        frame.pack()
        tk.Label(frame, text=f"비고 — {engine._s(pr.get('Parameter'))}", bg="#fff8c4",
                 fg="#7a5d00", font=self.fonts["sub"], anchor="w").pack(
            fill="x", padx=8, pady=(6, 0))
        txt = tk.Text(frame, width=42, height=6, font=self.fonts["base"],
                      bg="#fffce8", fg=self.p["text"], relief="flat", wrap="word")
        txt.insert("1.0", note or "(비고 없음 — 더블클릭해 입력)")
        txt.config(state="disabled")
        txt.pack(padx=8, pady=6)

        bar = tk.Frame(frame, bg="#fff8c4")
        bar.pack(fill="x", padx=8, pady=(0, 6))
        state = {"editing": False}

        def enable_edit(_=None):
            if self.read_only or state["editing"]:
                return
            state["editing"] = True
            txt.config(state="normal", bg="#ffffff")
            if not note:
                txt.delete("1.0", "end")
            txt.focus_set()
            save_btn.pack(side="right")

        def save(_=None):
            new = txt.get("1.0", "end").strip()
            self._push_undo()
            pr.set("비고", new if new else None)
            self.dirty = True
            pop.destroy()
            self._set_status(f"비고 저장: {engine._s(pr.get('Parameter'))}")
            self._render()

        txt.bind("<Double-Button-1>", enable_edit)
        save_btn = tk.Button(bar, text="저장", relief="flat", bd=0,
                             bg=self.p["primary"], fg="#ffffff", padx=10,
                             cursor="hand2", command=save)
        tk.Button(bar, text="닫기", relief="flat", bd=0, bg="#e8e0b0",
                  fg="#7a5d00", padx=10, cursor="hand2",
                  command=pop.destroy).pack(side="right", padx=(0, 4))
        tk.Label(bar, text="더블클릭=수정", bg="#fff8c4", fg="#9a7d20",
                 font=self.fonts["sub"]).pack(side="left")
        pop.bind("<Escape>", lambda e: pop.destroy())

    def _pick_color(self, pr, pop=None):
        if not self._guard():
            return
        rgb, hx = colorchooser.askcolor(title="파라미터 색 선택",
                                        initialcolor=self.recent_colors[0]
                                        if self.recent_colors else "#FFF24D")
        if pop is not None:
            pop.destroy()
        if not hx:
            return
        self._push_undo()
        self.repo.cell_colors[_color_key(pr.row_id)] = hx
        self._remember_color(hx)
        self.dirty = True
        self._render()

    def _clear_color(self, pr):
        if not self._guard():
            return
        if _color_key(pr.row_id) not in self.repo.cell_colors:
            return
        self._push_undo()
        self.repo.cell_colors.pop(_color_key(pr.row_id), None)
        self.dirty = True
        self._render()

    def _highlight_focused(self):
        if self.read_only:
            return
        w = self.focus_get()
        pr = getattr(w, "_param", None)
        if pr is None:
            return
        self._push_undo()
        self.repo.cell_colors[_color_key(pr.row_id)] = HIGHLIGHT_YELLOW
        self._remember_color(HIGHLIGHT_YELLOW)
        self.dirty = True
        self._render()

    def _remember_color(self, hx):
        if hx in self.recent_colors:
            self.recent_colors.remove(hx)
        self.recent_colors.insert(0, hx)
        self.recent_colors = self.recent_colors[:10]
        self._cfg["recent_colors"] = self.recent_colors
        save_config(self._cfg)

    def _add_param(self, st, alg):
        if not self._guard():
            return
        self._push_undo()
        # 같은 Zone/Alg 마지막 행 아래에 삽입(메타 상속)
        idx = -1
        for i, r in enumerate(self.repo.rows):
            if (engine._s(r.get("PI")) == st["pi"]
                    and engine._s(r.get("Recipe")) == st["recipe"]
                    and engine._s(r.get("Zone")) == self.cur_zone
                    and engine._s(r.get("Alg")) == alg):
                idx = i
        vals = {"PI": st["pi"], "Recipe": st["recipe"], "Zone": self.cur_zone,
                "Alg": alg, "Parameter": ""}
        if idx >= 0:
            self.repo.insert_row_after(idx, vals)
        else:
            self.repo.add_row(vals)
        self.dirty = True
        self._render()
        # 새 파라미터 이름 입력 안내
        new = simpledialog_safe(self, "새 파라미터 이름")
        if new:
            # 방금 추가한 행(빈 이름) 찾아 이름 지정
            for r in self.repo.rows:
                if (engine._s(r.get("Zone")) == self.cur_zone
                        and engine._s(r.get("Alg")) == alg
                        and engine._s(r.get("Parameter")) == ""):
                    r.set("Parameter", new)
                    break
            self._render()

    # ---- 드래그 이동(순서변경 / 다른 Alg 이동) ------------------------
    def _drag_start(self, e, pr):
        if self.read_only:
            return
        self._drag = {"row": pr, "float": None}

    def _drag_move(self, e):
        if not self._drag:
            return
        if self._drag["float"] is None:
            f = tk.Toplevel(self)
            f.wm_overrideredirect(True)
            f.attributes("-alpha", 0.85)
            tk.Label(f, text=f"⋮⋮ {engine._s(self._drag['row'].get('Parameter')) or '(이름 없음)'}",
                     bg=self.p["primary"], fg="#ffffff", padx=10, pady=4).pack()
            self._drag["float"] = f
        self._drag["float"].wm_geometry(f"+{e.x_root + 12}+{e.y_root + 8}")

    def _drag_drop(self, e, st):
        if not self._drag:
            return
        if self._drag["float"] is not None:
            self._drag["float"].destroy()
        src = self._drag["row"]
        self._drag = None
        # 커서 y 위치로 드롭 대상 행/Alg 결정
        target = None
        for pr, frame, alg in self._row_widgets:
            try:
                top = frame.winfo_rooty()
                bot = top + frame.winfo_height()
            except Exception:
                continue
            if top <= e.y_root <= bot:
                target = (pr, alg)
                break
        if not target or target[0] is src:
            return
        tpr, talg = target
        self._push_undo()
        # 다른 Alg 로 이동 시 Alg 갱신
        if engine._s(src.get("Alg")) != talg:
            src.set("Alg", talg)
        # display_order 를 대상 이웃 사이로
        self._reorder(src, tpr)
        self.dirty = True
        self._render()

    def _reorder(self, src, tpr):
        rows = self.repo.rows
        if src in rows:
            rows.remove(src)
        idx = rows.index(tpr)
        rows.insert(idx, src)
        # display_order 재부여(전역 순번)
        for i, r in enumerate(rows):
            r.display_order = i + 1

    # ====================================================================
    #  특이사항 / 참고자료 뷰 (tksheet — 열너비조절/자동줄바꿈/색칠/행열삭제)
    # ====================================================================
    def _make_table(self, headers, data, col_edit=False, force_edit=False):
        s = Sheet(self.body, theme="light blue",
                  show_x_scrollbar=True, show_y_scrollbar=True,
                  font=(self.p["family"], 10, "normal"),
                  header_font=(self.p["family"], 10, "bold"))
        if headers is not None:
            s.headers(headers)
        s.set_sheet_data(data, reset_col_positions=True)
        s.set_options(table_wrap="w", header_wrap="w",
                      show_vertical_grid=True, show_horizontal_grid=True,
                      edit_cell_return="", edit_cell_tab="")
        binds = ["single_select", "drag_select", "row_select", "column_select",
                 "arrowkeys", "copy", "rc_select", "column_width_resize",
                 "double_click_column_resize", "row_height_resize"]
        # 특이사항/참고자료/장비IP 는 독립 파일이라 값 확인 읽기전용과 무관하게 편집 가능
        if force_edit or not self.read_only:
            binds += ["paste", "cut", "delete", "edit_cell",
                      "rc_insert_row", "rc_delete_row"]
            if col_edit:
                binds += ["rc_insert_column", "rc_delete_column"]
        s.enable_bindings(*binds)
        return s

    def _fit_table_heights(self, s, ncol):
        try:
            n = s.get_total_rows()
        except Exception:
            return
        for r in range(min(n, 400)):
            try:
                h = max((s.MT.get_wrapped_cell_height(r, c) for c in range(ncol)), default=28)
            except Exception:
                h = 28
            try:
                s.row_height(row=r, height=max(28, h))
            except Exception:
                pass
        try:
            s.redraw()
        except Exception:
            pass

    def _toolbar(self, kind):
        bar = tk.Frame(self.body, bg=self.p["bg"])
        bar.pack(side="top", fill="x", padx=10, pady=(8, 0))
        tk.Label(bar, text="선택 셀:", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left", padx=(0, 4))
        tk.Button(bar, text="강조(노랑)", relief="flat", bd=0, bg=HIGHLIGHT_YELLOW,
                  fg="#5a4b00", cursor="hand2",
                  command=lambda: self._table_fill(kind, HIGHLIGHT_YELLOW)).pack(side="left", padx=2)
        tk.Button(bar, text="색 선택", relief="flat", bd=0, bg=self.p["head_bg"],
                  fg=self.p["text"], cursor="hand2",
                  command=lambda: self._table_fill(kind, None)).pack(side="left", padx=2)
        tk.Button(bar, text="색 없음", relief="flat", bd=0, bg=self.p["head_bg"],
                  fg=self.p["danger"], cursor="hand2",
                  command=lambda: self._table_fill(kind, "CLEAR")).pack(side="left", padx=2)
        tk.Label(bar, text="  (열 경계 드래그=너비 · 우클릭=행/열 삽입·삭제 · 셀 직접 입력)",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"]).pack(side="left", padx=8)
        return bar

    def _table_cells(self, s):
        try:
            cells = list(s.get_selected_cells())
        except Exception:
            cells = []
        if not cells:
            sel = s.get_currently_selected()
            if sel and getattr(sel, "row", None) is not None:
                cells = [(sel.row, sel.column)]
        return cells

    def _table_fill(self, kind, color):
        s = self._cur_sheet
        cells = self._table_cells(s)
        if not cells:
            self._set_status("색을 칠할 셀을 먼저 선택하세요.")
            return
        if color is None:
            _, color = colorchooser.askcolor(
                title="셀 색 선택",
                initialcolor=self.recent_colors[0] if self.recent_colors else "#FFF24D")
            if not color:
                return
        cc = self.special_colors if kind == "special" else self.ref_colors
        for (r, c) in cells:
            if color == "CLEAR":
                cc.pop((r, c), None)
            else:
                cc[(r, c)] = color
        if color not in (None, "CLEAR"):
            self._remember_color(color)
        self._save_refdata()          # 색상 즉시 파일에 저장
        self._render()

    def _apply_table_colors(self, s, kind):
        cc = self.special_colors if kind == "special" else self.ref_colors
        for (r, c), color in cc.items():
            try:
                s.highlight_cells(row=int(r), column=int(c), bg=color,
                                  fg=self._fg_for(color), redraw=False)
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _fg_for(hexcolor):
        try:
            h = str(hexcolor).lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"
        except Exception:
            return "#111111"

    def _need_save_dir(self) -> bool:
        if self.save_dir:
            return True
        tk.Label(self.body, text="먼저 저장 폴더를 지정하세요(⋯파일 메뉴).",
                 bg=self.p["bg"], fg=self.p["muted"]).pack(pady=30)
        return False

    def _view_special(self):
        """특이사항 = 저장폴더의 특이사항.xlsx (편집·셀 색상 즉시 저장)."""
        if not self._need_save_dir():
            return
        from .engine import SPECIAL_BOOL_COL, SPECIAL_HEADERS
        self._toolbar("special")
        btnbar = tk.Frame(self.body, bg=self.p["bg"])
        btnbar.pack(side="top", fill="x", padx=10)
        tk.Button(btnbar, text="＋ 특이사항(행) 추가", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["primary"], font=self.fonts["bold"],
                  cursor="hand2", command=self._special_add).pack(side="left", pady=4)
        tk.Label(btnbar, text="  (특이사항.xlsx 에 자동 저장)", bg=self.p["bg"],
                 fg=self.p["muted"], font=self.fonts["sub"]).pack(side="left")
        bcol = SPECIAL_HEADERS.index(SPECIAL_BOOL_COL)
        data = []
        for rec in self.special_rows:
            row = []
            for h in SPECIAL_HEADERS:
                v = rec.get(h)
                if h == SPECIAL_BOOL_COL:
                    v = "☑" if bool(v) else "☐"
                elif h == "일자":
                    v = engine.format_kdate(v)[0]
                else:
                    v = engine._s(v)
                row.append(v)
            data.append(row)
        s = self._make_table(SPECIAL_HEADERS, data, col_edit=False, force_edit=True)
        s.pack(side="top", fill="both", expand=True, padx=10, pady=8)
        for i, w in enumerate((95, 80, 130, 55, 70, 110, 150, 70, 340)):
            try:
                s.column_width(column=i, width=w)
            except Exception:
                pass
        s.extra_bindings([("end_edit_cell", lambda e: self._special_sync()),
                          ("rc_delete_row", lambda e: self.after(10, self._special_sync)),
                          ("rc_insert_row", lambda e: self.after(10, self._special_sync))])
        s.MT.bind("<ButtonRelease-1>",
                  lambda e: self.after(10, lambda: self._special_toggle(s, bcol)), add="+")
        s.CH.bind("<ButtonRelease-1>",
                  lambda e: self.after(15, lambda: self._fit_table_heights(s, len(SPECIAL_HEADERS))), add="+")
        self._cur_sheet, self._cur_kind = s, "special"
        self._apply_table_colors(s, "special")
        self._fit_table_heights(s, len(SPECIAL_HEADERS))

    def _special_sync(self):
        if self._cur_kind != "special":
            return
        from .engine import SPECIAL_BOOL_COL, SPECIAL_HEADERS
        data = self._cur_sheet.get_sheet_data()
        new = []
        for row in data:
            rec = {}
            for c, h in enumerate(SPECIAL_HEADERS):
                v = row[c] if c < len(row) else ""
                if h == SPECIAL_BOOL_COL:
                    rec[h] = (engine._s(v) == "☑")
                else:
                    rec[h] = engine._s(v) or None
            new.append(rec)
        self.special_rows = new
        self._save_refdata()
        self._set_status("특이사항 저장됨")

    def _special_toggle(self, s, bcol):
        sel = s.get_currently_selected()
        if not sel or getattr(sel, "column", None) != bcol:
            return
        cur = s.get_cell_data(sel.row, bcol)
        s.set_cell_data(sel.row, bcol, "☐" if engine._s(cur) == "☑" else "☑")
        s.redraw()
        self._special_sync()

    def _special_add(self):
        from .engine import SPECIAL_HEADERS
        self.special_rows.append({h: (False if h == "종료 여부" else None)
                                  for h in SPECIAL_HEADERS})
        self._save_refdata()
        self._render()

    def _view_reference(self):
        """참고자료 = 저장폴더의 참고자료.xlsx (사람 자유 메모, 셀 색상 저장)."""
        if not self._need_save_dir():
            return
        self._toolbar("reference")
        btnbar = tk.Frame(self.body, bg=self.p["bg"])
        btnbar.pack(side="top", fill="x", padx=10)
        tk.Button(btnbar, text="＋ 행 추가", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["primary"], font=self.fonts["bold"], cursor="hand2",
                  command=self._ref_add).pack(side="left", pady=4)
        tk.Label(btnbar, text="  (자유 메모 · 참고자료.xlsx 에 자동 저장 · 우클릭=행/열 삽입·삭제)",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"]).pack(side="left")
        grid = [list(r) for r in self.ref_grid] or [list(refdata.REF_DEFAULT_HEADERS)]
        ncol = max((len(r) for r in grid), default=3)
        grid = [row + [""] * (ncol - len(row)) for row in grid]
        s = self._make_table(None, [[engine._s(c) for c in row] for row in grid],
                             col_edit=True, force_edit=True)
        s.pack(side="top", fill="both", expand=True, padx=10, pady=8)
        for i, w in enumerate((160, 300, 200, 160)):
            if i < ncol:
                try:
                    s.column_width(column=i, width=w)
                except Exception:
                    pass
        s.extra_bindings([("end_edit_cell", lambda e: self._ref_sync()),
                          ("rc_delete_row", lambda e: self.after(10, self._ref_sync)),
                          ("rc_insert_row", lambda e: self.after(10, self._ref_sync)),
                          ("rc_delete_column", lambda e: self.after(10, self._ref_sync)),
                          ("rc_insert_column", lambda e: self.after(10, self._ref_sync))])
        s.CH.bind("<ButtonRelease-1>",
                  lambda e: self.after(15, lambda: self._fit_table_heights(s, ncol)), add="+")
        self._cur_sheet, self._cur_kind = s, "reference"
        self._apply_table_colors(s, "reference")
        self._fit_table_heights(s, ncol)

    def _ref_sync(self):
        if self._cur_kind != "reference":
            return
        self.ref_grid = [[engine._s(c) for c in row]
                         for row in self._cur_sheet.get_sheet_data()]
        self._save_refdata()
        self._set_status("참고자료 저장됨")

    def _ref_add(self):
        ncol = max((len(r) for r in self.ref_grid), default=3)
        self.ref_grid.append([""] * ncol)
        self._render()

    def _view_ip(self):
        """장비 IP 주소 = 저장폴더의 장비 IP 주소.xlsx (호기·IP, 호기 버튼의 기준)."""
        if not self._need_save_dir():
            return
        btnbar = tk.Frame(self.body, bg=self.p["bg"])
        btnbar.pack(side="top", fill="x", padx=10, pady=(8, 0))
        tk.Button(btnbar, text="＋ 호기(행) 추가", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["primary"], font=self.fonts["bold"], cursor="hand2",
                  command=self._ip_add).pack(side="left", pady=4)
        tk.Label(btnbar, text="  (호기·IP · 장비 IP 주소.xlsx 에 자동 저장 · 호기 버튼·값 "
                              "업데이트의 기준)", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left")
        headers = refdata.IP_HEADERS
        data = [[engine._s(r.get("호기")), engine._s(r.get("IP"))]
                for r in self.ip_rows] or [["", ""]]
        s = self._make_table(headers, data, col_edit=False, force_edit=True)
        s.pack(side="top", fill="both", expand=True, padx=10, pady=8)
        for i, w in enumerate((160, 220)):
            try:
                s.column_width(column=i, width=w)
            except Exception:
                pass
        s.extra_bindings([("end_edit_cell", lambda e: self._ip_sync()),
                          ("rc_delete_row", lambda e: self.after(10, self._ip_sync)),
                          ("rc_insert_row", lambda e: self.after(10, self._ip_sync))])
        self._cur_sheet, self._cur_kind = s, "ip"
        self._fit_table_heights(s, len(headers))

    def _ip_sync(self):
        if self._cur_kind != "ip":
            return
        rows = []
        for row in self._cur_sheet.get_sheet_data():
            ho = engine._s(row[0]).strip() if len(row) > 0 else ""
            if not ho:
                continue
            rows.append({"호기": ho,
                         "IP": engine._s(row[1]).strip() if len(row) > 1 else ""})
        self.ip_rows = rows
        self._save_refdata()
        self._set_status("장비 IP 저장됨(호기 목록 갱신)")

    def _ip_add(self):
        self.ip_rows.append({"호기": "", "IP": ""})
        self._render()

    # ====================================================================
    #  파일 / 저장 / 잠금
    # ====================================================================
    # ====================================================================
    #  로딩 모달 + 백그라운드 실행(응답없음 방지 — 스펙 1.1.3)
    # ====================================================================
    def _run_busy(self, title, work, on_done, parent=None):
        """'로딩 중' 모달을 띄우고 work()를 백그라운드 스레드에서 실행한다.
        work: 인자 없는 함수 — **GUI 위젯을 절대 건드리지 않는** 순수 작업만
              (파싱/취합/저장/비교 등). 반환값은 on_done(ok, result)로 전달.
        on_done(ok, result): 메인 스레드에서 호출(위젯 조작 안전). ok=False면
              result 는 예외 객체."""
        parent = parent or self
        win = tk.Toplevel(parent)
        win.title(title)
        win.configure(bg=self.p["bg"])
        win.transient(parent)
        win.resizable(False, False)
        tk.Label(win, text="⏳ " + title, bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["bold"]).pack(padx=28, pady=(18, 4))
        tk.Label(win, text="잠시만 기다려 주세요…", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(padx=28, pady=(0, 6))
        pb = ttk.Progressbar(win, mode="indeterminate", length=280)
        pb.pack(padx=28, pady=(0, 18))
        pb.start(12)
        try:
            win.grab_set()
        except tk.TclError:
            pass
        box = {"done": False, "ok": False, "res": None}

        def runner():
            try:
                box["res"], box["ok"] = work(), True
            except Exception as e:  # noqa: BLE001
                box["res"], box["ok"] = e, False
            finally:
                box["done"] = True

        threading.Thread(target=runner, daemon=True).start()

        def poll():
            if box["done"]:
                pb.stop()
                try:
                    win.grab_release()
                except tk.TclError:
                    pass
                win.destroy()
                on_done(box["ok"], box["res"])
                return
            win.after(90, poll)

        win.after(90, poll)

    # ====================================================================
    #  '파라미터 값 확인' 상단 액션 바 + ⋯파일(특이사항/참고자료만)
    # ====================================================================
    def _param_actionbar(self):
        bar = tk.Frame(self.body, bg=self.p["head_bg"])
        bar.pack(side="top", fill="x")
        tk.Button(bar, text="🔄 파라미터 값 업데이트", relief="flat", bd=0,
                  bg=self.p["primary"], fg="#ffffff", padx=12, pady=5, cursor="hand2",
                  command=self._update_values_dialog).pack(side="left", padx=(10, 4), pady=5)
        tk.Button(bar, text="🕑 파라미터 이력 확인", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=12, pady=5, cursor="hand2",
                  command=self._history_dialog).pack(side="left", padx=4, pady=5)
        tk.Button(bar, text="↻ 최신 취합 새로고침", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=12, pady=5, cursor="hand2",
                  command=self._refresh_view).pack(side="left", padx=4, pady=5)
        tk.Label(bar, text="  (최신 '파라미터 값 취합'을 자동 표시 · 값 읽기전용)",
                 bg=self.p["head_bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left", padx=6)

    def _open_collation_view(self, path):
        """취합/양식 파일을 값 확인 화면(읽기전용 병합)으로 연다."""
        try:
            self.repo = collate.load_as_repo(path, self._all_machines())
            self.path, self.read_only = path, True
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("열기 실패", str(e))
            return
        self.view = "param"
        self._sync_tab_style()
        self.navigate(screen="s0")

    def _refresh_view(self):
        self._load_refdata()
        self._load_latest_collate()
        self._render()

    def _change_save_dir(self):
        if self._choose_save_dir():
            self._load_refdata()
            self._load_latest_collate()
            self._render()

    def _file_menu(self):
        """⋯파일 — 저장 폴더 변경 / 참고자료·특이사항 다시 읽기 / 장비 다운로드."""
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="저장 폴더 변경…", command=self._change_save_dir)
        m.add_command(label="참고자료·특이사항 다시 읽기", command=self._refresh_view)
        m.add_separator()
        m.add_command(label="장비 폴더에서 파라미터 다운로드…", command=self._download_dialog)
        try:
            m.tk_popup(self.btn_file.winfo_rootx(),
                       self.btn_file.winfo_rooty() + self.btn_file.winfo_height())
        finally:
            m.grab_release()

    def save(self):
        """‘값 확인’은 읽기 전용. 특이사항/참고자료는 편집 시 자동 저장된다."""
        if self.view in ("special", "reference"):
            self._save_refdata()
            self._set_status("특이사항/참고자료 저장됨")
            return
        messagebox.showinfo(
            "저장",
            "‘파라미터 값 확인’은 읽기 전용입니다(값은 ‘값 업데이트’로 채웁니다).\n"
            "특이사항·참고자료 탭의 내용은 편집 시 자동 저장됩니다.")

    def _download_dialog(self):
        win = tk.Toplevel(self)
        win.title("장비 폴더에서 파라미터 다운로드")
        win.geometry("960x640")
        win.configure(bg=self.p["bg"])
        self._dl_win = win

        tk.Label(win, text="장비 폴더에서 파라미터 원본 가져오기", bg=self.p["bg"],
                 fg=self.p["text"], font=self.fonts["title"]).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(win, text="호기 경로를 한 줄에 하나씩 입력 → [후보 검색] → Recipe·변형(x5/x20) 선택 → [다운로드]. "
                          "원본은 읽기만 하며 수정하지 않습니다. (현재 RDL만 지원, PI 추후)",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"]).pack(anchor="w", padx=14)

        top = tk.Frame(win, bg=self.p["bg"])
        top.pack(fill="x", padx=14, pady=8)
        tk.Label(top, text="호기 경로(여러 개, 예: P:\\AOI-18)", bg=self.p["bg"],
                 fg=self.p["text"], font=self.fonts["sub"]).pack(anchor="w")
        self._dl_paths = tk.Text(top, height=4, font=self.fonts["base"], relief="solid", bd=1)
        self._dl_paths.pack(fill="x", pady=(2, 6))

        row = tk.Frame(top, bg=self.p["bg"])
        row.pack(fill="x")
        tk.Label(row, text="다운로드 폴더:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).pack(side="left")
        self._dl_dest = tk.StringVar(
            value=self._cfg.get("download_root", os.path.join(os.path.expanduser("~"), "Downloads", "AOI_Params")))
        tk.Entry(row, textvariable=self._dl_dest, font=self.fonts["base"],
                 relief="solid", bd=1).pack(side="left", fill="x", expand=True, padx=6)
        tk.Button(row, text="찾아보기", relief="flat", bd=0, bg=self.p["surface"],
                  cursor="hand2", command=self._dl_pick_dest).pack(side="left")
        tk.Button(row, text="후보 검색", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=14, cursor="hand2",
                  command=self._dl_search).pack(side="left", padx=(8, 0))

        # 결과(스크롤): Recipe별 후보 선택 행
        mid = tk.Frame(win, bg=self.p["surface"], highlightbackground=self.p["border"],
                       highlightthickness=1)
        mid.pack(fill="both", expand=True, padx=14, pady=6)
        canvas = tk.Canvas(mid, bg=self.p["surface"], highlightthickness=0)
        vsb = ttk.Scrollbar(mid, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._dl_inner = tk.Frame(canvas, bg=self.p["surface"])
        canvas.create_window((0, 0), window=self._dl_inner, anchor="nw", tags="i")
        self._dl_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("i", width=e.width))

        bot = tk.Frame(win, bg=self.p["bg"])
        bot.pack(fill="x", padx=14, pady=(0, 12))
        tk.Button(bot, text="선택 항목 다운로드", relief="flat", bd=0, bg=self.p["ok"],
                  fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=self._dl_run).pack(side="left")
        self._dl_status = tk.Label(bot, text="", bg=self.p["bg"], fg=self.p["muted"],
                                   font=self.fonts["sub"])
        self._dl_status.pack(side="left", padx=12)

        self._dl_rows = []

    def _dl_pick_dest(self):
        d = filedialog.askdirectory(title="다운로드 폴더 선택")
        if d:
            self._dl_dest.set(d)

    def _dl_search(self):
        for w in self._dl_inner.winfo_children():
            w.destroy()
        self._dl_rows = []
        paths = []
        for line in self._dl_paths.get("1.0", "end").splitlines():
            paths += dl.split_pasted_windows_paths(line)
        if not paths:
            self._dl_status.config(text="호기 경로를 입력하세요.")
            return
        any_found = False
        for aoi in paths:
            try:
                found = dl.discover(aoi)
            except Exception as e:  # noqa: BLE001
                tk.Label(self._dl_inner, text=f"✗ {aoi} — {e}", bg=self.p["surface"],
                         fg=self.p["danger"], font=self.fonts["sub"], anchor="w").pack(
                    fill="x", padx=8, pady=2)
                continue
            tk.Label(self._dl_inner, text=f"■ {aoi}", bg=self.p["surface"], fg=self.p["text"],
                     font=self.fonts["bold"], anchor="w").pack(fill="x", padx=8, pady=(8, 0))
            for recipe, cands in found.items():
                self._dl_make_row(aoi, recipe, cands)
                any_found = True
        self._dl_status.config(text="후보 검색 완료. Recipe별로 선택 후 다운로드하세요."
                               if any_found else "후보를 찾지 못했습니다.")

    def _dl_make_row(self, aoi, recipe, cands):
        fr = tk.Frame(self._dl_inner, bg=self.p["surface"])
        fr.pack(fill="x", padx=18, pady=1)
        tk.Label(fr, text=recipe, bg=self.p["surface"], fg=self.p["text"],
                 font=self.fonts["base"], width=20, anchor="w").pack(side="left")
        opts = ["(다운로드 안 함)"] + [c.label for c in cands] + ["(수동 경로 입력)"]
        var = tk.StringVar(value=cands[0].label if cands else "(수동 경로 입력)")
        cb = ttk.Combobox(fr, textvariable=var, values=opts, state="readonly", width=70)
        cb.pack(side="left", padx=6, fill="x", expand=True)
        manual = tk.Entry(fr, font=self.fonts["sub"], relief="solid", bd=1)
        row = {"aoi": aoi, "recipe": recipe, "cands": cands, "var": var, "manual": manual}

        def on_sel(_=None):
            if var.get() == "(수동 경로 입력)":
                manual.pack(side="left", padx=6, fill="x", expand=True)
            else:
                manual.pack_forget()
        cb.bind("<<ComboboxSelected>>", on_sel)
        on_sel()
        self._dl_rows.append(row)

    def _dl_run(self):
        dest_root = self._dl_dest.get().strip()
        if not dest_root:
            self._dl_status.config(text="다운로드 폴더를 지정하세요.")
            return
        self._cfg["download_root"] = dest_root
        save_config(self._cfg)
        done, errs = [], []
        for row in self._dl_rows:
            sel = row["var"].get()
            if sel == "(다운로드 안 함)":
                continue
            try:
                if sel == "(수동 경로 입력)":
                    p = row["manual"].get().strip()
                    if not p:
                        continue
                    cand = dl.parse_manual_wafer(p)
                else:
                    cand = next(c for c in row["cands"] if c.label == sel)
                res = dl.copy_wafer(cand, dest_root)
                done.append(f"{row['recipe']}: {res['count']}개 → {res['dest']}")
            except Exception as e:  # noqa: BLE001
                errs.append(f"{row['recipe']}: {e}")
        msg = f"다운로드 완료 {len(done)}건"
        if errs:
            msg += f", 오류 {len(errs)}건"
        self._dl_status.config(text=msg)
        detail = "\n".join(done) + ("\n\n[오류]\n" + "\n".join(errs) if errs else "")
        messagebox.showinfo("다운로드 결과",
                            detail or "다운로드한 항목이 없습니다.", parent=self._dl_win)

    # ====================================================================
    #  파라미터 폴더 분석 → 취사선택(큐레이션)
    # ====================================================================
    def _ip_to_aoi(self, ip: str) -> str:
        """'장비 IP 주소'로 IP → 호기 역매핑. 못 찾으면 ''."""
        ip = engine._s(ip).strip()
        for r in self.ip_rows:
            if engine._s(r.get("IP")).strip() == ip:
                return engine._s(r.get("호기")).strip()
        return ""

    def _map_ips_to_machines(self, ips, parent=None):
        """각 IP를 어느 호기(AOI-xx)에 넣을지 지정하는 매칭창.
        반환: {ip: 호기} 또는 None(취소). 참고자료 IP표로 자동 추정 프리필."""
        parent = parent or self
        win = tk.Toplevel(parent)
        win.title("IP ↔ 호기 매칭")
        win.configure(bg=self.p["bg"])
        win.transient(parent)
        win.grab_set()
        tk.Label(win, text="각 IP의 값을 어느 호기(AOI-xx) 열에 채울지 지정하세요.",
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["bold"]).pack(
                 anchor="w", padx=14, pady=(12, 2))
        tk.Label(win, text="IP로 새 열을 만들지 않고, 지정한 기존 호기 열에 값을 갱신합니다.",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"]).pack(
                 anchor="w", padx=14)
        machines = self._all_machines()
        rows = {}
        grid = tk.Frame(win, bg=self.p["bg"])
        grid.pack(fill="both", expand=True, padx=14, pady=8)
        for i, ip in enumerate(ips):
            tk.Label(grid, text=ip, bg=self.p["bg"], fg=self.p["text"],
                     font=self.fonts["base"]).grid(row=i, column=0, sticky="w", pady=3)
            tk.Label(grid, text="→", bg=self.p["bg"], fg=self.p["muted"]).grid(
                row=i, column=1, padx=8)
            var = tk.StringVar(value=self._ip_to_aoi(ip))
            cb = ttk.Combobox(grid, textvariable=var, values=machines, width=16)
            cb.grid(row=i, column=2, sticky="w", pady=3)
            rows[ip] = var
        res = {"val": None}

        def ok():
            mapping = {ip: v.get().strip() for ip, v in rows.items()}
            missing = [ip for ip, m in mapping.items() if not m]
            if missing:
                messagebox.showwarning("호기 미지정",
                                       "다음 IP의 호기를 지정하세요:\n" + ", ".join(missing),
                                       parent=win)
                return
            dups = [m for m in set(mapping.values())
                    if list(mapping.values()).count(m) > 1]
            if dups and not messagebox.askyesno(
                    "호기 중복", f"같은 호기에 여러 IP가 지정됨: {', '.join(sorted(set(dups)))}\n"
                    "나중 IP 값이 앞 값을 덮어씁니다. 계속할까요?", parent=win):
                return
            res["val"] = mapping
            win.destroy()
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=14, pady=(0, 12))
        tk.Button(bt, text="확인", relief="flat", bd=0, bg=self.p["primary"], fg="#ffffff",
                  padx=16, cursor="hand2", command=ok).pack(side="left")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=16,
                  cursor="hand2", command=win.destroy).pack(side="left", padx=6)
        win.wait_window()
        return res["val"]

    def _pick_list_chooser(self, kind, title, items, multi):
        """collector 용 모달 선택창. 반환: 선택 목록 또는 None(취소)."""
        win = tk.Toplevel(getattr(self, "_chooser_parent", None) or self)
        win.title(title)
        win.configure(bg=self.p["bg"])
        win.grab_set()
        tk.Label(win, text=title, bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["bold"]).pack(anchor="w", padx=12, pady=(10, 2))
        if multi:
            tk.Label(win, text="여러 개 선택: Ctrl/Shift+클릭", bg=self.p["bg"],
                     fg=self.p["muted"], font=self.fonts["sub"]).pack(anchor="w", padx=12)
        fr = tk.Frame(win, bg=self.p["bg"])
        fr.pack(fill="both", expand=True, padx=12, pady=6)
        sb = ttk.Scrollbar(fr, orient="vertical")
        lb = tk.Listbox(fr, selectmode=("extended" if multi else "browse"),
                        height=min(22, max(8, len(items))), width=80,
                        font=self.fonts["base"], yscrollcommand=sb.set)
        sb.config(command=lb.yview)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for it in items:
            lb.insert("end", it.name if isinstance(it, Path) else str(it))
        if items:
            lb.selection_set(0)
        result = {"val": None}

        def ok(_=None):
            sel = [items[i] for i in lb.curselection()]
            result["val"] = sel or None
            win.destroy()
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=12, pady=(0, 10))
        tk.Button(bt, text="선택", relief="flat", bd=0, bg=self.p["primary"], fg="#ffffff",
                  padx=16, cursor="hand2", command=ok).pack(side="left")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"],
                  padx=16, cursor="hand2", command=win.destroy).pack(side="left", padx=6)
        lb.bind("<Double-Button-1>", ok)
        win.wait_window()
        return result["val"]

    def _open_in_excel(self, path) -> bool:
        """저장된 initial/양식 파일을 실제 Excel(또는 OS 기본 앱)로 연다."""
        import shutil
        import subprocess
        try:
            if os.name == "nt":
                os.startfile(path)          # noqa: E1101 (Windows 전용)
                return True
            opener = shutil.which("xdg-open") or shutil.which("open")
            if opener:
                subprocess.Popen([opener, path])
                return True
        except Exception:  # noqa: BLE001
            pass
        return False

    # ====================================================================
    #  장비 수집 / 파싱 (양식 만들기·값 업데이트 공용)
    # ====================================================================
    def _collect_dialog(self, staging_root, on_sources, level_hint=""):
        """장비 IP 수집 모달. IP↔호기 매칭 후 staging_root/{호기}/ 로 읽기전용 복사.
        완료 시 on_sources(sources) 호출. sources=[(폴더, job_keyword, 호기)]."""
        win = tk.Toplevel(self)
        win.title("장비에서 수집(읽기전용)")
        win.geometry("620x380")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        self._chooser_parent = win
        tk.Label(win, text="장비 네트워크(\\\\IP\\c$\\Job)에서 설정 파일 수집",
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["bold"]).pack(
                 anchor="w", padx=14, pady=(12, 2))
        tk.Label(win, text="원본은 읽기·복사만. 장비 1대씩 접속 후 즉시 해제, 비밀번호는 "
                          "이번 실행 메모리에만 보관.", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"], justify="left").pack(anchor="w", padx=14)
        tk.Label(win, text="장비 IP(여러 개, 쉼표/줄바꿈):", bg=self.p["bg"],
                 fg=self.p["text"], font=self.fonts["sub"]).pack(anchor="w", padx=14, pady=(8, 0))
        ips_txt = tk.Text(win, height=4, font=self.fonts["base"], relief="solid", bd=1)
        ips_txt.pack(fill="x", padx=14, pady=(2, 8))
        row = tk.Frame(win, bg=self.p["bg"])
        row.pack(fill="x", padx=14)
        tk.Label(row, text="접속 ID:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).pack(side="left")
        uid_var = tk.StringVar(value=self._cfg.get("collect_user", "amkor"))
        tk.Entry(row, textvariable=uid_var, width=12, relief="solid", bd=1).pack(
            side="left", padx=(4, 10))
        tk.Label(row, text="비밀번호:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).pack(side="left")
        pw_var = tk.StringVar()
        tk.Entry(row, textvariable=pw_var, width=16, show="*", relief="solid", bd=1).pack(
            side="left", padx=(4, 10))
        net_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row, text="net use 접속(자동 해제)", variable=net_var,
                       bg=self.p["bg"], font=self.fonts["sub"]).pack(side="left")
        status = tk.Label(win, text="", bg=self.p["bg"], fg=self.p["muted"],
                          font=self.fonts["sub"])
        status.pack(fill="x", padx=14, pady=6)

        def run():
            ips = collector.split_ips(ips_txt.get("1.0", "end"))
            if not ips:
                status.config(text="IP를 입력하세요.")
                return
            if net_var.get() and not collector.is_windows():
                status.config(text="net use 는 Windows 전용입니다. 체크를 끄고 이미 "
                                   "연결된 경로로 시도하세요.")
                return
            ip_map = self._map_ips_to_machines(ips, parent=win)
            if ip_map is None:
                return
            self._cfg["collect_user"] = uid_var.get().strip() or "amkor"
            save_config(self._cfg)
            sources, errors = [], []
            plan = None
            for i, ip in enumerate(ips, 1):
                aoi = ip_map.get(ip) or self._ip_to_aoi(ip) or ip.replace(".", "_")
                status.config(text=f"[{i}/{len(ips)}] {ip} ({aoi}) 수집 중…")
                win.update_idletasks()

                def staging_for(kw, aoi=aoi):
                    d = os.path.join(staging_root, _sanitize_name(aoi))
                    os.makedirs(d, exist_ok=True)
                    return d

                def confirm(planned, ip=ip):
                    lines = [f"· {src}" for src, _, _ in planned[:15]]
                    more = f"\n…외 {len(planned) - 15}개" if len(planned) > 15 else ""
                    return messagebox.askyesno(
                        "복사 확인", f"[{ip}] {len(planned)}개 파일을 로컬로 복사"
                        "(원본은 읽기만):\n" + "\n".join(lines) + more, parent=win)
                try:
                    _, plan, rootp = collector.collect_equipment(
                        ip, staging_for, self._pick_list_chooser,
                        username=uid_var.get().strip() or "amkor",
                        password=pw_var.get(), use_net_use=net_var.get(),
                        plan=plan, confirm=confirm)
                    sources.append((str(rootp), plan.job_keyword, aoi))
                except collector.UserCancelled:
                    errors.append(f"{ip}: 취소")
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{ip}: {e}")
            pw_var.set("")
            if errors:
                messagebox.showwarning("수집 결과",
                                       f"완료 {len(sources)}건, 실패 {len(errors)}건\n\n"
                                       + "\n".join(errors), parent=win)
            win.destroy()
            if sources:
                on_sources(sources)

        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=14, pady=(4, 12))
        tk.Button(bt, text="수집 시작", relief="flat", bd=0, bg=self.p["ok"], fg="#ffffff",
                  padx=16, pady=6, cursor="hand2", command=run).pack(side="left")
        tk.Button(bt, text="닫기", relief="flat", bd=0, bg=self.p["surface"], padx=16,
                  pady=6, cursor="hand2", command=win.destroy).pack(side="left", padx=8)

    def _coef_lookup_cb(self, fixed_machine=None):
        """scan_tree 용 변환계수 콜백 — (호기,MAG) 저장소 우선, 없으면 RTP.txt 로 자동
        추정해 upsert(사람값 우선). fixed_machine 지정 시 그 호기로 조회·저장.
        반환: (콜백, 변경카운트 dict)."""
        state = {"changed": 0}

        def cb(equipment, mag_value, config_dir=None, variant=""):
            if fixed_machine:
                equipment = fixed_machine
            c = coefstore.lookup(self.coef_rows, equipment, mag_value)
            if c is not None:
                return c
            if config_dir is not None and engine._s(equipment).strip():
                try:
                    coef = coef_detector.detect_from_dir(config_dir).get("Coefficient")
                except Exception:  # noqa: BLE001
                    coef = None
                if coef:
                    if coefstore.upsert(self.coef_rows, equipment, mag_value, coef, variant):
                        state["changed"] += 1
                    try:
                        return float(coef)
                    except (TypeError, ValueError):
                        return None
            return None
        return cb, state

    def _coef_save_if_changed(self, state):
        if state.get("changed") and self.save_dir:
            try:
                coefstore.save(coefstore.coef_path(self.save_dir), self.coef_rows)
            except Exception:  # noqa: BLE001
                pass

    def _parse_sources_busy(self, sources, on_ready, default_level="", scales=None):
        """수집/로컬 폴더 → 파싱 피벗. 변환계수는 (호기,MAG) 저장소 기준(없으면 RTP.txt
        자동추정·저장). scales 는 폴백."""
        def work():
            cb, state = self._coef_lookup_cb()
            cfgs = []
            for rootp, kw, aoi in sources:
                # 사용자가 고른 레시피 레벨(default_level)이 장비 Job 키워드(kw)보다 우선.
                cfgs += ini_parser.scan_tree(rootp, default_level=default_level or kw,
                                             default_equipment=aoi, scales=scales,
                                             coef_lookup=cb)
            valid = [c for c in cfgs if rtp.config_valid(c)]
            rows, machines = ini_parser.build_pivot(valid)
            self._coef_save_if_changed(state)
            return rows, machines

        def done(ok, res):
            if not ok:
                messagebox.showerror("파싱 실패", str(res))
                return
            rows, machines = res
            if not rows:
                messagebox.showwarning("파싱 결과", "인식된 설정(config) 폴더가 없습니다.\n"
                                       "GlobalRTP.ini/OpticPreset.ini/Zones 구조를 확인하세요.")
                return
            on_ready(rows, machines)
        self._run_busy("파싱 중…", work, done)

    def _ask_scales(self, variants, recommended=None):
        """변형별 변환계수 입력창. recommended={변형: coef_detector 결과}면 RTP.txt로
        추정한 값을 **추천값으로 미리 채우고** 신뢰도를 표시(사용자가 확정/수정).
        반환: {변형: 계수(float)} 또는 None(취소)."""
        recommended = recommended or {}
        win = tk.Toplevel(self)
        win.title("변환 계수 확인(변형별)")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="변형(레시피)별 변환 계수를 확인하세요.", bg=self.p["bg"],
                 fg=self.p["text"], font=self.fonts["bold"]).pack(anchor="w", padx=14,
                                                                  pady=(12, 2))
        tk.Label(win, text="RTP.txt(표시값)와 ini(원본값)를 비교해 계수를 자동 추정했습니다. "
                          "추천값을 확인하고 필요하면 수정하세요(목록에서 고르거나 직접 입력).",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left", wraplength=560).pack(anchor="w", padx=14)
        opts = [f"{s:.16g}" for s in ini_parser.KNOWN_SCALES]
        grid = tk.Frame(win, bg=self.p["bg"])
        grid.pack(fill="both", expand=True, padx=14, pady=8)
        tk.Label(grid, text="변형", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).grid(row=0, column=0, sticky="w")
        tk.Label(grid, text="계수(추천값 자동 입력)", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).grid(row=0, column=1, sticky="w", padx=8)
        tk.Label(grid, text="추정 근거", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).grid(row=0, column=2, sticky="w")
        vars_ = {}
        for i, v in enumerate(variants, start=1):
            tk.Label(grid, text=v, bg=self.p["bg"], fg=self.p["text"],
                     font=self.fonts["base"]).grid(row=i, column=0, sticky="w", pady=4)
            dec = recommended.get(v) or {}
            coef = dec.get("Coefficient")
            var = tk.StringVar(value=(f"{coef:.16g}" if coef is not None else ""))
            ttk.Combobox(grid, textvariable=var, values=opts, width=26).grid(
                row=i, column=1, padx=8, pady=4)
            vars_[v] = var
            if coef is not None:
                note = f"RTP 추정 {dec.get('Display')} · 신뢰도 {dec.get('Confidence')} " \
                       f"(증거 {dec.get('Count', 0)}건)"
                fg = self.p["ok"] if dec.get("Confidence") == "High" else self.p["text"]
            else:
                note = "RTP.txt 없음/근거 부족 — 직접 입력하세요"
                fg = self.p["danger"]
            tk.Label(grid, text=note, bg=self.p["bg"], fg=fg,
                     font=self.fonts["sub"]).grid(row=i, column=2, sticky="w", padx=6)
        res = {"val": None}

        def ok():
            out = {}
            for v, var in vars_.items():
                s = var.get().strip()
                try:
                    out[v] = float(s)
                except ValueError:
                    messagebox.showwarning("계수 오류",
                                           f"'{v}'의 계수를 숫자로 입력하세요(현재: '{s}').",
                                           parent=win)
                    return
            res["val"] = out
            win.destroy()
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=14, pady=(0, 12))
        tk.Button(bt, text="확인", relief="flat", bd=0, bg=self.p["primary"], fg="#ffffff",
                  padx=16, cursor="hand2", command=ok).pack(side="left")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=16,
                  cursor="hand2", command=win.destroy).pack(side="left", padx=6)
        win.wait_window()
        return res["val"]

    def _pick_levels(self, levels, title="취합할 레시피를 선택하세요"):
        """레시피 다중 선택 알림창. 반환: 선택 목록 또는 None."""
        win = tk.Toplevel(self)
        win.title("레시피 선택")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        tk.Label(win, text=title, bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["bold"]).pack(anchor="w", padx=14, pady=(12, 6))
        vars_ = {}
        for lv in levels:
            v = tk.BooleanVar(value=True)
            vars_[lv] = v
            tk.Checkbutton(win, text=lv, variable=v, bg=self.p["bg"],
                           font=self.fonts["base"]).pack(anchor="w", padx=20)
        res = {"val": None}

        def ok():
            sel = [lv for lv, v in vars_.items() if v.get()]
            res["val"] = sel or None
            win.destroy()
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=14, pady=12)
        tk.Button(bt, text="선택", relief="flat", bd=0, bg=self.p["primary"], fg="#ffffff",
                  padx=16, cursor="hand2", command=ok).pack(side="left")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=16,
                  cursor="hand2", command=win.destroy).pack(side="left", padx=6)
        win.wait_window()
        return res["val"]

    # ====================================================================
    #  양식 만들기(저장폴더/양식/{레시피}/{생성시간}/…)
    # ====================================================================
    def _view_form(self):
        if not hasattr(self, "_form_kind"):
            self._form_kind = tk.StringVar(value="PI")
            self._form_level = tk.StringVar(value="PI3")
        wrap = tk.Frame(self.body, bg=self.p["bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=18)
        tk.Label(wrap, text="양식 만들기", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w")
        tk.Label(wrap, text="레시피를 고르고 장비/로컬에서 새로 불러오면 초안(수정본) 엑셀이 "
                          "실제 Excel로 열립니다. 편집·저장 후 '편집 완료'를 누르면 확정 양식이 "
                          "'양식/{레시피}/{생성시간}/' 에 저장됩니다(원본·수정본·원본ini는 관련파일 폴더).",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left", wraplength=920).pack(anchor="w", pady=(2, 14))

        box = tk.LabelFrame(wrap, text=" ① 레시피 선택 ", bg=self.p["bg"], fg=self.p["text"],
                            font=self.fonts["bold"], padx=12, pady=10)
        box.pack(fill="x")
        krow = tk.Frame(box, bg=self.p["bg"])
        krow.pack(fill="x")
        level_combo = ttk.Combobox(krow, textvariable=self._form_level, state="readonly",
                                   width=14, values=RECIPE_LEVELS["PI"])

        def on_kind():
            k = self._form_kind.get()
            if k in RECIPE_LEVELS:
                vals = RECIPE_LEVELS[k]
                level_combo.config(values=vals, state="readonly")
                if self._form_level.get() not in vals:
                    self._form_level.set(vals[0])
            else:
                level_combo.config(values=[], state="normal")
                if self._form_level.get() in RECIPE_LEVELS["PI"] + RECIPE_LEVELS["RDL"]:
                    self._form_level.set("")
        for k in ("PI", "RDL", "기타"):
            tk.Radiobutton(krow, text=("기타(직접 입력)" if k == "기타" else k),
                           variable=self._form_kind, value=k, bg=self.p["bg"],
                           font=self.fonts["bold"], command=on_kind).pack(side="left",
                                                                          padx=(0, 10))
        tk.Label(krow, text="레시피:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).pack(side="left", padx=(10, 4))
        level_combo.pack(side="left")
        on_kind()

        box2 = tk.LabelFrame(wrap, text=" ② 불러오기 방식 ", bg=self.p["bg"], fg=self.p["text"],
                             font=self.fonts["bold"], padx=12, pady=10)
        box2.pack(fill="x", pady=(14, 0))
        tk.Button(box2, text="🖥  장비 폴더에서 신규 불러오기", relief="flat", bd=0,
                  bg=self.p["primary"], fg="#ffffff", padx=16, pady=8, cursor="hand2",
                  command=lambda: self._form_new(from_equipment=True)).pack(side="left")
        tk.Button(box2, text="📁  로컬 폴더에서 신규 불러오기", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=16, pady=8, cursor="hand2",
                  command=lambda: self._form_new(from_equipment=False)).pack(side="left", padx=8)
        tk.Button(box2, text="🗂  이전 버전 불러오기", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=16, pady=8, cursor="hand2",
                  command=self._load_previous_form).pack(side="left")

    def _form_new(self, from_equipment: bool):
        if not self.save_dir:
            messagebox.showinfo("저장 폴더", "먼저 저장 폴더를 지정하세요(⋯파일).")
            return
        level = self._form_level.get().strip()
        kind = self._form_kind.get()
        if not level:
            messagebox.showwarning("레시피 미지정",
                                   "레시피(레벨)를 선택하거나 '기타'에서 직접 입력하세요.")
            return
        if kind == "기타":
            kind = "RDL" if level.upper().startswith("RDL") else "PI"
        st = workdirs.stamp()
        run_dir = workdirs.form_run_dir(self.save_dir, level, st)
        related = workdirs.related_dir(run_dir)
        if from_equipment:
            self._collect_dialog(
                related,
                lambda sources: self._scales_then_build(sources, level, kind,
                                                        run_dir, related, st),
                level_hint=level)
        else:
            d = filedialog.askdirectory(title=f"{level} 레시피 파일이 있는 로컬 폴더 선택")
            if not d:
                return
            self._scales_then_build([(d, level, "")], level, kind, run_dir, related, st)

    def _scales_then_build(self, sources, level, kind, run_dir, related, st):
        def detect():
            variants = []
            dirs = {}                       # 변형 → config 폴더(계수 추정용)
            for rootp, kw, aoi in sources:
                for c in ini_parser.scan_tree(rootp, default_level=level or kw,
                                              default_equipment=aoi):
                    if not rtp.config_valid(c):
                        continue
                    v = c.mag or "(기본)"
                    if v not in variants:
                        variants.append(v)
                        dirs[v] = c.config_dir
            variants = variants or ["(기본)"]
            # RTP.txt + ini 로 변형별 계수 자동 추정(추천값)
            reco = {}
            for v in variants:
                d = dirs.get(v)
                if d is not None:
                    try:
                        reco[v] = coef_detector.detect_from_dir(d)
                    except Exception:  # noqa: BLE001
                        reco[v] = None
            return variants, reco

        def after_detect(ok, res):
            if not ok:
                messagebox.showerror("변형 감지 실패", str(res))
                return
            variants, reco = res
            scales_ui = self._ask_scales(variants, reco)
            if scales_ui is None:
                return
            scale_map = {("" if k == "(기본)" else k): v for k, v in scales_ui.items()}

            def parse_ready(rows, machines):
                self._form_build_and_edit(rows, machines, level, kind, scale_map,
                                          run_dir, related, st)
            self._parse_sources_busy(sources, parse_ready, default_level=level,
                                     scales=scale_map)
        self._run_busy("변형(레시피) 감지 중…", detect, after_detect)

    def _form_build_and_edit(self, rows, machines, level, kind, scales, run_dir, related, st):
        aoi = next((m for m in machines if m), "로컬")
        draft = workdirs.form_draft_path(related, level, aoi, st)

        def work():
            formbuilder.build_initial_workbook(rows, draft, level=level,
                                               source=f"{level} / {aoi}")
            import shutil
            orig = workdirs.form_original_path(related, level, aoi, st)
            shutil.copy2(draft, orig)          # 편집 전 원본 보존
            return orig

        def done(ok, res):
            if not ok:
                messagebox.showerror("초안 생성 실패", str(res))
                return
            opened = self._open_in_excel(draft)
            self._form_finalize_dialog(draft, res, level, kind, scales, run_dir,
                                       aoi, st, opened)
        self._run_busy("초안(수정본) 엑셀 생성 중…", work, done)

    def _form_finalize_dialog(self, draft, orig, level, kind, scales, run_dir, aoi, st, opened):
        win = tk.Toplevel(self)
        win.title("양식 편집 완료")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        msg = (f"수정본이 생성되었습니다:\n{draft}\n\n"
               + ("실제 Excel로 열었습니다. " if opened else
                  "이 환경에서 Excel을 자동으로 열지 못했습니다. 위 파일을 직접 여세요.\n")
               + "Excel에서 '사용'·'최종 Parameter'를 편집·저장한 뒤 '편집 완료'를 누르세요.\n"
               f"(편집 전 원본 보존: {os.path.basename(orig)})")
        tk.Label(win, text=msg, bg=self.p["bg"], fg=self.p["text"], font=self.fonts["sub"],
                 justify="left", wraplength=560).pack(padx=16, pady=(14, 10))
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(bt, text="다시 열기", relief="flat", bd=0, bg=self.p["surface"],
                  padx=12, pady=6, cursor="hand2",
                  command=lambda: self._open_in_excel(draft)).pack(side="left")
        tk.Button(bt, text="편집 완료 → 양식 확정", relief="flat", bd=0, bg=self.p["ok"],
                  fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=lambda: self._form_finalize(draft, level, kind, scales,
                                                      run_dir, aoi, st, win)).pack(side="right")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=12,
                  pady=6, cursor="hand2", command=win.destroy).pack(side="right", padx=6)

    def _form_finalize(self, draft, level, kind, scales, run_dir, aoi, st, win):
        final = workdirs.form_final_path(run_dir, level, aoi, st)

        def work():
            return formbuilder.build_final_from_initial(
                draft, final, user=self.user, level=level, source=f"{level} 양식",
                scales=scales)

        def done(ok, res):
            if not ok:
                messagebox.showerror("양식 확정 실패", str(res), parent=win)
                return
            win.destroy()
            if messagebox.askyesno(
                    "양식 확정 완료",
                    f"확정 양식 생성: {os.path.basename(final)}\n"
                    f"항목 {res['kept']}개(제외 {res['dropped']}개).\n"
                    f"위치: {run_dir}\n\n지금 화면으로 열어 볼까요?"):
                self._open_collation_view(final)
        self._run_busy("양식 확정 중…", work, done)

    def _load_previous_form(self):
        """이전 버전 불러오기 — 레시피 → 생성시간(버전) 선택 → 확정 양식 열기."""
        if not self.save_dir:
            messagebox.showinfo("저장 폴더", "먼저 저장 폴더를 지정하세요.")
            return
        recipes = workdirs.list_recipes(self.save_dir)
        if not recipes:
            messagebox.showinfo("이전 버전", "저장된 양식이 없습니다. 먼저 양식을 만드세요.")
            return
        pick = self._pick_list_chooser("recipe", "레시피 선택", recipes, False)
        if not pick:
            return
        versions = workdirs.list_form_versions(self.save_dir, pick[0])
        if not versions:
            messagebox.showinfo("이전 버전", f"'{pick[0]}' 레시피에 저장된 확정 양식이 없습니다.")
            return
        labels = [f"{st}   ({os.path.basename(p)})" for st, p in versions]
        chosen = self._pick_list_chooser("ver", "이전 버전 선택(최신순)", labels, False)
        if not chosen:
            return
        path = dict(zip(labels, [p for _, p in versions]))[chosen[0]]
        self._open_collation_view(path)

    # ====================================================================
    #  파라미터 값 업데이트 → '파라미터 값 취합_{시간}.xlsx'(레시피별 시트)
    # ====================================================================
    def _update_values_dialog(self):
        if not self.save_dir:
            messagebox.showinfo("값 업데이트", "먼저 저장 폴더를 지정하세요.")
            return
        recipes = workdirs.list_recipes(self.save_dir)
        if not recipes:
            messagebox.showinfo("값 업데이트", "먼저 '양식 만들기'로 양식을 만드세요.")
            return
        if not self._all_machines():
            messagebox.showinfo("값 업데이트", "참고자료에 호기가 없습니다. 참고자료 탭에서 "
                                "호기·IP를 등록하세요.")
            return
        chosen = self._pick_levels(recipes)          # 레시피 선택 알림창
        if not chosen:
            return
        # 각 레시피 최신 양식의 변환계수 병합(재파싱에 사용)
        scales = {}
        for r in chosen:
            f = workdirs.latest_form(self.save_dir, r)
            if f:
                scales.update(extract_io.read_scales(f))
        # 레시피 1개만 고르면 그 레벨을 파싱에 주입(장비 Job 키워드 오탐 방지 — 양식과 일치).
        dlevel = chosen[0] if len(chosen) == 1 else ""

        win = tk.Toplevel(self)
        win.title("파라미터 값 업데이트")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        tk.Label(win, text="파라미터 값 업데이트", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(win, text=f"대상 레시피: {', '.join(chosen)}\n"
                          "여러 장비에서 값을 읽어 레시피별 시트로 취합합니다(참고자료의 모든 "
                          "호기 열, 이번에 수집 안 한 호기는 직전 취합본 값 유지).",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=16)
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=16, pady=16)

        def from_equip():
            win.destroy()
            staging = os.path.join(self.save_dir, "_수집임시", workdirs.stamp())
            self._collect_dialog(
                staging,
                lambda sources: self._parse_sources_busy(
                    sources, lambda rows, machines: self._update_collate_flow(chosen, rows),
                    default_level=dlevel, scales=scales),
                level_hint=dlevel)

        def from_local():
            win.destroy()
            d = filedialog.askdirectory(title="장비에서 받아둔 로컬 폴더 선택")
            if not d:
                return
            self._parse_sources_busy(
                [(d, dlevel, "")],
                lambda rows, machines: self._update_collate_flow(chosen, rows),
                default_level=dlevel, scales=scales)
        tk.Button(bt, text="🖥 장비 IP에서 수집", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=16, pady=8, cursor="hand2",
                  command=from_equip).pack(side="left")
        tk.Button(bt, text="📁 로컬 폴더에서", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=16, pady=8, cursor="hand2",
                  command=from_local).pack(side="left", padx=8)

    def _update_collate_flow(self, chosen, pivot_rows):
        machines_all = self._all_machines()
        prev = workdirs.latest_collate(self.save_dir)

        def work():
            return collate.build_collation(self.save_dir, chosen, pivot_rows,
                                           machines_all, prev_collate_path=prev)

        def done(ok, res):
            if not ok:
                messagebox.showerror("취합 실패", str(res))
                return
            self._update_write_results(res, machines_all)
        self._run_busy("취합 중…", work, done)

    def _update_write_results(self, results, machines_all):
        made = {}
        notes = []
        for recipe, res in results.items():
            if res.missing_form:
                notes.append(f"· {recipe}: 양식 없음(건너뜀)")
                continue
            if res.mismatches:
                names = ", ".join(sorted({m["param"] for m in res.mismatches})[:12])
                more = f" 외 {len(res.mismatches) - 12}개" if len(res.mismatches) > 12 else ""
                if not messagebox.askyesno(
                        "항목 불일치",
                        f"[{recipe}] 양식과 장비 파일의 파라미터가 일부 맞지 않습니다.\n"
                        f"불일치 {len(res.mismatches)}개: {names}{more}\n\n"
                        "이 레시피를 그래도 취합에 포함할까요?(불일치 항목은 값 없이 유지)"):
                    notes.append(f"· {recipe}: 불일치로 제외")
                    continue
            made[recipe] = res
        if not made:
            messagebox.showinfo("값 업데이트",
                                "취합된 레시피가 없습니다.\n" + "\n".join(notes))
            return
        dest = workdirs.collate_path(self.save_dir, workdirs.stamp())
        collate.write_collation(dest, made, machines_all)
        self._load_latest_collate()
        self.view = "param"
        self._sync_tab_style()
        self.navigate(screen="s0")
        summary = "\n".join(f"· {r}: 매칭 {made[r].matched_rows}행 / 값 {made[r].filled_cells}칸"
                            for r in made)
        extra = ("\n\n" + "\n".join(notes)) if notes else ""
        messagebox.showinfo(
            "값 업데이트 완료",
            f"취합 파일 생성: {os.path.basename(dest)}\n\n{summary}{extra}\n\n"
            "값 확인 화면에 최신 취합이 표시됩니다.")

    # ====================================================================
    #  파라미터 이력 확인 — 취합 파일 2개 선택 → 다른 부분만 새 창
    # ====================================================================
    def _history_dialog(self):
        if not self.save_dir:
            messagebox.showinfo("이력", "먼저 저장 폴더를 지정하세요.")
            return
        files = workdirs.list_collate_files(self.save_dir)
        if len(files) < 2:
            messagebox.showinfo("이력", "비교하려면 '파라미터 값 취합' 파일이 2개 이상 필요합니다.")
            return
        labels = [os.path.basename(f) for f in files]
        a = self._pick_list_chooser("hist", "이전(비교 기준) 취합 파일 선택", labels, False)
        if not a:
            return
        b = self._pick_list_chooser("hist", "최신(달라진) 취합 파일 선택", labels, False)
        if not b:
            return
        old_p = files[labels.index(a[0])]
        new_p = files[labels.index(b[0])]

        def work():
            return history_mod.diff_files(old_p, new_p)

        def done(ok, res):
            if not ok:
                messagebox.showerror("이력 비교 실패", str(res))
                return
            diff = res
            if not diff.changes and not diff.added_rows and not diff.removed_rows:
                messagebox.showinfo("이력", "두 파일 사이에 바뀐 값이 없습니다.")
                return
            self._show_diff_window(diff, os.path.basename(old_p), os.path.basename(new_p))
        self._run_busy("이력 비교 중…", work, done)

    def _show_diff_window(self, diff, old_label, new_label):
        win = tk.Toplevel(self)
        win.title(f"변경내역: {old_label} → {new_label}")
        win.geometry("1000x620")
        win.configure(bg=self.p["bg"])
        tk.Label(win, text=f"달라진 부분만 표시 — 값 변경 {len(diff.changes)}건 · 행 추가 "
                          f"{len(diff.added_rows)} · 삭제 {len(diff.removed_rows)}",
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["bold"]).pack(
                 anchor="w", padx=12, pady=(10, 4))
        cols = ("레시피", "PI", "Zone", "Alg", "Parameter", "호기", "이전 값", "새 값", "구분")
        tv = ttk.Treeview(win, columns=cols, show="headings", height=22)
        widths = (90, 60, 130, 120, 200, 80, 110, 110, 70)
        for c, w in zip(cols, widths):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor="w")
        for c in diff.changes:
            tv.insert("", "end", values=(c.sheet, c.pi, c.zone, c.alg, c.param,
                                         c.machine, c.old or "(빈)", c.new or "(빈)", c.kind))
        vs = ttk.Scrollbar(win, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vs.set)
        tv.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        vs.pack(side="left", fill="y", pady=6)
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(side="bottom", fill="x", padx=12, pady=(0, 10))

        def save_excel():
            dest = filedialog.asksaveasfilename(
                title="변경내역 엑셀 저장", defaultextension=".xlsx",
                initialfile=f"변경내역_{workdirs.stamp()}.xlsx",
                filetypes=[("Excel", "*.xlsx")], parent=win)
            if not dest:
                return
            history_mod.write_diff_excel(diff, dest, old_label=old_label, new_label=new_label)
            if messagebox.askyesno("저장 완료",
                                   f"{os.path.basename(dest)} 저장.\n지금 Excel로 열까요?",
                                   parent=win):
                self._open_in_excel(dest)
        tk.Button(bt, text="변경내역 엑셀로 저장(비고 메모)", relief="flat", bd=0,
                  bg=self.p["primary"], fg="#ffffff", padx=14, pady=6, cursor="hand2",
                  command=save_excel).pack(side="left")
        if diff.added_rows or diff.removed_rows:
            tk.Label(bt, text=f"  (행 추가/삭제는 엑셀 '행 추가·삭제' 시트에서 확인)",
                     bg=self.p["bg"], fg=self.p["muted"],
                     font=self.fonts["sub"]).pack(side="left", padx=8)
        tk.Button(bt, text="닫기", relief="flat", bd=0, bg=self.p["surface"], padx=14,
                  pady=6, cursor="hand2", command=win.destroy).pack(side="right")

    # ====================================================================
    #  첫 실행 / 저장 폴더 / 참고자료·특이사항 로드 (3차 재설계)
    # ====================================================================
    def _startup(self):
        if not self.save_dir or not os.path.isdir(self.save_dir):
            if not self._choose_save_dir(first=True):
                self._set_status("저장 폴더가 지정되지 않았습니다. ⋯파일에서 지정하세요.")
                return
        self._load_refdata()
        self._load_latest_collate()
        self._render()

    def _choose_save_dir(self, first=False) -> bool:
        if first:
            messagebox.showinfo(
                "저장 폴더 지정",
                "프로그램이 사용할 저장 폴더를 지정하세요.\n"
                "이 폴더 안에 참고자료.xlsx·특이사항.xlsx 와 '양식'·'파라미터 값 취합' "
                "폴더가 만들어집니다.")
        d = filedialog.askdirectory(title="저장 폴더 선택")
        if not d:
            return False
        self.save_dir = d
        self._cfg["save_dir"] = d
        save_config(self._cfg)
        return True

    def _ensure_file(self, path, label, creator) -> str | None:
        """파일이 없으면 [빈 양식 생성] 또는 [다른 파일 선택(복사)] 안내."""
        if os.path.isfile(path):
            return path
        if messagebox.askyesno(
                f"{label} 없음",
                f"저장 폴더에 {os.path.basename(path)} 가 없습니다.\n\n"
                f"[예] = {label} 빈 양식을 새로 만듭니다\n"
                "[아니오] = 기존 파일을 골라 저장 폴더로 복사합니다"):
            creator(path)
            return path
        picked = filedialog.askopenfilename(
            title=f"{label} 엑셀 선택", filetypes=[("Excel", "*.xlsx")])
        if not picked:
            creator(path)              # 취소하면 빈 양식 생성
            return path
        try:
            import shutil
            shutil.copy2(picked, path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("복사 실패", str(e))
            creator(path)
        return path

    def _load_refdata(self):
        if not self.save_dir:
            return
        ipp = self._ensure_file(refdata.ip_path(self.save_dir), "장비 IP 주소",
                                refdata.create_blank_ip)
        rp = self._ensure_file(refdata.ref_path(self.save_dir), "참고자료",
                               refdata.create_blank_reference)
        sp = self._ensure_file(refdata.special_path(self.save_dir), "특이사항",
                               refdata.create_blank_special)
        cfp = self._ensure_file(coefstore.coef_path(self.save_dir), "변환계수",
                                coefstore.create_blank)
        try:
            self.coef_rows = coefstore.load(cfp)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("변환계수 로드 실패", str(e))
            self.coef_rows = []
        try:
            self.ip_rows = refdata.load_ip(ipp)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("장비 IP 로드 실패", str(e))
            self.ip_rows = []
        try:
            self.ref_grid, self.ref_colors = refdata.load_reference(rp)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("참고자료 로드 실패", str(e))
            self.ref_grid, self.ref_colors = [], {}
        try:
            self.special_rows, self.special_colors = refdata.load_special(sp)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("특이사항 로드 실패", str(e))
            self.special_rows, self.special_colors = [], {}
        self._set_status(f"저장 폴더: {self.save_dir}  (호기 {len(self._all_machines())}대)")

    def _load_latest_collate(self):
        """최신 '파라미터 값 취합' 파일을 값 확인용으로 로드(없으면 빈 화면)."""
        if not self.save_dir:
            self.repo = None
            return
        latest = workdirs.latest_collate(self.save_dir)
        if not latest:
            self.repo = None
            return
        try:
            self.repo = collate.load_as_repo(latest, self._all_machines())
            self.path, self.kind, self.read_only = latest, "PI", True
            # 값 확인 그리드는 읽기전용(스냅샷). 특이사항/참고자료 탭은 read_only 를
            # 보지 않으므로 편집·자동저장에 영향 없음.
        except Exception as e:  # noqa: BLE001
            messagebox.showwarning("취합 로드 실패", str(e))
            self.repo = None

    def _save_refdata(self):
        """현재 장비 IP/참고자료/특이사항을 저장 폴더의 파일에 기록(색상 포함)."""
        if not self.save_dir:
            return
        try:
            refdata.save_ip(refdata.ip_path(self.save_dir), self.ip_rows)
            refdata.save_reference(refdata.ref_path(self.save_dir), self.ref_grid,
                                   self.ref_colors)
            refdata.save_special(refdata.special_path(self.save_dir), self.special_rows,
                                 self.special_colors)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("저장 실패", str(e))

    def _on_close(self):
        self.destroy()


def simpledialog_safe(parent, title) -> str | None:
    """tkinter.simpledialog 를 지연 임포트해 새 파라미터 이름을 입력받는다."""
    from tkinter import simpledialog
    return simpledialog.askstring(title, "이름:", parent=parent)


def main():
    app = EquipApp()
    app.mainloop()


if __name__ == "__main__":
    main()
