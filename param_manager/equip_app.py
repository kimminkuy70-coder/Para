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

        self._build_chrome()
        self._render()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<F4>", lambda e: self._highlight_focused())

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

        # Recipe 제목줄
        head = tk.Frame(outer, bg=self.p["surface"],
                        highlightbackground=self.p["border"], highlightthickness=1)
        head.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(head, text=f"  {st['recipe'] or st['pi']}", bg=self.p["surface"],
                 fg=self.p["text"], font=self.fonts["title"]).pack(side="left", pady=8)
        tk.Label(head, text=f"선택 호기: {st['machine']}   ", bg=self.p["surface"],
                 fg=self.p["primary"], font=self.fonts["bold"]).pack(side="right", pady=8)

        # Zone 가로 탭
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
            # 더블클릭 → Zone 이름 수정
            b.bind("<Double-Button-1>",
                   lambda e, zz=z, w=b, s=st: self._edit_popup(
                       w, zz, lambda new, old=zz, ss=s: self._rename_zone(ss, old, new)))
        tk.Label(ztab, text="  (탭 더블클릭=Zone 이름 수정)", bg=self.p["bg"],
                 fg=self.p["muted"], font=self.fonts["sub"]).pack(side="left")

        # 스크롤 영역(Alg 섹션 + 파라미터 행)
        canvas = tk.Canvas(outer, bg=self.p["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=10)
        vsb.pack(side="right", fill="y", pady=10)
        self._canvas = canvas
        inner = tk.Frame(canvas, bg=self.p["bg"])
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("inner", width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        self._row_widgets = []
        zrows = [r for r in rows if engine._s(r.get("Zone")) == self.cur_zone]
        # Alg 그룹(등장 순서 유지)
        algs = []
        for r in zrows:
            a = engine._s(r.get("Alg"))
            if a not in algs:
                algs.append(a)
        for a in algs:
            self._build_alg_section(inner, st, a, [r for r in zrows
                                                   if engine._s(r.get("Alg")) == a])

        if not zrows:
            tk.Label(inner, text="이 Zone 에 표시할 파라미터가 없습니다.",
                     bg=self.p["bg"], fg=self.p["muted"]).pack(pady=20)

    def _set_zone(self, z):
        self.cur_zone = z
        self._render()

    def _build_alg_section(self, parent, st, alg, prows):
        key = f"{self.cur_zone}|{alg}"
        coll = key in self.collapsed
        sec = tk.Frame(parent, bg=self.p["bg"])
        sec.pack(fill="x", pady=(10, 0))

        hdr = tk.Frame(sec, bg="#e2e8f0", cursor="hand2")
        hdr.pack(fill="x")
        arrow = "▶" if coll else "▼"
        alg_lbl = tk.Label(hdr, text=f" {arrow}  {alg or '(Alg 없음)'}", bg="#e2e8f0",
                           fg=self.p["text"], font=self.fonts["bold"], anchor="w")
        alg_lbl.pack(side="left", fill="x", expand=True, ipady=6)
        tk.Label(hdr, text=f"{len(prows)}개  ", bg="#e2e8f0",
                 fg=self.p["muted"], font=self.fonts["sub"]).pack(side="right")
        for w in (hdr, *hdr.winfo_children()):
            w.bind("<Button-1>", lambda e, k=key: self._toggle_alg(k))
        # 더블클릭 → Alg 이름 수정(접힘 토글보다 우선)
        alg_lbl.bind("<Double-Button-1>",
                     lambda e, a=alg, w=alg_lbl, s=st: self._edit_popup(
                         w, a, lambda new, old=a, ss=s: self._rename_alg(ss, old, new)))

        if coll:
            return

        body = tk.Frame(sec, bg=self.p["surface"],
                        highlightbackground=self.p["border"], highlightthickness=1)
        body.pack(fill="x")
        for pr in prows:
            self._build_param_row(body, st, pr, alg)
        # 파라미터 추가 버튼(Alg 하위)
        add = tk.Button(body, text="＋ 파라미터 추가", relief="flat", bd=0,
                        bg=self.p["surface"], fg=self.p["primary"],
                        font=self.fonts["bold"], cursor="hand2", anchor="w", padx=12,
                        activebackground=self.p["primary_lt"],
                        command=lambda: self._add_param(st, alg))
        add.pack(fill="x", pady=2)

    def _toggle_alg(self, key):
        if key in self.collapsed:
            self.collapsed.discard(key)
        else:
            self.collapsed.add(key)
        self._render()

    def _build_param_row(self, parent, st, pr, alg):
        machine = st["machine"]
        row = tk.Frame(parent, bg=self.p["surface"])
        row.pack(fill="x", padx=6, pady=1)
        self._row_widgets.append((pr, row, alg))

        # 드래그 그립(꾹 눌러 이동)
        grip = tk.Label(row, text="⋮⋮", bg=self.p["surface"], fg=self.p["muted"],
                        font=self.fonts["bold"], cursor="fleur", width=2)
        grip.pack(side="left")
        grip.bind("<ButtonPress-1>", lambda e, p=pr: self._drag_start(e, p))
        grip.bind("<B1-Motion>", self._drag_move)
        grip.bind("<ButtonRelease-1>", lambda e, s=st: self._drag_drop(e, s))

        # 색칩(파라미터별 색/강조)
        col = self.repo.cell_colors.get(_color_key(pr.row_id), "")
        chip = tk.Label(row, text=" ", bg=(col or self.p["border"]), width=2,
                        cursor="hand2", relief="flat")
        chip.pack(side="left", padx=(2, 8))
        chip.bind("<Button-1>", lambda e, p=pr: self._pick_color(p))
        chip.bind("<Button-3>", lambda e, p=pr: self._clear_color(p))

        # 파라미터 이름 {단위/추천값}
        name = engine._s(pr.get("Parameter")) or "(이름 없음)"
        rec = engine._s(pr.get("초기 추천값"))
        ntxt = name + (f"  〔{rec}〕" if rec else "")
        nbg = col or self.p["surface"]
        lbl = tk.Label(row, text=ntxt, bg=nbg, fg=self.p["text"],
                       font=self.fonts["base"], width=34, anchor="w")
        lbl.pack(side="left")
        # 더블클릭 → 파라미터 이름 수정
        lbl.bind("<Double-Button-1>",
                 lambda e, p=pr, w=lbl: self._edit_popup(
                     w, engine._s(p.get("Parameter")),
                     lambda new, pp=p: self._rename_param(pp, new)))

        # 우클릭 → 변경 내역 보기
        for w in (row, lbl):
            w.bind("<Button-3>", lambda e, p=pr: self._param_menu(e, p))

        # 선택 호기 입력칸
        var = tk.StringVar(value=engine._s(pr.get(machine)))
        ent = tk.Entry(row, textvariable=var, font=self.fonts["base"], width=14,
                       relief="solid", bd=1, justify="center",
                       disabledbackground=self.p["head_bg"])
        if self.read_only:
            ent.config(state="disabled")
        ent.pack(side="left", padx=8)
        ent.bind("<FocusOut>", lambda e, p=pr, m=machine, v=var: self._set_value(p, m, v))
        ent.bind("<Return>", lambda e, p=pr, m=machine, v=var: self._set_value(p, m, v))

        # 강조(F4) 표시용으로 입력칸에 현재 파라미터 연결
        ent._param = pr

        # ? 버튼 — 비고(메모) 보기/수정
        has_note = bool(engine._s(pr.get("비고")))
        qbtn = tk.Button(row, text="?", width=2, relief="flat", bd=0, cursor="hand2",
                         font=self.fonts["bold"],
                         bg=(self.p["primary_lt"] if has_note else self.p["head_bg"]),
                         fg=(self.p["primary"] if has_note else self.p["muted"]))
        qbtn.config(command=lambda p=pr, w=qbtn: self._show_note(p, w))
        qbtn.pack(side="left", padx=(2, 4))

        # 다른 호기 값(옅게)
        others = []
        for m in self.repo.aoi_units:
            if m == machine:
                continue
            v = engine._s(pr.get(m))
            if v:
                others.append(f"{m}:{v}")
        otxt = "   ".join(others) if others else "다른 호기 값 없음"
        ol = tk.Label(row, text=otxt, bg=self.p["surface"], fg="#aab2bd",
                      font=self.fonts["sub"], anchor="w", justify="left")
        ol.pack(side="left", fill="x", expand=True, padx=(10, 4))

    # ---- 값/색/추가/삭제 ----------------------------------------------
    def _set_value(self, pr, machine, var):
        if self.read_only:
            return
        new = var.get()
        if engine._s(pr.get(machine)) != engine._s(new):
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

    def _pick_color(self, pr):
        if not self._guard():
            return
        rgb, hx = colorchooser.askcolor(title="파라미터 색 선택",
                                        initialcolor=self.recent_colors[0]
                                        if self.recent_colors else "#FFF24D")
        if not hx:
            return
        self.repo.cell_colors[_color_key(pr.row_id)] = hx
        self._remember_color(hx)
        self.dirty = True
        self._render()

    def _clear_color(self, pr):
        if not self._guard():
            return
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
    #  특이사항 / 참고자료 뷰
    # ====================================================================
    def _scroll_area(self):
        """본문에 스크롤 가능한 inner Frame 생성해 반환."""
        canvas = tk.Canvas(self.body, bg=self.p["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(self.body, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=8)
        vsb.pack(side="right", fill="y", pady=8)
        inner = tk.Frame(canvas, bg=self.p["bg"])
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("inner", width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        return inner

    def _view_special(self):
        if not self.repo:
            tk.Label(self.body, text="먼저 ⋯파일 메뉴에서 공용 파일을 여세요.",
                     bg=self.p["bg"], fg=self.p["muted"]).pack(pady=30)
            return
        from .engine import SPECIAL_BOOL_COL, SPECIAL_HEADERS
        inner = self._scroll_area()
        widths = {"일자": 12, "호기": 9, "라트 번호": 16, "S/M": 6, "Layer": 8,
                  "목적": 14, "진행 상황": 18, "종료 여부": 8, "특이사항": 40}
        # 헤더
        for c, h in enumerate(SPECIAL_HEADERS):
            tk.Label(inner, text=h, bg=self.p["header_bar"], fg="#f8fafc",
                     font=self.fonts["bold"], width=widths.get(h, 12),
                     anchor="w", padx=4).grid(row=0, column=c, sticky="nsew", padx=1, pady=1)
        # 데이터
        for ri, rec in enumerate(self.repo.special, start=1):
            for c, h in enumerate(SPECIAL_HEADERS):
                if h == SPECIAL_BOOL_COL:
                    bv = tk.BooleanVar(value=bool(rec.get(h)))
                    cb = tk.Checkbutton(inner, variable=bv, bg=self.p["surface"],
                                        command=lambda r=rec, v=bv: self._special_set(r, SPECIAL_BOOL_COL, v.get()))
                    if self.read_only:
                        cb.config(state="disabled")
                    cb.grid(row=ri, column=c, sticky="nsew", padx=1, pady=1)
                else:
                    sv = tk.StringVar(value=engine._s(rec.get(h)))
                    e = tk.Entry(inner, textvariable=sv, width=widths.get(h, 12),
                                 font=self.fonts["base"], relief="solid", bd=1)
                    if self.read_only:
                        e.config(state="disabled")
                    e.grid(row=ri, column=c, sticky="nsew", padx=1, pady=1)
                    e.bind("<FocusOut>", lambda ev, r=rec, hh=h, v=sv: self._special_set(r, hh, v.get()))
        # 추가 버튼
        if not self.read_only:
            tk.Button(inner, text="＋ 특이사항 추가", relief="flat", bd=0,
                      bg=self.p["surface"], fg=self.p["primary"], font=self.fonts["bold"],
                      cursor="hand2", command=self._special_add).grid(
                row=len(self.repo.special) + 1, column=0, columnspan=3, sticky="w", pady=6)

    def _special_set(self, rec, field, value):
        if self.read_only:
            return
        cur = rec.get(field)
        if field == "종료 여부":
            value = bool(value)
        new = value if value != "" else None
        if engine._s(cur) != engine._s(new) or (field == "종료 여부" and bool(cur) != value):
            rec[field] = new if field != "종료 여부" else value
            self.dirty = True
            self._set_status("특이사항 변경됨")

    def _special_add(self):
        if not self._guard():
            return
        from .engine import SPECIAL_HEADERS
        rec = {h: (False if h == "종료 여부" else None) for h in SPECIAL_HEADERS}
        self.repo.special.append(rec)
        self.dirty = True
        self._render()

    def _view_reference(self):
        if not self.repo:
            tk.Label(self.body, text="먼저 ⋯파일 메뉴에서 공용 파일을 여세요.",
                     bg=self.p["bg"], fg=self.p["muted"]).pack(pady=30)
            return
        inner = self._scroll_area()
        tk.Label(inner, text="참고자료 (호기 IP 등). 셀을 직접 수정할 수 있습니다.",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"]).grid(
            row=0, column=0, columnspan=engine.REF_COLS, sticky="w", pady=(0, 6))
        grid = [list(r) + [""] * (engine.REF_COLS - len(r)) for r in self.repo.reference]
        for ri, rowv in enumerate(grid):
            for ci in range(engine.REF_COLS):
                sv = tk.StringVar(value=engine._s(rowv[ci]) if ci < len(rowv) else "")
                e = tk.Entry(inner, textvariable=sv, width=26, font=self.fonts["base"],
                             relief="solid", bd=1)
                if self.read_only:
                    e.config(state="disabled")
                e.grid(row=ri + 1, column=ci, sticky="nsew", padx=1, pady=1)
                e.bind("<FocusOut>", lambda ev, r=ri, c=ci, v=sv: self._ref_set(r, c, v.get()))
        if not self.read_only:
            tk.Button(inner, text="＋ 행 추가", relief="flat", bd=0, bg=self.p["surface"],
                      fg=self.p["primary"], font=self.fonts["bold"], cursor="hand2",
                      command=self._ref_add).grid(
                row=len(grid) + 1, column=0, sticky="w", pady=6)

    def _ref_set(self, r, c, value):
        if self.read_only:
            return
        ref = self.repo.reference
        while len(ref) <= r:
            ref.append([""] * engine.REF_COLS)
        while len(ref[r]) <= c:
            ref[r].append("")
        if engine._s(ref[r][c]) != engine._s(value):
            ref[r][c] = value
            self.dirty = True
            self._set_status("참고자료 변경됨")

    def _ref_add(self):
        if not self._guard():
            return
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
            repo.ensure_machines()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("열기 실패", str(e))
            return False
        self.repo, self.path, self.kind = repo, path, kind
        self.dirty = False
        if not self.read_only:
            engine.write_lock(path, self.user)
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
