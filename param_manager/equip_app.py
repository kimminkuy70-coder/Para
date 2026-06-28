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
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from tksheet import Sheet

from . import engine
from .engine import MACHINES, ParamRepository
from .theme import apply_theme

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".pi_param_manager.json")
HIGHLIGHT_YELLOW = "#FFF24D"   # 강조(노랑)


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

        # 상단 3탭(파라미터 / 특이사항 / 참고자료)
        self.view = "param"

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

        self._build_chrome()
        self._render()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<F4>", lambda e: self._highlight_focused())
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
        for key, label in (("param", "파라미터"), ("special", "특이사항"),
                           ("reference", "참고자료")):
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
        st = self._state()
        self.btn_back.config(state=("normal" if self.nav_idx > 0 else "disabled"))
        self.btn_fwd.config(state=("normal" if self.nav_idx < len(self.nav) - 1 else "disabled"))
        self._update_crumb(st)
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
    def _screen_machines(self):
        wrap = tk.Frame(self.body, bg=self.p["bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=18)
        tk.Label(wrap, text="호기 선택", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", pady=(0, 4))
        tk.Label(wrap, text="관리할 장비(호기)를 선택하세요.", bg=self.p["bg"],
                 fg=self.p["muted"], font=self.fonts["sub"]).pack(anchor="w", pady=(0, 14))

        grid = tk.Frame(wrap, bg=self.p["bg"])
        grid.pack(fill="both", expand=True)
        cols = 8
        for i, m in enumerate(MACHINES):
            r, c = divmod(i, cols)
            b = tk.Button(grid, text=m, width=10, height=3, relief="flat", bd=0,
                          bg=self.p["surface"], fg=self.p["text"],
                          activebackground=self.p["primary_lt"],
                          font=self.fonts["bold"], cursor="hand2",
                          command=lambda mm=m: self.navigate(screen="s1", machine=mm))
            b.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            b.bind("<Enter>", lambda e, w=b: w.config(bg=self.p["primary_lt"]))
            b.bind("<Leave>", lambda e, w=b: w.config(bg=self.p["surface"]))
        for c in range(cols):
            grid.columnconfigure(c, weight=1)

    # ====================================================================
    #  S1 — PI / RDL
    # ====================================================================
    def _screen_kind(self, st):
        wrap = self._choice_wrap(f"{st['machine']} — 종류 선택", "PI 또는 RDL 을 선택하세요.")
        for kind, desc in (("PI", "PI Core Parameter"), ("RDL", "RDL Parameter")):
            self._big_button(wrap, kind, desc,
                             lambda k=kind: self._enter_kind(k))

    def _enter_kind(self, kind):
        if not self._load_kind(kind):
            return
        self.navigate(screen="s2", kind=kind)

    # ====================================================================
    #  S2 — PI 값(PI2/PI3/PI4 …)
    # ====================================================================
    def _screen_pi(self, st):
        wrap = self._choice_wrap(f"{st['machine']} ▸ {st['kind']} — 단계 선택",
                                 "파일에서 자동 인식된 PI 단계입니다.")
        vals = self._distinct("PI")
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
        ro = "  [읽기 전용]" if self.read_only else ""
        tk.Label(head, text=f"좌=선택 호기 · 우=다른 호기(직접 수정 가능) · Shift+휠=가로스크롤{ro}   ",
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
        mid = tk.Frame(outer, bg=self.p["bg"])
        mid.pack(fill="both", expand=True, padx=12, pady=10)
        vbar = ttk.Scrollbar(mid, orient="vertical", command=self._yview_both)
        vbar.pack(side="right", fill="y")
        self._vbar = vbar

        LEFT_W = 540
        left_wrap = tk.Frame(mid, bg=self.p["bg"], width=LEFT_W)
        left_wrap.pack(side="left", fill="y")
        left_wrap.pack_propagate(False)
        lcanvas = tk.Canvas(left_wrap, bg=self.p["bg"], highlightthickness=0)
        lcanvas.pack(side="left", fill="both", expand=True)
        linner = tk.Frame(lcanvas, bg=self.p["bg"])
        lcanvas.create_window((0, 0), window=linner, anchor="nw", tags="inner")
        lcanvas.bind("<Configure>", lambda e: lcanvas.itemconfig("inner", width=e.width))
        lcanvas.config(yscrollcommand=vbar.set)

        # 좌(선택 호기) / 우(다른 호기) 경계 세로선
        divider = tk.Frame(mid, bg="#94a3b8", width=3)
        divider.pack(side="left", fill="y")

        right_wrap = tk.Frame(mid, bg=self.p["bg"])
        right_wrap.pack(side="left", fill="both", expand=True)
        hbar = ttk.Scrollbar(right_wrap, orient="horizontal")
        hbar.pack(side="bottom", fill="x")
        rcanvas = tk.Canvas(right_wrap, bg=self.p["bg"], highlightthickness=0)
        rcanvas.pack(side="left", fill="both", expand=True)
        hbar.config(command=rcanvas.xview)
        rcanvas.config(xscrollcommand=hbar.set)
        rinner = tk.Frame(rcanvas, bg=self.p["bg"])
        rcanvas.create_window((0, 0), window=rinner, anchor="nw")

        self._left_canvas, self._right_canvas = lcanvas, rcanvas

        self._row_widgets = []
        others = [m for m in self.repo.aoi_units if m != st["machine"]]
        self._build_panes(linner, rinner, st, others)

        def _upd(_=None):
            lcanvas.configure(scrollregion=lcanvas.bbox("all"))
            rcanvas.configure(scrollregion=rcanvas.bbox("all"))
        linner.bind("<Configure>", _upd)
        rinner.bind("<Configure>", _upd)
        self.after(60, _upd)
        self._scope_wheel(mid, lcanvas, rcanvas, hcanvas=rcanvas)

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
        r = 0
        # 헤더행: 좌 라벨 / 우 호기명
        self._grid_row(linner, rinner, r, self.HDR_H)
        lh = tk.Frame(linner, bg=self.p["head_bg"])
        lh.grid(row=r, column=0, sticky="nsew")
        tk.Label(lh, text="  파라미터 〔추천값〕  값", bg=self.p["head_bg"],
                 fg=self.p["muted"], font=self.fonts["sub"], anchor="w").pack(
            side="left", fill="both", expand=True)
        hf = tk.Frame(rinner, bg=self.p["head_bg"])
        hf.grid(row=r, column=0, sticky="nsew")
        for m in others:
            tk.Label(hf, text=m, bg=self.p["head_bg"], fg=self.p["text"],
                     font=self.fonts["sub"], width=10, anchor="center",
                     bd=0, highlightthickness=1,
                     highlightbackground="#b8c0cc").pack(side="left", fill="y")
        r += 1

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
                self._grid_row(linner, rinner, r, self.ROW_H)
                self._build_left_row(linner, r, st, pr, a)
                self._build_right_row(rinner, r, pr, others)
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

    def _build_left_row(self, linner, r, st, pr, alg):
        machine = st["machine"]
        row = tk.Frame(linner, bg=self.p["surface"])
        row.grid(row=r, column=0, sticky="nsew")
        self._row_widgets.append((pr, row, alg))

        grip = tk.Label(row, text="⋮⋮", bg=self.p["surface"], fg=self.p["muted"],
                        font=self.fonts["bold"], cursor="fleur", width=2)
        grip.pack(side="left")
        grip.bind("<ButtonPress-1>", lambda e, p=pr: self._drag_start(e, p))
        grip.bind("<B1-Motion>", self._drag_move)
        grip.bind("<ButtonRelease-1>", lambda e, s=st: self._drag_drop(e, s))

        col = self.repo.cell_colors.get(_color_key(pr.row_id), "")
        chip = tk.Label(row, text=" ", bg=(col or self.p["border"]), width=2,
                        cursor="hand2", relief="flat")
        chip.pack(side="left", padx=(2, 6))
        chip.bind("<Button-1>", lambda e, p=pr, w=chip: self._color_popup(p, w))
        chip.bind("<Button-3>", lambda e, p=pr: self._clear_color(p))

        name = engine._s(pr.get("Parameter")) or "(이름 없음)"
        # 글자 영역(이름 라벨)에는 색을 칠하지 않는다 — 색은 색칩으로만 표시
        lbl = tk.Label(row, text=name, bg=self.p["surface"], fg=self.p["text"],
                       font=self.fonts["base"], width=20, anchor="w")
        lbl.pack(side="left")
        lbl.bind("<Double-Button-1>",
                 lambda e, p=pr, w=lbl: self._edit_popup(
                     w, engine._s(p.get("Parameter")),
                     lambda new, pp=p: self._rename_param(pp, new)))
        for w in (row, lbl):
            w.bind("<Button-3>", lambda e, p=pr: self._param_menu(e, p))

        # 추천값(초기 추천값) — 모든 호기 공통. 직접 수정 가능
        rvar = tk.StringVar(value=engine._s(pr.get("초기 추천값")))
        rent = tk.Entry(row, textvariable=rvar, font=self.fonts["sub"], width=6,
                        relief="solid", bd=1, justify="center", fg=self.p["muted"],
                        disabledbackground=self.p["head_bg"])
        if self.read_only:
            rent.config(state="disabled")
        rent.pack(side="left", padx=(4, 6))
        rent.bind("<FocusOut>", lambda e, p=pr, v=rvar: self._set_reco(p, v))
        rent.bind("<Return>", lambda e, p=pr, v=rvar: (self._set_reco(p, v), self.focus_set()))

        # 선택 호기 입력칸
        var = tk.StringVar(value=engine._s(pr.get(machine)))
        ent = tk.Entry(row, textvariable=var, font=self.fonts["base"], width=12,
                       relief="solid", bd=1, justify="center",
                       disabledbackground=self.p["head_bg"])
        if self.read_only:
            ent.config(state="disabled")
        ent.pack(side="left", padx=2)
        ent.bind("<FocusOut>", lambda e, p=pr, m=machine, v=var: self._set_value(p, m, v))
        ent.bind("<Return>", lambda e, p=pr, m=machine, v=var:
                 (self._set_value(p, m, v), self.focus_set()))
        ent._param = pr

        has_note = bool(engine._s(pr.get("비고")))
        qbtn = tk.Button(row, text="?", width=2, relief="flat", bd=0, cursor="hand2",
                         font=self.fonts["bold"],
                         bg=(self.p["primary_lt"] if has_note else self.p["head_bg"]),
                         fg=(self.p["primary"] if has_note else self.p["muted"]))
        qbtn.config(command=lambda p=pr, w=qbtn: self._show_note(p, w))
        qbtn.pack(side="left", padx=(4, 2))

    def _build_right_row(self, rinner, r, pr, others):
        f = tk.Frame(rinner, bg=self.p["surface"])
        f.grid(row=r, column=0, sticky="nsew")
        for m in others:
            # 다른 호기 값도 직접 수정 가능(해당 호기 컬럼에 반영) — 엑셀형 격자 셀
            var = tk.StringVar(value=engine._s(pr.get(m)))
            e = tk.Entry(f, textvariable=var, width=10, justify="center",
                         font=self.fonts["sub"], fg="#6b7280",
                         relief="solid", bd=1, highlightthickness=0,
                         disabledbackground=self.p["head_bg"])
            if self.read_only:
                e.config(state="disabled")
            e.pack(side="left", fill="y")
            e.bind("<FocusOut>", lambda ev, p=pr, mm=m, v=var: self._set_value(p, mm, v))
            e.bind("<Return>", lambda ev, p=pr, mm=m, v=var:
                   (self._set_value(p, mm, v), self.focus_set()))
            e._param = pr

    # ---- 스크롤 동기/스코프 -------------------------------------------
    def _yview_both(self, *args):
        for c in (getattr(self, "_left_canvas", None), getattr(self, "_right_canvas", None)):
            if c is not None:
                c.yview(*args)

    def _scope_wheel(self, widget, *canvases, hcanvas=None):
        """포인터가 widget 위에 있을 때만 휠 스크롤(다른 창/빈영역 영향 차단).
        세로: 내용이 화면보다 짧으면 무시. 가로(hcanvas): Shift+휠 / 가로 휠."""
        def on_v(e):
            ref = canvases[0]
            bbox = ref.bbox("all")
            if not bbox or (bbox[3] - bbox[1]) <= ref.winfo_height():
                return
            n = int(-e.delta / 120) or (-1 if e.delta > 0 else 1)
            for c in canvases:
                c.yview_scroll(n, "units")
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
    def _set_reco(self, pr, var):
        if self.read_only:
            return
        new = var.get()
        if engine._s(pr.get("초기 추천값")) != engine._s(new):
            self._push_undo()
            pr.set("초기 추천값", new if new != "" else None)
            self.dirty = True
            self._set_status(f"추천값 변경: {engine._s(pr.get('Parameter'))} = {new}")

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
        if self.read_only:
            return
        new = var.get()
        if engine._s(pr.get(machine)) != engine._s(new):
            self._push_undo()
            pr.set(machine, new if new != "" else None)
            self.dirty = True
            self._set_status(f"변경됨: {engine._s(pr.get('Parameter'))} [{machine}] = {new}")

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
    def _make_table(self, headers, data, col_edit=False):
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
        if not self.read_only:
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
        if self.read_only:
            tk.Label(bar, text="읽기 전용 — 다른 사용자가 편집 중", bg=self.p["bg"],
                     fg=self.p["danger"], font=self.fonts["sub"]).pack(side="left")
            return bar
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
        if not self._guard():
            return
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
        self._push_undo()
        cc = self.repo.cell_colors
        for (r, c) in cells:
            key = f"S|{r}|{c}" if kind == "special" else f"R|{r}|{c}"
            if color == "CLEAR":
                cc.pop(key, None)
            else:
                cc[key] = color
        if color not in (None, "CLEAR"):
            self._remember_color(color)
        self.dirty = True
        self._render()

    def _apply_table_colors(self, s, kind):
        cc = self.repo.cell_colors
        pre = "S|" if kind == "special" else "R|"
        for key, color in cc.items():
            if not key.startswith(pre):
                continue
            try:
                _, r, c = key.split("|")
                s.highlight_cells(row=int(r), column=int(c), bg=color,
                                  fg=self._fg_for(color), redraw=False)
            except Exception:
                pass

    @staticmethod
    def _fg_for(hexcolor):
        try:
            h = str(hexcolor).lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"
        except Exception:
            return "#111111"

    def _view_special(self):
        if not self.repo:
            tk.Label(self.body, text="먼저 ⋯파일 메뉴에서 공용 파일을 여세요.",
                     bg=self.p["bg"], fg=self.p["muted"]).pack(pady=30)
            return
        from .engine import SPECIAL_BOOL_COL, SPECIAL_HEADERS
        self._toolbar("special")
        if not self.read_only:
            btnbar = tk.Frame(self.body, bg=self.p["bg"])
            btnbar.pack(side="top", fill="x", padx=10)
            tk.Button(btnbar, text="＋ 특이사항(행) 추가", relief="flat", bd=0,
                      bg=self.p["surface"], fg=self.p["primary"], font=self.fonts["bold"],
                      cursor="hand2", command=self._special_add).pack(side="left", pady=4)
        bcol = SPECIAL_HEADERS.index(SPECIAL_BOOL_COL)
        data = []
        for rec in self.repo.special:
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
        s = self._make_table(SPECIAL_HEADERS, data, col_edit=False)
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
        if self.read_only or self._cur_kind != "special":
            return
        from .engine import SPECIAL_BOOL_COL, SPECIAL_HEADERS
        s = self._cur_sheet
        data = s.get_sheet_data()
        self._push_undo()
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
        self.repo.special = new
        self.dirty = True
        self._set_status("특이사항 변경됨")

    def _special_toggle(self, s, bcol):
        if self.read_only:
            return
        sel = s.get_currently_selected()
        if not sel or getattr(sel, "column", None) != bcol:
            return
        cur = s.get_cell_data(sel.row, bcol)
        s.set_cell_data(sel.row, bcol, "☐" if engine._s(cur) == "☑" else "☑")
        s.redraw()
        self._special_sync()

    def _special_add(self):
        if not self._guard():
            return
        self._push_undo()
        from .engine import SPECIAL_HEADERS
        self.repo.special.append({h: (False if h == "종료 여부" else None) for h in SPECIAL_HEADERS})
        self.dirty = True
        self._render()

    def _view_reference(self):
        if not self.repo:
            tk.Label(self.body, text="먼저 ⋯파일 메뉴에서 공용 파일을 여세요.",
                     bg=self.p["bg"], fg=self.p["muted"]).pack(pady=30)
            return
        self._toolbar("reference")
        if not self.read_only:
            btnbar = tk.Frame(self.body, bg=self.p["bg"])
            btnbar.pack(side="top", fill="x", padx=10)
            tk.Button(btnbar, text="＋ 행 추가", relief="flat", bd=0, bg=self.p["surface"],
                      fg=self.p["primary"], font=self.fonts["bold"], cursor="hand2",
                      command=self._ref_add).pack(side="left", pady=4)
        ncol = max(engine.REF_COLS, max((len(r) for r in self.repo.reference), default=engine.REF_COLS))
        grid = [list(r) + [""] * (ncol - len(r)) for r in self.repo.reference] or [[""] * ncol]
        s = self._make_table(None, [[engine._s(c) for c in row] for row in grid], col_edit=True)
        s.pack(side="top", fill="both", expand=True, padx=10, pady=8)
        for i, w in enumerate((300, 220, 160, 160)):
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
        if self.read_only or self._cur_kind != "reference":
            return
        s = self._cur_sheet
        self._push_undo()
        self.repo.reference = [[engine._s(c) for c in row] for row in s.get_sheet_data()]
        self.dirty = True
        self._set_status("참고자료 변경됨")

    def _ref_add(self):
        if not self._guard():
            return
        self._push_undo()
        self.repo.reference.append([""] * engine.REF_COLS)
        self.dirty = True
        self._render()

    # ====================================================================
    #  파일 / 저장 / 잠금
    # ====================================================================
    def _file_menu(self):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="PI 공용 파일 열기(.xlsx)", command=lambda: self._open_dialog("PI"))
        m.add_command(label="RDL 공용 파일 열기(.xlsx)", command=lambda: self._open_dialog("RDL"))
        m.add_separator()
        m.add_command(label="기존 엑셀(.xlsm) 가져오기 → PI",
                      command=lambda: self._import_dialog("PI"))
        m.add_command(label="기존 엑셀(.xlsm) 가져오기 → RDL",
                      command=lambda: self._import_dialog("RDL"))
        m.add_separator()
        m.add_command(label="다른 이름으로 내보내기", command=self._export_dialog)
        m.add_command(label="새로고침(다시 읽기)", command=self._reload)
        try:
            m.tk_popup(self.btn_file.winfo_rootx(),
                       self.btn_file.winfo_rooty() + self.btn_file.winfo_height())
        finally:
            m.grab_release()

    def _load_kind(self, kind) -> bool:
        """해당 종류의 공용 파일을 로드(이미 같은 파일이면 재사용)."""
        path = self._cfg.get(f"{kind.lower()}_path")
        if not path or not os.path.exists(path):
            return self._open_dialog(kind)
        if self.repo is not None and self.path == path and self.kind == kind:
            return True
        return self._do_open(path, kind)

    def _open_dialog(self, kind) -> bool:
        p = filedialog.askopenfilename(
            title=f"{kind} 공용 파일(.xlsx) 열기",
            filetypes=[("Excel", "*.xlsx"), ("모든 파일", "*.*")])
        if not p:
            return False
        return self._do_open(p, kind)

    def _do_open(self, path, kind) -> bool:
        if self.path and not self.read_only:
            engine.release_lock(self.path, self.user)
        self.read_only = False
        lock = engine.read_lock(path)
        if lock and not lock.is_stale() and lock.user != self.user:
            # 먼저 접속한 사용자가 있음 → 강제 읽기 전용(확인만 가능)
            self.read_only = True
            messagebox.showwarning(
                "편집 중인 사용자 있음",
                f"현재 '{lock.user}' 님이 편집 중입니다 (시작 {lock.time}).\n\n"
                "읽기 전용으로 열립니다. 파라미터 확인만 가능하며 수정/저장은 잠깁니다.\n"
                "(상대가 종료하면 다시 열어 편집할 수 있습니다. "
                f"응답 없는 잠금은 {engine.LOCK_STALE_MINUTES}분 후 자동 해제됩니다.)")
        repo = ParamRepository(path)
        try:
            repo.load()
            added = repo.ensure_machines()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("열기 실패", str(e))
            return False
        self.repo, self.path, self.kind = repo, path, kind
        self.dirty = False
        if not self.read_only:
            engine.write_lock(path, self.user)
            # 파일에 신규 호기 열이 빠져 있으면 즉시 디스크에 반영(저장)
            if added:
                try:
                    repo.save(user=self.user)
                    messagebox.showinfo(
                        "신규 호기 반영",
                        f"엑셀 PI_ALL 시트에 신규 호기 {len(added)}개 열을 추가해 저장했습니다.\n"
                        + ", ".join(added))
                except Exception as e:  # noqa: BLE001
                    messagebox.showwarning("신규 호기 반영 실패",
                                           f"신규 호기 열 저장 중 오류: {e}")
        self._cfg[f"{kind.lower()}_path"] = path
        save_config(self._cfg)
        conflicts = engine.find_conflict_copies(path)
        if conflicts:
            messagebox.showwarning(
                "충돌본 감지",
                "OneDrive 동기화 충돌본으로 보이는 파일이 있습니다:\n"
                + "\n".join(os.path.basename(c) for c in conflicts))
        self._set_status(f"{kind} 파일 로드: {os.path.basename(path)}  "
                         f"(파라미터 {len(repo.rows)}개, 호기 {len(repo.aoi_units)})")
        return True

    def _import_dialog(self, kind):
        src = filedialog.askopenfilename(
            title="가져올 기존 엑셀(.xlsm/.xlsx)",
            filetypes=[("Excel", "*.xlsm *.xlsx"), ("모든 파일", "*.*")])
        if not src:
            return
        dest = filedialog.asksaveasfilename(
            title=f"{kind} 공용 파일로 저장(.xlsx)", defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")])
        if not dest:
            return
        try:
            repo = engine.import_from_xlsm(src, dest)
            repo.ensure_machines()
            repo.save(user=self.user)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("가져오기 실패", str(e))
            return
        self._do_open(dest, kind)
        messagebox.showinfo("가져오기 완료",
                            f"{os.path.basename(dest)} 생성 완료.\n파라미터 {len(repo.rows)}개")

    def _export_dialog(self):
        if not self.path:
            messagebox.showinfo("내보내기", "먼저 파일을 여세요.")
            return
        dest = filedialog.asksaveasfilename(
            title="다른 이름으로 내보내기", defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")])
        if dest:
            engine.export_copy(self.path, dest)
            messagebox.showinfo("내보내기", f"{os.path.basename(dest)} 저장 완료.")

    def _reload(self):
        if not self.path:
            return
        if self.dirty and not messagebox.askyesno(
                "새로고침", "저장하지 않은 변경이 있습니다. 버리고 다시 읽을까요?"):
            return
        self._do_open(self.path, self.kind or "PI")
        self._render()

    def save(self):
        if not self.repo or not self.path:
            messagebox.showinfo("저장", "먼저 파일을 여세요.")
            return
        if self.read_only:
            messagebox.showwarning("읽기 전용", "읽기 전용으로 열려 있어 저장할 수 없습니다.")
            return
        self._set_status("저장 중…")
        try:
            engine.write_lock(self.path, self.user)
            stats = self.repo.save(user=self.user)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("저장 실패", str(e))
            return
        self.dirty = False
        self._set_status(f"저장 완료 — 변경 {stats.get('changes', 0)}건")
        self._render()

    def _on_close(self):
        if self.dirty and not messagebox.askyesno(
                "종료", "저장하지 않은 변경이 있습니다. 그래도 종료할까요?"):
            return
        if self.path and not self.read_only:
            engine.release_lock(self.path, self.user)
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
