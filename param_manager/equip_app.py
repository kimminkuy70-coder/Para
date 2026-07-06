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

from . import collate
from . import collector
from . import downloader as dl
from . import engine
from . import extract_io
from . import formbuilder
from . import history as history_mod
from . import ini_parser
from . import refresh as refresh_mod
from . import rtp_parser as rtp
from . import versioning
from . import workdirs
from .engine import MACHINES, ParamRepository
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

        self._build_chrome()
        self._render()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<F4>", lambda e: self._highlight_focused())
        self.after(200, self._auto_open_last)   # 첫 실행: 마지막 양식 자동 열기
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
                           ("special", "특이사항"), ("reference", "참고자료")):
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
        """고정 34호기 + 사용자가 추가한 커스텀 호기(중복 제거, 순서 유지)."""
        out = list(MACHINES)
        for m in self._cfg.get("custom_machines", []):
            if m and m not in out:
                out.append(m)
        return out

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
        machines = self._all_machines()
        custom = set(self._cfg.get("custom_machines", []))
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
        """새 AOI 호기(열) 추가 — 다른 호기들과 동일한 파라미터로 운용."""
        from tkinter import simpledialog
        name = simpledialog.askstring(
            "호기 추가",
            "추가할 호기 이름을 입력하세요.\n(예: AOI-26, AOI-K7)",
            parent=self)
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        if name in self._all_machines():
            messagebox.showinfo("이미 있음", f"'{name}' 호기는 이미 있습니다.")
            return
        custom = list(self._cfg.get("custom_machines", []))
        custom.append(name)
        self._cfg["custom_machines"] = custom
        save_config(self._cfg)
        # 현재 열려 있는 파일에 즉시 열 추가(다른 파일은 다음에 열 때 자동 반영)
        saved = False
        if self.repo is not None and not self.read_only:
            added = self.repo.ensure_machines(self._all_machines())
            if added:
                try:
                    self.repo.save(user=self.user)
                    saved = True
                except Exception:  # noqa: BLE001
                    self.dirty = True
        self._render()
        msg = f"호기 '{name}' 추가 완료. 기존 호기와 동일한 파라미터로 운용됩니다."
        if self.repo is not None and not saved and not self.read_only:
            msg += "\n(현재 파일에는 열을 추가했으나 저장은 보류 — 저장 버튼으로 반영)"
        elif self.repo is None:
            msg += "\n(PI/RDL 파일을 열면 해당 호기 열이 자동 추가됩니다.)"
        messagebox.showinfo("호기 추가", msg)

    def _machine_ctx(self, event, machine):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label=f"'{machine}' 호기 삭제",
                      command=lambda: self._remove_custom_machine(machine))
        m.tk_popup(event.x_root, event.y_root)

    def _remove_custom_machine(self, machine):
        if not messagebox.askyesno(
                "호기 삭제",
                f"'{machine}' 호기를 목록에서 제거할까요?\n"
                "(이미 저장된 파일의 열/값은 그대로 남습니다.)"):
            return
        custom = [m for m in self._cfg.get("custom_machines", []) if m != machine]
        self._cfg["custom_machines"] = custom
        save_config(self._cfg)
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
        # 좌측 행 레이아웃(grip/chip/이름/추천값/값/?)에 맞춰 컬럼 제목 정렬
        tk.Label(lhdr, text="", bg=hb, width=2, font=self.fonts["bold"]).pack(side="left")           # grip
        tk.Label(lhdr, text="", bg=hb, width=2).pack(side="left", padx=(2, 6))                       # chip
        tk.Label(lhdr, text="파라미터", bg=hb, fg=hfg, font=self.fonts["base"],
                 width=20, anchor="w").pack(side="left")
        tk.Label(lhdr, text="추천값", bg=hb, fg=self.p["primary"], font=self.fonts["sub"],
                 width=6, anchor="center").pack(side="left", padx=(4, 6))
        tk.Label(lhdr, text=f"{st['machine']} 값", bg=hb, fg=self.p["primary"],
                 font=self.fonts["sub"], width=12, anchor="center").pack(side="left", padx=2)
        tk.Label(lhdr, text="비고", bg=hb, fg=hfg, font=self.fonts["sub"],
                 width=2).pack(side="left", padx=(4, 2))
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
        if self.read_only or self.values_readonly:
            ent.config(state="disabled")     # 값 확인은 읽기 전용(스펙)
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
        """우측 셀들 중 가장 긴 값 기준으로 필요한 줄 수(자동 줄바꿈)."""
        import math
        mx = 1
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
        tk.Button(bar, text="📂 값 파일 열기", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=12, pady=5, cursor="hand2",
                  command=self._open_value_file).pack(side="left", padx=(10, 4), pady=5)
        tk.Button(bar, text="🔄 파라미터 값 업데이트", relief="flat", bd=0,
                  bg=self.p["primary"], fg="#ffffff", padx=12, pady=5, cursor="hand2",
                  command=self._update_values_dialog).pack(side="left", padx=4, pady=5)
        tk.Button(bar, text="🕑 파라미터 이력 확인", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=12, pady=5, cursor="hand2",
                  command=self._history_dialog).pack(side="left", padx=4, pady=5)
        tk.Label(bar, text="  (값은 읽기 전용 — '값 업데이트'로만 채웁니다)",
                 bg=self.p["head_bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left", padx=6)
        tk.Button(bar, text="⋯ 더보기", relief="flat", bd=0, bg=self.p["head_bg"],
                  fg=self.p["muted"], padx=10, pady=5, cursor="hand2",
                  command=self._more_menu).pack(side="right", padx=(4, 10), pady=5)

    def _detect_kind(self, path) -> str:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True)
            names = wb.sheetnames
            wb.close()
            if any("RDL" in engine._s(n).upper() for n in names):
                return "RDL"
        except Exception:  # noqa: BLE001
            pass
        return "PI"

    def _open_value_file(self):
        """취합/양식 엑셀(.xlsx)을 화면으로 불러와 값 확인(PI/RDL 자동 판별)."""
        p = filedialog.askopenfilename(
            title="값 파일(취합/양식 .xlsx) 열기",
            filetypes=[("Excel", "*.xlsx"), ("모든 파일", "*.*")])
        if not p:
            return
        if self._do_open(p, self._detect_kind(p)):
            self.view = "param"
            self._sync_tab_style()
            self.navigate(screen="s0")

    def _more_menu(self):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="PI 공용 파일 열기(.xlsx)", command=lambda: self._open_dialog("PI"))
        m.add_command(label="RDL 공용 파일 열기(.xlsx)", command=lambda: self._open_dialog("RDL"))
        m.add_separator()
        m.add_command(label="기존 엑셀(.xlsm) 가져오기 → PI",
                      command=lambda: self._import_dialog("PI"))
        m.add_command(label="기존 엑셀(.xlsm) 가져오기 → RDL",
                      command=lambda: self._import_dialog("RDL"))
        m.add_command(label="장비 폴더에서 파라미터 다운로드…", command=self._download_dialog)
        m.add_separator()
        m.add_command(label="파라미터 불러오기(통합 마법사)…", command=self._curate_dialog)
        m.add_command(label="다른 이름으로 내보내기", command=self._export_dialog)
        m.add_command(label="새로고침(다시 읽기)", command=self._reload)
        try:
            m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            m.grab_release()

    def _file_menu(self):
        """스펙 1.1.1.1 — ⋯파일 기능 단순화: 특이사항/참고자료 엑셀 불러오기만."""
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="특이사항 엑셀(.xlsx) 불러오기",
                      command=self._load_special_excel)
        m.add_command(label="참고자료 엑셀(.xlsx) 불러오기",
                      command=self._load_reference_excel)
        try:
            m.tk_popup(self.btn_file.winfo_rootx(),
                       self.btn_file.winfo_rooty() + self.btn_file.winfo_height())
        finally:
            m.grab_release()

    def _load_special_excel(self):
        if not self.repo:
            messagebox.showinfo("특이사항 불러오기",
                                "먼저 값 파일을 열어 두세요('값 파일 열기').")
            return
        p = filedialog.askopenfilename(title="특이사항 엑셀(.xlsx)",
                                       filetypes=[("Excel", "*.xlsx")])
        if not p:
            return
        from .engine import SPECIAL_BOOL_COL, SPECIAL_HEADERS
        try:
            import openpyxl
            wb = openpyxl.load_workbook(p, data_only=True)
            ws = wb[wb.sheetnames[0]]
            heads = [engine._s(c.value).strip() for c in ws[1]]
            hidx = {h: i for i, h in enumerate(heads) if h in SPECIAL_HEADERS}
            rows = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row is None or all(v in (None, "") for v in row):
                    continue
                rec = {}
                for h in SPECIAL_HEADERS:
                    v = row[hidx[h]] if h in hidx and hidx[h] < len(row) else None
                    if h == SPECIAL_BOOL_COL:
                        rec[h] = engine._s(v).strip() in ("☑", "Y", "1", "True", "종료", "예")
                    else:
                        rec[h] = v
                rows.append(rec)
            wb.close()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("불러오기 실패", str(e))
            return
        if not rows:
            messagebox.showinfo("특이사항 불러오기", "읽을 행이 없습니다.")
            return
        replace = messagebox.askyesno(
            "특이사항 불러오기",
            f"{len(rows)}행을 읽었습니다.\n\n[예]=기존 특이사항을 이 내용으로 교체\n"
            "[아니오]=기존 아래에 이어붙이기")
        self._push_undo()
        self.repo.special = rows if replace else (list(self.repo.special) + rows)
        self.dirty = True
        self.view = "special"
        self._sync_tab_style()
        self._render()

    def _load_reference_excel(self):
        if not self.repo:
            messagebox.showinfo("참고자료 불러오기",
                                "먼저 값 파일을 열어 두세요('값 파일 열기').")
            return
        p = filedialog.askopenfilename(title="참고자료 엑셀(.xlsx)",
                                       filetypes=[("Excel", "*.xlsx")])
        if not p:
            return
        try:
            import openpyxl
            wb = openpyxl.load_workbook(p, data_only=True)
            ws = wb[wb.sheetnames[0]]
            grid = []
            for row in ws.iter_rows(values_only=True):
                if row is None or all(v in (None, "") for v in row):
                    continue
                grid.append([engine._s(v) for v in row])
            wb.close()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("불러오기 실패", str(e))
            return
        if not grid:
            messagebox.showinfo("참고자료 불러오기", "읽을 행이 없습니다.")
            return
        replace = messagebox.askyesno(
            "참고자료 불러오기",
            f"{len(grid)}행을 읽었습니다.\n\n[예]=기존 참고자료를 교체\n"
            "[아니오]=기존 아래에 이어붙이기")
        self._push_undo()
        self.repo.reference = grid if replace else (list(self.repo.reference) + grid)
        self.dirty = True
        self.view = "reference"
        self._sync_tab_style()
        self._render()

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
            added = repo.ensure_machines(self._all_machines())
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
                except PermissionError:
                    messagebox.showwarning(
                        "신규 호기 반영 보류",
                        "신규 호기 열을 추가했지만 파일에 저장하지 못했습니다(권한/잠금).\n"
                        "Excel에서 이 파일을 닫은 뒤 저장 버튼을 누르면 반영됩니다.")
                except Exception as e:  # noqa: BLE001
                    messagebox.showwarning("신규 호기 반영 실패",
                                           f"신규 호기 열 저장 중 오류: {e}")
        self._cfg[f"{kind.lower()}_path"] = path
        self._cfg["last_form"] = path
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
            repo.ensure_machines(self._all_machines())
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
        except PermissionError:
            messagebox.showerror(
                "저장 실패 — 권한/잠금",
                "파일에 저장할 수 없습니다 (권한 거부).\n\n"
                "다음을 확인하세요:\n"
                "1. 이 파일을 Excel에서 열어두지 않았는지 (열려 있으면 닫고 다시 저장)\n"
                "2. 파일 속성의 '읽기 전용' 체크 해제\n"
                "3. OneDrive 동기화가 끝났는지\n"
                "4. 다른 사람이 편집 중이면 그 사람이 닫은 뒤 저장\n\n"
                f"경로: {self.path}")
            self._set_status("저장 실패 — 파일이 열려있거나 권한이 없습니다.")
            return
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("저장 실패", str(e))
            return
        self.dirty = False
        self._set_status(f"저장 완료 — 변경 {stats.get('changes', 0)}건")
        self._render()

    # ====================================================================
    #  장비 폴더에서 파라미터 다운로드 (para-auto)
    # ====================================================================
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
    def _curate_dialog(self):
        win = tk.Toplevel(self)
        win.title("파라미터 불러오기(통합)")
        win.geometry("1180x760")
        win.configure(bg=self.p["bg"])
        self._cur_win = win
        self._cur_items = []
        self._cur_machines = []
        self._cur_sources = []          # 수집 결과 [(path, level, aoi)]
        self._cur_pivot_rows = []       # 값 갱신용 파싱 피벗
        self._cur_pivot_machines = []
        self._cur_stamp = None          # 실행일시(폴더 배치용)

        tk.Label(win, text="파라미터 불러오기(통합) — 수집 → 취사선택 → 양식/값갱신",
                 bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", padx=14, pady=(12, 0))
        tk.Label(win, text="① 장비에서 수집(읽기전용 복사) 또는 받아둔 로컬 폴더 분석 "
                          "(GlobalRTP.ini·OpticPreset.ini·Zones 기준, RTP.txt 미사용) → "
                          "② 화면에서 쓸 파라미터 체크(01_초안 자동 저장) → "
                          "③ 양식 만들기 또는 열린 공용 파일 값 갱신(백업 자동).",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=14)

        top = tk.Frame(win, bg=self.p["bg"])
        top.pack(fill="x", padx=14, pady=8)
        tk.Button(top, text="① 장비에서 수집…", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=14, cursor="hand2",
                  command=self._cur_collect_dialog).pack(side="left")
        tk.Label(top, text="  또는 로컬 폴더:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).pack(side="left")
        self._cur_path = tk.StringVar(value=self._cfg.get("param_folder", ""))
        tk.Entry(top, textvariable=self._cur_path, font=self.fonts["base"],
                 relief="solid", bd=1).pack(side="left", fill="x", expand=True, padx=(4, 0))
        tk.Button(top, text="폴더 선택", relief="flat", bd=0, bg=self.p["surface"],
                  cursor="hand2", command=self._cur_pick).pack(side="left", padx=6)
        tk.Button(top, text="분석", relief="flat", bd=0, bg=self.p["primary"], fg="#ffffff",
                  padx=14, cursor="hand2", command=self._cur_analyze).pack(side="left")

        sel = tk.Frame(win, bg=self.p["bg"])
        sel.pack(fill="x", padx=14)
        tk.Label(sel, text="Recipe·배율:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).pack(side="left")
        self._cur_group = ttk.Combobox(sel, state="readonly", width=30)
        self._cur_group.pack(side="left", padx=6)
        self._cur_group.bind("<<ComboboxSelected>>", lambda e: self._cur_render())
        self._cur_only_match = tk.BooleanVar(value=False)
        tk.Checkbutton(sel, text="사전 매칭만(신규 항목) 보기", variable=self._cur_only_match,
                       bg=self.p["bg"], command=self._cur_render).pack(side="left", padx=8)
        tk.Label(sel, text="  기존 양식(위) + 새로 불러온 항목(아래)을 각각 전체선택으로 고르세요.",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"]).pack(side="left")

        mid = tk.Frame(win, bg=self.p["surface"], highlightbackground=self.p["border"],
                       highlightthickness=1)
        mid.pack(fill="both", expand=True, padx=14, pady=6)
        canvas = tk.Canvas(mid, bg=self.p["surface"], highlightthickness=0)
        vsb = ttk.Scrollbar(mid, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._cur_inner = tk.Frame(canvas, bg=self.p["surface"])
        canvas.create_window((0, 0), window=self._cur_inner, anchor="nw", tags="i")
        self._cur_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("i", width=e.width))
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        bot = tk.Frame(win, bg=self.p["bg"])
        bot.pack(fill="x", padx=14, pady=(0, 12))
        tk.Button(bot, text="③ 선택 항목으로 양식 만들기(.xlsx)", relief="flat", bd=0,
                  bg=self.p["ok"], fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=self._cur_save).pack(side="left")
        tk.Button(bot, text="③ 열린 공용 파일 값 갱신(백업 후)", relief="flat", bd=0,
                  bg=self.p["primary"], fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=self._cur_update_values).pack(side="left", padx=(8, 0))
        tk.Label(bot, text="(양식: 선택 항목만 새 파일로 / 값갱신: 열린 파일 구조 유지·값만)",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"]).pack(side="left", padx=8)
        self._cur_status = tk.Label(bot, text="", bg=self.p["bg"], fg=self.p["muted"],
                                    font=self.fonts["sub"])
        self._cur_status.pack(side="left", padx=12)

    def _cur_pick(self):
        d = filedialog.askdirectory(title="파라미터 폴더 선택")
        if d:
            self._cur_path.set(d)

    def _cur_analyze(self, from_collect: bool = False):
        """소스(수집 결과 또는 로컬 폴더)를 ini 기준으로 파싱해 취사선택 목록 구성.
        파싱 소스 = GlobalRTP.ini + OpticPreset.ini + Zones/*.ini (RTP.txt 미사용)."""
        sources = list(self._cur_sources) if from_collect else []
        if not sources:
            path = self._cur_path.get().strip()
            if not path or not os.path.isdir(path):
                self._cur_status.config(text="폴더를 선택하거나 장비에서 수집하세요.")
                return
            self._cfg["param_folder"] = path
            save_config(self._cfg)
            sources = [(path, "", "")]
            self._cur_sources = []
        self._cur_status.config(text="분석 중…")
        self.update_idletasks()
        try:
            cfgs = []
            for spath, level, aoi in sources:
                cfgs += ini_parser.scan_tree(spath, default_level=level,
                                             default_equipment=aoi)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("분석 실패", str(e), parent=self._cur_win)
            return

        valid = [c for c in cfgs if rtp.config_valid(c)]
        invalid = [c for c in cfgs if not rtp.config_valid(c)]
        # 변형 미지정(구조 안 맞는) 폴더 → 불러오지 않고 안내
        if invalid:
            lines = []
            for c in invalid[:25]:
                lines.append(f"· {c.config_dir.name}  ({rtp.invalid_reason(c)})")
            more = f"\n…외 {len(invalid) - 25}개" if len(invalid) > 25 else ""
            messagebox.showwarning(
                "변형 미지정 폴더(불러오지 않음)",
                f"아래 {len(invalid)}개 폴더는 변형이 지정되지 않아 불러오지 않습니다.\n"
                "PI 는 폴더명에 PI/PI3…(기본) 또는 BUBBLE 포함,\n"
                "RDL 은 x5/x20 폴더(또는 OpticPreset 의 Scan2d Mag)여야 합니다.\n\n"
                + "\n".join(lines) + more, parent=self._cur_win)
        if not valid:
            messagebox.showerror(
                "불러올 항목 없음",
                "설정 파일(GlobalRTP.ini/OpticPreset.ini/Zones)을 가진 유효 폴더가 없습니다.\n"
                "폴더 구조를 맞춘 뒤 다시 시도하세요.", parent=self._cur_win)
            self._cur_status.config(text="인식된 유효 폴더 없음.")
            return
        # 제대로 인식된 것 불러올지 확인
        vsum = {}
        for c in valid:
            vsum.setdefault(f"{c.layer} {c.recipe} {c.mag}", 0)
            vsum[f"{c.layer} {c.recipe} {c.mag}"] += 1
        if not messagebox.askyesno(
                "인식 결과",
                f"제대로 인식된 설정 {len(valid)}개를 불러올까요?"
                + (f"  (미지정 {len(invalid)}개 제외)" if invalid else "") + "\n\n"
                + ", ".join(f"{k}×{v}" for k, v in sorted(vsum.items())),
                parent=self._cur_win):
            self._cur_status.config(text="불러오기 취소.")
            return
        try:
            rows, machines = ini_parser.build_pivot(valid)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("분석 실패", str(e), parent=self._cur_win)
            return
        self._cur_pivot_rows = rows          # 값 갱신(③)용 원본 피벗
        self._cur_pivot_machines = list(machines)
        if not self._cur_stamp:
            self._cur_stamp = workdirs.run_stamp()

        self._cur_items = []
        existing_keys = set()

        # 1) 기존 양식(현재 저장돼 있는 PI/RDL 파일)을 먼저 불러온다
        for kind, layer in (("pi_path", "PI"), ("rdl_path", "RDL")):
            fp = self._cfg.get(kind)
            if not fp or not os.path.exists(fp):
                continue
            try:
                erepo = ParamRepository(fp)
                erepo.load()
            except Exception:  # noqa: BLE001
                continue
            for m in erepo.aoi_units:
                if m not in machines:
                    machines.append(m)
            for pr in erepo.rows:
                recipe = engine._s(pr.get("PI"))
                mag = engine._s(pr.get("Recipe")) or "-"
                zone = engine._s(pr.get("Zone")); alg = engine._s(pr.get("Alg"))
                param = engine._s(pr.get("Parameter"))
                vals = {m: pr.get(m) for m in erepo.aoi_units}
                key = (layer, recipe, mag, rtp.norm_key(zone), rtp.norm_key(alg), rtp.norm_key(param))
                existing_keys.add(key)
                self._cur_items.append(self._cur_make_item(
                    "existing", layer, recipe, mag, zone, alg, param, vals,
                    name=param, note=engine._s(pr.get("비고")), matched=True,
                    rep=engine._s(pr.get("초기 추천값")) or self._cur_rep(vals)))

        # 2) 폴더에서 새로 불러온 항목 — 기존에 이미 있는 것은 제외
        self._cur_machines = machines
        groups = []
        for r in rows:
            key = (r["layer"], r["recipe"], r["mag"],
                   rtp.norm_key(r["zone"]), rtp.norm_key(r["alg"]), rtp.norm_key(r["param"]))
            if key in existing_keys:
                continue
            rec = rtp.recommend(r["layer"], r["recipe"], r["mag"], r["zone"], r["alg"], r["param"])
            self._cur_items.append(self._cur_make_item(
                "new", r["layer"], r["recipe"], r["mag"], r["zone"], r["alg"], r["param"],
                r["values"], name=(rec or {}).get("param") or r["param"],
                note=(rec or {}).get("desc_kr") or "", matched=rec is not None,
                rep=self._cur_rep({m: v for m, v in r["values"].items() if engine._s(v) != ""}),
                ext=r.get("extract")))

        for it in self._cur_items:
            g = f"{it['layer']} / {it['recipe']} / {it['mag']}"
            if g not in groups:
                groups.append(g)
        self._cur_group["values"] = groups
        if groups:
            self._cur_group.current(0)
        ne = sum(1 for it in self._cur_items if it["source"] == "existing")
        nn = len(self._cur_items) - ne
        # ② 01_초안 자동 저장 — 새로 파싱된 전체(취사선택 전 스냅샷)
        snap_note = ""
        try:
            new_items = [it for it in self._cur_items if it["source"] == "new"]
            written = self._write_stage_snapshots("initial", new_items)
            if written:
                snap_note = f" 01_초안 {len(written)}개 저장."
        except Exception as e:  # noqa: BLE001
            snap_note = f" (01_초안 저장 실패: {e})"
        self._cur_status.config(
            text=f"분석 완료: 기존 {ne} + 새로 {nn} = {len(self._cur_items)}항목, "
                 f"호기 {len(machines)}.{snap_note}")
        self._cur_render()

    def _cur_make_item(self, source, layer, recipe, mag, zone, alg, param, vals,
                       name, note, matched, rep, ext=None):
        return {
            "source": source, "layer": layer, "recipe": recipe, "mag": mag,
            "zone": zone, "alg": alg, "param": param, "values": dict(vals),
            "rep": rep, "matched": matched,
            "ext": ext,   # 재추출 메타(설정파일/섹션/키/변환) — _EXTRACT_MAP 기록용
            "sel": tk.BooleanVar(value=(source == "existing")),  # 기존은 기본 유지
            "name": tk.StringVar(value=name), "note": tk.StringVar(value=note),
            # 변형: 폴더명으로 판정된 값(PI/PI-bubble/x5/x20)을 기본 선택.
            # ini 인식이 실패해 ""이면 사용자가 직접 골라야 저장됨(기존 정책).
            "variant": tk.StringVar(value=mag),
        }

    @staticmethod
    def _cur_rep(vals: dict) -> str:
        vv = [engine._s(v) for v in vals.values() if engine._s(v) != ""]
        if not vv:
            return ""
        from collections import Counter
        return Counter(vv).most_common(1)[0][0]

    def _cur_group_items(self, source=None):
        if not self._cur_group.get():
            return []
        layer, recipe, mag = [x.strip() for x in self._cur_group.get().split("/")]
        out = []
        for it in self._cur_items:
            if it["layer"] != layer or it["recipe"] != recipe or it["mag"] != mag:
                continue
            if source and it["source"] != source:
                continue
            if it["source"] == "new" and self._cur_only_match.get() and not it["matched"]:
                continue
            out.append(it)
        return out

    def _cur_section(self, title, items, color):
        bar = tk.Frame(self._cur_inner, bg=color)
        bar.pack(fill="x", pady=(8, 0))
        tk.Label(bar, text=f"  {title} ({len(items)})", bg=color, fg="#ffffff",
                 font=self.fonts["bold"], anchor="w").pack(side="left", ipady=3)
        tk.Button(bar, text="전체선택", relief="flat", bd=0, bg="#ffffff",
                  cursor="hand2", command=lambda: [it["sel"].set(True) for it in items]).pack(side="right", padx=2, pady=2)
        tk.Button(bar, text="전체해제", relief="flat", bd=0, bg="#ffffff",
                  cursor="hand2", command=lambda: [it["sel"].set(False) for it in items]).pack(side="right", padx=2, pady=2)
        hdr = tk.Frame(self._cur_inner, bg=self.p["head_bg"])
        hdr.pack(fill="x")
        for txt, w in (("✓", 3), ("변형(PI/PI_bubble)", 16), ("Zone", 16), ("Alg", 18),
                       ("파라미터(추천이름)", 24), ("비고(번역)", 28), ("대표값/호기", 16)):
            tk.Label(hdr, text=txt, bg=self.p["head_bg"], fg=self.p["muted"],
                     font=self.fonts["sub"], width=w, anchor="w").pack(side="left")
        for it in items:
            row = tk.Frame(self._cur_inner, bg=self.p["surface"])
            row.pack(fill="x")
            tk.Checkbutton(row, variable=it["sel"], bg=self.p["surface"], width=2).pack(side="left")
            vbox = tk.Frame(row, bg=self.p["surface"], width=130)
            vbox.pack(side="left")
            vbox.pack_propagate(False)
            if it["layer"] == "PI":
                # PI 는 PI / PI-bubble 을 직접 선택(미정이면 저장 차단). 기존 양식 라벨과 통일
                tk.Radiobutton(vbox, text="PI", variable=it["variant"], value="PI",
                               bg=self.p["surface"], font=self.fonts["sub"]).pack(side="left")
                tk.Radiobutton(vbox, text="PI-bubble", variable=it["variant"], value="PI-bubble",
                               bg=self.p["surface"], font=self.fonts["sub"]).pack(side="left")
            else:
                tk.Entry(vbox, textvariable=it["variant"], font=self.fonts["sub"],
                         relief="solid", bd=1, justify="center").pack(side="left", fill="x", expand=True)
            tk.Label(row, text=it["zone"], bg=self.p["surface"], fg=self.p["text"],
                     font=self.fonts["sub"], width=16, anchor="w").pack(side="left")
            tk.Label(row, text=it["alg"], bg=self.p["surface"], fg=self.p["muted"],
                     font=self.fonts["sub"], width=18, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=it["name"], font=self.fonts["sub"], width=24,
                     relief="solid", bd=1).pack(side="left", padx=1)
            tk.Entry(row, textvariable=it["note"], font=self.fonts["sub"], width=28,
                     relief="solid", bd=1).pack(side="left", padx=1)
            nval = len([v for v in it["values"].values() if engine._s(v) != ""])
            tag = "" if it["matched"] else "  ✦신규"
            tk.Label(row, text=f"{it['rep']}  ({nval}호기){tag}", bg=self.p["surface"],
                     fg=("#9aa3af" if it["matched"] else self.p["danger"]),
                     font=self.fonts["sub"], width=18, anchor="w").pack(side="left")

    def _cur_render(self):
        for w in self._cur_inner.winfo_children():
            w.destroy()
        ex = self._cur_group_items("existing")
        nw = self._cur_group_items("new")
        if ex:
            self._cur_section("기존 양식 (유지할 것 선택)", ex, "#1d4ed8")
        if nw:
            self._cur_section("새로 불러옴 (추가할 것 선택)", nw, self.p["ok"])
        if not ex and not nw:
            tk.Label(self._cur_inner, text="이 그룹에 표시할 항목이 없습니다.",
                     bg=self.p["surface"], fg=self.p["muted"]).pack(pady=20)
        self._cur_status.config(
            text=f"{self._cur_group.get()} — 기존 {len(ex)} / 새로 {len(nw)}")

    def _cur_records(self, items, only_machine=None):
        """items → (공용 스키마 레코드, 재추출 메타) 병렬 목록.
        only_machine 지정 시 그 호기 값만 싣는다(호기별 스냅샷용)."""
        recs, exts = [], []
        for it in items:
            rec = {"PI": it["recipe"], "Recipe": it["variant"].get().strip() or it["mag"],
                   "Zone": it["zone"], "Alg": it["alg"],
                   "Parameter": it["name"].get().strip() or it["param"],
                   "초기 추천값": it["rep"], "비고": it["note"].get().strip()}
            for m, v in it["values"].items():
                if not m or engine._s(v) == "":
                    continue
                if only_machine is not None and m != only_machine:
                    continue
                rec[m] = v
            recs.append(rec)
            exts.append(it.get("ext"))
        return recs, exts

    def _snapshot_base_dir(self, default=None) -> str | None:
        """initial/final/백업 폴더의 루트 = 공용 파일이 있는 폴더."""
        for p in (self.path, self._cfg.get("pi_path"), self._cfg.get("rdl_path")):
            if p and os.path.isfile(p):
                return workdirs.base_dir_for(p)
        return default

    def _write_stage_snapshots(self, stage: str, items, base: str | None = None):
        """items 를 (레시피레벨, 호기)별로 나눠 01_초안/02_확정 파일 기록.
        반환: 생성 파일 경로 목록. base 미지정 시 공용 파일 폴더."""
        base = base or self._snapshot_base_dir()
        if not base or not items:
            return []
        if not self._cur_stamp:
            self._cur_stamp = workdirs.run_stamp()
        groups: dict[tuple, list] = {}   # (레벨, 호기, layer) → 항목들
        for it in items:
            level = engine._s(it["recipe"]) or "레벨미상"
            for m, v in it["values"].items():
                if m and engine._s(v) != "":
                    groups.setdefault((level, m, it["layer"]), []).append(it)
        prefix = "01_초안" if stage == "initial" else "02_확정"
        run_dir_fn = (workdirs.initial_run_dir if stage == "initial"
                      else workdirs.final_run_dir)
        written = []
        for (level, m, layer), its in groups.items():
            if not its:
                continue
            sheet = "RDL_ALL" if layer == "RDL" else "PI_ALL"
            rundir = run_dir_fn(base, level, m, self._cur_stamp)
            dest = os.path.join(rundir, f"{prefix}_{m}_{level}.xlsx")
            recs, exts = self._cur_records(its, only_machine=m)
            extract_io.write_snapshot(
                dest, recs, [m], sheet, exts, stage=stage, level=level, aoi=m,
                source=self._cur_path.get().strip(), user=self.user)
            written.append(dest)
        return written

    def _cur_save(self):
        sel = [it for it in self._cur_items if it["sel"].get()]
        if not sel:
            self._cur_status.config(text="선택된 항목이 없습니다.")
            return
        # PI 항목은 변형이 정해져야 함(빈 값=미정만 차단. 기존 양식의 PI/PI-bubble 등은 통과)
        undecided = [it for it in sel
                     if it["layer"] == "PI" and it["variant"].get().strip() == ""]
        if undecided:
            grps = sorted({f"{it['recipe']}" for it in undecided})
            messagebox.showwarning(
                "변형 미정",
                f"선택한 PI 항목 {len(undecided)}개의 변형(PI / PI_bubble)이 정해지지 않았습니다.\n"
                f"해당 Recipe: {', '.join(grps)}\n\n"
                "각 항목의 PI / PI_bubble 을 선택한 뒤 저장하세요.",
                parent=self._cur_win)
            # 첫 미정 그룹으로 이동
            first = undecided[0]
            g = f"{first['layer']} / {first['recipe']} / {first['mag']}"
            if g in list(self._cur_group["values"]):
                self._cur_group.set(g)
                self._cur_render()
            return
        # Layer 로 분리: PI → PI_ALL 시트, RDL → RDL_ALL 시트(각각 다른 파일)
        pi_items = [it for it in sel if it["layer"] == "PI"]
        rdl_items = [it for it in sel if it["layer"] == "RDL"]
        other = [it for it in sel if it["layer"] not in ("PI", "RDL")]
        if other:
            pi_items += other   # Layer 미상은 PI 쪽에

        base = filedialog.asksaveasfilename(
            title="양식 저장 위치/이름(.xlsx) — PI/RDL 은 각각 _PI/_RDL 로 저장",
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")], parent=self._cur_win)
        if not base:
            return
        stem = base[:-5] if base.lower().endswith(".xlsx") else base
        done = []
        try:
            # 선택한 항목만으로 새로 생성(기존에서 뺀 건 빠지고, 새로 고른 건 추가됨)
            if pi_items:
                p = f"{stem}_PI.xlsx"
                engine.create_from_records(p, self._cur_records(pi_items)[0],
                                           self._cur_machines,
                                           user=self.user, sheet_name="PI_ALL")
                self._cfg["pi_path"] = p
                done.append(("PI", p, len(pi_items)))
            if rdl_items:
                p = f"{stem}_RDL.xlsx"
                engine.create_from_records(p, self._cur_records(rdl_items)[0],
                                           self._cur_machines,
                                           user=self.user, sheet_name="RDL_ALL")
                self._cfg["rdl_path"] = p
                done.append(("RDL", p, len(rdl_items)))
            save_config(self._cfg)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("저장 실패", str(e), parent=self._cur_win)
            return
        # ③ 02_확정 스냅샷(호기·레벨별) — 새로 불러온 항목만(재추출 메타 보유)
        fin_note = ""
        try:
            fin = self._write_stage_snapshots(
                "final", [it for it in sel if it["source"] == "new"],
                base=os.path.dirname(stem))
            if fin:
                fin_note = f"\n02_확정 {len(fin)}개 저장(final 폴더)."
        except Exception as e:  # noqa: BLE001
            fin_note = f"\n(02_확정 저장 실패: {e})"
        summary = "\n".join(f"{k}: {n}개 → {os.path.basename(p)}" for k, p, n in done) + fin_note
        self._cur_status.config(text="저장 완료: " + ", ".join(f"{k} {n}" for k, p, n in done))
        first = done[0]
        if messagebox.askyesno("완료", f"양식 저장 완료.\n{summary}\n\n지금 열까요? ({first[0]})",
                               parent=self._cur_win):
            self._cur_win.destroy()
            self._do_open(first[1], first[0])
            self.navigate(screen="s0")

    # ---- ③ 값 갱신: 백업 → 미리보기 → 적용 → 02_확정 -------------------
    def _cur_update_values(self):
        """열린 공용 파일의 구조는 유지하고, 분석된 최신 파싱값으로 값만 갱신."""
        if not self._cur_pivot_rows:
            self._cur_status.config(text="먼저 수집/분석을 실행하세요.")
            return
        if not self.repo:
            messagebox.showinfo("값 갱신", "먼저 공용 양식 파일을 여세요.",
                                parent=self._cur_win)
            return
        if self.read_only:
            messagebox.showwarning("읽기 전용", "읽기 전용이라 값을 갱신할 수 없습니다.",
                                   parent=self._cur_win)
            return
        plan = refresh_mod.plan_refresh(self.repo, self._cur_pivot_rows,
                                        self._cur_pivot_machines)
        if not plan.changes and not plan.new_machines:
            messagebox.showinfo(
                "값 갱신", "변경할 값이 없습니다(모두 최신).\n"
                f"매칭 {plan.matched_rows}행 / 매칭 안 됨 {plan.unmatched_rows}행.",
                parent=self._cur_win)
            return
        # 변경 미리보기(적용 전 확인) — 세부목표: 대대적 변동 전 안전장치
        lines = [f"· {c.pi} {c.recipe} | {c.zone} > {c.alg} > {c.param} "
                 f"| {c.machine}: {c.old or '(빈값)'} → {c.new}"
                 for c in plan.changes[:30]]
        more = f"\n…외 {len(plan.changes) - 30}건" if len(plan.changes) > 30 else ""
        newm = (f"\n새 호기 열 추가: {', '.join(plan.new_machines)}"
                if plan.new_machines else "")
        if not messagebox.askyesno(
                "값 갱신 미리보기",
                f"변경될 셀 {len(plan.changes)}건 (매칭 {plan.matched_rows}행, "
                f"매칭 안 됨 {plan.unmatched_rows}행 → 그대로 둠){newm}\n\n"
                + "\n".join(lines) + more
                + "\n\n적용 전에 공용 파일 백업본을 자동 생성합니다. 진행할까요?",
                parent=self._cur_win):
            self._cur_status.config(text="값 갱신 취소.")
            return
        try:
            backup = workdirs.backup_shared_file(self.path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("백업 실패", f"백업을 만들지 못해 중단합니다.\n{e}",
                                 parent=self._cur_win)
            return
        self._push_undo()
        stats = refresh_mod.apply_refresh(self.repo, plan)
        self.repo.ensure_machines(self._all_machines())
        self.dirty = True
        self._render()
        fin_note = ""
        try:
            fin = self._write_stage_snapshots(
                "final", [it for it in self._cur_items if it["source"] == "new"])
            if fin:
                fin_note = f"\n02_확정 {len(fin)}개 저장(final 폴더)."
        except Exception as e:  # noqa: BLE001
            fin_note = f"\n(02_확정 저장 실패: {e})"
        messagebox.showinfo(
            "값 갱신 완료",
            f"갱신된 행 {stats['updated_rows']}개, 셀 {stats['updated_cells']}개.\n"
            f"매칭 안 된 행 {stats['unmatched_rows']}개(구조 다름 → 그대로 둠).\n"
            f"백업: {backup}{fin_note}\n\n"
            "변경은 아직 메모리에만 있습니다. 저장 버튼으로 공용 파일에 기록하세요.",
            parent=self._cur_win)

    # ---- ① 장비 네트워크 수집 ------------------------------------------
    def _ip_to_aoi(self, ip: str) -> str:
        """참고자료/관련자료의 IP표로 IP → AOI-호기 역매핑. 못 찾으면 ''."""
        rev = {}
        if self.repo:
            for k, v in (self.repo.aoi_ip or {}).items():
                rev[engine._s(v)] = engine._s(k)
            for row in (self.repo.reference or []):
                if len(row) >= 2 and engine._s(row[0]).upper().startswith("AOI") \
                        and engine._s(row[1]):
                    rev.setdefault(engine._s(row[1]), engine._s(row[0]).upper())
        return rev.get(engine._s(ip), "")

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

    def _cur_collect_dialog(self):
        """장비 IP 입력 → net use(선택) → Job/Setup/Recipe 선택 → 읽기전용 수집."""
        win = tk.Toplevel(self._cur_win)
        win.title("장비에서 수집(읽기전용)")
        win.geometry("640x430")
        win.configure(bg=self.p["bg"])
        tk.Label(win, text="장비 네트워크(\\\\IP\\c$\\Job)에서 설정 파일 수집",
                 bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(win, text="원본은 절대 수정하지 않고 읽기·복사만 합니다. 장비 1대씩 접속 후 즉시\n"
                          "연결을 해제하며, 비밀번호는 이번 실행 메모리에만 보관됩니다.\n"
                          "탐색기로 이미 연결해 두었다면 'net use 접속' 체크를 해제하세요(수동 접속과 동일).",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=14)

        frm = tk.Frame(win, bg=self.p["bg"])
        frm.pack(fill="both", expand=True, padx=14, pady=8)
        tk.Label(frm, text="장비 IP(여러 개, 쉼표/줄바꿈 구분) — 첫 장비에서 고른 "
                          "Job·Recipe 선택을 다음 장비에 자동 적용:",
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w")
        ips_txt = tk.Text(frm, height=4, font=self.fonts["base"], relief="solid", bd=1)
        ips_txt.pack(fill="x", pady=(2, 8))

        row = tk.Frame(frm, bg=self.p["bg"])
        row.pack(fill="x")
        tk.Label(row, text="접속 ID:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).pack(side="left")
        uid_var = tk.StringVar(value=self._cfg.get("collect_user", "amkor"))
        tk.Entry(row, textvariable=uid_var, width=14, font=self.fonts["base"],
                 relief="solid", bd=1).pack(side="left", padx=(4, 12))
        tk.Label(row, text="비밀번호:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).pack(side="left")
        pw_var = tk.StringVar()
        tk.Entry(row, textvariable=pw_var, width=18, show="*", font=self.fonts["base"],
                 relief="solid", bd=1).pack(side="left", padx=(4, 12))
        net_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row, text="net use 접속(끝나면 자동 해제)", variable=net_var,
                       bg=self.p["bg"], font=self.fonts["sub"]).pack(side="left")

        status = tk.Label(frm, text="", bg=self.p["bg"], fg=self.p["muted"],
                          font=self.fonts["sub"], justify="left", anchor="w")
        status.pack(fill="x", pady=6)

        def run():
            ips = collector.split_ips(ips_txt.get("1.0", "end"))
            if not ips:
                status.config(text="IP를 입력하세요.")
                return
            if net_var.get() and not collector.is_windows():
                status.config(text="net use 접속은 Windows 에서만 가능합니다. "
                                   "체크 해제 후 이미 연결된 경로로 시도하세요.")
                return
            base = self._snapshot_base_dir()
            if not base:
                messagebox.showinfo(
                    "저장 위치", "수집 파일을 둘 기준(공용 파일)이 없습니다.\n"
                    "먼저 공용 파일을 열거나, 저장 폴더를 직접 선택하세요.", parent=win)
                base = filedialog.askdirectory(title="수집 저장 기준 폴더 선택",
                                               parent=win)
                if not base:
                    return
            self._cfg["collect_user"] = uid_var.get().strip() or "amkor"
            save_config(self._cfg)
            self._cur_stamp = workdirs.run_stamp()
            self._cur_sources = []
            plan = None
            errors = []
            for i, ip in enumerate(ips, 1):
                aoi = self._ip_to_aoi(ip) or ip.replace(".", "_")
                status.config(text=f"[{i}/{len(ips)}] {ip} ({aoi}) 수집 중…")
                win.update_idletasks()

                def staging_for(kw, aoi=aoi):
                    rd = workdirs.initial_run_dir(base, kw or "레벨미상", aoi,
                                                  self._cur_stamp)
                    return workdirs.staging_dir(rd)

                def confirm(planned, ip=ip):
                    lines = [f"· {src}" for src, _, _ in planned[:15]]
                    more = (f"\n…외 {len(planned) - 15}개"
                            if len(planned) > 15 else "")
                    return messagebox.askyesno(
                        "복사 확인",
                        f"[{ip}] 총 {len(planned)}개 파일을 로컬로 복사합니다"
                        "(원본은 읽기만):\n" + "\n".join(lines) + more, parent=win)
                try:
                    _, plan, root = collector.collect_equipment(
                        ip, staging_for, self._pick_list_chooser,
                        username=uid_var.get().strip() or "amkor",
                        password=pw_var.get(), use_net_use=net_var.get(),
                        plan=plan, confirm=confirm)
                    self._cur_sources.append(
                        (str(root), plan.job_keyword, aoi))
                except collector.UserCancelled:
                    errors.append(f"{ip}: 사용자가 취소")
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{ip}: {e}")
            pw_var.set("")               # 비밀번호는 실행 후 즉시 소거
            done = len(self._cur_sources)
            msg = f"수집 완료 {done}건" + (f", 실패 {len(errors)}건" if errors else "")
            if errors:
                messagebox.showwarning("수집 결과", msg + "\n\n" + "\n".join(errors),
                                       parent=win)
            status.config(text=msg)
            if done:
                win.destroy()
                self._cur_analyze(from_collect=True)

        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=14, pady=(0, 12))
        tk.Button(bt, text="수집 시작", relief="flat", bd=0, bg=self.p["ok"],
                  fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=run).pack(side="left")
        tk.Button(bt, text="닫기", relief="flat", bd=0, bg=self.p["surface"],
                  padx=16, pady=6, cursor="hand2",
                  command=win.destroy).pack(side="left", padx=8)

    # ====================================================================
    #  실제 Excel 열기 + 소스 수집/파싱 공용 헬퍼
    # ====================================================================
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

    def _ask_base_dir(self, title="작업 폴더(공용 파일 위치)를 선택하세요") -> str | None:
        base = self._snapshot_base_dir()
        if base:
            return base
        d = filedialog.askdirectory(title=title)
        return d or None

    def _collect_dialog(self, level_hint: str, on_sources):
        """장비 IP 수집 전용 모달. 완료되면 on_sources(sources, base) 호출.
        sources = [(staging_root, job_keyword, aoi)]. (양식/값 업데이트 공용)"""
        base = self._ask_base_dir()
        if not base:
            return
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
            self._cfg["collect_user"] = uid_var.get().strip() or "amkor"
            save_config(self._cfg)
            stamp = workdirs.run_stamp()
            sources, errors = [], []
            plan = None
            for i, ip in enumerate(ips, 1):
                aoi = self._ip_to_aoi(ip) or ip.replace(".", "_")
                status.config(text=f"[{i}/{len(ips)}] {ip} ({aoi}) 수집 중…")
                win.update_idletasks()

                def staging_for(kw, aoi=aoi):
                    rd = workdirs.initial_run_dir(base, kw or level_hint or "레벨미상",
                                                  aoi, stamp)
                    return workdirs.staging_dir(rd)

                def confirm(planned, ip=ip):
                    lines = [f"· {src}" for src, _, _ in planned[:15]]
                    more = f"\n…외 {len(planned) - 15}개" if len(planned) > 15 else ""
                    return messagebox.askyesno(
                        "복사 확인", f"[{ip}] {len(planned)}개 파일을 로컬로 복사"
                        "(원본은 읽기만):\n" + "\n".join(lines) + more, parent=win)
                try:
                    _, plan, root = collector.collect_equipment(
                        ip, staging_for, self._pick_list_chooser,
                        username=uid_var.get().strip() or "amkor",
                        password=pw_var.get(), use_net_use=net_var.get(),
                        plan=plan, confirm=confirm)
                    sources.append((str(root), plan.job_keyword, aoi))
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
                on_sources(sources, base)

        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=14, pady=(4, 12))
        tk.Button(bt, text="수집 시작", relief="flat", bd=0, bg=self.p["ok"], fg="#ffffff",
                  padx=16, pady=6, cursor="hand2", command=run).pack(side="left")
        tk.Button(bt, text="닫기", relief="flat", bd=0, bg=self.p["surface"], padx=16,
                  pady=6, cursor="hand2", command=win.destroy).pack(side="left", padx=8)

    def _parse_sources_busy(self, sources, on_ready, default_level=""):
        """수집 결과(또는 로컬 폴더) → 파싱 피벗을 백그라운드로 계산."""
        def work():
            cfgs = []
            for root, kw, aoi in sources:
                cfgs += ini_parser.scan_tree(root, default_level=kw or default_level,
                                             default_equipment=aoi)
            valid = [c for c in cfgs if rtp.config_valid(c)]
            rows, machines = ini_parser.build_pivot(valid)
            return rows, machines, [c for c in cfgs if not rtp.config_valid(c)]

        def done(ok, res):
            if not ok:
                messagebox.showerror("파싱 실패", str(res))
                return
            rows, machines, invalid = res
            if not rows:
                messagebox.showwarning("파싱 결과", "인식된 설정(config) 폴더가 없습니다.\n"
                                       "GlobalRTP.ini/OpticPreset.ini/Zones 구조를 확인하세요.")
                return
            on_ready(rows, machines)
        self._run_busy("파싱 중…", work, done)

    # ====================================================================
    #  양식 만들기 탭(스펙 1.1.2) — 신규(장비/로컬)/기존(버전) → 실제 Excel → final
    # ====================================================================
    def _view_form(self):
        if not hasattr(self, "_form_kind"):
            self._form_kind = tk.StringVar(value="PI")
            self._form_level = tk.StringVar(value="PI3")
        wrap = tk.Frame(self.body, bg=self.p["bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=18)
        tk.Label(wrap, text="양식 만들기", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w")
        tk.Label(wrap, text="레시피를 고르고, 장비 폴더에서 새로 불러오거나 기존 저장 양식을 "
                          "엽니다. initial 엑셀을 실제 Excel로 편집·저장한 뒤 '편집 완료'를 "
                          "누르면 final(양식) 파일이 만들어집니다(원형 initial은 따로 보존).",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left", wraplength=900).pack(anchor="w", pady=(2, 14))

        # 1) 레시피 선택
        box = tk.LabelFrame(wrap, text=" ① 레시피 선택 ", bg=self.p["bg"], fg=self.p["text"],
                            font=self.fonts["bold"], padx=12, pady=10)
        box.pack(fill="x")
        krow = tk.Frame(box, bg=self.p["bg"])
        krow.pack(fill="x")
        level_combo = ttk.Combobox(krow, textvariable=self._form_level, state="readonly",
                                   width=10, values=RECIPE_LEVELS["PI"])

        def on_kind():
            vals = RECIPE_LEVELS[self._form_kind.get()]
            level_combo.config(values=vals)
            if self._form_level.get() not in vals:
                self._form_level.set(vals[0])
        for k in ("PI", "RDL"):
            tk.Radiobutton(krow, text=k, variable=self._form_kind, value=k,
                           bg=self.p["bg"], font=self.fonts["bold"],
                           command=on_kind).pack(side="left", padx=(0, 10))
        tk.Label(krow, text="레시피:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).pack(side="left", padx=(10, 4))
        level_combo.pack(side="left")
        on_kind()

        # 2) 소스 선택
        box2 = tk.LabelFrame(wrap, text=" ② 불러오기 방식 ", bg=self.p["bg"], fg=self.p["text"],
                             font=self.fonts["bold"], padx=12, pady=10)
        box2.pack(fill="x", pady=(14, 0))
        tk.Button(box2, text="🖥  장비 폴더에서 신규 불러오기", relief="flat", bd=0,
                  bg=self.p["primary"], fg="#ffffff", padx=16, pady=8, cursor="hand2",
                  command=lambda: self._form_new(from_equipment=True)).pack(side="left")
        tk.Button(box2, text="📁  로컬 폴더에서 신규 불러오기", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=16, pady=8, cursor="hand2",
                  command=lambda: self._form_new(from_equipment=False)).pack(side="left", padx=8)
        tk.Button(box2, text="🗂  기존 저장 양식 열기(버전)", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=16, pady=8, cursor="hand2",
                  command=self._form_open_existing).pack(side="left")

    def _form_canonical(self, level: str, base: str) -> str:
        """레시피 레벨별 양식 파일의 표준 경로(cfg 기억, 없으면 base에 기본명)."""
        key = f"form_path_{level}"
        p = self._cfg.get(key)
        if p:
            return p
        return os.path.join(base, f"양식_{level}.xlsx")

    def _form_new(self, from_equipment: bool):
        level = self._form_level.get()
        kind = self._form_kind.get()

        def after_pivot(rows, machines):
            self._form_build_and_edit(rows, machines, level, kind)

        if from_equipment:
            self._collect_dialog(level, lambda sources, base:
                                 self._parse_sources_busy(sources, after_pivot,
                                                          default_level=level))
        else:
            d = filedialog.askdirectory(title=f"{level} 레시피 파일이 있는 로컬 폴더 선택")
            if not d:
                return
            self._parse_sources_busy([(d, level, "")], after_pivot, default_level=level)

    def _form_build_and_edit(self, rows, machines, level, kind):
        base = self._ask_base_dir()
        if not base:
            return
        stamp = workdirs.run_stamp()
        aoi = next((m for m in machines if m), "로컬")
        idir = workdirs.initial_run_dir(base, level, aoi, stamp)
        init_path = os.path.join(idir, f"01_초안_{level}.xlsx")

        def work():
            formbuilder.build_initial_workbook(rows, init_path, level=level,
                                               source=f"{level} / {aoi}")
            # 원형(편집 전) 보존 — 스펙 요구
            import shutil
            orig = os.path.join(idir, f"원형_01_초안_{level}.xlsx")
            shutil.copy2(init_path, orig)
            return orig

        def done(ok, res):
            if not ok:
                messagebox.showerror("초안 생성 실패", str(res))
                return
            opened = self._open_in_excel(init_path)
            self._form_finalize_dialog(init_path, res, level, kind, base, opened)
        self._run_busy("초안 엑셀 생성 중…", work, done)

    def _form_finalize_dialog(self, init_path, orig_path, level, kind, base, opened):
        win = tk.Toplevel(self)
        win.title("양식 편집 완료")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        msg = (f"초안이 생성되었습니다:\n{init_path}\n\n"
               + ("실제 Excel로 열었습니다. " if opened else
                  "이 환경에서 Excel을 자동으로 열지 못했습니다. 위 파일을 직접 여세요.\n")
               + "Excel에서 '사용' 열과 '최종 Parameter'를 편집·저장한 뒤,\n"
               "아래 '편집 완료 → 양식 생성'을 누르세요.\n"
               f"(편집 전 원형은 보존됨: {os.path.basename(orig_path)})")
        tk.Label(win, text=msg, bg=self.p["bg"], fg=self.p["text"], font=self.fonts["sub"],
                 justify="left", wraplength=560).pack(padx=16, pady=(14, 10))
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(bt, text="다시 열기", relief="flat", bd=0, bg=self.p["surface"],
                  padx=12, pady=6, cursor="hand2",
                  command=lambda: self._open_in_excel(init_path)).pack(side="left")
        tk.Button(bt, text="편집 완료 → 양식 생성", relief="flat", bd=0, bg=self.p["ok"],
                  fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=lambda: self._form_finalize(init_path, level, kind, base, win)
                  ).pack(side="right")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=12,
                  pady=6, cursor="hand2", command=win.destroy).pack(side="right", padx=6)

    def _form_finalize(self, init_path, level, kind, base, win):
        canonical = self._form_canonical(level, base)
        mode = "new"
        if os.path.exists(canonical):
            ans = messagebox.askyesnocancel(
                "저장 방식", f"양식 파일이 이미 있습니다:\n{canonical}\n\n"
                "[예]=덮어쓰기   [아니오]=새 버전으로 저장(이전 보존)   [취소]",
                parent=win)
            if ans is None:
                return
            mode = "overwrite" if ans else "version"

        def work():
            if mode == "version" and os.path.exists(canonical):
                versioning.save_new_version(canonical)   # 이전 내용 버전 폴더에 보존
            res = formbuilder.build_final_from_initial(
                init_path, canonical, user=self.user, level=level,
                source=f"{level} 양식")
            return res

        def done(ok, res):
            if not ok:
                messagebox.showerror("양식 생성 실패", str(res), parent=win)
                return
            self._cfg[f"form_path_{level}"] = canonical
            self._cfg[f"{kind.lower()}_path"] = canonical
            save_config(self._cfg)
            win.destroy()
            if messagebox.askyesno(
                    "양식 생성 완료",
                    f"final(양식) 생성 완료: {os.path.basename(canonical)}\n"
                    f"항목 {res['kept']}개(제외 {res['dropped']}개), 시트 {res['sheet']}.\n\n"
                    "지금 화면으로 열까요?"):
                self._do_open(canonical, kind)
                self.view = "param"
                self._sync_tab_style()
                self.navigate(screen="s0")
        self._run_busy("양식 생성 중…", work, done)

    def _form_open_existing(self):
        """기존 저장 양식 열기 — 파일 선택 후 버전이 있으면 버전 선택창.
        현재본은 실제 Excel로 편집(저장 시 덮어쓰기/새 버전) 가능, 과거 버전은 보기 전용."""
        p = filedialog.askopenfilename(title="기존 양식 파일(.xlsx) 선택",
                                       filetypes=[("Excel", "*.xlsx")])
        if not p:
            return
        versions = versioning.list_versions(p)
        target = p
        if versions:
            picked = self._pick_version(p, versions)
            if picked is None:
                return
            target = picked
        is_current = (os.path.abspath(target) == os.path.abspath(p))
        if is_current and messagebox.askyesno(
                "열기 방식",
                "이 양식을 실제 Excel로 편집하시겠습니까?\n\n"
                "[예] = Excel로 편집(저장 후 덮어쓰기/새 버전 선택)\n"
                "[아니오] = 프로그램 화면으로 보기(읽기 전용)"):
            opened = self._open_in_excel(p)
            self._existing_finish_dialog(p, opened)
            return
        if self._do_open(target, self._detect_kind(target)):
            self.view = "param"
            self._sync_tab_style()
            self.navigate(screen="s0")

    def _existing_finish_dialog(self, canonical, opened):
        """기존 양식을 Excel로 편집한 뒤 저장 방식(덮어쓰기/새 버전)을 고른다."""
        win = tk.Toplevel(self)
        win.title("양식 편집 완료")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        tk.Label(win, text=("Excel에서 편집·저장한 뒤 저장 방식을 고르세요.\n"
                            + ("" if opened else "(Excel 자동 열기 실패 — 파일을 직접 여세요)\n")
                            + f"파일: {canonical}"),
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["sub"],
                 justify="left", wraplength=520).pack(padx=16, pady=(14, 10))
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=16, pady=(0, 14))

        def overwrite():
            win.destroy()
            messagebox.showinfo("저장 완료", "현재본을 덮어썼습니다(Excel 저장분 그대로).")

        def new_version():
            try:
                v = versioning.save_new_version(canonical)
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("새 버전 저장 실패", str(e), parent=win)
                return
            win.destroy()
            messagebox.showinfo("새 버전 저장",
                                f"현재본을 새 버전으로 보존했습니다:\n{os.path.basename(v)}")
        tk.Button(bt, text="다시 열기", relief="flat", bd=0, bg=self.p["surface"], padx=12,
                  pady=6, cursor="hand2",
                  command=lambda: self._open_in_excel(canonical)).pack(side="left")
        tk.Button(bt, text="새 버전으로 저장", relief="flat", bd=0, bg=self.p["ok"],
                  fg="#ffffff", padx=14, pady=6, cursor="hand2",
                  command=new_version).pack(side="right")
        tk.Button(bt, text="덮어쓰기(현재본만)", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=14, pady=6, cursor="hand2",
                  command=overwrite).pack(side="right", padx=6)

    def _pick_version(self, canonical, versions):
        """버전 선택창. 반환: 선택 경로(현재본=canonical 포함) 또는 None(취소)."""
        win = tk.Toplevel(self)
        win.title("버전 선택")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="열 버전을 선택하세요", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["bold"]).pack(anchor="w", padx=12, pady=(10, 4))
        items = [("현재본 (최신 저장본)", canonical)] + [
            (versioning.label_for(canonical, v), v) for v in reversed(versions)]
        lb = tk.Listbox(win, height=min(16, max(4, len(items))), width=54,
                        font=self.fonts["base"])
        for label, _ in items:
            lb.insert("end", label)
        lb.selection_set(0)
        lb.pack(fill="both", expand=True, padx=12, pady=6)
        res = {"val": None}

        def ok(_=None):
            sel = lb.curselection()
            if sel:
                res["val"] = items[sel[0]][1]
            win.destroy()
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=12, pady=(0, 10))
        tk.Button(bt, text="열기", relief="flat", bd=0, bg=self.p["primary"], fg="#ffffff",
                  padx=16, cursor="hand2", command=ok).pack(side="left")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=16,
                  cursor="hand2", command=win.destroy).pack(side="left", padx=6)
        lb.bind("<Double-Button-1>", ok)
        win.wait_window()
        return res["val"]

    # ====================================================================
    #  파라미터 값 업데이트(스펙 1.1.1.1) — IP 여러 대 → 레시피별 취합(새 버전)
    # ====================================================================
    def _update_values_dialog(self):
        form_path = self.path
        if not form_path or not os.path.exists(form_path):
            form_path = filedialog.askopenfilename(
                title="기준이 될 양식 파일(.xlsx) 선택",
                filetypes=[("Excel", "*.xlsx")])
            if not form_path:
                return

        def after_pivot(rows, machines, base):
            self._update_collate_flow(form_path, rows, machines, base)

        # 소스: 장비 IP 또는 로컬 폴더
        win = tk.Toplevel(self)
        win.title("파라미터 값 업데이트")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        tk.Label(win, text="파라미터 값 업데이트", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(win, text=f"기준 양식: {os.path.basename(form_path)}\n"
                          "여러 장비에서 값을 읽어 레시피(PI#/RDL#)마다 호기별 취합 엑셀을 "
                          "새 버전으로 만듭니다.", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"], justify="left").pack(anchor="w", padx=16)
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=16, pady=16)

        def from_equip():
            win.destroy()
            self._collect_dialog("", lambda sources, base:
                                 self._parse_sources_busy(
                                     sources, lambda r, m: after_pivot(r, m, base)))

        def from_local():
            win.destroy()
            d = filedialog.askdirectory(title="장비에서 받아둔 로컬 폴더 선택")
            if not d:
                return
            base = self._snapshot_base_dir() or os.path.dirname(form_path)
            self._parse_sources_busy([(d, "", "")],
                                     lambda r, m: after_pivot(r, m, base))
        tk.Button(bt, text="🖥 장비 IP에서 수집", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=16, pady=8, cursor="hand2",
                  command=from_equip).pack(side="left")
        tk.Button(bt, text="📁 로컬 폴더에서", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=16, pady=8, cursor="hand2",
                  command=from_local).pack(side="left", padx=8)

    def _update_collate_flow(self, form_path, rows, machines, base):
        # 어떤 레시피(레벨)를 취합할지 선택 알림창(스펙 1.1.1.1.1)
        levels = sorted({engine._s(r.get("recipe")).strip()
                         for r in rows if engine._s(r.get("recipe")).strip()})
        if not levels:
            messagebox.showwarning("값 업데이트", "파싱 결과에서 레시피 레벨(PI#/RDL#)을 "
                                   "인식하지 못했습니다.")
            return
        chosen = self._pick_levels(levels)
        if not chosen:
            return

        def work():
            return collate.collate(form_path, rows, selected_levels=chosen)

        def done(ok, res):
            if not ok:
                messagebox.showerror("취합 실패", str(res))
                return
            self._update_write_results(res, form_path, base)
        self._run_busy("취합 중…", work, done)

    def _pick_levels(self, levels):
        """레시피 레벨 다중 선택 알림창. 반환: 선택 목록 또는 None."""
        win = tk.Toplevel(self)
        win.title("레시피 선택")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="취합할 레시피(PI#/RDL#)를 선택하세요", bg=self.p["bg"],
                 fg=self.p["text"], font=self.fonts["bold"]).pack(anchor="w", padx=14,
                                                                  pady=(12, 6))
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

    def _update_write_results(self, results, form_path, base):
        out_dir = os.path.join(base, "취합")
        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(form_path))[0]
        made = []
        for res in results:
            if res.mismatches:
                names = ", ".join(sorted({m["param"] for m in res.mismatches})[:12])
                more = f" 외 {len(res.mismatches) - 12}개" if len(res.mismatches) > 12 else ""
                go = messagebox.askyesno(
                    "항목 불일치",
                    f"[{res.level}] 양식과 장비 파일의 파라미터가 일부 맞지 않습니다.\n"
                    f"불일치 {len(res.mismatches)}개: {names}{more}\n\n"
                    "이 항목들은 '불일치'로 표기하고 취합 파일을 만들까요?")
                if not go:
                    continue
            canonical = os.path.join(out_dir, f"{stem}_{res.level}_취합.xlsx")
            # 항상 새 버전으로 저장(이전 버전 보존) + 현재본 갱신
            dest = versioning.next_version_path(canonical)
            collate.write_collated(res, dest, source=f"값 업데이트 {res.level}",
                                   user=self.user)
            import shutil
            shutil.copy2(dest, canonical)     # '현재본' 최신 포인터
            made.append((res.level, canonical, dest, res.matched_rows,
                         len(res.mismatches), res.filled_cells))
        if not made:
            messagebox.showinfo("값 업데이트", "생성된 취합 파일이 없습니다.")
            return
        lines = [f"· {lv}: 매칭 {mt}행 / 불일치 {mm} / 값 {fc}칸  → "
                 f"{os.path.basename(can)}" for lv, can, ver, mt, mm, fc in made]
        first = made[0]
        if messagebox.askyesno(
                "값 업데이트 완료",
                "레시피별 취합 파일을 새 버전으로 저장했습니다:\n\n" + "\n".join(lines)
                + "\n\n첫 취합 파일을 지금 화면으로 열까요?"):
            self._do_open(first[1], self._detect_kind(first[1]))
            self.view = "param"
            self._sync_tab_style()
            self.navigate(screen="s0")

    # ====================================================================
    #  파라미터 이력 확인(스펙 1.1.1.2) — 두 취합 버전 비교 + 변경내역 엑셀
    # ====================================================================
    def _history_dialog(self):
        old_p = filedialog.askopenfilename(
            title="이전(비교 기준) 취합/양식 엑셀 선택", filetypes=[("Excel", "*.xlsx")])
        if not old_p:
            return
        new_p = filedialog.askopenfilename(
            title="최신(달라진) 취합/양식 엑셀 선택", filetypes=[("Excel", "*.xlsx")])
        if not new_p:
            return

        def work():
            return history_mod.diff_files(old_p, new_p)

        def done(ok, res):
            if not ok:
                messagebox.showerror("이력 비교 실패", str(res))
                return
            diff = res
            n = len(diff.changes)
            if n == 0 and not diff.added_rows and not diff.removed_rows:
                messagebox.showinfo("파라미터 이력", "두 파일 사이에 바뀐 값이 없습니다.")
                return
            preview = "\n".join(
                f"· {c.param} | {c.machine}: {c.old or '(빈)'} → {c.new} ({c.kind})"
                for c in diff.changes[:20])
            more = f"\n…외 {n - 20}건" if n > 20 else ""
            go = messagebox.askyesno(
                "파라미터 이력",
                f"값 변경 {n}건, 행 추가 {len(diff.added_rows)} / 삭제 "
                f"{len(diff.removed_rows)}.\n\n{preview}{more}\n\n"
                "변경내역 엑셀을 저장할까요? (비고 열에 특이사항을 적을 수 있습니다)")
            if not go:
                return
            dest = filedialog.asksaveasfilename(
                title="변경내역 엑셀 저장", defaultextension=".xlsx",
                initialfile="변경내역.xlsx", filetypes=[("Excel", "*.xlsx")])
            if not dest:
                return
            history_mod.write_diff_excel(
                diff, dest, old_label=os.path.basename(old_p),
                new_label=os.path.basename(new_p))
            if messagebox.askyesno("저장 완료",
                                   f"{os.path.basename(dest)} 저장 완료.\n지금 Excel로 열까요?"):
                self._open_in_excel(dest)
        self._run_busy("이력 비교 중…", work, done)

    def _auto_open_last(self):
        """첫 실행 시 마지막으로 연 양식 파일을 자동으로 연다."""
        path = self._cfg.get("last_form")
        if path and os.path.exists(path) and not self.repo:
            try:
                self._do_open(path, self._cfg_kind_for(path))
                self.navigate(screen="s0")
            except Exception:  # noqa: BLE001
                pass

    def _cfg_kind_for(self, path) -> str:
        if self._cfg.get("rdl_path") == path:
            return "RDL"
        return "PI"

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
