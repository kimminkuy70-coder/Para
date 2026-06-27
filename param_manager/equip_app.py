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

        # 내비게이션 스택(뒤로/앞으로)
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

        # 본문 컨테이너
        self.body = tk.Frame(self, bg=self.p["bg"])
        self.body.pack(side="top", fill="both", expand=True)

        # 상태바
        self.status = tk.Label(self, text="", anchor="w", bg=self.p["head_bg"],
                               fg=self.p["muted"], font=self.fonts["sub"], padx=10)
        self.status.pack(side="bottom", fill="x")

    def _set_status(self, msg: str):
        self.status.config(text=msg)
        self.update_idletasks()

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
        tk.Label(hdr, text=f" {arrow}  {alg or '(Alg 없음)'}", bg="#e2e8f0",
                 fg=self.p["text"], font=self.fonts["bold"], anchor="w").pack(
            side="left", fill="x", expand=True, ipady=6)
        tk.Label(hdr, text=f"{len(prows)}개  ", bg="#e2e8f0",
                 fg=self.p["muted"], font=self.fonts["sub"]).pack(side="right")
        for w in (hdr, *hdr.winfo_children()):
            w.bind("<Button-1>", lambda e, k=key: self._toggle_alg(k))

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
        new = var.get()
        if engine._s(pr.get(machine)) != engine._s(new):
            pr.set(machine, new if new != "" else None)
            self.dirty = True
            self._set_status(f"변경됨: {engine._s(pr.get('Parameter'))} [{machine}] = {new}")

    def _pick_color(self, pr):
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
        self.repo.cell_colors.pop(_color_key(pr.row_id), None)
        self.dirty = True
        self._render()

    def _highlight_focused(self):
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
            self.read_only = messagebox.askyesno(
                "편집 잠금",
                f"현재 '{lock.user}' 님이 편집 중입니다 (시작 {lock.time}).\n\n"
                "읽기 전용으로 열까요?\n(아니오 = 잠금 무시하고 편집 — 충돌 위험)")
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
