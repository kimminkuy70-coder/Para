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
from datetime import datetime
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from tksheet import Sheet

from . import coef_detector
from . import coefstore
from . import collate
from . import collector
from . import commonality as cm
from . import downloader as dl
from . import editor_model
from . import engine
from . import errlog
from . import exporter
from . import extract_io
from . import formbuilder
from . import history as history_mod
from . import ini_parser
from . import localdirs
from . import locking
from . import refdata
from . import refresh as refresh_mod
from . import rtp_parser as rtp
from . import tray
from . import __version__
from . import updater
from . import watcher
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



def icon_path() -> str | None:
    """프로그램 아이콘(.ico) 경로. 없으면 None(아이콘 없이 동작)."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                     "para_icon.ico")
    return p if os.path.isfile(p) else None


def _sanitize_name(s: str) -> str:
    import re
    return re.sub(r'[<>:"/\\|?*]+', "_", str(s)).strip().strip(".") or "item"


class EquipApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Camtek AOI 장비 파라미터 관리")
        self.geometry("1400x860")
        self.minsize(1080, 680)
        self._set_window_icon()
        self.p = apply_theme(self)
        self.fonts = self.p["fonts"]
        self.user = engine.current_user()

        # 상태
        self._cfg = load_config()
        self.repo: ParamRepository | None = None
        self.path: str | None = None
        self.kind: str | None = None         # "PI" / "RDL"
        self.read_only = False
        self.recent_colors: list = self._cfg.get("recent_colors", [])

        # 3차 재설계: 저장 폴더 + 3개 독립 파일(장비 IP / 참고자료 / 특이사항)
        self.save_dir: str | None = self._cfg.get("save_dir")
        # 임시/로그는 OneDrive 밖(로컬)에 — 동기화 폭주·보안경고 방지
        self.local_dir: str = self._cfg.get("local_dir") or \
            localdirs.default_root()
        localdirs.set_root(self.local_dir)
        self.ip_rows: list[dict] = []        # 장비 IP 주소 [{호기, IP}] — 호기 기준
        self.ref_grid: list[list] = []       # 참고자료(자유형 메모 그리드)
        self.ref_colors: dict = {}           # 참고자료 셀 색상 {(r,c): '#hex'}
        self.special_rows: list[dict] = []   # 특이사항 행들
        self.special_colors: dict = {}       # 특이사항 셀 색상

        # Commonality 조사 진행 상태(호기 1대씩) — 세션 메모리
        self._cm: dict = {}                  # {machine, root, plan, lots, staging, ...}
        self.coef_rows: list[dict] = []      # 변환계수.xlsx [호기,MAG,변형,계수,비고]

        # 상단 탭(파라미터 값 확인 / 양식 만들기 / 특이사항 / 참고자료)
        self.view = "param"
        # '파라미터 값 확인'은 항상 읽기 전용(최신 취합 스냅샷 표시). 값 채우기는
        # '파라미터 값 업데이트', 양식 수정은 '양식 만들기 → 기존 양식 수정하기'.

        # 내비게이션 스택(뒤로/앞으로) — 파라미터 탭 전용
        self.nav: list[dict] = [{"screen": "s0"}]
        self.nav_idx = 0

        # 값 확인 화면 보조 상태
        self.cur_zone: str | None = None
        self._param_query = ""               # 파라미터 검색어(값 확인 화면)
        self._view_colors = None             # 값 확인 셀 색상(저장폴더별, 지연 로드)
        self._cur_sheet = None               # 특이사항/참고자료 tksheet
        self._cur_kind = None

        # 동시 접속 제어 — 내가 쥔 편집 잠금 {경로: 문서이름}, 문서별 열었을 때의 파일
        # 상태(저장 직전 재검증용). 읽기 전용으로 연 문서는 _ro_docs 에 기록.
        self._tray = None                # 트레이 아이콘(창 닫아도 감시 계속)
        self._tray_hint_shown = False    # '백그라운드 계속' 안내는 1회만
        self._pending_report = None      # 풍선 알림 클릭 시 열어줄 보고서
        self._watch_owned = False        # 이 PC 가 감시 전역 잠금을 쥐었는가
        self._watch_busy = False         # 감시 회차 실행 중(중복 실행 방지)
        self._locks: dict[str, str] = {}
        self._doc_stamps: dict[str, tuple] = {}
        self._ro_docs: set = set()

        self._build_chrome()
        self._render()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._startup)   # 저장폴더 지정 → 참고자료/특이사항 로드 → 최신 취합
        self.after(3000, self._presence_tick)   # 접속자 하트비트 + 잠금 갱신
        self.after(10_000, self._watch_tick)    # 자동 감시 주기 확인

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
        # 현재 접속자 표시(클릭 시 상세 목록) — 동시 편집 상황을 항상 보이게
        self._presence_lbl = tk.Label(bar, text="👤 나만 접속 중",
                                      bg=self.p["header_bar"], fg="#cbd5e1",
                                      font=self.fonts["sub"], cursor="hand2")
        self._presence_lbl.pack(side="right", padx=8, pady=11)
        self._presence_lbl.bind("<Button-1>", lambda e: self._show_sessions())
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
                           ("commonality", "Commonality 조사"),
                           ("special", "특이사항"), ("reference", "참고자료"),
                           ("ip", "장비 IP")):
            b = tk.Button(self.tabbar, text=label, relief="flat", bd=0,
                          font=self.fonts["bold"], padx=22, pady=8, cursor="hand2",
                          command=lambda k=key: self._set_view(k))
            b.pack(side="left", padx=(8 if key == "param" else 2, 2), pady=4)
            b.bind("<Enter>", lambda e, k=key, w=b:
                   w.config(bg=self.p["primary_lt"]) if k != self.view else None)
            b.bind("<Leave>", lambda e, k=key, w=b:
                   w.config(bg=self.p["head_bg"]) if k != self.view else None)
            self._tab_btns[key] = b

        # 상태바 — 안내/경고문이 계속 남아 거슬리지 않게 ✕ 로 닫을 수 있다.
        # (닫아도 내용은 로그에 남으므로 원인 추적에는 지장 없음)
        self.statusbar = tk.Frame(self, bg=self.p["head_bg"])
        self.statusbar.pack(side="bottom", fill="x")
        self.status = tk.Label(self.statusbar, text="", anchor="w",
                               bg=self.p["head_bg"], fg=self.p["muted"],
                               font=self.fonts["sub"], padx=10, justify="left")
        self.status.pack(side="left", fill="x", expand=True)
        self.btn_status_x = tk.Button(
            self.statusbar, text="✕", relief="flat", bd=0, padx=8, pady=0,
            bg=self.p["head_bg"], fg=self.p["muted"], activebackground=self.p["border"],
            font=self.fonts["sub"], cursor="hand2", command=self.clear_status)
        self.btn_status_x.bind("<Enter>",
                               lambda e: self.btn_status_x.config(fg=self.p["danger"]))
        self.btn_status_x.bind("<Leave>",
                               lambda e: self.btn_status_x.config(fg=self.p["muted"]))
        self._status_x_shown = False        # 메시지가 있을 때만 ✕ 를 보인다

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
        self._render()      # 내비 위젯 표시/숨김은 _render 가 일괄 처리

    def _sync_nav_widgets(self):
        """뒤로/앞으로/처음/크럼 은 '파라미터 값 확인' 탭에서만, 저장 버튼은 편집
        가능한 탭(특이사항/참고자료/장비 IP)에서만 보이게. 어떤 경로로 view 가
        바뀌든(_set_view/직접대입+navigate) _render 가 호출하므로 항상 일치."""
        want = (self.view == "param")
        if getattr(self, "_nav_shown", None) != want:
            self._nav_shown = want
            if want:
                self.btn_back.pack(side="left", padx=(12, 4), pady=11)
                self.btn_fwd.pack(side="left", padx=4, pady=11)
                self.btn_home.pack(side="left", padx=4, pady=11)
                self.lbl_crumb.pack(side="left", padx=16)
            else:
                for w in self._nav_widgets:
                    w.pack_forget()
        editable = (self.view in ("special", "reference", "ip"))
        if getattr(self, "_save_shown", None) != editable:
            self._save_shown = editable
            if editable:
                self.btn_save.pack(side="right", padx=4, pady=11,
                                   before=self.title_lbl)
            else:
                self.btn_save.pack_forget()

    def _set_status(self, msg: str, warn: bool = False):
        """하단 상태바 문구. warn=True 면 경고색(빨강)으로 눈에 띄게.
        문구가 있으면 ✕(닫기) 버튼이 함께 나타난다."""
        text = str(msg or "")
        self.status.config(text=text,
                           fg=(self.p["danger"] if warn and text.strip()
                               else self.p["muted"]))
        want = bool(text.strip())
        if want != getattr(self, "_status_x_shown", None):
            self._status_x_shown = want
            if want:
                self.btn_status_x.pack(side="right")
            else:
                self.btn_status_x.pack_forget()
        self.update_idletasks()

    def clear_status(self):
        """상태바 문구 닫기(✕). 내용은 이미 로그에 있으므로 지워도 안전하다."""
        self._set_status("")

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

    def _wheelify(self, canvas):
        """캔버스 위에 마우스가 있는 동안 휠로 세로 스크롤(모든 스크롤 화면 공통).
        Windows(<MouseWheel>)·Linux(Button-4/5) 모두 대응. Enter 때만 전역 바인딩,
        Leave 때 해제해 다른 창까지 스크롤되는 것 방지."""
        def on_wheel(e):
            num = getattr(e, "num", None)
            if num == 4:
                canvas.yview_scroll(-1, "units")
            elif num == 5:
                canvas.yview_scroll(1, "units")
            else:
                d = int(-e.delta / 120) if e.delta else 0
                canvas.yview_scroll(d or (-1 if (e.delta or 0) > 0 else 1), "units")
            return "break"

        def enter(_=None):
            for s in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                try:
                    canvas.bind_all(s, on_wheel)
                except tk.TclError:
                    pass

        def leave(_=None):
            for s in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                try:
                    canvas.unbind_all(s)
                except tk.TclError:
                    pass
        canvas.bind("<Enter>", enter)
        canvas.bind("<Leave>", leave)
        return canvas

    def _render(self):
        self._sync_nav_widgets()      # 뒤로/앞으로/처음 표시를 view 와 항상 일치
        # 이전 화면의 휠 바인딩 잔재 제거(다른 창까지 스크롤되는 문제 방지)
        for seq in ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-6>", "<Button-7>"):
            try:
                self.unbind_all(seq)
            except tk.TclError:
                pass
        for w in self.body.winfo_children():
            w.destroy()
        self._release_docs_except(self.view)   # 떠난 화면의 편집 잠금은 즉시 반납
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
        if self.view == "commonality":
            self._view_commonality()
            return
        st = self._state()
        self.btn_back.config(state=("normal" if self.nav_idx > 0 else "disabled"))
        self.btn_fwd.config(state=("normal" if self.nav_idx < len(self.nav) - 1 else "disabled"))
        self._update_crumb(st)
        self._param_actionbar()
        scr = st.get("screen", "s0")
        if scr == "s0":
            self._screen_machines()
        elif scr in ("s1", "s2", "s3"):      # 구 단계(종류→레벨→Recipe)는 한 화면으로 통합
            self._screen_recipe_pick(st)
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
        custom = set(self._all_machines())   # 참고자료 기반 호기(우클릭 삭제 가능)
        # 표시 목록 = 참고자료 호기 + 최신 취합에 값이 있는 호기(참고자료에 없어도 보이게)
        machines = list(self._all_machines())
        if self.repo:
            for m in self.repo.aoi_units:
                if m not in machines:
                    machines.append(m)
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
    #  S1 — 레시피 선택(레벨+변형 한 화면, 구 종류→레벨→Recipe 3단계 통합)
    # ====================================================================
    def _screen_recipe_pick(self, st):
        wrap = tk.Frame(self.body, bg=self.p["bg"])
        wrap.pack(fill="both", expand=True, padx=28, pady=(22, 8))
        tk.Label(wrap, text=f"{st['machine']} — 레시피 선택", bg=self.p["bg"],
                 fg=self.p["text"], font=self.fonts["title"]).pack(anchor="w", pady=(0, 2))
        tk.Label(wrap, text="확인할 레시피를 선택하세요(레시피(레벨)별로 한 줄씩 묶었습니다).",
                 bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(anchor="w", pady=(0, 8))
        if not self.repo or not self.repo.rows:
            tk.Label(wrap, text="표시할 취합 데이터가 없습니다.\n"
                              "상단 '파라미터 값 업데이트'로 먼저 값을 수집하세요.",
                     bg=self.p["bg"], fg=self.p["danger"], font=self.fonts["bold"],
                     justify="left").pack(anchor="w", pady=8)
            return
        # 레벨(PI 컬럼)별로 묶고, 그 안에서 변형(Recipe) 카드. 레벨이 많으면 세로 스크롤.
        combos: dict[tuple, int] = {}
        levels: list[str] = []
        for r in self.repo.rows:
            lvl, var = engine._s(r.get("PI")), engine._s(r.get("Recipe"))
            if not lvl:
                continue
            if lvl not in levels:
                levels.append(lvl)
            combos[(lvl, var)] = combos.get((lvl, var), 0) + 1
        # PI 계열 먼저, RDL 계열 뒤, 그 안은 이름순
        levels.sort(key=lambda l: (l.upper().startswith("RDL"), l))

        # 세로 스크롤 캔버스
        cwrap = tk.Frame(wrap, bg=self.p["bg"])
        cwrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(cwrap, bg=self.p["bg"], highlightthickness=0)
        vbar = ttk.Scrollbar(cwrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.p["bg"])
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="i")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("i", width=e.width))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")
        self._wheelify(canvas)

        tk.Label(inner, text="(레시피(레벨) 이름·카드를 우클릭하면 그 레시피를 취합에서 "
                            "삭제할 수 있습니다)", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(anchor="w", pady=(0, 4))
        for lvl in levels:
            variants = sorted(v for (l, v) in combos if l == lvl)
            kind = "RDL" if lvl.upper().startswith("RDL") else "PI"
            block = tk.Frame(inner, bg=self.p["bg"])
            block.pack(fill="x", anchor="w", pady=(6, 2))
            hdr = tk.Label(block, text=lvl, bg=self.p["bg"], fg=self.p["text"],
                           font=self.fonts["bold"], cursor="hand2")
            hdr.pack(anchor="w", pady=(4, 2))
            hdr.bind("<Button-3>", lambda e, l_=lvl: self._recipe_delete_menu(e, l_))
            rowf = tk.Frame(block, bg=self.p["bg"])
            rowf.pack(anchor="w", fill="x")
            for var in variants:
                card = self._big_button(
                    rowf, var or "(기본)", f"파라미터 {combos[(lvl, var)]}개",
                    lambda l_=lvl, v_=var, k_=kind: self.navigate(
                        screen="s4", kind=k_, pi=l_, recipe=v_))
                self._bind_right(card,
                                 lambda e, l_=lvl: self._recipe_delete_menu(e, l_))

    def _bind_right(self, widget, handler):
        widget.bind("<Button-3>", handler)
        for c in widget.winfo_children():
            self._bind_right(c, handler)

    def _recipe_delete_menu(self, event, level):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label=f"🗑  '{level}' 레시피 삭제 (취합 시트 제거)",
                      command=lambda: self._delete_recipe(level))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _delete_recipe(self, level):
        latest = workdirs.latest_collate(self.save_dir) if self.save_dir else None
        if not latest:
            messagebox.showinfo("레시피 삭제", "취합 파일이 없습니다.")
            return
        if not messagebox.askyesno(
                "레시피 삭제",
                f"'{level}' 레시피를 취합 파일에서 삭제할까요?\n"
                f"({os.path.basename(latest)} 의 해당 시트를 제거합니다 — 되돌릴 수 없음)"):
            return
        try:
            n = collate.delete_recipe(latest, level)
        except Exception as e:  # noqa: BLE001
            self._err("E101", "레시피 삭제 실패", e)
            return
        if not n:
            messagebox.showinfo("레시피 삭제", f"'{level}' 에 해당하는 시트를 찾지 못했습니다.")
            return
        self._load_latest_collate()          # 파일 반영본 다시 로드
        self._render()                        # 레시피 선택 화면 갱신(카드 제거)
        self._set_status(f"'{level}' 레시피 삭제됨 — 취합 시트 {n}개 제거")

    # ---- 선택 화면 공통 위젯 ------------------------------------------
    def _big_button(self, parent, text, desc, cmd):
        card = tk.Frame(parent, bg=self.p["surface"], width=250, height=96,
                        highlightbackground=self.p["border"], highlightthickness=1,
                        cursor="hand2")
        card.pack(side="left", padx=(0, 10), pady=8)
        card.pack_propagate(False)
        tk.Label(card, text=text, bg=self.p["surface"], fg=self.p["primary"],
                 font=self.fonts["title"]).pack(anchor="w", padx=16, pady=(16, 2))
        tk.Label(card, text=desc, bg=self.p["surface"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(anchor="w", padx=16)
        kids = card.winfo_children()

        def paint(bg, border):
            card.config(bg=bg, highlightbackground=border)
            for k in kids:                      # 글자 라벨 배경도 함께(박스 자국 방지)
                k.config(bg=bg)
        for w in (card, *kids):
            w.bind("<Button-1>", lambda e: cmd())
            w.bind("<Enter>", lambda e: paint(self.p["primary_lt"], self.p["primary"]))
            w.bind("<Leave>", lambda e: paint(self.p["surface"], self.p["border"]))
        return card

    # ====================================================================
    #  S4 — 파라미터 값 확인(tksheet, 읽기 전용) : Zone 탭 + 검색 + 단일 그리드
    # ====================================================================
    def _filtered_rows(self, st) -> list:
        return [r for r in self.repo.rows
                if engine._s(r.get("PI")) == st["pi"]
                and engine._s(r.get("Recipe")) == st["recipe"]]

    def _set_zone(self, z):
        self.cur_zone = z
        self._render()

    def _screen_equipment(self, st):
        rows = self._filtered_rows(st)
        zones = []
        for r in rows:
            z = engine._s(r.get("Zone"))
            if z not in zones:
                zones.append(z)
        if self.cur_zone not in zones:
            self.cur_zone = zones[0] if zones else None
        machine = st["machine"]
        others = [m for m in self.repo.aoi_units if m != machine]

        outer = tk.Frame(self.body, bg=self.p["bg"])
        outer.pack(fill="both", expand=True)

        # ── 제목줄: "AOI-25 : PI3" + 변환계수 + 읽기전용 안내
        head = tk.Frame(outer, bg=self.p["surface"],
                        highlightbackground=self.p["border"], highlightthickness=1)
        head.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(head, text=f"  {machine} : {st['recipe'] or st['pi']}",
                 bg=self.p["surface"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(side="left", pady=8)
        coef_txt = self._coef_label_for(machine)
        tk.Label(head, text=coef_txt, bg=self.p["surface"],
                 fg=(self.p["primary"] if "계수" in coef_txt else self.p["muted"]),
                 font=self.fonts["bold"]).pack(side="left", padx=(6, 0))
        tk.Label(head, text="왼쪽=선택 호기(값·비고) · 오른쪽=다른 호기 비교 · "
                          "셀 우클릭=색칠 · 비고 더블클릭=편집   ",
                 bg=self.p["surface"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="right", pady=8)

        # ── Zone 탭 + 파라미터 검색
        ztab = tk.Frame(outer, bg=self.p["bg"])
        ztab.pack(fill="x", padx=12, pady=(8, 0))
        for z in zones:
            sel = (z == self.cur_zone) and not self._param_query
            b = tk.Button(ztab, text=z or "(Zone 없음)", relief="flat", bd=0,
                          bg=(self.p["primary"] if sel else self.p["surface"]),
                          fg=("#ffffff" if sel else self.p["text"]),
                          font=self.fonts["bold"], padx=16, pady=7, cursor="hand2",
                          command=lambda zz=z: self._zone_clicked(zz))
            b.pack(side="left", padx=(0, 4))
        sbox = tk.Frame(ztab, bg=self.p["bg"])
        sbox.pack(side="right")
        tk.Label(sbox, text="🔍", bg=self.p["bg"], fg=self.p["muted"]).pack(side="left")
        self._search_var = tk.StringVar(value=self._param_query)
        ent = tk.Entry(sbox, textvariable=self._search_var, width=26,
                       relief="solid", bd=1, font=self.fonts["base"])
        ent.pack(side="left", padx=(4, 2), ipady=3)
        ent.bind("<KeyRelease>", self._search_changed)
        if getattr(self, "_search_focus", False):
            self._search_focus = False
            ent.focus_set()
            ent.icursor("end")
        if self._param_query:
            tk.Button(sbox, text="✕", relief="flat", bd=0, bg=self.p["bg"],
                      fg=self.p["danger"], cursor="hand2",
                      command=self._search_clear).pack(side="left")
            tk.Label(ztab, text="  검색 중 — 모든 Zone에서 찾습니다",
                     bg=self.p["bg"], fg=self.p["primary"],
                     font=self.fonts["sub"]).pack(side="right", padx=6)

        # ── 표시할 행: 검색 중이면 전체 Zone에서, 아니면 현재 Zone만
        q = self._param_query.casefold()
        if q:
            show = [r for r in rows if q in engine._s(r.get("Parameter")).casefold()
                    or q in engine._s(r.get("Alg")).casefold()
                    or q in engine._s(r.get("비고")).casefold()]
        else:
            show = [r for r in rows if engine._s(r.get("Zone")) == self.cur_zone]

        # ── 2분할 tksheet: 좌(선택 호기 블록, 고정) / 우(다른 호기, 가로 스크롤).
        # 세로 스크롤은 두 시트를 sync_scroll 로 묶어 항상 같은 행이 나란히 보인다
        # (실제 장비화면처럼 왼쪽 고정 + 오른쪽만 비교 스크롤). tksheet 라 대량에도 빠름.
        holder = tk.Frame(outer, bg=self.p["bg"])
        holder.pack(fill="both", expand=True, padx=12, pady=(8, 10))
        if not show:
            tk.Label(holder, text=("검색 결과가 없습니다." if q else
                                   "이 Zone에 파라미터가 없습니다."),
                     bg=self.p["bg"], fg=self.p["muted"],
                     font=self.fonts["bold"]).place(relx=0.5, rely=0.4,
                                                    anchor="center")
            return

        # 좌측(고정) 열: [Zone(검색시)] · Parameter · ★선택호기 · 비고
        # Alg 는 열에서 빼고 **그룹 헤더 행**으로 위에 한 번씩 표시(장비화면식).
        left_headers = (["Zone"] if q else []) + ["Parameter", f"★ {machine}", "비고"]
        left_widths = ([120] if q else []) + [300, 120, 210]
        base = 1 if q else 0
        c_sel = base + 1
        c_note = base + 2

        left_data, right_data = [], []
        header_rows: list[int] = []
        param_row_of: dict[int, object] = {}     # 시트행 → 취합 행(비고 편집용)
        cur_alg, li = None, 0
        for r in show:
            a = engine._s(r.get("Alg"))
            if a != cur_alg:
                cur_alg = a
                left_data.append(([""] if q else []) +
                                 [f"▸ {a or '(Alg 없음)'}", "", ""])
                right_data.append(["" for _ in others])
                header_rows.append(li)
                li += 1
            left_data.append(([engine._s(r.get("Zone"))] if q else []) + [
                engine._s(r.get("Parameter")), engine._s(r.get(machine)),
                engine._s(r.get("비고"))])
            right_data.append([engine._s(r.get(m)) for m in others])
            param_row_of[li] = r
            li += 1
        nrows = li

        def _mk(parent, headers, data, wraps):
            sh = Sheet(parent, theme="light blue",
                       show_x_scrollbar=True, show_y_scrollbar=True,
                       font=(self.p["family"], 10, "normal"),
                       header_font=(self.p["family"], 10, "bold"))
            sh.headers(headers)
            sh.set_sheet_data(data or [[]], reset_col_positions=True)
            sh.set_options(table_wrap=wraps, header_wrap="w",
                           show_vertical_grid=True, show_horizontal_grid=True)
            # rc_select 제외: 우클릭이 드래그 선택을 지우지 않게(여러 셀 한번에 색칠)
            sh.enable_bindings("single_select", "drag_select", "row_select",
                               "column_select", "arrowkeys", "copy",
                               "column_width_resize", "double_click_column_resize")
            sh.hide("row_index")
            return sh

        # 좌측 고정 시트(자체 스크롤바 숨김 — 우측 스크롤바가 세로로 둘 다 움직임)
        LEFT_W = sum(left_widths) + 8
        lwrap = tk.Frame(holder, bg=self.p["bg"], width=LEFT_W)
        lwrap.pack(side="left", fill="y")
        lwrap.pack_propagate(False)
        ls = _mk(lwrap, left_headers, left_data, "w")
        try:
            for ci, w in enumerate(left_widths):
                ls.column_width(column=ci, width=w)
            ls.highlight_columns(columns=[c_sel], bg=self.p["primary_lt"],
                                 fg=self.p["text"])
            ls.highlight_columns(columns=[c_note], bg="#fff8e1", fg=self.p["text"])
            if header_rows:
                ls.highlight_rows(rows=header_rows, bg="#e2e8f0",
                                  fg=self.p["text"], highlight_index=False)
        except Exception:  # noqa: BLE001
            pass
        ls.hide("y_scrollbar")
        ls.hide("x_scrollbar")
        ls.pack(fill="both", expand=True)
        # 좌측은 **가로로 절대 안 움직이게** 고정: 우측 가로 스크롤이 sync 로 전파돼도
        # 좌측 x 이동/스크롤바 콜백을 무력화(휠/스크롤바 두 경로 모두 차단).
        ls.MT.set_xviews = lambda *a, **k: None
        ls.MT._xscrollbar = lambda *a, **k: None

        # 비고 셀 더블클릭 = 편집(그 외 읽기 전용). 편집값은 최신 취합본에 저장.
        def _on_note_dbl(e):
            rr = ls.identify_row(e)
            cc = ls.identify_column(e)
            if rr is None or cc != c_note:
                return
            pr = param_row_of.get(rr)
            if pr is not None:
                self._edit_note_cell(ls, rr, c_note, pr, e)
        ls.MT.bind("<Double-Button-1>", _on_note_dbl, add="+")

        # 좌/우 구분선
        tk.Frame(holder, bg="#94a3b8", width=2).pack(side="left", fill="y")

        rs = None
        # 우측 비교 시트(다른 호기) — 없으면 안내
        if others:
            rwrap = tk.Frame(holder, bg=self.p["bg"])
            rwrap.pack(side="left", fill="both", expand=True)
            rs = _mk(rwrap, list(others), right_data, "")
            try:
                for i in range(len(others)):
                    rs.column_width(column=i, width=92)
                if header_rows:
                    rs.highlight_rows(rows=header_rows, bg="#e2e8f0",
                                      fg=self.p["text"], highlight_index=False)
            except Exception:  # noqa: BLE001
                pass
            rs.pack(fill="both", expand=True)
            ls.sync_scroll(rs)                    # 세로 스크롤 동기화(양방향)
            self.after(60, lambda: self._equalize_sheet_heights(
                ls, len(left_headers), rs, len(others), nrows))
        else:
            tk.Label(holder, text="비교할 다른 호기가 없습니다.", bg=self.p["bg"],
                     fg=self.p["muted"]).pack(side="left", padx=10)
            self.after(60, lambda: self._equalize_sheet_heights(
                ls, len(left_headers), None, 0, nrows))

        # ── 셀 색칠(좌/우 각 셀) — 우클릭 메뉴로 색 지정, 저장폴더에 영구 저장
        self._paint_ctx = {
            "ls": ls, "rs": rs, "machine": machine, "others": list(others),
            "c_param": base, "c_sel": c_sel, "c_note": c_note,
            "zone_col": (0 if q else None), "param_row_of": param_row_of,
        }
        ls.MT.bind("<Button-3>", lambda e: self._cell_paint_menu(e, "left"), add="+")
        if rs is not None:
            rs.MT.bind("<Button-3>", lambda e: self._cell_paint_menu(e, "right"),
                       add="+")
        self._apply_cell_colors()

    # ---- 셀 색칠 저장/적용 --------------------------------------------
    def _view_colors_path(self):
        return (os.path.join(self.save_dir, "값확인_셀색상.json")
                if self.save_dir else None)

    def _ensure_view_colors(self) -> dict:
        if getattr(self, "_view_colors", None) is None:
            self._view_colors = {}
            p = self._view_colors_path()
            if p and os.path.isfile(p):
                try:
                    with open(p, encoding="utf-8") as fh:
                        self._view_colors = json.load(fh)
                except Exception:  # noqa: BLE001
                    self._view_colors = {}
        return self._view_colors

    def _save_view_colors(self):
        p = self._view_colors_path()
        if not p:
            return
        try:
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(self._view_colors, fh, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _pkey(r):
        return tuple(engine._s(r.get(f)).strip()
                     for f in ("PI", "Recipe", "Zone", "Alg", "Parameter"))

    def _paint_target(self, side, c):
        """(side, 열 index) → 색 저장 대상 문자열(호기명/'비고'/'param'/'zone')."""
        ctx = self._paint_ctx
        if side == "left":
            if c == ctx["c_param"]:
                return "param"
            if c == ctx["c_sel"]:
                return ctx["machine"]
            if c == ctx["c_note"]:
                return "비고"
            if ctx["zone_col"] is not None and c == ctx["zone_col"]:
                return "zone"
            return None
        others = ctx["others"]
        return others[c] if 0 <= c < len(others) else None

    def _cell_paint_menu(self, event, side):
        ctx = getattr(self, "_paint_ctx", None)
        if not ctx:
            return
        sheet = ctx["ls"] if side == "left" else ctx["rs"]
        if sheet is None:
            return
        try:
            cells = [tuple(x) for x in sheet.get_selected_cells()]
        except Exception:  # noqa: BLE001
            cells = []
        rr, cc = sheet.identify_row(event), sheet.identify_column(event)
        if not cells and rr is not None and cc is not None:
            cells = [(rr, cc)]
        # 헤더행/무효 대상 제외
        cells = [(r, c) for (r, c) in cells
                 if r in ctx["param_row_of"] and self._paint_target(side, c)]
        if not cells:
            return
        m = tk.Menu(self, tearoff=0)
        palette = [("강조(노랑)", HIGHLIGHT_YELLOW), ("초록", "#dcfce7"),
                   ("빨강", "#fee2e2"), ("파랑", "#dbeafe")]
        for label, hx in palette:
            m.add_command(label=f"■ {label}",
                          command=lambda h=hx: self._paint_cells(side, cells, h))
        m.add_command(label="다른 색…",
                      command=lambda: self._paint_cells(side, cells, None, pick=True))
        m.add_separator()
        m.add_command(label="색 없음",
                      command=lambda: self._paint_cells(side, cells, ""))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _paint_cells(self, side, cells, hx, pick=False):
        ctx = self._paint_ctx
        sheet = ctx["ls"] if side == "left" else ctx["rs"]
        if pick:
            _, hx = colorchooser.askcolor(title="셀 색 선택",
                                          initialcolor=HIGHLIGHT_YELLOW)
            if not hx:
                return
        store = self._ensure_view_colors()
        for (r, c) in cells:
            pr = ctx["param_row_of"].get(r)
            target = self._paint_target(side, c)
            if pr is None or not target:
                continue
            key = "\x1f".join(self._pkey(pr) + (target,))
            try:
                if hx == "":
                    store.pop(key, None)
                    sheet.dehighlight_cells(cells=[(r, c)], redraw=False)
                else:
                    store[key] = hx
                    sheet.highlight_cells(cells=[(r, c)], bg=hx, redraw=False)
            except Exception:  # noqa: BLE001
                pass
        try:
            sheet.redraw()
        except Exception:  # noqa: BLE001
            pass
        self._save_view_colors()

    def _apply_cell_colors(self):
        """저장된 셀 색을 현재 좌/우 시트에 다시 적용(렌더 시 호출)."""
        ctx = getattr(self, "_paint_ctx", None)
        if not ctx:
            return
        store = self._ensure_view_colors()
        if not store:
            return
        ls, rs = ctx["ls"], ctx["rs"]
        machine, others = ctx["machine"], ctx["others"]
        # pkey → 시트행
        row_of = {}
        for sr, pr in ctx["param_row_of"].items():
            row_of[self._pkey(pr)] = sr
        for key, hx in list(store.items()):
            parts = key.split("\x1f")
            if len(parts) != 6 or not hx:
                continue
            pkey, target = tuple(parts[:5]), parts[5]
            sr = row_of.get(pkey)
            if sr is None:
                continue
            try:
                if target == "param":
                    ls.highlight_cells(row=sr, column=ctx["c_param"], bg=hx, redraw=False)
                elif target == "비고":
                    ls.highlight_cells(row=sr, column=ctx["c_note"], bg=hx, redraw=False)
                elif target == "zone" and ctx["zone_col"] is not None:
                    ls.highlight_cells(row=sr, column=ctx["zone_col"], bg=hx, redraw=False)
                elif target == machine:
                    ls.highlight_cells(row=sr, column=ctx["c_sel"], bg=hx, redraw=False)
                elif rs is not None and target in others:
                    rs.highlight_cells(row=sr, column=others.index(target), bg=hx,
                                       redraw=False)
            except Exception:  # noqa: BLE001
                pass
        try:
            ls.redraw()
            if rs is not None:
                rs.redraw()
        except Exception:  # noqa: BLE001
            pass

    def _edit_note_cell(self, sheet, r, c, pr, event):
        """비고 셀 인라인 편집 팝업(작은 Entry) → 취합 행·최신 취합본에 저장."""
        top = tk.Toplevel(self)
        top.wm_overrideredirect(True)
        top.attributes("-topmost", True)
        top.wm_geometry(f"+{event.x_root}+{event.y_root}")
        var = tk.StringVar(value=engine._s(pr.get("비고")))
        ent = tk.Entry(top, textvariable=var, font=self.fonts["base"],
                       width=32, relief="solid", bd=1)
        ent.pack()
        ent.focus_set()
        ent.select_range(0, "end")

        def commit(_=None):
            new = var.get().strip()
            top.destroy()
            if new == engine._s(pr.get("비고")):
                return
            pr.set("비고", new if new else None)
            try:
                sheet.set_cell_data(r, c, new)
            except Exception:  # noqa: BLE001
                pass
            self._persist_note(pr, new)
            self._set_status(f"비고 저장: {engine._s(pr.get('Parameter'))}")
        ent.bind("<Return>", commit)
        ent.bind("<Escape>", lambda e: top.destroy())
        ent.bind("<FocusOut>", lambda e: top.destroy())

    def _persist_note(self, pr, note):
        """최신 '파라미터 값 취합' 파일에서 이 파라미터 행을 찾아 비고를 갱신·저장."""
        path = workdirs.latest_collate(self.save_dir) if self.save_dir else None
        if not path or not os.path.isfile(path):
            return
        import openpyxl
        key = tuple(engine._s(pr.get(f)).strip()
                    for f in ("PI", "Recipe", "Zone", "Alg", "Parameter"))
        try:
            wb = openpyxl.load_workbook(path)
            changed = False
            for ws in wb.worksheets:
                heads = [engine._s(c.value).strip() for c in ws[1]]
                if "Parameter" not in heads or "비고" not in heads:
                    continue
                idx = {h: i for i, h in enumerate(heads)}
                need = ("PI", "Recipe", "Zone", "Alg", "Parameter")
                if not all(h in idx for h in need):
                    continue
                for row in ws.iter_rows(min_row=2):
                    rk = tuple(engine._s(row[idx[h]].value).strip() for h in need)
                    if rk == key:
                        row[idx["비고"]].value = note or None
                        changed = True
            if changed:
                wb.save(path)
            wb.close()
        except Exception:  # noqa: BLE001
            pass

    def _equalize_sheet_heights(self, ls, nleft, rs, nright, nrows):
        """좌/우 시트의 각 행 높이를 **둘 중 큰 쪽**으로 맞춰 나란히 정렬한다
        (좌측 Parameter 줄바꿈으로 행 높이가 달라져 어긋나는 것 방지).
        행 수가 매우 많으면(>500) 단일 줄 고정 높이로 빠르게 처리."""
        try:
            if not ls.winfo_exists():
                return
            self.update_idletasks()
            if nrows > 500:
                for r in range(nrows):
                    ls.row_height(row=r, height=28, redraw=False)
                    if rs is not None:
                        rs.row_height(row=r, height=28, redraw=False)
            else:
                for r in range(nrows):
                    hl = max((ls.MT.get_wrapped_cell_height(r, c)
                              for c in range(nleft)), default=28)
                    hr = 28
                    if rs is not None and nright:
                        hr = max((rs.MT.get_wrapped_cell_height(r, c)
                                  for c in range(nright)), default=28)
                    h = max(28, hl, hr)
                    ls.row_height(row=r, height=h, redraw=False)
                    if rs is not None:
                        rs.row_height(row=r, height=h, redraw=False)
            ls.redraw()
            if rs is not None:
                rs.redraw()
        except Exception:  # noqa: BLE001
            pass

    def _zone_clicked(self, z):
        self._param_query = ""               # Zone 클릭 = 검색 해제 후 해당 Zone
        self._set_zone(z)

    def _search_changed(self, _e=None):
        # 타이핑 멈춘 뒤 250ms 후 한 번만 다시 그림(입력 중 렉 방지)
        pending = getattr(self, "_search_after", None)
        if pending:
            try:
                self.after_cancel(pending)
            except Exception:  # noqa: BLE001
                pass

        def apply():
            self._search_after = None
            newq = self._search_var.get().strip()
            if newq != self._param_query:
                self._param_query = newq
                self._search_focus = True    # 다시 그린 뒤 검색창 포커스 유지
                self._render()
        self._search_after = self.after(250, apply)

    def _search_clear(self):
        self._param_query = ""
        self._render()

    def _remember_color(self, hx):
        if hx in self.recent_colors:
            self.recent_colors.remove(hx)
        self.recent_colors.insert(0, hx)
        self.recent_colors = self.recent_colors[:10]
        self._cfg["recent_colors"] = self.recent_colors
        save_config(self._cfg)

    # ====================================================================
    #  특이사항 / 참고자료 뷰 (tksheet — 열너비조절/자동줄바꿈/색칠/행열삭제)
    # ====================================================================
    def _make_table(self, headers, data, col_edit=False, force_edit=False,
                    read_only=False):
        """read_only=True 면 다른 사람이 편집 중인 문서 — 편집 바인딩을 아예 붙이지
        않는다(force_edit 보다 우선). 보기·복사는 그대로 가능."""
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
        # (단 다른 사람이 편집 중이면 read_only=True 로 잠긴다)
        if not read_only and (force_edit or not self.read_only):
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
            self._set_status("색을 칠할 셀을 먼저 선택하세요.", warn=True)
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
        # 동시 편집 방지 — 다른 사람이 수정 중이면 읽기 전용
        doc = refdata.special_path(self.save_dir)
        editable = self._acquire_doc(doc, "특이사항")
        if not editable:
            self._ro_banner(self.body, "특이사항", doc)
        btnbar = tk.Frame(self.body, bg=self.p["bg"])
        btnbar.pack(side="top", fill="x", padx=10)
        if editable:
            tk.Button(btnbar, text="＋ 특이사항(행) 추가", relief="flat", bd=0,
                      bg=self.p["surface"], fg=self.p["primary"],
                      font=self.fonts["bold"], cursor="hand2",
                      command=self._special_add).pack(side="left", pady=4)
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
        s = self._make_table(SPECIAL_HEADERS, data, col_edit=False, force_edit=True,
                             read_only=not editable)
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
        doc = refdata.ref_path(self.save_dir)
        editable = self._acquire_doc(doc, "참고자료")
        if not editable:
            self._ro_banner(self.body, "참고자료", doc)
        btnbar = tk.Frame(self.body, bg=self.p["bg"])
        btnbar.pack(side="top", fill="x", padx=10)
        if editable:
            tk.Button(btnbar, text="＋ 행 추가", relief="flat", bd=0,
                      bg=self.p["surface"], fg=self.p["primary"],
                      font=self.fonts["bold"], cursor="hand2",
                      command=self._ref_add).pack(side="left", pady=4)
            tk.Label(btnbar,
                     text="  (자유 메모 · 참고자료.xlsx 에 자동 저장 · 우클릭=행/열 삽입·삭제)",
                     bg=self.p["bg"], fg=self.p["muted"],
                     font=self.fonts["sub"]).pack(side="left")
        grid = [list(r) for r in self.ref_grid] or [list(refdata.REF_DEFAULT_HEADERS)]
        ncol = max((len(r) for r in grid), default=3)
        grid = [row + [""] * (ncol - len(row)) for row in grid]
        s = self._make_table(None, [[engine._s(c) for c in row] for row in grid],
                             col_edit=True, force_edit=True, read_only=not editable)
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
        doc = refdata.ip_path(self.save_dir)
        editable = self._acquire_doc(doc, "장비 IP 주소")
        if not editable:
            self._ro_banner(self.body, "장비 IP 주소", doc)
        btnbar = tk.Frame(self.body, bg=self.p["bg"])
        btnbar.pack(side="top", fill="x", padx=10, pady=(8, 0))
        if editable:
            tk.Button(btnbar, text="＋ 호기(행) 추가", relief="flat", bd=0,
                      bg=self.p["surface"], fg=self.p["primary"],
                      font=self.fonts["bold"], cursor="hand2",
                      command=self._ip_add).pack(side="left", pady=4)
            tk.Label(btnbar, text="  (호기·IP · 장비 IP 주소.xlsx 에 자동 저장 · 호기 버튼·값 "
                                  "업데이트의 기준)", bg=self.p["bg"], fg=self.p["muted"],
                     font=self.fonts["sub"]).pack(side="left")
        headers = refdata.IP_HEADERS
        data = [[engine._s(r.get("호기")), engine._s(r.get("IP"))]
                for r in self.ip_rows] or [["", ""]]
        s = self._make_table(headers, data, col_edit=False, force_edit=True,
                             read_only=not editable)
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
    #  오류 코드 + 로그(원인 파악용) — 에러 발생 지점마다 고유 코드(E###) 부여.
    #    코드는 소스에 그대로 있어(grep 가능), 사용자가 화면의 코드를 알려주면
    #    개발자가 즉시 발생 지점을 찾는다. 전체 traceback 은 로그 파일에 남긴다.
    # ====================================================================
    def _log_path(self):
        return errlog.log_path(getattr(self, "save_dir", None))

    def _write_log(self, code, title, exc=None):
        errlog.write_log(getattr(self, "save_dir", None), code, title, exc)

    def _err(self, code, title, exc=None, parent=None, extra=None):
        """오류를 사용자에게 코드와 함께 보여주고 로그에 남긴다.
        code: 발생 지점 고유 코드(E### — 소스에서 grep 가능).
        exc : 예외 객체(또는 문자열). 화면엔 요약, 로그엔 전체 traceback."""
        errlog.write_log(getattr(self, "save_dir", None), code, title, exc)
        msg = errlog.user_message(code, title, exc, extra, self._log_path())
        try:
            messagebox.showerror(f"오류 {code}", msg, parent=parent or self)
        except Exception:  # noqa: BLE001
            pass
        return code

    def _logerr(self, code, exc=None):
        """치명적이지 않은(폴백 처리되는) 오류를 팝업 없이 로그에만 남긴다.
        예: tksheet 스타일 적용 실패 — 화면은 계속 동작하나 원인은 기록."""
        errlog.write_log(getattr(self, "save_dir", None), code, "(비치명 · 폴백)", exc)

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
        tk.Button(bar, text="📤 내보내기", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=12, pady=5, cursor="hand2",
                  command=self._export_dialog).pack(side="left", padx=4, pady=5)
        self._watch_btn = tk.Button(bar, text="🔔 자동 감시", relief="flat", bd=0,
                                    bg=self.p["surface"], fg=self.p["text"], padx=12,
                                    pady=5, cursor="hand2",
                                    command=self._watch_dialog)
        self._watch_btn.pack(side="left", padx=4, pady=5)
        self._sync_watch_btn()
        tk.Label(bar, text="  (최신 '파라미터 값 취합'을 자동 표시 · 값 읽기전용)",
                 bg=self.p["head_bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left", padx=6)

    def _open_collation_view(self, path):
        """취합/양식 파일을 값 확인 화면(읽기전용 병합)으로 연다."""
        try:
            self.repo = collate.load_as_repo(path, self._all_machines())
            self.path, self.read_only = path, True
        except Exception as e:  # noqa: BLE001
            self._err("E102", "열기 실패", e)
            return
        self.view = "param"
        self._sync_tab_style()
        self.navigate(screen="s0")

    def _refresh_view(self):
        """최신 '파라미터 값 취합' 파일을 디스크에서 다시 읽어 값 확인 화면에 반영.
        (값 자동 수집은 '파라미터 값 업데이트'가 담당 — 여기서는 최신 취합본 재로드.)"""
        self._load_refdata()
        latest = workdirs.latest_collate(self.save_dir) if self.save_dir else None
        self._load_latest_collate()
        # 값 확인 화면으로 전환 후 처음 화면부터 다시 그림(취합이 바뀌면 즉시 반영)
        self.view = "param"
        self._sync_tab_style()
        self.navigate(screen="s0")
        if not self.save_dir:
            self._set_status("저장 폴더가 지정되지 않았습니다.", warn=True)
        elif not latest:
            self._set_status("표시할 '파라미터 값 취합' 파일이 아직 없습니다. "
                             "'파라미터 값 업데이트'로 먼저 취합을 만드세요.",
                             warn=True)
        else:
            n = len(self.repo.rows) if self.repo else 0
            self._set_status(f"최신 취합 재로드: {os.path.basename(latest)} · "
                             f"{len(self._all_machines())}호기 / {n}행")

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
        m.add_command(label="로컬 작업 폴더…", command=self._local_dir_dialog)
        m.add_separator()
        m.add_command(label="현재 접속자 보기…", command=self._show_sessions)
        m.add_separator()
        m.add_command(label="지금 업데이트 확인…",
                      command=lambda: self._check_update_prompt(manual=True))
        m.add_command(label="새 버전 배포…(개발자용)", command=self._publish_update_dialog)
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
        self._wheelify(canvas)

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

    def _match_recipes_dialog(self, all_recipes, target_levels, aoi="", parent=None):
        """레시피(레벨)마다 장비 **Job 폴더**를 매칭하는 창(복수 선택).
        레벨(PI2/PI3/PI4 …)이 서로 다른 Job 폴더에 있을 수 있어 레벨별로 Job 을 고른다.
        레벨 1개든 여러 개든 같은 화면. 이름 토큰이 맞는 폴더는 자동 체크(추천).
        반환: {레벨: [Path]} 또는 None(취소). all_recipes = Job 폴더 Path 목록."""
        parent = parent or self
        win = tk.Toplevel(parent)
        win.title("레시피 ↔ Job 폴더 매칭" + (f" — {aoi}" if aoi else ""))
        win.geometry("760x580")
        win.configure(bg=self.p["bg"])
        win.transient(parent)
        try:
            win.grab_set()
        except tk.TclError:
            pass
        tk.Label(win, text="선택한 레시피마다 장비 Job 폴더를 지정하세요(복수 선택 가능).",
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["bold"]).pack(
                 anchor="w", padx=14, pady=(12, 2))
        tk.Label(win, text="이름이 맞는 폴더는 자동 체크했습니다(◀ 추천). 각 레시피의 Job 폴더를 "
                          "고르면 그 폴더 안의 Recipe 를 전부 수집합니다.",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=14, pady=(0, 6))

        canvas = tk.Canvas(win, bg=self.p["bg"], highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.p["bg"])
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="i")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("i", width=e.width))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="top", fill="both", expand=True, padx=14)
        vbar.pack(side="right", fill="y")
        self._wheelify(canvas)

        vars_: dict = {}                       # {level: [(BooleanVar, Path)]}
        for lvl in target_levels:
            box = tk.LabelFrame(inner, text=f"  {lvl}  ", bg=self.p["bg"],
                                fg=self.p["primary"], font=self.fonts["bold"],
                                padx=8, pady=4)
            box.pack(fill="x", expand=True, pady=(6, 2))
            vars_[lvl] = []
            if not all_recipes:
                tk.Label(box, text="(장비에서 Job 폴더를 찾지 못함)", bg=self.p["bg"],
                         fg=self.p["danger"], font=self.fonts["sub"]).pack(anchor="w")
            for p in all_recipes:
                name = p.name if isinstance(p, Path) else str(p)
                hit = collector.level_folder_match(name, lvl)
                v = tk.BooleanVar(value=hit)
                vars_[lvl].append((v, p))
                tk.Checkbutton(box, text=name + ("   ◀ 추천" if hit else ""),
                               variable=v, bg=self.p["bg"],
                               fg=(self.p["text"] if hit else self.p["muted"]),
                               font=self.fonts["sub"], anchor="w").pack(anchor="w")

        res = {"val": None}

        def ok():
            mapping = {}
            for lvl, items in vars_.items():
                sel = [p for v, p in items if v.get()]
                if sel:
                    mapping[lvl] = sel
            if not mapping:
                messagebox.showwarning("매칭", "레시피별 장비 폴더를 하나 이상 선택하세요.",
                                       parent=win)
                return
            empty = [lvl for lvl in target_levels if lvl not in mapping]
            if empty and not messagebox.askyesno(
                    "일부 레시피 미지정",
                    "폴더를 고르지 않은 레시피: " + ", ".join(empty)
                    + "\n이 레시피는 이번에 수집하지 않습니다. 계속할까요?", parent=win):
                return
            res["val"] = mapping
            win.destroy()
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(side="bottom", fill="x", padx=14, pady=10)
        tk.Button(bt, text="확인", relief="flat", bd=0, bg=self.p["primary"], fg="#ffffff",
                  padx=16, pady=6, cursor="hand2", command=ok).pack(side="left")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=16,
                  pady=6, cursor="hand2", command=win.destroy).pack(side="left", padx=6)
        win.wait_window()
        return res["val"]

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

    def _pick_list_chooser(self, kind, title, items, multi,
                           labels=None, preselect=None, note=""):
        """collector 용 모달 선택창. 반환: 선택 목록 또는 None(취소).
        labels: 항목별 표시 문구(기본 = 항목 이름). preselect: 미리 선택할 인덱스들.
        note: 목록 위 안내문(예: 취합 대상 레시피)."""
        # 버그 수정: _chooser_parent 가 이미 닫힌 창이면(장비 수집창 사용 후 등)
        # Toplevel 생성이 TclError 로 죽어 목록창이 아예 안 떴다 → 살아있을 때만 사용.
        parent = getattr(self, "_chooser_parent", None)
        try:
            if parent is None or not parent.winfo_exists():
                parent = self
        except tk.TclError:
            parent = self
        win = tk.Toplevel(parent)
        win.title(title)
        win.configure(bg=self.p["bg"])
        try:
            win.grab_set()
        except tk.TclError:
            pass
        win.lift()
        win.focus_force()
        tk.Label(win, text=title, bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["bold"]).pack(anchor="w", padx=12, pady=(10, 2))
        if note:
            tk.Label(win, text=note, bg=self.p["bg"], fg=self.p["primary"],
                     font=self.fonts["sub"], justify="left").pack(anchor="w", padx=12)
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
        for i, it in enumerate(items):
            base = it.name if isinstance(it, Path) else str(it)
            lb.insert("end", labels[i] if labels else base)
        if preselect:
            for i in preselect:
                if 0 <= i < len(items):
                    lb.selection_set(i)
                    if not multi:
                        break
            if preselect:
                lb.see(preselect[0])
        elif items:
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
    def _collect_dialog(self, staging_root, on_sources, level_hint="", levels=None):
        """장비 수집 모달 — ① 장비 IP 목록에서 선택(1순위, 호기별 비밀번호) +
        ② IP 직접 입력(2순위). staging_root/{호기}/ 로 읽기전용 복사.
        levels: 취합 대상 레시피 목록 — Job/Recipe 폴더 선택창에 매칭 표시.
        완료 시 on_sources(sources) 호출. sources=[(폴더, job_keyword, 호기)]."""
        levels = [lv for lv in (levels or ([level_hint] if level_hint else [])) if lv]
        win = tk.Toplevel(self)
        win.title("장비에서 수집(읽기전용)")
        win.geometry("720x640")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        self._chooser_parent = win
        tk.Label(win, text="장비 네트워크(\\\\IP\\c$\\Job)에서 설정 파일 수집",
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["bold"]).pack(
                 anchor="w", padx=14, pady=(12, 2))
        sub = "원본은 읽기·복사만. 장비 1대씩 접속 후 즉시 해제, 비밀번호는 " \
              "이번 실행 메모리에만 보관."
        if levels:
            sub += f"\n취합 대상 레시피: {', '.join(levels)}"
        tk.Label(win, text=sub, bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"], justify="left").pack(anchor="w", padx=14)

        default_uid = self._cfg.get("collect_user", "amkor")
        # ── ① 장비 IP 목록에서 선택(1순위) — 호기별 접속 ID·비밀번호 입력
        box1 = tk.LabelFrame(win, text=" ① 장비 목록에서 선택 (호기별 접속 ID·비밀번호) ",
                             bg=self.p["bg"], fg=self.p["text"],
                             font=self.fonts["bold"], padx=8, pady=6)
        box1.pack(fill="both", expand=True, padx=14, pady=(8, 4))
        listing = [(engine._s(r.get("호기")).strip(), engine._s(r.get("IP")).strip())
                   for r in self.ip_rows
                   if engine._s(r.get("호기")).strip() and engine._s(r.get("IP")).strip()]
        rows_ui = []                     # [(check_var, 호기, ip, id_var, pw_var)]
        if listing:
            cv = tk.Canvas(box1, bg=self.p["bg"], highlightthickness=0, height=200)
            vsb = ttk.Scrollbar(box1, orient="vertical", command=cv.yview)
            inner = tk.Frame(cv, bg=self.p["bg"])
            cv.create_window((0, 0), window=inner, anchor="nw")
            cv.configure(yscrollcommand=vsb.set)
            cv.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")
            inner.bind("<Configure>",
                       lambda e: cv.configure(scrollregion=cv.bbox("all")))
            self._wheelify(cv)
            for i, (aoi, ip) in enumerate(listing):
                ck = tk.BooleanVar(value=False)
                uid = tk.StringVar(value=default_uid)
                pw = tk.StringVar()
                tk.Checkbutton(inner, text=f"{aoi}", variable=ck, bg=self.p["bg"],
                               font=self.fonts["bold"], width=10, anchor="w").grid(
                    row=i, column=0, sticky="w", pady=1)
                tk.Label(inner, text=ip, bg=self.p["bg"], fg=self.p["muted"],
                         font=self.fonts["base"], width=16, anchor="w").grid(
                    row=i, column=1, sticky="w")
                tk.Label(inner, text="ID:", bg=self.p["bg"], fg=self.p["muted"],
                         font=self.fonts["sub"]).grid(row=i, column=2, sticky="e")
                ue = tk.Entry(inner, textvariable=uid, width=12, relief="solid", bd=1)
                ue.grid(row=i, column=3, sticky="w", padx=(4, 6), pady=1)
                tk.Label(inner, text="비밀번호:", bg=self.p["bg"], fg=self.p["muted"],
                         font=self.fonts["sub"]).grid(row=i, column=4, sticky="e")
                pe = tk.Entry(inner, textvariable=pw, width=16, show="*",
                              relief="solid", bd=1)
                pe.grid(row=i, column=5, sticky="w", padx=(4, 2), pady=1)
                # ID/비번 칸 클릭 시 그 장비 자동 선택
                for e_ in (ue, pe):
                    e_.bind("<FocusIn>", lambda e, c=ck: c.set(True))
                rows_ui.append((ck, aoi, ip, uid, pw))
        else:
            tk.Label(box1, text="장비 IP 목록이 비어 있습니다. '장비 IP' 탭에서 "
                              "호기·IP를 등록하면 여기서 바로 선택할 수 있습니다.",
                     bg=self.p["bg"], fg=self.p["danger"],
                     font=self.fonts["sub"]).pack(anchor="w", padx=4, pady=4)
        conv = tk.Frame(win, bg=self.p["bg"])
        conv.pack(fill="x", padx=14)
        common_uid = tk.StringVar(value=default_uid)
        common_pw = tk.StringVar()
        tk.Label(conv, text="공통 ID:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).pack(side="left")
        tk.Entry(conv, textvariable=common_uid, width=12, relief="solid",
                 bd=1).pack(side="left", padx=(4, 8))
        tk.Label(conv, text="공통 비밀번호:", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["sub"]).pack(side="left")
        tk.Entry(conv, textvariable=common_pw, width=16, show="*", relief="solid",
                 bd=1).pack(side="left", padx=(4, 4))

        def apply_common():
            for ck, _aoi, _ip, uid, pw in rows_ui:
                if ck.get():
                    if common_uid.get().strip():
                        uid.set(common_uid.get().strip())
                    if not pw.get():
                        pw.set(common_pw.get())
        tk.Button(conv, text="선택 장비에 적용", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=10, cursor="hand2",
                  command=apply_common).pack(side="left")
        tk.Label(conv, text="  (ID·비밀번호가 같은 장비는 이걸로 한 번에)",
                 bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left")

        # ── ② IP 직접 입력(2순위) — 목록에 없는 장비
        box2 = tk.LabelFrame(win, text=" ② IP 직접 입력 (목록에 없는 장비, 쉼표/줄바꿈) ",
                             bg=self.p["bg"], fg=self.p["muted"],
                             font=self.fonts["sub"], padx=8, pady=4)
        box2.pack(fill="x", padx=14, pady=(6, 4))
        ips_txt = tk.Text(box2, height=2, font=self.fonts["base"], relief="solid", bd=1)
        ips_txt.pack(fill="x", pady=(2, 4))
        drow = tk.Frame(box2, bg=self.p["bg"])
        drow.pack(fill="x")
        direct_uid = tk.StringVar(value=default_uid)
        direct_pw = tk.StringVar()
        tk.Label(drow, text="직접 입력 IP — 접속 ID:", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left")
        tk.Entry(drow, textvariable=direct_uid, width=12, relief="solid",
                 bd=1).pack(side="left", padx=(4, 8))
        tk.Label(drow, text="비밀번호:", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left")
        tk.Entry(drow, textvariable=direct_pw, width=16, show="*", relief="solid",
                 bd=1).pack(side="left", padx=(4, 0))

        # ── 공통 설정(net use)
        row = tk.Frame(win, bg=self.p["bg"])
        row.pack(fill="x", padx=14, pady=(6, 0))
        net_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row, text="net use 접속(자동 해제) — 끄면 탐색기로 미리 연결한 "
                                "세션 사용(비밀번호 불필요)", variable=net_var,
                       bg=self.p["bg"], font=self.fonts["sub"]).pack(side="left")
        status = tk.Label(win, text="", bg=self.p["bg"], fg=self.p["muted"],
                          font=self.fonts["sub"])
        status.pack(fill="x", padx=14, pady=6)

        # Job/Recipe 폴더 선택창에 '어떤 취합 레시피인지' 자동 매칭 표시 + 미리선택
        def chooser(kind, title, items, multi):
            if kind in ("job", "recipe") and levels:
                labels, pre = [], []
                for i, it in enumerate(items):
                    nm = it.name if isinstance(it, Path) else str(it)
                    hit = next((lv for lv in levels
                                if collector.contains_keyword(nm, lv)), "")
                    labels.append(f"{nm}    ◀ {hit} 레시피" if hit else nm)
                    if hit:
                        pre.append(i)
                return self._pick_list_chooser(
                    kind, title, items, multi, labels=labels, preselect=pre,
                    note=f"취합 대상 레시피: {', '.join(levels)} — "
                         "'◀' 표시가 자동 매칭된 폴더입니다.")
            return self._pick_list_chooser(kind, title, items, multi)

        def run():
            # 1순위: 목록에서 체크한 장비(호기 확정, 호기별 접속 ID·비밀번호)
            targets = []                     # [(ip, aoi, uid, pw)]
            for ck, aoi, ip, uid, pw in rows_ui:
                if ck.get():
                    u = uid.get().strip() or common_uid.get().strip() or "amkor"
                    targets.append((ip, aoi, u, pw.get() or common_pw.get()))
            # 2순위: 직접 입력 IP(호기는 IP↔호기 매칭창에서)
            direct_ips = collector.split_ips(ips_txt.get("1.0", "end"))
            direct_ips = [ip for ip in direct_ips
                          if ip not in {t[0] for t in targets}]
            if not targets and not direct_ips:
                status.config(text="장비를 선택하거나 IP를 입력하세요.")
                return
            if net_var.get() and not collector.is_windows():
                status.config(text="net use 는 Windows 전용입니다. 체크를 끄고 이미 "
                                   "연결된 경로로 시도하세요.")
                return
            if direct_ips:
                ip_map = self._map_ips_to_machines(direct_ips, parent=win)
                if ip_map is None:
                    return
                du = direct_uid.get().strip() or common_uid.get().strip() or "amkor"
                for ip in direct_ips:
                    aoi = ip_map.get(ip) or self._ip_to_aoi(ip) or ip.replace(".", "_")
                    targets.append((ip, aoi, du, direct_pw.get() or common_pw.get()))
            # net use 모드인데 비밀번호가 빈 장비 확인
            if net_var.get():
                nopw = [f"{aoi}({ip})" for ip, aoi, _u, pw in targets if not pw]
                if nopw and not messagebox.askyesno(
                        "비밀번호 없음",
                        "다음 장비는 비밀번호가 비어 있습니다:\n"
                        + ", ".join(nopw)
                        + "\n\n빈 비밀번호로 접속을 시도할까요?", parent=win):
                    return
            # 마지막으로 쓴 접속 ID 를 기본값으로 저장(공통/첫 장비 기준)
            self._cfg["collect_user"] = (common_uid.get().strip()
                                         or targets[0][2] or "amkor")
            save_config(self._cfg)
            sources, errors = [], []
            plan = None
            for i, (ip, aoi, uid, pw) in enumerate(targets, 1):
                status.config(text=f"[{i}/{len(targets)}] {ip} ({aoi}) 수집 중…")
                win.update_idletasks()

                def staging_for(kw, aoi=aoi):
                    d = os.path.join(staging_root, _sanitize_name(aoi))
                    os.makedirs(d, exist_ok=True)
                    return d

                def confirm(planned, ip=ip, aoi=aoi):
                    lines = [f"· {src}" for src, _, _ in planned[:15]]
                    more = f"\n…외 {len(planned) - 15}개" if len(planned) > 15 else ""
                    return messagebox.askyesno(
                        "복사 확인", f"[{aoi} · {ip}] {len(planned)}개 파일을 로컬로 "
                        "복사(원본은 읽기만):\n" + "\n".join(lines) + more, parent=win)
                def match_cb(all_recipes, tlevels, aoi=aoi):
                    return self._match_recipes_dialog(all_recipes, tlevels, aoi,
                                                      parent=win)
                try:
                    _, plan, srcs = collector.collect_equipment(
                        ip, staging_for, chooser,
                        username=uid or "amkor",
                        password=pw, use_net_use=net_var.get(),
                        plan=plan, confirm=confirm,
                        target_levels=(levels or None), match_recipes=match_cb)
                    for d, lvl in srcs:                 # 레벨별(또는 단일) 소스
                        sources.append((d, lvl, aoi))
                except collector.UserCancelled:
                    errors.append(f"{aoi}({ip}): 취소")
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{aoi}({ip}): {e}")
            # 비밀번호는 메모리에만 — 사용 후 즉시 소거
            for _ck, _aoi, _ip, _uid, pw in rows_ui:
                pw.set("")
            common_pw.set("")
            direct_pw.set("")
            # 확정된 Job/Setup/Recipe 선택을 감시 설정에 보존 — 무인 회차가 선택창
            # 없이 그대로 재사용한다(비밀번호는 저장하지 않음).
            if plan is not None and self.save_dir:
                try:
                    ws_, wst_ = watcher.load_settings(self.save_dir)
                    ws_.plan = watcher.plan_to_dict(plan)
                    watcher.save_settings(self.save_dir, ws_, wst_)
                except Exception as e:  # noqa: BLE001
                    self._logerr("E161", e)
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

    def _resolve_local_machine_dir(self, root: str, aoi: str):
        """지정 로컬 폴더 아래에서 호기(aoi) 폴더를 찾는다.
        1) {root}/{호기} 정확히, 2) 없으면 이름에 호기가 포함된 하위 폴더."""
        import re as _re
        cand = os.path.join(root, _sanitize_name(aoi))
        if os.path.isdir(cand):
            return cand
        key = _re.sub(r"[^0-9a-z]", "", aoi.lower())
        try:
            for n in sorted(os.listdir(root)):
                p = os.path.join(root, n)
                if os.path.isdir(p) and key and key in _re.sub(r"[^0-9a-z]", "", n.lower()):
                    return p
        except OSError:
            pass
        return None

    def _local_pick_sources(self, on_sources, level_hint=""):
        """로컬 불러오기 — 폴더 직접 선택 대신 **호기 선택 창**을 띄우고, 지정된 로컬
        상위 폴더에서 그 호기 폴더를 자동으로 찾아 sources 를 만든다(req6).
        on_sources([(folder, level_hint, 호기)]) 호출. 지정 폴더는 config 에 기억."""
        machines = self._all_machines()
        if not machines:
            messagebox.showinfo("로컬 불러오기", "참고자료(장비 IP)에 호기가 없습니다. "
                                "'장비 IP' 탭에서 호기를 먼저 등록하세요.")
            return
        root = self._cfg.get("local_root", "")
        if not root or not os.path.isdir(root):
            messagebox.showinfo("로컬 상위 폴더 지정",
                                "장비에서 받아둔 파일들이 들어 있는 **상위 폴더**를 지정하세요.\n"
                                "(그 아래 호기 이름 폴더에서 자동으로 찾습니다.)")
            root = filedialog.askdirectory(title="로컬 상위 폴더 선택")
            if not root:
                return
            self._cfg["local_root"] = root
            save_config(self._cfg)

        win = tk.Toplevel(self)
        win.title("로컬에서 불러오기 — 호기 선택")
        win.geometry("560x560")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="불러올 호기를 선택하세요(지정 로컬 폴더에서 자동으로 찾습니다).",
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["bold"]).pack(
                 anchor="w", padx=14, pady=(12, 2))
        root_var = tk.StringVar(value=root)
        rrow = tk.Frame(win, bg=self.p["bg"])
        rrow.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(rrow, text="로컬 상위 폴더:", bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left")
        tk.Label(rrow, textvariable=root_var, bg=self.p["bg"], fg=self.p["primary"],
                 font=self.fonts["sub"]).pack(side="left", padx=(4, 8))

        def change_root():
            d = filedialog.askdirectory(title="로컬 상위 폴더 선택", parent=win)
            if d:
                root_var.set(d)
                self._cfg["local_root"] = d
                save_config(self._cfg)
                refresh()
        tk.Button(rrow, text="폴더 변경", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=8, cursor="hand2",
                  command=change_root).pack(side="left")

        lwrap = tk.Frame(win, bg=self.p["bg"])
        lwrap.pack(fill="both", expand=True, padx=14)
        lcanvas = tk.Canvas(lwrap, bg=self.p["bg"], highlightthickness=0)
        lvbar = ttk.Scrollbar(lwrap, orient="vertical", command=lcanvas.yview)
        listfrm = tk.Frame(lcanvas, bg=self.p["bg"])
        listfrm.bind("<Configure>",
                     lambda e: lcanvas.configure(scrollregion=lcanvas.bbox("all")))
        lcanvas.create_window((0, 0), window=listfrm, anchor="nw", tags="i")
        lcanvas.bind("<Configure>", lambda e: lcanvas.itemconfig("i", width=e.width))
        lcanvas.configure(yscrollcommand=lvbar.set)
        lcanvas.pack(side="left", fill="both", expand=True)
        lvbar.pack(side="right", fill="y")
        self._wheelify(lcanvas)
        vars_ = {}

        def refresh():
            for w in listfrm.winfo_children():
                w.destroy()
            vars_.clear()
            for m in machines:
                found = self._resolve_local_machine_dir(root_var.get(), m)
                v = tk.BooleanVar(value=bool(found))
                vars_[m] = (v, found)
                r = tk.Frame(listfrm, bg=self.p["bg"])
                r.pack(fill="x", anchor="w")
                tk.Checkbutton(r, text=m, variable=v, bg=self.p["bg"],
                               font=self.fonts["bold"], width=10, anchor="w",
                               state=("normal" if found else "disabled")).pack(side="left")
                tk.Label(r, text=(found if found else "폴더 없음"), bg=self.p["bg"],
                         fg=(self.p["muted"] if found else self.p["danger"]),
                         font=self.fonts["sub"], anchor="w").pack(side="left", padx=(6, 0))
        refresh()

        def ok():
            sources = [(found, level_hint, m)
                       for m, (v, found) in vars_.items() if v.get() and found]
            if not sources:
                messagebox.showwarning("호기 선택", "불러올 호기를 선택하세요(폴더가 있는 호기).",
                                       parent=win)
                return
            win.destroy()
            on_sources(sources)
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=14, pady=12)
        tk.Button(bt, text="불러오기", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=ok).pack(side="left")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=16,
                  pady=6, cursor="hand2", command=win.destroy).pack(side="left", padx=6)

    def _coef_lookup_cb(self, fixed_machine=None):
        """scan_tree 용 변환계수 콜백 — (호기,MAG) 저장소 우선, 없으면 RTP.txt 로 자동
        추정해 upsert(사람값 우선). fixed_machine 을 주면(commonality: 조사 호기 1대)
        파싱 태그(equipment=S/M)를 무시하고 그 호기로 조회·저장. 반환: (콜백, 변경 dict)."""
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
        """수집/로컬 폴더 → 파싱 피벗을 백그라운드로 계산. 변환계수는 (호기,MAG) 저장소
        기준(없으면 RTP.txt 자동추정·저장). scales 는 폴백."""
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
                self._err("E110", "파싱 실패", res)
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
        """레시피 다중 선택 알림창 — 레시피별 최신 양식 정보 표시. 반환: 목록/None."""
        win = tk.Toplevel(self)
        win.title("레시피 선택")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        tk.Label(win, text=title, bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["bold"]).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(win, text="선택한 레시피마다 장비 Job 폴더에서 해당 Recipe 폴더를 "
                          "고르게 됩니다(자동 매칭 표시).",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=14, pady=(0, 6))
        vars_ = {}
        grid = tk.Frame(win, bg=self.p["bg"])
        grid.pack(fill="x", padx=20, pady=(0, 4))
        for i, lv in enumerate(levels):
            v = tk.BooleanVar(value=True)
            vars_[lv] = v
            tk.Checkbutton(grid, text=lv, variable=v, bg=self.p["bg"],
                           font=self.fonts["bold"]).grid(row=i, column=0,
                                                         sticky="w", pady=2)
            # 최신 확정 양식 정보(생성시간·파일명) — 어떤 양식으로 취합되는지 보여줌
            info = "양식 없음"
            try:
                vs = workdirs.list_form_versions(self.save_dir, lv)
                if vs:
                    st_, p_ = vs[0]
                    info = f"최신 양식 {st_}  ({os.path.basename(p_)})"
            except Exception:  # noqa: BLE001
                pass
            tk.Label(grid, text=info, bg=self.p["bg"],
                     fg=(self.p["muted"] if info != "양식 없음" else self.p["danger"]),
                     font=self.fonts["sub"]).grid(row=i, column=1, sticky="w",
                                                  padx=(14, 0))
        res = {"val": None}

        def set_all(v):
            for var in vars_.values():
                var.set(v)

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
        tk.Button(bt, text="전체 해제", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["muted"], padx=12, cursor="hand2",
                  command=lambda: set_all(False)).pack(side="right")
        tk.Button(bt, text="전체 선택", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["muted"], padx=12, cursor="hand2",
                  command=lambda: set_all(True)).pack(side="right", padx=6)
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
        tk.Label(wrap, text="레시피를 고르고 장비/로컬에서 새로 불러오면 ①기존 레시피와 유사도 "
                          "안내(활용/새로 만들기) → ②프로그램 화면 편집기(Zone·Alg·Parameter 계층, "
                          "체크박스·이름/변환/계수 편집, 계수 적용 표시값)로 파라미터를 고릅니다. "
                          "우측 상단 ‘엑셀에서 편집하기’로 엑셀 편집도 가능. 확정 양식은 "
                          "‘양식/{레시피}/{생성시간}/’ 에 저장됩니다.",
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
        tk.Button(box2, text="📁  로컬(호기 선택)에서 신규 불러오기", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=16, pady=8, cursor="hand2",
                  command=lambda: self._form_new(from_equipment=False)).pack(side="left", padx=8)
        tk.Button(box2, text="✏  기존 양식 수정하기", relief="flat", bd=0,
                  bg=self.p["ok"], fg="#ffffff", padx=16, pady=8, cursor="hand2",
                  command=self._edit_existing_form).pack(side="left")
        tk.Button(box2, text="🗂  이전 버전 보기(읽기전용)", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=16, pady=8, cursor="hand2",
                  command=self._load_previous_form).pack(side="left", padx=8)

    def _edit_existing_form(self):
        """기존 양식 수정하기 — 저장된 확정 양식을 **프로그램 편집기**로 불러와 편집→확정.
        (엑셀 대신 양식 만들기와 동일한 화면. 우측 상단 '엑셀에서 편집하기'로 엑셀도 가능.)
        원본 버전은 보존하고 새 버전으로 확정하며, 확정 후 기존 값 이어받기·신규 항목
        업데이트 안내가 이어진다."""
        import glob as _glob
        import re as _re
        import shutil as _shutil
        if not self.save_dir:
            messagebox.showinfo("저장 폴더", "먼저 저장 폴더를 지정하세요(⋯파일).")
            return
        recipes = workdirs.list_recipes(self.save_dir)
        if not recipes:
            messagebox.showinfo("기존 양식", "저장된 양식이 없습니다. 먼저 양식을 만드세요.")
            return
        pick = self._pick_list_chooser("recipe", "수정할 레시피 선택", recipes, False)
        if not pick:
            return
        level = pick[0]
        versions = workdirs.list_form_versions(self.save_dir, level)
        if not versions:
            messagebox.showinfo("기존 양식", f"'{level}' 에 저장된 확정 양식이 없습니다.")
            return
        labels = [f"{st}   ({os.path.basename(p)})" for st, p in versions]
        chosen = self._pick_list_chooser("ver", "수정할 버전 선택(최신순)", labels, False)
        if not chosen:
            return
        final_path = dict(zip(labels, [p for _, p in versions]))[chosen[0]]
        m = _re.search(r"_(.+?)호기_참조_", os.path.basename(final_path))
        aoi = m.group(1) if m else "로컬"

        # 레시피 이름 수정(선택)
        from tkinter import simpledialog
        new_level = simpledialog.askstring(
            "레시피 이름",
            "레시피 이름을 확인/수정하세요.\n"
            "(바꾸면 저장 폴더·파일 제목과 양식 안의 PI(레시피) 값도 함께 바뀝니다)",
            initialvalue=level, parent=self)
        if new_level is None:
            return
        new_level = (new_level.strip() or level)
        renamed = (new_level != level)
        kind = "RDL" if new_level.upper().startswith("RDL") else "PI"

        # 확정 양식 → 편집기용 rows/scales 복원
        try:
            rows, scales = formbuilder.form_to_pivot(final_path)
        except Exception as e:  # noqa: BLE001
            self._err("E111", "양식 불러오기 실패", e)
            return
        if renamed:
            for r in rows:                       # 편집기 PI = new_level 로 확정
                r["recipe"] = new_level
        new_st = workdirs.stamp()
        new_run = workdirs.form_run_dir(self.save_dir, new_level, new_st)
        related = workdirs.related_dir(new_run)

        def on_confirm(records, extracts, scales_out, win):
            new_final = workdirs.form_final_path(new_run, new_level, aoi, new_st)
            sheet = "RDL_ALL" if kind == "RDL" else "PI_ALL"

            def w():
                extract_io.write_snapshot(
                    new_final, records, machines=[], sheet_name=sheet, extracts=extracts,
                    stage="final", level=new_level, aoi=aoi,
                    source=f"{new_level} 양식", user=self.user, scales=scales_out)
                return new_final

            def d(ok, res):
                if not ok:
                    self._err("E112", "양식 확정 실패(기존 양식 수정)", res)
                    return
                win.destroy()
                # 이전 값 이어받기 + 신규 항목 업데이트 안내(원본 확정본 기준)
                self._post_finalize_merge(new_final, final_path, new_level,
                                          {"kept": len(records), "dropped": 0})
            self._run_busy("양식 확정 중…", w, d)

        def on_excel():
            # 엑셀 편집 폴백 — 옛 초안(수정본) 복사 또는 확정본 복사 후 Excel 열기
            drafts = sorted(_glob.glob(os.path.join(
                workdirs.related_dir(os.path.dirname(final_path)), "*수정본*.xlsx")))
            if drafts:
                new_draft = workdirs.form_draft_path(related, new_level, aoi, new_st)
                try:
                    _shutil.copy2(drafts[-1], new_draft)
                    if renamed:
                        formbuilder.force_level(new_draft, new_level)
                except Exception as e:  # noqa: BLE001
                    self._err("E113", "초안 복사 실패", e)
                    return
                opened = self._open_in_excel(new_draft)
                self._form_finalize_dialog(new_draft, drafts[-1], new_level, kind,
                                           scales or None, new_run, aoi, new_st, opened,
                                           prev_form=final_path)
            else:
                new_final = workdirs.form_final_path(new_run, new_level, aoi, new_st)
                try:
                    _shutil.copy2(final_path, new_final)
                    if renamed:
                        formbuilder.force_level(new_final, new_level)
                except Exception as e:  # noqa: BLE001
                    self._err("E114", "복사 실패", e)
                    return
                self._open_in_excel(new_final)
                self._set_status(f"새 버전으로 복사: {os.path.basename(new_final)} — "
                                 "Excel에서 저장하면 그대로 반영됩니다.")

        self._form_param_editor(rows, new_level, kind, scales, new_run, related, new_st,
                                aoi, base_keys=None, base_name="", title_prefix="기존 양식 수정",
                                on_confirm=on_confirm, on_excel=on_excel, default_use=True)

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
        # 같은 레시피 양식을 두 사람이 동시에 만들면 서로 덮어쓴다(레시피별 잠금).
        if not self._acquire_global(f"양식_{level}", f"{level} 양식 만들기"):
            return
        st = workdirs.stamp()
        run_dir = workdirs.form_run_dir(self.save_dir, level, st)
        related = workdirs.related_dir(run_dir)
        if from_equipment:
            self._collect_dialog(
                related,
                lambda sources: self._scales_then_build(sources, level, kind,
                                                        run_dir, related, st),
                level_hint=level, levels=[level])
        else:
            # req6: 폴더 직접 선택 대신 호기 선택 → 지정 로컬 폴더에서 자동 로드
            self._local_pick_sources(
                lambda sources: self._scales_then_build(sources, level, kind,
                                                        run_dir, related, st),
                level_hint=level)

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
                self._err("E115", "변형(레시피) 감지 실패", res)
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

    def _form_build_and_edit(self, rows, machines, level, kind, scales, run_dir, related,
                             st, title_prefix="양식 만들기"):
        """파싱된 새 레시피 → ① 기존 양식과 유사도 순위 안내(기존 활용/새로 만들기)
        → ② 프로그램 화면 편집기(기본). 엑셀 편집은 편집기의 버튼으로."""
        aoi = next((m for m in machines if m), "로컬")
        # 기존 양식들과 파라미터 유사도 순위
        parsed_keys = formbuilder.pivot_param_keys(rows)
        forms = {}
        try:
            for r in workdirs.list_recipes(self.save_dir):
                if r == level:
                    continue
                f = workdirs.latest_form(self.save_dir, r)
                if f:
                    forms[r] = formbuilder.form_params(f)
        except Exception:  # noqa: BLE001
            forms = {}
        ranked = formbuilder.rank_similar_forms(parsed_keys, forms)
        base = self._form_base_dialog(level, ranked, title_prefix)
        if base is None:                       # 취소
            return
        base_keys = None
        if base:                               # 기존 레시피 활용 → 그 양식의 사용 항목 기준
            bf = workdirs.latest_form(self.save_dir, base)
            base_keys = formbuilder.form_params(bf) if bf else None
        self._form_param_editor(rows, level, kind, scales, run_dir, related, st, aoi,
                                base_keys=base_keys, base_name=base,
                                title_prefix=title_prefix)

    def _form_base_dialog(self, level, ranked, title_prefix="양식 만들기"):
        """기존 레시피 활용 / 새로 만들기 선택 알림창. 반환: 레시피명 / '' (새로) / None(취소).
        ranked = [(레시피, 일치수, 기존항목수)] (유사도 높은 순)."""
        win = tk.Toplevel(self)
        win.title(f"{title_prefix} — 기반 레시피 선택")
        win.geometry("560x520")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        tk.Label(win, text=f"새 레시피 '{level}' 를 어떻게 만들까요?", bg=self.p["bg"],
                 fg=self.p["text"], font=self.fonts["bold"]).pack(anchor="w", padx=14,
                                                                  pady=(12, 2))
        tk.Label(win, text="기존 레시피를 기반으로 하면 그 레시피가 쓰는 파라미터가 자동 선택됩니다"
                          "(새 항목은 미선택). 유사한(겹치는 파라미터 많은) 순서로 정렬했습니다.",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left", wraplength=520).pack(anchor="w", padx=14, pady=(0, 6))
        # tkinter Radiobutton 은 변수값이 tristatevalue(기본 "")와 같으면 그 라디오가
        # '삼상태'로 칠해져 **선택 안 한 항목까지 채워져** 보인다. '새로 만들기'에 빈 값("")을
        # 쓰면 변수도 ""가 되어 나머지 라디오가 전부 채워진 듯 나오는 버그가 생긴다
        #  → '새로 만들기'에 센티넬 값을 주어 변수가 절대 ""가 되지 않게 한다(반환 시 ""로 환원).
        _NEW = "\x00새로만들기"
        sel = tk.StringVar(value=_NEW)         # 센티넬 = 새로 만들기
        body = tk.Frame(win, bg=self.p["bg"])
        body.pack(fill="both", expand=True, padx=14)
        canvas = tk.Canvas(body, bg=self.p["bg"], highlightthickness=0)
        vbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.p["bg"])
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="i")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("i", width=e.width))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")
        self._wheelify(canvas)
        tk.Radiobutton(inner, text="＋ 새로 만들기(추천 항목 자동 체크)", variable=sel,
                       value=_NEW, bg=self.p["bg"], font=self.fonts["bold"],
                       anchor="w").pack(anchor="w", pady=2)
        for recipe, match, total in ranked:
            tk.Radiobutton(
                inner, text=f"{recipe}   (겹치는 파라미터 {match} / 기존 {total}개)",
                variable=sel, value=recipe, bg=self.p["bg"], font=self.fonts["base"],
                anchor="w").pack(anchor="w", pady=1)
        res = {"val": None}

        def ok():
            v = sel.get()
            res["val"] = "" if v == _NEW else v   # 센티넬 → "" (새로 만들기)
            win.destroy()
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=14, pady=12)
        tk.Button(bt, text="다음", relief="flat", bd=0, bg=self.p["primary"], fg="#ffffff",
                  padx=18, pady=6, cursor="hand2", command=ok).pack(side="left")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=16,
                  pady=6, cursor="hand2", command=win.destroy).pack(side="left", padx=6)
        win.wait_window()
        return res["val"]

    # ---- 프로그램 화면 파라미터 편집기(양식/commonality 공통) -----------
    #  변환방식 라벨/격자 구성/확정 규칙은 editor_model(헤드리스 테스트됨)에 있다.

    def _form_param_editor(self, rows, level, kind, scales, run_dir, related, st, aoi,
                           base_keys=None, base_name="", title_prefix="양식 만들기",
                           on_confirm=None, on_excel=None, default_use=None):
        """상위/하위(변형·Zone·Alg·Parameter) 계층 + 체크박스 + 행별 편집(이름/변환/
        사용) + 변형별 계수(상단, 수정 시 일괄 적용) + 계수 적용 표시값. 엑셀 편집 버튼도.
        on_confirm(records, extracts, scales_out, win)·on_excel(win) 를 주면 그걸 사용
        (commonality 등 다른 저장 경로 재사용). 없으면 기본(양식 만들기) 동작."""
        # GUI 비의존 로직은 editor_model(헤드리스 테스트됨)에 위임 — 파일 종류가 달라도
        # 격자 구성·확정 규칙·표시값 계산이 동일하게 동작한다.
        label_values = editor_model.LABEL_VALUES
        _method = editor_model.method_of
        try:                                          # 파라미터 해석(파일 의존)
            entries = editor_model.build_entries(rows, base_keys=base_keys,
                                                 default_use=default_use)
            variants = editor_model.variants_of(entries)
        except Exception as _e:  # noqa: BLE001
            self._err("E200", "편집기 열기 실패(파라미터 해석)", _e)
            return
        coef_vars = {}
        for v in variants:
            c = scales.get(v, ini_parser.DEFAULT_SCALE)
            try:
                coef_vars[v] = tk.StringVar(value=f"{float(c):.16g}")
            except Exception as _e:  # noqa: BLE001
                self._logerr("E210", _e)             # 계수 표기 실패→기본값 폴백
                coef_vars[v] = tk.StringVar(value=f"{ini_parser.DEFAULT_SCALE:.16g}")

        def coef_of(variant):
            try:
                return float(coef_vars[variant].get())
            except Exception:  # noqa: BLE001
                return ini_parser.DEFAULT_SCALE

        def disp_of(entry, label):                    # 어떤 원본값에도 예외 없이(파일 대비)
            return editor_model.safe_display(
                entry["raw"], _method(label), coef_of(entry["variant"]))

        win = tk.Toplevel(self)
        win.title(f"{title_prefix} — 파라미터 선택/편집 ({level})")
        win.geometry("1180x780")
        win.configure(bg=self.p["bg"])

        # 상단: 제목 + 계수바 + 엑셀 편집 버튼
        top = tk.Frame(win, bg=self.p["surface"], highlightbackground=self.p["border"],
                       highlightthickness=1)
        top.pack(fill="x", padx=10, pady=(10, 0))
        left = tk.Frame(top, bg=self.p["surface"])
        left.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        base_txt = (f"기반: {base_name}" if base_name else
                    ("기존 양식 수정" if default_use else "새로 만들기(추천 항목 체크)"))
        tk.Label(left, text=f"{level}  ·  {base_txt}", bg=self.p["surface"],
                 fg=self.p["text"], font=self.fonts["title"]).pack(anchor="w")
        cbar = tk.Frame(left, bg=self.p["surface"])
        cbar.pack(anchor="w", pady=(4, 0))
        tk.Label(cbar, text="변형별 변환계수(수정 후 [적용]=표시값 일괄 갱신):",
                 bg=self.p["surface"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left")
        for v in variants:
            tk.Label(cbar, text=f"  {v or '(기본)'}=", bg=self.p["surface"],
                     fg=self.p["primary"], font=self.fonts["bold"]).pack(side="left")
            tk.Entry(cbar, textvariable=coef_vars[v], width=14, relief="solid",
                     bd=1).pack(side="left", padx=(0, 4))
        tk.Button(cbar, text="적용", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["primary"], padx=8, cursor="hand2",
                  command=lambda: refresh_all()).pack(side="left", padx=(4, 0))
        rbtn = tk.Frame(top, bg=self.p["surface"])
        rbtn.pack(side="right", padx=10, pady=8)
        tk.Button(rbtn, text="📄 엑셀 파일에서 편집하기", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=12, pady=6,
                  cursor="hand2", command=lambda: to_excel()).pack()

        # 본문: 단일 tksheet(완전 가상화) — 셀을 캔버스에 직접 그려 **보이는 행만** 도색.
        #   1600행이라도 로딩 렉이 없고, 스크롤바를 잡고 빠르게 올려도 글씨가 깨지지 않는다
        #   (임베드 위젯이 없으므로 OS 재도색 지연 문제 자체가 사라짐).
        body = tk.Frame(win, bg=self.p["bg"])
        body.pack(fill="both", expand=True, padx=10, pady=8)

        multi_variant = len(variants) > 1
        HDR = ["사용", "항목", "분류(변환방식)", "원본값", "표시값(계수적용)"]
        try:                                          # 격자 구성(파일 의존)
            grid = editor_model.build_grid(entries, multi_variant, disp_of)
        except Exception as _e:  # noqa: BLE001
            self._err("E201", "편집기 열기 실패(격자 구성)", _e, parent=win)
            win.destroy()
            return
        data = grid["data"]; kinds = grid["kinds"]
        row_entry = grid["row_entry"]
        descend_param = grid["descend_param"]; descend_head = grid["descend_head"]
        ancestors = grid["ancestors"]

        try:                                          # 표(tksheet) 생성
            sheet = Sheet(body, theme="light blue", headers=HDR, data=data,
                          show_row_index=False, show_x_scrollbar=True,
                          show_y_scrollbar=True,
                          font=(self.p["family"], 10, "normal"),
                          header_font=(self.p["family"], 10, "bold"))
            sheet.enable_bindings("single_select", "drag_select", "row_select",
                                  "arrowkeys", "column_width_resize",
                                  "double_click_column_resize", "copy", "edit_cell")
            sheet.pack(fill="both", expand=True)
        except Exception as _e:  # noqa: BLE001
            self._err("E202", "편집기 표(tksheet) 생성 실패", _e, parent=win)
            win.destroy()
            return
        try:
            sheet.set_column_widths([56, 430, 250, 130, 150])
        except Exception as _e:  # noqa: BLE001
            self._logerr("E211", _e)

        header_rows = [i for i, k in enumerate(kinds) if k != "param"]
        param_r = [i for i, k in enumerate(kinds) if k == "param"]

        def sync_header(h):
            kids = descend_param.get(h, [])
            val = bool(kids) and all(bool(sheet.get_cell_data(k, 0)) for k in kids)
            sheet.set_cell_data(h, 0, val, redraw=False)

        def on_check(ed):                                # 체크박스 클릭 콜백
            try:
                r = ed["row"]; val = bool(ed["value"])
            except Exception:  # noqa: BLE001
                return
            if kinds[r] != "param":                      # 헤더=하위 전체 동기화
                for k in descend_param.get(r, []):
                    sheet.set_cell_data(k, 0, val, redraw=False)
                for h in descend_head.get(r, []):
                    sheet.set_cell_data(h, 0, val, redraw=False)
            for h in ancestors.get(r, []):               # 상위 헤더 상태 재계산
                sync_header(h)
            sheet.refresh()

        def on_dd(ed):                                   # 변환방식 드롭다운 선택 콜백
            try:
                r = ed["row"]; label = ed["value"]
            except Exception:  # noqa: BLE001
                return
            e = row_entry.get(r)
            if e is not None:
                sheet.set_cell_data(r, 4, disp_of(e, label), redraw=False)
            sheet.refresh()

        def refresh_all():                               # 계수 [적용]=표시값 일괄 갱신
            for r in param_r:
                e = row_entry[r]
                label = engine._s(sheet.get_cell_data(r, 2))
                sheet.set_cell_data(r, 4, disp_of(e, label), redraw=False)
            sheet.refresh()

        def set_all(val):
            for i in range(len(data)):
                sheet.set_cell_data(i, 0, bool(val), redraw=False)
            sheet.refresh()

        # 사용(체크박스) 열 전체 — 헤더행=그룹 토글, 파라미터행=개별 선택
        try:
            sheet.checkbox("A", check_function=on_check, redraw=False)
        except Exception as _e:  # noqa: BLE001
            self._logerr("E212", _e)
        # 분류(변환방식): 파라미터 행만 셀 단위 드롭다운(헤더 행엔 드롭다운 없음).
        #   열 단위로 걸면 헤더 행에서도 드롭다운이 떠 셀 단위로 개별 적용한다.
        for r in param_r:
            try:
                sheet.dropdown(f"C{r + 1}", values=label_values, edit_data=False,
                               selection_function=on_dd, redraw=False)
            except Exception as _e:  # noqa: BLE001
                self._logerr("E213", _e)
        # 읽기전용: 원본값/표시값 열 전체 + 헤더행의 항목·분류 셀
        try:
            sheet.readonly("D"); sheet.readonly("E")
            for hr in header_rows:
                sheet.readonly(f"B{hr + 1}"); sheet.readonly(f"C{hr + 1}")
        except Exception as _e:  # noqa: BLE001
            self._logerr("E214", _e)
        # 계층 헤더 행 색칠(가독성)
        for tag, color in (("variant", "#dbe4f0"), ("zone", "#e2e8f0"),
                           ("alg", "#eef2f7")):
            rws = [i for i, k in enumerate(kinds) if k == tag]
            if rws:
                try:
                    sheet.highlight_rows(rows=rws, bg=color, fg=self.p["text"],
                                         highlight_index=False, redraw=False)
                except Exception as _e:  # noqa: BLE001
                    self._logerr("E215", _e)
        try:
            sheet.set_options(table_wrap="", header_wrap="w")
        except Exception as _e:  # noqa: BLE001
            self._logerr("E216", _e)
        sheet.refresh()

        # Enter = 현재 행 체크박스 선택/해제 + **다음 행으로 이동**(연속 체크 편의).
        #   tksheet 는 <Key>→open_cell 로 Enter 시 토글만 하고 이동은 안 한다. <Return> 은
        #   <Key> 보다 구체적이라 이 바인딩이 Enter 를 전담(중복 토글 없음). 이름/드롭다운
        #   편집 중엔 포커스가 편집 위젯에 있어 이 핸들러가 안 불린다(안전).
        def _enter_step(event=None):
            try:
                cur = sheet.get_currently_selected()
                if not cur:
                    return "break"
                r, c = cur.row, cur.column
                if c != 0:                        # 체크박스 열이 아니면 기본 동작 위임
                    sheet.MT.open_cell(event)
                    return "break"
                newv = not bool(sheet.get_cell_data(r, 0))
                sheet.set_cell_data(r, 0, newv, redraw=False)
                on_check({"row": r, "value": newv})   # 헤더/하위 동기화 + 재도색
                nr = r + 1
                if nr <= len(data) - 1:
                    sheet.select_cell(nr, 0)
                    sheet.see(nr, 0)
            except Exception as _e:  # noqa: BLE001
                self._logerr("E217", _e)
            return "break"
        try:
            sheet.MT.bind("<Return>", _enter_step)
        except Exception as _e:  # noqa: BLE001
            self._logerr("E218", _e)

        # 하단: 전체 선택/해제 + 확정/취소
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(bt, text="전체 선택", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=10, pady=6, cursor="hand2",
                  command=lambda: set_all(True)).pack(side="left")
        tk.Button(bt, text="전체 해제", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=10, pady=6, cursor="hand2",
                  command=lambda: set_all(False)).pack(side="left", padx=6)
        tk.Label(bt, text=("  (체크박스 클릭=선택 · 상위행 체크=하위 전체 선택·해제 · "
                           "항목/분류는 셀을 더블클릭해 편집)"),
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"]).pack(side="left")

        def to_excel():
            if on_excel is not None:
                win.destroy()
                on_excel()
                return
            win.destroy()
            draft = workdirs.form_draft_path(related, level, aoi, st)

            def work():
                formbuilder.build_initial_workbook(rows, draft, level=level,
                                                   source=f"{level} / {aoi}")
                import shutil
                orig = workdirs.form_original_path(related, level, aoi, st)
                shutil.copy2(draft, orig)
                return orig

            def done(ok, res):
                if not ok:
                    self._err("E203", "초안(수정본) 엑셀 생성 실패", res)
                    return
                opened = self._open_in_excel(draft)
                self._form_finalize_dialog(draft, res, level, kind, scales, run_dir,
                                           aoi, st, opened)
            self._run_busy("초안(수정본) 엑셀 생성 중…", work, done)

        def confirm():
            # 격자 셀에서 현재 상태를 읽어 selected 구성 → editor_model 이 저장 규칙 적용
            try:
                selected = []
                for r in param_r:
                    e = row_entry[r]
                    selected.append({
                        "use": bool(sheet.get_cell_data(r, 0)),
                        "name": sheet.get_cell_data(r, 1),
                        "reco": e["reco"], "variant": e["variant"],
                        "zone": e["zone"], "alg": e["alg"], "ext": e["ext"],
                        "method": sheet.get_cell_data(r, 2),
                        "coef": coef_of(e["variant"])})
                records, extracts, used_scales = editor_model.build_records(
                    selected, level)
            except Exception as _e:  # noqa: BLE001
                self._err("E204", "양식 확정 실패(선택 항목 해석)", _e, parent=win)
                return
            if not records:
                messagebox.showinfo("확정", "선택된 파라미터가 없습니다.", parent=win)
                return
            if on_confirm is not None:               # commonality 등 다른 저장 경로
                on_confirm(records, extracts, dict(used_scales), win)
                return
            sheet_name = "RDL_ALL" if kind == "RDL" else "PI_ALL"
            final = workdirs.form_final_path(run_dir, level, aoi, st)
            scales_out = dict(used_scales)

            def work():
                extract_io.write_snapshot(
                    final, records, machines=[], sheet_name=sheet_name, extracts=extracts,
                    stage="final", level=level, aoi=aoi, source=f"{level} 양식",
                    user=self.user, scales=scales_out)
                return final

            def done(ok, res):
                if not ok:
                    self._err("E205", "양식 확정 실패(파일 저장)", res, parent=win)
                    return
                win.destroy()
                if messagebox.askyesno(
                        "양식 확정 완료",
                        f"확정 양식 생성: {os.path.basename(final)}\n"
                        f"항목 {len(records)}개.\n위치: {run_dir}\n\n지금 열어 볼까요?"):
                    self._open_collation_view(final)
            self._run_busy("양식 확정 중…", work, done)
        tk.Button(bt, text="✔ 편집 완료 → 양식 확정", relief="flat", bd=0, bg=self.p["ok"],
                  fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=confirm).pack(side="right")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=14,
                  pady=6, cursor="hand2", command=win.destroy).pack(side="right", padx=6)

    def _form_finalize_dialog(self, draft, orig, level, kind, scales, run_dir, aoi, st,
                              opened, prev_form=None):
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
                                                      run_dir, aoi, st, win,
                                                      prev_form=prev_form)).pack(side="right")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=12,
                  pady=6, cursor="hand2", command=win.destroy).pack(side="right", padx=6)

    def _form_finalize(self, draft, level, kind, scales, run_dir, aoi, st, win,
                       prev_form=None):
        final = workdirs.form_final_path(run_dir, level, aoi, st)

        def work():
            return formbuilder.build_final_from_initial(
                draft, final, user=self.user, level=level, source=f"{level} 양식",
                scales=scales)

        def done(ok, res):
            if not ok:
                self._err("E118", "양식 확정 실패", res, parent=win)
                return
            win.destroy()
            self._release_global(f"양식_{level}")      # 양식 확정 완료 — 잠금 반납
            # 기존 양식 수정 확정 → 이전 값 이어받기 + 신규 항목 값 업데이트 안내(req5)
            if prev_form:
                self._post_finalize_merge(final, prev_form, level, res)
                return
            if messagebox.askyesno(
                    "양식 확정 완료",
                    f"확정 양식 생성: {os.path.basename(final)}\n"
                    f"항목 {res['kept']}개(제외 {res['dropped']}개).\n"
                    f"위치: {run_dir}\n\n지금 화면으로 열어 볼까요?"):
                self._open_collation_view(final)
        self._run_busy("양식 확정 중…", work, done)

    def _post_finalize_merge(self, final, prev_form, level, res):
        """기존 양식 수정 확정 후: 이전 취합 값을 새 양식 구조로 이어받아 저장하고,
        새(변경) 파라미터는 빈칸으로 둔 뒤 '지금 값 업데이트할까요?' 를 물어본다."""
        machines = self._all_machines()
        prev_collate = workdirs.latest_collate(self.save_dir)

        # 신규 파라미터 = 새 양식엔 있고 이전 양식엔 없던 항목
        try:
            old_keys = formbuilder.form_params(prev_form)
            new_keys = formbuilder.form_params(final)
            added = new_keys - old_keys
        except Exception:  # noqa: BLE001
            added = set()

        def work():
            # 빈 파싱(pivot 없음) + 직전 취합 이어받기 → 기존값 채움, 신규는 빈칸
            cl = (lambda ho, mag: coefstore.lookup(self.coef_rows, ho, mag))
            out = collate.build_collation(self.save_dir, [level], [], machines,
                                          prev_collate_path=prev_collate, coef_lookup=cl)
            made = {r: v for r, v in out.items() if not v.missing_form}
            dest = workdirs.collate_path(self.save_dir, workdirs.stamp())
            collate.write_collation(dest, made, machines)
            return dest

        def done(ok, dest):
            if not ok:
                messagebox.showerror("값 이어받기 실패", str(dest))
                return
            self._load_latest_collate()
            self.view = "param"
            self._sync_tab_style()
            self.navigate(screen="s0")
            n_add = len(added)
            base_msg = (f"확정 양식: {os.path.basename(final)}\n"
                        f"항목 {res['kept']}개. 기존 파라미터 값은 이전 취합본에서 "
                        "이어받았습니다.")
            if n_add and messagebox.askyesno(
                    "새 항목 값 업데이트",
                    base_msg + f"\n\n새로(변경) 추가된 파라미터 {n_add}개는 값이 "
                    "비어 있습니다.\n지금 이 항목들의 값을 장비/로컬에서 업데이트할까요?"):
                self._start_value_update(chosen=[level])
            else:
                messagebox.showinfo("양식 확정 완료", base_msg
                                    + (f"\n새 항목 {n_add}개는 빈칸으로 두었습니다."
                                       if n_add else ""))
        self._run_busy("이전 값 이어받는 중…", work, done)

    # ====================================================================
    #  Commonality 조사 (Scanresult Lot 파라미터 공통성/변경 조사)
    # ====================================================================
    def _cm_roots(self) -> dict:
        return self._cfg.setdefault("commonality_roots", {})

    def _cm_step(self, parent, n, title, desc, buttons, done=False):
        """조사 단계 카드 1개. buttons=[(라벨, 콜백, 강조여부)]."""
        card = tk.Frame(parent, bg=self.p["surface"], bd=0, highlightthickness=1,
                        highlightbackground=self.p["head_bg"])
        card.pack(fill="x", padx=4, pady=5)
        head = tk.Frame(card, bg=self.p["surface"])
        head.pack(fill="x", padx=12, pady=(10, 2))
        mark = "✓ " if done else f"{n}. "
        tk.Label(head, text=mark + title, bg=self.p["surface"],
                 fg=(self.p["ok"] if done else self.p["text"]),
                 font=self.fonts["bold"]).pack(side="left")
        if desc:
            tk.Label(card, text=desc, bg=self.p["surface"], fg=self.p["muted"],
                     font=self.fonts["sub"], justify="left", wraplength=760).pack(
                     anchor="w", padx=12, pady=(0, 6))
        if buttons:
            bar = tk.Frame(card, bg=self.p["surface"])
            bar.pack(fill="x", padx=12, pady=(0, 10))
            for lbl, cb, primary in buttons:
                tk.Button(bar, text=lbl, relief="flat", bd=0,
                          bg=(self.p["primary"] if primary else self.p["head_bg"]),
                          fg=("#ffffff" if primary else self.p["text"]),
                          padx=12, pady=5, cursor="hand2", command=cb).pack(
                          side="left", padx=(0, 6))
        return card

    def _view_commonality(self):
        wrap = tk.Frame(self.body, bg=self.p["bg"])
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=self.p["bg"], highlightthickness=0)
        vbar = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.p["bg"])
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="i")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("i", width=e.width))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")
        self._wheelify(canvas)

        tk.Label(inner, text="Commonality 조사", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", padx=8, pady=(14, 2))
        tk.Label(inner, text="Scanresult 아래 여러 Lot의 파라미터가 바뀌었는지 조사합니다. "
                            "호기 1대씩 진행 → 호기 취합·비교로 마무리.",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=8, pady=(0, 8))

        if not self.save_dir:
            tk.Label(inner, text="먼저 저장 폴더를 지정하세요(파라미터 값 확인 탭의 ⋯파일).",
                     bg=self.p["bg"], fg=self.p["danger"],
                     font=self.fonts["sub"]).pack(anchor="w", padx=8)
            return

        cm = self._cm
        machine = cm.get("machine")

        # Step 1 — 호기 선택 + 호기 폴더(그 아래 Scanresult 전부 자동 탐색)
        mlabel = machine or "(미선택)"
        root = self._cm_roots().get(machine, "") if machine else ""
        desc1 = f"선택 호기: {mlabel}"
        if machine:
            desc1 += f"\n호기 폴더: {root or '(미지정 — 지정 필요)'}"
            if root:
                try:
                    srs = cm.scanresult_roots(root, machine)
                    names = ", ".join(p.name for p in srs)
                    desc1 += f"\n탐색 대상 Scanresult({len(srs)}): {names}"
                except Exception:  # noqa: BLE001
                    pass
        self._cm_step(inner, 1, "조사할 장비(호기) 선택", desc1, [
            ("호기 선택", self._cm_pick_machine, True),
            *([("호기 폴더 지정", self._cm_choose_root, False)] if machine else []),
        ], done=bool(machine and root))

        if not (machine and root):
            return

        # Step 2 — Lot 계획 엑셀
        n_plan = len(cm.get("plan_rows") or [])
        self._cm_step(inner, 2, "Lot 계획 엑셀 (디바이스명/공정번호/S·M/AOI호기)",
                      f"업로드된 계획: {n_plan}행(이 호기 {mlabel} 기준 필터)"
                      if n_plan else "템플릿을 만들어 채운 뒤 업로드하세요.", [
                          ("템플릿 만들기", self._cm_make_template, False),
                          ("계획 업로드", self._cm_upload_plan, True),
                      ], done=bool(cm.get("lots")))

        # Step 3 — 폴더 확인 + 복사
        lots = cm.get("lots") or []
        if lots:
            ok = [l for l in lots if l.exists]
            self._cm_step(inner, 3, "폴더 확인 및 안전 복사(원본 수정 금지)",
                          f"조사 대상 Lot: {len(ok)}개(찾음). "
                          f"복사됨: {'예' if cm.get('lot_dirs') else '아니오'}", [
                              ("Lot 폴더 확인/추가", self._cm_confirm_lots, False),
                              ("복사 실행", self._cm_copy, True),
                          ], done=bool(cm.get("lot_dirs")))

        # Step 4 — 양식 만들기
        if cm.get("lot_dirs"):
            self._cm_step(inner, 4, "조사할 파라미터 양식 만들기",
                          f"양식 제목(레시피): {cm.get('recipe') or '(미지정)'}\n"
                          "양식 만들기와 동일 방식(OpticPreset 추림·변환계수·추천 파라미터). "
                          "Lot 간 구조가 다르면 확인창을 띄웁니다.", [
                              ("Lot 구조 확인", self._cm_structure_check, False),
                              ("양식 만들기/편집", self._cm_make_form, True),
                          ], done=bool(cm.get("form_path")))

        # Step 5 — 값 조사
        if cm.get("form_path"):
            self._cm_step(inner, 5, "Lot별 파라미터 값 조사 → 호기 결과 엑셀",
                          f"결과: {os.path.basename(cm['result_path'])}"
                          if cm.get("result_path") else "확정 양식 기준으로 Lot별 값을 채웁니다.",
                          [("값 조사 실행", self._cm_collate, True),
                           *([("결과 열기", lambda: self._open_in_excel(cm["result_path"]),
                              False)] if cm.get("result_path") else [])],
                          done=bool(cm.get("result_path")))

        # Step 6/7 — 호기 취합·비교 + 뷰어 (호기 무관, 항상 노출)
        n_res = len(workdirs.list_commonality_results(self._cm_root()))
        self._cm_step(inner, 6, "호기별 조사 결과 취합·비교 + 뷰어",
                      f"저장된 호기 결과 파일: {n_res}개. 파라미터 항목 비교 후 "
                      "과반수와 다른 값을 색칠하고, 변경/이상치 뷰어를 엽니다.", [
                          ("취합·비교 + 뷰어 열기", self._cm_compare, True),
                      ])

        # 새 호기 진행
        tk.Button(inner, text="＋ 다른 호기로 새로 시작", relief="flat", bd=0,
                  bg=self.p["head_bg"], fg=self.p["text"], padx=12, pady=5,
                  cursor="hand2", command=self._cm_new).pack(anchor="w", padx=8, pady=10)

    def _cm_new(self):
        self._cm = {}
        self._render()

    def _cm_pick_machine(self):
        machines = self._all_machines()
        if not machines:
            messagebox.showinfo("호기 없음", "장비 IP 주소에 호기가 없습니다. "
                                "'장비 IP' 탭에서 먼저 등록하세요.")
            return
        win = tk.Toplevel(self)
        win.title("조사할 호기 선택")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="Commonality 조사할 호기를 1대 선택하세요.", bg=self.p["bg"],
                 fg=self.p["text"], font=self.fonts["bold"]).pack(padx=16, pady=(12, 8))
        lb = tk.Listbox(win, height=min(12, len(machines)), width=24,
                        font=self.fonts["sub"], activestyle="dotbox")
        for m in machines:
            lb.insert("end", m)
        lb.pack(padx=16, pady=(0, 8))

        def ok():
            sel = lb.curselection()
            if not sel:
                return
            m = machines[sel[0]]
            self._cm = {"machine": m}
            win.destroy()
            if not self._cm_roots().get(m):
                self._cm_choose_root()
            else:
                self._render()
        tk.Button(win, text="선택", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=16, pady=5, cursor="hand2", command=ok).pack(
                  pady=(0, 12))

    def _cm_choose_root(self):
        m = self._cm.get("machine")
        if not m:
            return
        messagebox.showinfo(
            "Scanresult 루트",
            f"'{m}' 의 **호기 폴더**를 선택하세요(예: …\\AOI-9, 읽기 전용).\n"
            "• 그 아래 Scanresult 폴더는 자동으로 찾습니다.\n"
            "• 백업본이 여러 개(Scanresult / Scanresult_260402 / "
            "SCANRESULT_BACKUP_260805 등)면 **전부 탐색**해 Lot 을 찾습니다.\n"
            "• Scanresult 폴더 하나만 직접 골라도 됩니다(그 폴더만 사용).\n"
            "한 번 지정하면 이 호기에 대해 자동 재사용됩니다.")
        d = filedialog.askdirectory(title=f"{m} 호기 폴더(또는 Scanresult) 선택")
        if not d:
            return
        self._cm_roots()[m] = d
        save_config(self._cfg)
        self._render()

    def _cm_scan_roots(self):
        m = self._cm["machine"]
        base = self._cm_roots().get(m, "")
        return cm.scanresult_roots(base, m)

    def _cm_make_template(self):
        path = filedialog.asksaveasfilename(
            title="Lot 계획 템플릿 저장", defaultextension=".xlsx",
            initialfile="Lot계획.xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        cm.create_plan_template(path)
        if messagebox.askyesno("템플릿 생성",
                               f"템플릿을 만들었습니다:\n{path}\n\n지금 Excel로 열까요?"):
            self._open_in_excel(path)

    def _cm_upload_plan(self):
        m = self._cm.get("machine")
        path = filedialog.askopenfilename(title="작성한 Lot 계획 엑셀 선택",
                                          filetypes=[("Excel", "*.xlsx")])
        if not path:
            return

        def work():
            rows = cm.read_plan(path)
            mine = cm.filter_plan_for_machine(rows, m)
            scan_roots = self._cm_scan_roots()
            lots = cm.resolve_plan(scan_roots, mine)
            return mine, lots

        def done(ok, res):
            if not ok:
                self._err("E120", "Lot 계획 읽기 실패", res)
                return
            mine, lots = res
            self._cm["plan_path"] = path
            self._cm["plan_rows"] = mine
            self._cm["lots"] = lots
            self._cm.pop("lot_dirs", None)
            self._cm.pop("form_path", None)
            self._cm.pop("result_path", None)
            self._render()
            if not mine:
                messagebox.showwarning("계획 필터", f"'{m}' 호기에 해당하는 행이 없습니다. "
                                       "AOI호기 열을 확인하세요.")
            else:
                self._cm_confirm_lots()
        self._run_busy("Lot 폴더 확인 중…", work, done)

    def _cm_confirm_lots(self):
        """찾은 S/M 폴더(변형 포함)를 체크박스로 표시 — 기본 전체 선택."""
        lots = self._cm.get("lots") or []
        win = tk.Toplevel(self)
        win.title("S/M 폴더 선택")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        win.geometry("720x520")
        tk.Label(win, text="조사할 S/M 폴더를 선택하세요(변형 이름 포함). 기본은 전체 선택.",
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["bold"]).pack(
                 anchor="w", padx=14, pady=(12, 2))
        tk.Label(win, text="노란색 = fail(계획 fail여부=Y) · ✗ = 폴더 없음(선택 불가)",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"]).pack(
                 anchor="w", padx=14, pady=(0, 6))
        # 스크롤 영역
        outer = tk.Frame(win, bg=self.p["bg"])
        outer.pack(fill="both", expand=True, padx=14)
        canvas = tk.Canvas(outer, bg=self.p["bg"], highlightthickness=0)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.p["bg"])
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="i")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("i", width=e.width))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")
        self._wheelify(canvas)

        self._cm_sel_vars = []       # [(BooleanVar, LotFolder)]
        for l in lots:
            var = tk.BooleanVar(value=bool(l.exists))   # 기본 전체 선택(존재하는 것)
            self._cm_sel_vars.append((var, l))
            row = tk.Frame(inner, bg=self.p["bg"])
            row.pack(fill="x", pady=1)
            cb = tk.Checkbutton(row, variable=var, bg=self.p["bg"],
                                activebackground=self.p["bg"], selectcolor=self.p["surface"],
                                state=("normal" if l.exists else "disabled"))
            cb.pack(side="left")
            mark = "✓" if l.exists else "✗"
            detail = (f"{l.wafer_dir.name}" if l.exists else l.reason)
            txt = f"{mark}  {l.label}   ·   {l.device}/{l.lot}   →   {detail}"
            lbl = tk.Label(row, text=txt, bg=(self.p["bg"] if not l.fail else "#FFF6C8"),
                           fg=(self.p["text"] if l.exists else self.p["muted"]),
                           font=self.fonts["sub"], anchor="w")
            lbl.pack(side="left", fill="x", expand=True)

        def set_all(v):
            for var, l in self._cm_sel_vars:
                if l.exists:
                    var.set(v)

        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=14, pady=12)
        tk.Button(bt, text="전체 선택", relief="flat", bd=0, bg=self.p["surface"],
                  padx=10, pady=4, cursor="hand2",
                  command=lambda: set_all(True)).pack(side="left")
        tk.Button(bt, text="전체 해제", relief="flat", bd=0, bg=self.p["surface"],
                  padx=10, pady=4, cursor="hand2",
                  command=lambda: set_all(False)).pack(side="left", padx=4)
        tk.Button(bt, text="＋ 폴더 추가", relief="flat", bd=0, bg=self.p["surface"],
                  padx=10, pady=4, cursor="hand2",
                  command=lambda: (win.destroy(), self._cm_add_lot())).pack(side="left", padx=4)
        tk.Button(bt, text="선택한 폴더로 진행(복사)", relief="flat", bd=0,
                  bg=self.p["primary"], fg="#ffffff", padx=14, pady=5, cursor="hand2",
                  command=lambda: self._cm_confirm_proceed(win)).pack(side="right")
        tk.Button(bt, text="닫기", relief="flat", bd=0, bg=self.p["surface"], padx=12,
                  pady=5, cursor="hand2", command=win.destroy).pack(side="right", padx=6)

    def _cm_confirm_proceed(self, win):
        selected = [l for var, l in getattr(self, "_cm_sel_vars", [])
                    if var.get() and l.exists]
        if not selected:
            messagebox.showwarning("선택 없음", "복사할 S/M 폴더를 하나 이상 선택하세요.",
                                   parent=win)
            return
        self._cm["selected"] = selected
        win.destroy()
        self._cm_copy()

    def _cm_add_lot(self):
        m = self._cm.get("machine")
        win = tk.Toplevel(self)
        win.title("Lot 폴더 추가")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        frm = tk.Frame(win, bg=self.p["bg"])
        frm.pack(padx=16, pady=14)
        vs = {}
        for i, (key, lab) in enumerate((("디바이스명", "디바이스명"),
                                        ("공정번호", "공정번호"), ("S/M", "S/M"))):
            tk.Label(frm, text=lab + ":", bg=self.p["bg"], fg=self.p["text"],
                     font=self.fonts["sub"]).grid(row=i, column=0, sticky="w", pady=3)
            v = tk.StringVar()
            tk.Entry(frm, textvariable=v, width=26, relief="solid", bd=1).grid(
                row=i, column=1, padx=6, pady=3)
            vs[key] = v

        def ok():
            scan_roots = self._cm_scan_roots()
            found = cm.resolve_lot_variants(scan_roots, vs["디바이스명"].get().strip(),
                                            vs["공정번호"].get().strip(),
                                            vs["S/M"].get().strip(), m)
            self._cm.setdefault("lots", []).extend(found)
            win.destroy()
            ok_n = [l for l in found if l.exists]
            if not ok_n:
                messagebox.showwarning("폴더 없음",
                                       f"폴더를 찾지 못했습니다: {found[0].reason}")
            self._cm_confirm_lots()
        tk.Button(win, text="추가", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=16, pady=5, cursor="hand2", command=ok).pack(
                  pady=(0, 12))

    def _cm_copy(self):
        m = self._cm["machine"]
        # 선택 모드에서 고른 폴더 우선, 없으면 존재하는 전부.
        lots = self._cm.get("selected") or \
            [l for l in (self._cm.get("lots") or []) if l.exists]
        if not lots:
            messagebox.showwarning("복사 대상 없음", "찾은 S/M 폴더가 없습니다.")
            return
        st = workdirs.stamp()
        # Commonality 산출물은 **로컬**에(Lot 안전복사본 등 파일이 많아
        # OneDrive 에 두면 동기화가 폭주한다 — 2026-08 사고)
        run_dir = workdirs.commonality_run_dir(self._cm_root(), m, st)
        staging = workdirs.commonality_staging(run_dir)

        def work():
            lot_dirs, fail_labels = [], []
            for l in lots:
                res = cm.copy_lot(l, staging, verify=True)
                lot_dirs.append((l.label, res["dest"]))
                if l.fail:
                    fail_labels.append(l.label)
            return run_dir, st, lot_dirs, fail_labels

        def done(ok, res):
            if not ok:
                self._err("E121", "안전 복사 실패", res)
                return
            run_dir, st, lot_dirs, fail_labels = res
            self._cm.update(run_dir=run_dir, st=st, staging=staging,
                            lot_dirs=lot_dirs, fail_labels=fail_labels)
            self._cm.pop("form_path", None)
            self._cm.pop("result_path", None)
            self._render()
            messagebox.showinfo("복사 완료",
                                f"{len(lot_dirs)}개 S/M 폴더를 안전 복사했습니다(원본 수정 없음).\n"
                                + (f"fail 표시 {len(fail_labels)}개.\n" if fail_labels else "")
                                + f"위치: {staging}")
        self._run_busy("S/M 폴더 안전 복사 중…", work, done)

    def _cm_structure_check(self):
        from pathlib import Path
        lot_dirs = [(lbl, Path(d))
                    for lbl, d in (self._cm.get("lot_dirs") or [])]
        if not lot_dirs:
            return
        level = self._cm.get("recipe", "")
        prefix = self._cm.get("recipe_prefix", "")   # 다중 레시피면 현재 레시피 기준

        def work():
            return cm.structure_diff(lot_dirs, level=level, recipe_prefix=prefix)

        def done(ok, res):
            if not ok:
                self._err("E122", "Lot 구조 확인 실패", res)
                return
            if res["identical"]:
                messagebox.showinfo("구조 확인", "모든 Lot의 파라미터 구조가 동일합니다.")
                return
            lines = ["Lot 간 파라미터 구조가 다릅니다(빠진 항목):\n"]
            for lbl, info in res["lots"].items():
                if info["missing"]:
                    lines.append(f"[{lbl}] 빠짐 {len(info['missing'])}개: "
                                 + ", ".join(info["missing"][:6])
                                 + (" …" if len(info["missing"]) > 6 else ""))
            messagebox.showwarning("구조 불일치", "\n".join(lines))
        self._run_busy("Lot 구조 비교 중…", work, done)

    def _cm_make_form(self):
        from pathlib import Path as _P
        lot_dirs = [(lbl, _P(d)) for lbl, d in self._cm["lot_dirs"]]
        # ── 사전 확인: ActiveScenarioOptics.ini 유무 + 하위 레시피 개수 ──
        pre = cm.form_preflight(lot_dirs)
        rlist = pre["recipes"]
        lines = []
        if rlist:
            lines.append(f"• 하위 레시피: {len(rlist)}개")
            for r in rlist:
                a = pre["active"].get(r["name"], {})
                mark = ("있음" if a.get("file") else "없음")
                if a.get("file") and not a.get("scan2d"):
                    mark += "(Scan2d 항목 없음 → 구 방식)"
                elif a.get("file"):
                    mark += "(신 SW — Scan2d optic 지정)"
                lines.append(f"    - {r['name']}  ·  ActiveScenarioOptics.ini: {mark}")
        else:
            a = pre["active"].get("", {})
            lines.append("• 하위 레시피: 1개 (단일 — RecipesInfo.ini 없음/1개)")
            if a.get("file"):
                extra = ("Scan2d 항목 없음 → 구 방식" if not a.get("scan2d")
                         else "신 SW — Scan2d optic 지정")
                lines.append(f"• ActiveScenarioOptics.ini: 있음 ({extra})")
            else:
                lines.append("• ActiveScenarioOptics.ini: 없음 (구 SW 방식으로 target 추정)")
        if not pre["config_dir"]:
            lines.append("\n⚠ config 폴더(설정 .ini)를 찾지 못했습니다. 복사 결과를 확인하세요.")
        messagebox.showinfo(
            "양식 만들기 — 사전 확인",
            "이번 조사 대상의 구성입니다.\n\n" + "\n".join(lines) +
            "\n\n확인을 누르면 계속 진행합니다.")
        # 다중 레시피 자동 인식(RecipesInfo.ini) → 알림 후 레시피별 순차 진행
        recipes = rlist or None
        if recipes:
            from tkinter import simpledialog
            base = simpledialog.askstring(
                "다중 레시피 — 조사 제목",
                "레시피별로 순차 진행합니다(레시피마다 편집기 → 값 조사).\n"
                "양식·결과 파일은 레시피별로 따로 만들어지며, 같은 조사의 분기임을\n"
                f"알 수 있게 '조사제목_레시피명'(예: {self._cm.get('recipe') or 'PI3'}_{recipes[0]['name']})\n"
                "형식으로 저장됩니다.\n\n이 조사의 제목을 입력하세요:",
                initialvalue=self._cm.get("recipe") or "", parent=self)
            if not base:
                return
            self._cm["cm_base"] = base.strip()
            self._cm["recipes"] = recipes
            self._cm["recipe_idx"] = 0
            self._cm["recipe_done"] = []
            self._cm_process_recipe(lot_dirs)
            return
        # 단일 레시피(기존 동작): 제목 입력 후 진행
        from tkinter import simpledialog
        recipe = self._cm.get("recipe") or ""
        recipe = simpledialog.askstring(
            "양식 제목", "조사 양식 제목(레시피명)을 입력하세요(예: PI3, RDL2, 또는 직접 입력):",
            initialvalue=recipe, parent=self)
        if not recipe:
            return
        recipe = recipe.strip()
        self._cm["recipe"] = recipe
        self._cm.pop("recipes", None)
        self._cm_run_form_detect(lot_dirs, recipe, recipe_prefix="", multi=False)

    def _cm_process_recipe(self, lot_dirs):
        """다중 레시피 큐: 현재 레시피의 양식→값 조사 진행, 끝나면 다음 레시피로."""
        recipes = self._cm["recipes"]
        idx = self._cm["recipe_idx"]
        if idx >= len(recipes):                       # 전부 완료
            done = self._cm.get("recipe_done", [])
            self._cm.pop("_after_form", None)
            self._render()
            messagebox.showinfo(
                "다중 레시피 완료",
                f"레시피 {len(done)}개의 양식·값 조사가 끝났습니다: " + ", ".join(done) +
                "\n\n이제 '취합·비교 + 뷰어 열기'로 마무리하세요.")
            return
        rec = recipes[idx]
        base = self._cm.get("cm_base", "")
        # 파일명이 '조사제목_레시피명'(예 PI3_PI, PI3_PI_Bubble)이 되어 같은 조사의
        # 레시피 분기임을 확실히 구분한다.
        eff = f"{base}_{rec['name']}" if base else rec["name"]
        self._cm["recipe"] = eff
        self._cm["recipe_prefix"] = rec["prefix"]
        self._cm_run_form_detect(lot_dirs, eff, recipe_prefix=rec["prefix"], multi=True)

    def _advance_recipe(self, lot_dirs):
        self._cm.setdefault("recipe_done", []).append(self._cm.get("recipe"))
        self._cm["recipe_idx"] = self._cm.get("recipe_idx", 0) + 1
        self._cm_process_recipe(lot_dirs)

    def _cm_run_form_detect(self, lot_dirs, recipe, recipe_prefix="", multi=False):
        """변형·계수 감지(해당 레시피 파일 기준) → _ask_scales → 양식 빌드."""
        def detect():
            variants, dirs = [], {}
            for _lbl, d in lot_dirs:
                for c in ini_parser.scan_tree(d, default_level=recipe,
                                              recipe_prefix=recipe_prefix):
                    v = c.mag or "(기본)"
                    if v not in variants:
                        variants.append(v)
                        dirs[v] = c.config_dir
            variants = variants or ["(기본)"]
            reco = {}
            for v in variants:
                dd = dirs.get(v)
                try:
                    reco[v] = coef_detector.detect_from_dir(dd) if dd else None
                except Exception:  # noqa: BLE001
                    reco[v] = None
            return variants, reco

        def after(ok, res):
            if not ok:
                self._err("E123", "변형(레시피) 감지 실패", res)
                return
            variants, reco = res
            scales_ui = self._ask_scales(variants, reco)
            if scales_ui is None:
                return
            scale_map = {("" if k == "(기본)" else k): v for k, v in scales_ui.items()}
            self._cm["scales"] = scale_map
            self._cm_build_form(lot_dirs, recipe, scale_map,
                                recipe_prefix=recipe_prefix, multi=multi)
        self._run_busy(f"[{recipe}] 변형·계수 감지 중…" if multi else "변형·계수 감지 중…",
                       detect, after)

    def _cm_build_form(self, lot_dirs, recipe, scale_map, recipe_prefix="", multi=False):
        """Lot 파싱 → 기존 양식 유사도 안내 → 프로그램 편집기(양식 만들기와 동일 UX).
        확정 시 commonality 양식 경로로 저장(엑셀 편집 버튼도 제공)."""
        m, st = self._cm["machine"], self._cm["st"]
        run_dir = self._cm["run_dir"]

        # 다중 레시피면 양식 확정/편집 완료 후 자동으로 값 조사 → 다음 레시피로 진행
        if multi:
            self._cm["_after_form"] = lambda: self._cm_collate(
                then=lambda: self._advance_recipe(lot_dirs), announce=False)
        else:
            self._cm.pop("_after_form", None)
        title = f"Commonality 양식 [{recipe}]" if multi else "Commonality 양식"

        def work():
            cb, cstate = self._coef_lookup_cb(fixed_machine=m)   # 조사 호기 1대 기준
            pivot, labels = cm.parse_lots(lot_dirs, level=recipe, scales=scale_map,
                                          coef_lookup=cb, recipe_prefix=recipe_prefix)
            self._coef_save_if_changed(cstate)
            return pivot, labels

        def done(ok, res):
            if not ok:
                self._err("E124", "파싱 실패", res)
                return
            pivot, labels = res
            self._cm["pivot"], self._cm["labels"] = pivot, labels
            kind = "RDL" if recipe.upper().startswith("RDL") else "PI"
            # 기존 양식(양식 만들기)들과 유사도 순위
            parsed_keys = formbuilder.pivot_param_keys(pivot)
            forms = {}
            try:
                for r in workdirs.list_recipes(self.save_dir):
                    f = workdirs.latest_form(self.save_dir, r)
                    if f:
                        forms[r] = formbuilder.form_params(f)
            except Exception:  # noqa: BLE001
                forms = {}
            ranked = formbuilder.rank_similar_forms(parsed_keys, forms)
            base = self._form_base_dialog(recipe, ranked, "Commonality 양식")
            if base is None:
                return
            base_keys = None
            if base:
                bf = workdirs.latest_form(self.save_dir, base)
                base_keys = formbuilder.form_params(bf) if bf else None

            def cm_confirm(records, extracts, scales_out, win):
                form = workdirs.commonality_form_path(run_dir, recipe, m, st)
                sheet = "RDL_ALL" if kind == "RDL" else "PI_ALL"

                def w2():
                    extract_io.write_snapshot(
                        form, records, machines=[], sheet_name=sheet, extracts=extracts,
                        stage="final", level=recipe, aoi=m,
                        source=f"commonality {recipe}", user=self.user, scales=scales_out)
                    return form

                def d2(ok2, res2):
                    if not ok2:
                        messagebox.showerror("양식 확정 실패", str(res2))
                        return
                    win.destroy()
                    self._cm["form_path"] = form
                    after = self._cm.pop("_after_form", None)
                    if after:                          # 다중: 자동 값 조사 → 다음 레시피
                        after()
                    else:
                        self._render()
                        messagebox.showinfo("양식 확정",
                                            f"확정 양식 생성: {os.path.basename(form)}\n"
                                            f"항목 {len(records)}개.")
                self._run_busy("조사 양식 확정 중…", w2, d2)

            def cm_excel():
                draft = os.path.join(run_dir, f"양식초안_{recipe}_{m}_{st}.xlsx")

                def w3():
                    formbuilder.build_initial_workbook(
                        pivot, draft, level=recipe,
                        source=f"commonality {recipe} / {m}")
                    return draft

                def d3(ok3, res3):
                    if not ok3:
                        messagebox.showerror("초안 생성 실패", str(res3))
                        return
                    opened = self._open_in_excel(draft)
                    self._cm_form_finalize_dialog(draft, recipe, opened)
                self._run_busy("조사 양식 초안 생성 중…", w3, d3)

            self._form_param_editor(pivot, recipe, kind, scale_map, run_dir, run_dir,
                                    st, m, base_keys=base_keys, base_name=base,
                                    title_prefix=title,
                                    on_confirm=cm_confirm, on_excel=cm_excel)
        self._run_busy("조사 양식 파싱 중…", work, done)

    def _cm_form_finalize_dialog(self, draft, recipe, opened):
        win = tk.Toplevel(self)
        win.title("조사 양식 편집 완료")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        msg = (f"수정본 생성:\n{draft}\n\n"
               + ("실제 Excel로 열었습니다. " if opened else
                  "Excel을 자동으로 열지 못했습니다. 위 파일을 직접 여세요.\n")
               + "'사용'·'최종 Parameter'를 편집·저장한 뒤 '편집 완료'를 누르세요.")
        tk.Label(win, text=msg, bg=self.p["bg"], fg=self.p["text"], font=self.fonts["sub"],
                 justify="left", wraplength=560).pack(padx=16, pady=(14, 10))
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(bt, text="다시 열기", relief="flat", bd=0, bg=self.p["surface"],
                  padx=12, pady=6, cursor="hand2",
                  command=lambda: self._open_in_excel(draft)).pack(side="left")
        tk.Button(bt, text="편집 완료 → 양식 확정", relief="flat", bd=0, bg=self.p["ok"],
                  fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=lambda: self._cm_form_finalize(draft, recipe, win)).pack(
                  side="right")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"], padx=12,
                  pady=6, cursor="hand2", command=win.destroy).pack(side="right", padx=6)

    def _cm_form_finalize(self, draft, recipe, win):
        m, st = self._cm["machine"], self._cm["st"]
        form = workdirs.commonality_form_path(self._cm["run_dir"], recipe, m, st)

        def work():
            return formbuilder.build_final_from_initial(
                draft, form, user=self.user, level=recipe,
                source=f"commonality {recipe}", scales=self._cm.get("scales"))

        def done(ok, res):
            if not ok:
                self._err("E125", "양식 확정 실패", res, parent=win)
                return
            win.destroy()
            self._cm["form_path"] = form
            after = self._cm.pop("_after_form", None)
            if after:                              # 다중: 자동 값 조사 → 다음 레시피
                after()
            else:
                self._render()
                messagebox.showinfo("양식 확정",
                                    f"확정 양식 생성: {os.path.basename(form)}\n"
                                    f"항목 {res['kept']}개(제외 {res['dropped']}개).")
        self._run_busy("조사 양식 확정 중…", work, done)

    def _cm_collate(self, then=None, announce=True):
        recipe = self._cm["recipe"]
        form = self._cm["form_path"]
        m, st = self._cm["machine"], self._cm["st"]
        pivot, labels = self._cm.get("pivot"), self._cm.get("labels")
        result = workdirs.commonality_result_path(self._cm["run_dir"], recipe, m, st)

        fail_labels = self._cm.get("fail_labels") or []

        def cl(_lot, mag):
            return coefstore.lookup(self.coef_rows, m, mag)   # commonality 는 호기 고정

        def work():
            res = cm.collate_lots(recipe, form, pivot, labels, coef_lookup=cl)
            cm.write_lot_result(result, recipe, m, res, labels, fail_labels)
            return res

        def done(ok, res):
            if not ok:
                self._err("E126", "Lot 값 조사 실패", res)
                return
            self._cm["result_path"] = result
            self._render()
            if announce:
                messagebox.showinfo(
                    "값 조사 완료",
                    f"호기 결과 저장: {os.path.basename(result)}\n"
                    f"매칭 {res.matched_rows}행, 채운 셀 {res.filled_cells}개.\n"
                    + (f"불일치 {len(res.mismatches)}건." if res.mismatches else ""))
            if then:                               # 다중: 다음 레시피로
                then()
        self._run_busy("Lot별 값 조사 중…", work, done)

    def _cm_compare(self):
        results = workdirs.list_commonality_results(self._cm_root())
        if not results:
            messagebox.showinfo("취합·비교", "저장된 호기 결과가 없습니다. 먼저 값 조사를 하세요.")
            return
        picked = filedialog.askopenfilenames(
            title="취합·비교할 호기 결과 파일 선택(여러 개)",
            initialdir=workdirs.commonality_root(self._cm_root()),
            filetypes=[("Excel", "*.xlsx")])
        files = list(picked) if picked else results
        st = workdirs.stamp()
        out = workdirs.commonality_compare_path(self._cm_root(), st)

        def work():
            comp = cm.build_comparison(files)
            cm.write_comparison(out, comp, changed_only=False)
            return comp

        def done(ok, res):
            if not ok:
                self._err("E127", "호기 취합·비교 실패", res)
                return
            messagebox.showinfo("취합·비교 완료",
                                f"비교 파일 저장: {os.path.basename(out)}\n"
                                f"행 {len(res['rows'])}개, 변경 파라미터 "
                                f"{len(res['changed_params'])}개.")
            self._cm_open_viewer(res, out)
        self._run_busy("호기 취합·비교 중…", work, done)

    def _cm_open_viewer(self, comparison, out_path):
        """변경/이상치 뷰어 — tksheet 격자(과반수 이탈 셀 색칠 + 변경열만 필터)."""
        win = tk.Toplevel(self)
        win.title("Commonality 뷰어 — 변경/이상치")
        win.configure(bg=self.p["bg"])
        win.geometry("1000x620")
        bar = tk.Frame(win, bg=self.p["head_bg"])
        bar.pack(fill="x")
        only_var = tk.BooleanVar(value=True)
        holder = tk.Frame(win, bg=self.p["bg"])
        holder.pack(fill="both", expand=True)

        def render():
            for w in holder.winfo_children():
                w.destroy()
            changed_only = only_var.get()
            params = (comparison["changed_params"] if changed_only
                      else comparison["columns"][2:])
            columns = list(comparison["columns"][:2]) + list(params)  # ['S/M','호기',…]
            rows = comparison["rows"]
            data = [[engine._s(r.get(c)) for c in columns] for r in rows]
            s = Sheet(holder, theme="light blue", headers=columns, data=data,
                      show_x_scrollbar=True, show_y_scrollbar=True,
                      font=(self.p["family"], 10, "normal"),
                      header_font=(self.p["family"], 10, "bold"))
            s.enable_bindings("single_select", "drag_select", "arrowkeys", "copy",
                              "column_width_resize", "row_select", "column_select")
            # 헤더/셀 자동 줄바꿈(긴 파라미터 이름이 잘리지 않게)
            s.set_options(show_vertical_grid=True, show_horizontal_grid=True,
                          header_wrap="w", table_wrap="w")
            # 파라미터 열은 좁은 고정폭 → 헤더가 여러 줄로 줄바꿈되어 다 보인다.
            for i, c in enumerate(columns):
                try:
                    s.column_width(column=i, width=(70 if i < 2 else 96))
                except Exception:  # noqa: BLE001
                    pass
            # fail=Y S/M 행: 식별칸(S/M·호기) 노란색
            for ri in comparison.get("fail_rows") or set():
                if ri < len(rows):
                    for cix in (0, 1):
                        try:
                            s.highlight_cells(row=ri, column=cix,
                                              bg=f"#{cm.FAIL_FILL}", fg="#5A4A00")
                        except Exception:  # noqa: BLE001
                            pass
            # 과반수 이탈 셀 색칠
            col_idx = {c: i for i, c in enumerate(columns)}
            for (ri, pl) in comparison["outliers"]:
                if pl in col_idx and ri < len(rows):
                    try:
                        s.highlight_cells(row=ri, column=col_idx[pl],
                                          bg=f"#{cm.MISMATCH_FILL}", fg="#7A4E00")
                    except Exception:  # noqa: BLE001
                        pass
            # 헤더 줄바꿈이 보이도록 헤더 높이를 넉넉히(버전별 API 방어적 시도)
            for setter in (
                lambda: s.set_options(default_header_height=("pixels", 64)),
                lambda: s.set_options(default_header_height=64),
                lambda: s.set_header_height(height=64),
            ):
                try:
                    setter()
                    break
                except Exception:  # noqa: BLE001
                    continue
            try:
                s.redraw()
            except Exception:  # noqa: BLE001
                pass
            s.pack(fill="both", expand=True)

        tk.Label(bar, text="  변경/이상치 뷰어 — 노란 셀 = 과반수와 다른 값",
                 bg=self.p["head_bg"], fg=self.p["text"],
                 font=self.fonts["bold"]).pack(side="left", padx=8, pady=6)
        tk.Checkbutton(bar, text="변경된 파라미터만 보기", variable=only_var,
                       bg=self.p["head_bg"], fg=self.p["text"], selectcolor=self.p["bg"],
                       activebackground=self.p["head_bg"], font=self.fonts["sub"],
                       command=render).pack(side="left", padx=8)
        tk.Button(bar, text="비교 엑셀 열기", relief="flat", bd=0, bg=self.p["surface"],
                  padx=10, pady=4, cursor="hand2",
                  command=lambda: self._open_in_excel(out_path)).pack(side="right", padx=8)

        # 파라미터별 이탈 요약
        summ = tk.Frame(win, bg=self.p["bg"])
        summ.pack(fill="x")
        n_changed = len(comparison["changed_params"])
        tk.Label(summ, text=f"  변경 파라미터 {n_changed}개 · 이탈 셀 "
                            f"{len(comparison['outliers'])}개",
                 bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left", padx=8, pady=4)
        render()

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
        # 여러 PC 가 동시에 취합하면 장비에 중복 접속하고 취합 파일도 경합한다.
        if not self._acquire_global(locking.GLOBAL_COLLATE, "파라미터 값 업데이트"):
            return
        chosen = self._pick_levels(recipes)          # 레시피 선택 알림창
        if not chosen:
            self._release_global(locking.GLOBAL_COLLATE)
            return
        self._start_value_update(chosen)

    def _start_value_update(self, chosen):
        """레시피(chosen)가 정해진 상태에서 장비/로컬 수집 → 취합 흐름 시작."""
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

        def cancel():                    # 창을 그냥 닫으면 전역 잠금을 반납해야 한다
            self._release_global(locking.GLOBAL_COLLATE)
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", cancel)

        def from_equip():
            win.destroy()
            # 임시 수집본은 로컬에만(OneDrive 동기화 폭주 방지)
            staging = localdirs.new_temp_run(self.local_dir, "수집")
            self._collect_dialog(
                staging,
                lambda sources: self._parse_sources_busy(
                    sources, lambda rows, machines: self._update_collate_flow(chosen, rows),
                    default_level=dlevel, scales=scales),
                level_hint=dlevel, levels=chosen)

        def from_local():
            win.destroy()
            # req6: 폴더 직접 선택 대신 호기 선택 → 지정 로컬 폴더에서 자동 로드
            self._local_pick_sources(
                lambda sources: self._parse_sources_busy(
                    sources, lambda rows, machines: self._update_collate_flow(chosen, rows),
                    default_level=dlevel, scales=scales),
                level_hint=dlevel)
        tk.Button(bt, text="🖥 장비 IP에서 수집", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=16, pady=8, cursor="hand2",
                  command=from_equip).pack(side="left")
        tk.Button(bt, text="📁 로컬(호기 선택)에서", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=16, pady=8, cursor="hand2",
                  command=from_local).pack(side="left", padx=8)

    def _update_collate_flow(self, chosen, pivot_rows):
        machines_all = self._all_machines()
        prev = workdirs.latest_collate(self.save_dir)

        def cl(ho, mag):
            return coefstore.lookup(self.coef_rows, ho, mag)   # 호기별 계수

        def work():
            return collate.build_collation(self.save_dir, chosen, pivot_rows,
                                           machines_all, prev_collate_path=prev,
                                           coef_lookup=cl)

        def done(ok, res):
            if not ok:
                self._release_global(locking.GLOBAL_COLLATE)
                self._err("E128", "취합 실패", res)
                return
            self._update_write_results(res, machines_all)
        self._run_busy("취합 중…", work, done)

    def _update_write_results(self, results, machines_all):
        made = {}
        notes = []
        carried = []
        for recipe, res in results.items():
            if res.missing_form:
                notes.append(f"· {recipe}: 양식 없음(건너뜀)")
                continue
            if getattr(res, "carried", False):
                made[recipe] = res           # 직전 취합본에서 그대로 유지(누적)
                carried.append(recipe)
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
            self._release_global(locking.GLOBAL_COLLATE)
            messagebox.showinfo("값 업데이트",
                                "취합된 레시피가 없습니다.\n" + "\n".join(notes))
            return
        dest = workdirs.collate_path(self.save_dir, workdirs.stamp())
        collate.write_collation(dest, made, machines_all)
        self._release_global(locking.GLOBAL_COLLATE)   # 취합 완료 — 잠금 반납
        self._load_latest_collate()
        self.view = "param"
        self._sync_tab_style()
        self.navigate(screen="s0")
        summary = "\n".join(f"· {r}: 매칭 {made[r].matched_rows}행 / 값 {made[r].filled_cells}칸"
                            for r in made if r not in carried)
        if carried:
            summary += ("\n" if summary else "") + \
                f"· (유지) {', '.join(carried)}: 직전 취합본 값 그대로"
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
                self._err("E129", "이력 비교 실패", res)
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
    #  내보내기 — 레시피·호기·항목 선택(값 수정 가능) → Excel 저장
    # ====================================================================
    def _export_dialog(self):
        if not self.save_dir:
            messagebox.showinfo("내보내기", "먼저 저장 폴더를 지정하세요.")
            return
        latest = workdirs.latest_collate(self.save_dir)
        if not latest:
            messagebox.showinfo("내보내기", "내보낼 '파라미터 값 취합'이 아직 없습니다.\n"
                                "'파라미터 값 업데이트'로 먼저 취합을 만드세요.")
            return
        try:
            sheets, machines = collate.load_collation(latest)
        except Exception as e:  # noqa: BLE001
            self._err("E130", "내보내기 실패(취합 파일 읽기)", e)
            return
        if not sheets:
            messagebox.showinfo("내보내기", "취합 파일에 레시피 시트가 없습니다.")
            return
        # 1) 레시피 선택
        recs = self._pick_list_chooser(
            "export", "① 내보낼 레시피 선택(여러 개 가능)", list(sheets.keys()), True)
        if not recs:
            return
        # 2) 호기 선택
        if not machines:
            messagebox.showinfo("내보내기", "취합에 호기 열이 없습니다.")
            return
        mac = self._pick_list_chooser(
            "export", "② 내보낼 장비 호기 선택(여러 개 가능)", machines, True)
        if not mac:
            return
        # 3) 항목 선택 + 값 수정 창
        self._export_editor(latest, {r: sheets[r] for r in recs}, mac)

    def _export_editor(self, latest, sheets, machines):
        """③ zone/alg/parameter 선택(포함 토글) + 값 수정(더블클릭) → ④ 엑셀 내보내기.
        수정한 값은 **내보내는 파일에만** 적용되고 원본 취합/양식은 건드리지 않는다."""
        win = tk.Toplevel(self)
        win.title("내보내기 — 항목 선택 및 값 수정")
        win.geometry("1120x680")
        win.configure(bg=self.p["bg"])
        tk.Label(win, text="내보낼 항목을 고르고(포함 열 클릭), 값은 더블클릭해 수정하세요. "
                          "수정한 값은 내보내는 파일에만 적용됩니다.",
                 bg=self.p["bg"], fg=self.p["text"], font=self.fonts["bold"]).pack(
                 anchor="w", padx=12, pady=(10, 4))

        cols = ["inc", "레시피", "Zone", "Alg", "Parameter"] + list(machines)
        # 버튼 바를 먼저 하단에 고정(창이 짧아도 항상 보이게), 목록은 남은 공간을 채움
        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(side="bottom", fill="x", padx=12, pady=(2, 10))
        wrap = tk.Frame(win, bg=self.p["bg"])
        wrap.pack(side="top", fill="both", expand=True, padx=12, pady=4)
        tv = ttk.Treeview(wrap, columns=cols, show="headings", height=24)
        heads = {"inc": "포함", "레시피": "레시피", "Zone": "Zone", "Alg": "Alg",
                 "Parameter": "Parameter"}
        widths = {"inc": 46, "레시피": 80, "Zone": 130, "Alg": 130, "Parameter": 260}
        for c in cols:
            tv.heading(c, text=heads.get(c, c))
            tv.column(c, width=widths.get(c, 90),
                      anchor=("center" if c == "inc" else "w"))
        self._exp_map = {}
        for recipe, rows in sheets.items():
            for rd in rows:
                vals = ["✓", recipe, engine._s(rd.get("Zone")),
                        engine._s(rd.get("Alg")), engine._s(rd.get("Parameter"))]
                vals += [engine._s(rd.get(m)) for m in machines]
                it = tv.insert("", "end", values=vals)
                self._exp_map[it] = (recipe, dict(rd))
        vs = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        tv.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        def toggle(item):
            tv.set(item, "inc", "" if tv.set(item, "inc") == "✓" else "✓")

        def on_click(e):
            if tv.identify_region(e.x, e.y) != "cell":
                return
            if tv.identify_column(e.x) != "#1":     # 포함 열만
                return
            item = tv.identify_row(e.y)
            if item:
                toggle(item)

        def on_double(e):
            if tv.identify_region(e.x, e.y) != "cell":
                return
            col = tv.identify_column(e.x)            # 예: '#7'
            item = tv.identify_row(e.y)
            if not item or not col:
                return
            cidx = int(col[1:]) - 1
            if cidx < 0 or cidx >= len(cols):
                return
            cname = cols[cidx]
            if cname not in machines:                # 호기 값만 수정 가능
                return
            box = tv.bbox(item, col)
            if not box:
                return
            x, y, w, h = box
            ent = tk.Entry(tv)
            ent.place(x=x, y=y, width=w, height=h)
            ent.insert(0, tv.set(item, cname))
            ent.focus_set()
            ent.select_range(0, "end")

            def commit(_=None):
                tv.set(item, cname, ent.get())
                ent.destroy()
            ent.bind("<Return>", commit)
            ent.bind("<FocusOut>", commit)
            ent.bind("<Escape>", lambda _e: ent.destroy())

        def on_enter(_e=None):
            # 행 선택 후 Enter = 포함 토글 + 아래 행으로 이동(연속 조작 편하게)
            item = tv.focus() or (tv.selection()[0] if tv.selection() else "")
            if not item:
                kids = tv.get_children()
                item = kids[0] if kids else ""
            if not item:
                return "break"
            toggle(item)
            nxt = tv.next(item)
            if nxt:
                tv.selection_set(nxt)
                tv.focus(nxt)
                tv.see(nxt)
            return "break"

        tv.bind("<Button-1>", on_click, add="+")
        tv.bind("<Double-Button-1>", on_double)
        tv.bind("<Return>", on_enter)
        tv.bind("<KP_Enter>", on_enter)
        kids0 = tv.get_children()
        if kids0:                                # 첫 행 포커스 → 바로 Enter 조작 가능
            tv.selection_set(kids0[0])
            tv.focus(kids0[0])
        tv.focus_set()

        def set_all(v):
            for it in tv.get_children():
                tv.set(it, "inc", v)
        tk.Button(bt, text="전체 선택", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=12, pady=6, cursor="hand2",
                  command=lambda: set_all("✓")).pack(side="left")
        tk.Button(bt, text="전체 해제", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=12, pady=6, cursor="hand2",
                  command=lambda: set_all("")).pack(side="left", padx=6)

        def do_export():
            recipe_records = {}
            for it in tv.get_children():
                if tv.set(it, "inc") != "✓":
                    continue
                recipe, orig = self._exp_map[it]
                base = {f: orig.get(f) for f in engine.META_FIELDS}
                for m in machines:
                    base[m] = tv.set(it, m)
                recipe_records.setdefault(recipe, []).append(base)
            if not recipe_records:
                messagebox.showinfo("내보내기", "포함할 항목을 하나 이상 선택하세요.",
                                    parent=win)
                return
            dest = filedialog.asksaveasfilename(
                title="내보내기 엑셀 저장", defaultextension=".xlsx",
                initialfile=f"파라미터_내보내기_{workdirs.stamp()}.xlsx",
                filetypes=[("Excel", "*.xlsx")], parent=win)
            if not dest:
                return
            try:
                exporter.write_export(dest, recipe_records, list(machines),
                                      title="내보내기")
            except Exception as ex:  # noqa: BLE001
                self._err("E131", "내보내기 실패", ex, parent=win)
                return
            win.destroy()
            if messagebox.askyesno("내보내기 완료",
                                   f"{os.path.basename(dest)} 저장 완료.\n"
                                   "지금 Excel로 열까요?"):
                self._open_in_excel(dest)
        tk.Button(bt, text="📤 엑셀로 내보내기", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=do_export).pack(side="right")
        tk.Button(bt, text="닫기", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=14, pady=6, cursor="hand2",
                  command=win.destroy).pack(side="right", padx=6)

    # ====================================================================
    #  첫 실행 / 저장 폴더 / 참고자료·특이사항 로드 (3차 재설계)
    # ====================================================================
    def _startup(self):
        if self.save_dir and os.path.isdir(self.save_dir):
            # 매 실행 확인: 기존 폴더 유지 / 새 폴더 연결(하위 엑셀 다시 읽음).
            keep = messagebox.askyesno(
                "저장 폴더 확인",
                "기존 저장 폴더를 그대로 사용할까요?\n\n"
                f"현재 폴더:\n{self.save_dir}\n\n"
                "[예] 이 폴더 유지\n"
                "[아니오] 다른 폴더 연결(그 폴더의 엑셀들을 다시 읽습니다)")
            if not keep:
                self._choose_save_dir(first=False)   # 취소하면 기존 폴더 유지
        else:
            if not self._choose_save_dir(first=True):
                self._set_status("저장 폴더가 지정되지 않았습니다. ⋯파일에서 지정하세요.",
                                 warn=True)
                return
        self._setup_local_dir(first=not self._cfg.get("local_dir"))
        self._load_refdata()
        self._load_latest_collate()
        self._render()
        self.after(500, lambda: self._check_update_prompt(manual=False))

    # ====================================================================
    #  로컬 작업 폴더 — 임시파일·로그는 OneDrive 밖에 둔다
    # ====================================================================
    def _setup_local_dir(self, first=False) -> str:
        """로컬 작업 폴더 확보. 첫 실행이면 위치를 확인·변경할 기회를 준다.

        OneDrive 안에 임시파일을 만들면 동기화가 폭주해 보안 경고가 난다
        (실제 사고). 그래서 임시/로그는 반드시 동기화되지 않는 로컬에 둔다.
        """
        root = self._cfg.get("local_dir") or localdirs.default_root()
        if first:
            in_od = localdirs.is_under_onedrive(localdirs.program_root())
            warn = ("\n⚠ 프로그램이 OneDrive 폴더 안에 있어, 프로그램 옆에 만들면\n"
                    "   임시파일이 전원에게 동기화되어 보안 경고가 다시 발생합니다.\n"
                    "   그래서 안전한 위치를 기본값으로 제안합니다.\n"
                    if in_od else "")
            msg = ("작업 중 만들어지는 파일을 모아 둘 **로컬 폴더**입니다.\n\n"
                   f"  {root}\n\n"
                   "이 폴더 하나에 아래가 모두 들어갑니다:\n"
                   "  · Temp        수집 임시본(작업 끝나면 자동 삭제)\n"
                   "  · Logs        오류 로그\n"
                   "  · Cache       캐시\n"
                   "  · Commonality  Commonality 조사 결과\n\n"
                   "취합 엑셀·양식·변경보고서 등 **공유할 결과물은 저장 폴더**"
                   "(OneDrive)에 저장됩니다.\n"
                   + warn +
                   "\n이 위치를 사용할까요?  [아니오] 를 누르면 직접 고를 수 있습니다.")
            if not messagebox.askyesno("로컬 작업 폴더 설정", msg):
                picked = filedialog.askdirectory(title="로컬 작업 폴더 선택 "
                                                       "(OneDrive 밖 권장)")
                if picked:
                    root = os.path.join(picked, localdirs.APP_DIRNAME) \
                        if os.path.basename(picked) != localdirs.APP_DIRNAME else picked
        return self._apply_local_dir(root, warn_onedrive=True)

    def _apply_local_dir(self, root: str, warn_onedrive=False) -> str:
        """로컬 폴더를 확정·생성하고 config 에 저장. 실패하면 기본 위치로 되돌린다."""
        if warn_onedrive and localdirs.is_under_onedrive(root):
            if not messagebox.askyesno(
                    "OneDrive 안입니다",
                    f"고른 위치가 OneDrive 동기화 폴더 안으로 보입니다.\n\n{root}\n\n"
                    "여기에 임시파일을 만들면 전원에게 동기화되어 보안 경고가 다시 "
                    "발생할 수 있습니다.\n그래도 이 위치를 쓸까요?"):
                root = localdirs.default_root()
        try:
            root = localdirs.ensure(root)
        except Exception as e:  # noqa: BLE001
            self._logerr("E163", e)
            root = localdirs.ensure(localdirs.default_root())
        self.local_dir = root
        localdirs.set_root(root)   # errlog 등 다른 모듈도 같은 위치를 쓰게
        self._cfg["local_dir"] = root
        save_config(self._cfg)
        try:
            n = localdirs.cleanup_temp(root)        # 지난 회차 잔재 정리
            if n:
                self._write_log(f"임시 폴더 {n}개 정리: {root}")
        except Exception as e:  # noqa: BLE001
            self._logerr("E164", e)
        return root

    def _local_dir_dialog(self):
        """⋯파일 > 로컬 작업 폴더… — 위치 확인·변경·비우기."""
        root = getattr(self, "local_dir", None) or self._apply_local_dir(
            self._cfg.get("local_dir") or localdirs.default_root())
        win = tk.Toplevel(self)
        win.title("로컬 작업 폴더")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        tk.Label(win, text="로컬 작업 폴더", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(win, text="임시파일·로그는 여기에, 공유할 결과물은 저장 폴더에 "
                           "저장됩니다.\nOneDrive 안에 두면 동기화가 폭주해 보안 경고가 "
                           "발생합니다.",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=16)
        info = tk.Label(win, text="", bg=self.p["bg"], fg=self.p["text"],
                        font=self.fonts["base"], justify="left", anchor="w")
        info.pack(anchor="w", padx=16, pady=10)

        def refresh():
            warn = "  ⚠ OneDrive 안입니다" if localdirs.is_under_onedrive(
                self.local_dir) else ""
            info.config(text=f"위치: {self.local_dir}{warn}\n"
                             f"{localdirs.describe(self.local_dir)}")
        refresh()

        def change():
            picked = filedialog.askdirectory(title="로컬 작업 폴더 선택",
                                             parent=win)
            if picked:
                self._apply_local_dir(
                    os.path.join(picked, localdirs.APP_DIRNAME)
                    if os.path.basename(picked) != localdirs.APP_DIRNAME else picked,
                    warn_onedrive=True)
                refresh()

        def purge():
            if messagebox.askyesno("임시 폴더 비우기",
                                   "지금 작업 중이 아닌 임시 폴더를 모두 지웁니다.\n"
                                   "계속할까요?", parent=win):
                n = localdirs.cleanup_temp(self.local_dir, keep_hours=0)
                refresh()
                messagebox.showinfo("정리 완료", f"임시 폴더 {n}개를 지웠습니다.",
                                    parent=win)

        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=16, pady=12)
        tk.Button(bt, text="위치 변경…", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=14, pady=6, cursor="hand2",
                  command=change).pack(side="left")
        tk.Button(bt, text="임시 폴더 비우기", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=14, pady=6, cursor="hand2",
                  command=purge).pack(side="left", padx=6)
        tk.Button(bt, text="폴더 열기", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=14, pady=6, cursor="hand2",
                  command=lambda: self._open_path(self.local_dir)).pack(side="left")
        tk.Button(bt, text="닫기", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=win.destroy).pack(side="right")

    # ====================================================================
    #  자동 업데이트 — OneDrive 저장폴더만 사용(인터넷 미사용, 2026-08 확정 A안)
    # ====================================================================
    def _check_update_prompt(self, manual: bool):
        """저장폴더의 버전정보.json 을 확인해 새 버전이면 물어본다.

        manual=True(메뉴에서 직접 확인)면 '나중에' 기억을 무시하고 항상 확인하며,
        최신이어도 그 결과를 알려준다. manual=False(시작 시 자동)는 조용히 확인하고
        새 버전일 때만 말을 건다.
        """
        if not updater.is_frozen():
            if manual:
                messagebox.showinfo(
                    "업데이트 확인",
                    "소스로 실행 중입니다. 자동 업데이트는 배포된 실행파일(exe)"
                    "에서만 동작합니다.\nGitHub 에서 최신 코드를 받아 오세요.")
            return
        if not self.save_dir:
            if manual:
                messagebox.showinfo("업데이트 확인", "먼저 저장 폴더를 지정하세요.")
            return
        try:
            release = updater.read_manifest(self.save_dir)
        except Exception as e:  # noqa: BLE001
            self._logerr("E165", e)
            release = None
        if release is None:
            if manual:
                messagebox.showinfo("업데이트 확인",
                                    "게시된 버전 정보를 찾을 수 없습니다.")
            return
        if not updater.is_newer(release.version, __version__):
            if manual:
                messagebox.showinfo("업데이트 확인",
                                    f"이미 최신 버전입니다. (현재 {__version__})")
            return
        if not manual and self._cfg.get("update_skip_version") == release.version:
            return                             # 이 버전은 '나중에' 선택함 — 다시 안 물음
        if getattr(self, "_watch_busy", False):
            # 업데이트는 앱을 종료시키므로 수집 도중에 하면 그 회차가 통째로 날아간다.
            # 다음 시작(또는 수동 확인) 때 다시 묻는다.
            if manual:
                messagebox.showinfo(
                    "업데이트 확인",
                    f"새 버전 {release.version} 이 있지만 지금 자동 감시 수집이 "
                    "진행 중입니다.\n작업이 끝난 뒤 다시 시도해 주세요.")
            return
        note = f"\n\n변경 내용:\n{release.changelog}" if release.changelog else ""
        rename = ""
        try:
            cur_name = os.path.basename(updater.current_exe_path())
            if cur_name and cur_name != release.filename:
                # 파일명에 버전이 들어가므로 업데이트하면 이름이 바뀐다.
                # 바탕화면 바로가기를 쓰고 있으면 다시 만들어야 하므로 미리 알린다.
                rename = (f"\n\n실행 파일 이름이 바뀝니다:\n"
                          f"  {cur_name}\n  → {release.filename}\n"
                          "(바로가기를 쓰고 계시면 새로 만들어 주세요)")
        except Exception:  # noqa: BLE001
            rename = ""
        if not messagebox.askyesno(
                "새 버전 업데이트",
                f"새 버전 {release.version} 이 있습니다. (현재 {__version__})"
                f"{note}{rename}\n\n지금 업데이트할까요?"):
            self._cfg["update_skip_version"] = release.version
            save_config(self._cfg)
            return
        self._run_update(release)

    def _run_update(self, release: updater.ReleaseInfo):
        """새 exe 를 로컬로 받아 검증 후, 종료→교체→재실행을 예약하고 앱을 닫는다."""
        def work():
            local_exe = updater.download_to_local(self.save_dir, release,
                                                   self.local_dir)
            ok, reason = updater.verify_download(local_exe, release)
            if not ok:
                raise RuntimeError(reason)
            return local_exe

        def done(ok, res):
            if not ok:
                self._err("E166", "업데이트 실패", res)
                return
            local_exe = res
            current = updater.current_exe_path()
            backup = updater.backup_path_for(self.local_dir, current)
            # 파일명에 버전이 들어가므로 업데이트하면 로컬 exe 이름도 바뀐다.
            target = updater.local_target_path(current, release)
            try:
                script = updater.build_swap_script(self.local_dir, os.getpid(),
                                                   current, local_exe, backup,
                                                   target_exe=target)
            except Exception as e:  # noqa: BLE001
                self._err("E167", "업데이트 준비 실패", e)
                return
            if os.path.basename(target) != os.path.basename(current):
                self._set_status(f"업데이트 중… {os.path.basename(target)} 으로 "
                                 "다시 시작됩니다")
            else:
                self._set_status(f"업데이트 중… 잠시 후 {release.version} 으로 "
                                 "다시 시작됩니다")
            try:
                if os.name == "nt":
                    import subprocess
                    DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0)
                    NEWGROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    subprocess.Popen(["cmd", "/c", script], close_fds=True,
                                     creationflags=DETACHED | NEWGROUP)
                else:
                    self._err("E170", "업데이트 미지원", "Windows 전용 기능입니다.")
                    return
            except Exception as e:  # noqa: BLE001
                self._err("E168", "업데이트 실행 실패", e)
                return
            self.after(300, self._shutdown)   # 교체 스크립트가 내 종료를 기다림

        self._run_busy(f"업데이트 확인 중… ({release.version})", work, done)

    def _publish_update_dialog(self):
        """(개발자용) 새로 빌드한 exe 를 저장폴더에 게시 — 버전·변경내용 입력."""
        if not self._need_save_dir():
            return
        win = tk.Toplevel(self)
        win.title("새 버전 배포")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        tk.Label(win, text="새 버전 배포", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(win, text="build_exe.bat 으로 새로 만든 exe 를 저장 폴더에 게시합니다.\n"
                           "게시하면 다른 사용자 프로그램이 다음 시작 시 자동으로 "
                           "안내받습니다.",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=16, pady=(0, 8))

        cur = updater.read_manifest(self.save_dir)
        if cur:
            tk.Label(win, text=f"현재 게시된 버전: {cur.version}"
                               f"{'  · ' + cur.published_by if cur.published_by else ''}",
                     bg=self.p["bg"], fg=self.p["muted"],
                     font=self.fonts["sub"]).pack(anchor="w", padx=16)
        # 게시 폴더는 저장폴더 '옆'(형제)에 만들어진다 — 어디에 올라가는지 명시
        tk.Label(win, text=f"게시 폴더: {updater.resolve_program_dir(self.save_dir)}",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left", wraplength=520).pack(anchor="w", padx=16)

        body = tk.Frame(win, bg=self.p["bg"])
        body.pack(fill="x", padx=16, pady=10)
        tk.Label(body, text="exe 파일:", bg=self.p["bg"],
                 fg=self.p["text"]).grid(row=0, column=0, sticky="w", pady=3)
        exe_var = tk.StringVar()
        tk.Entry(body, textvariable=exe_var, width=42, relief="solid",
                 bd=1).grid(row=0, column=1, sticky="we", padx=6)

        def browse():
            p = filedialog.askopenfilename(
                title="게시할 exe 선택(dist\\PI_Param_Manager.exe)",
                filetypes=[("실행 파일", "*.exe"), ("모든 파일", "*.*")], parent=win)
            if p:
                exe_var.set(p)
        tk.Button(body, text="찾아보기…", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], cursor="hand2",
                  command=browse).grid(row=0, column=2, padx=2)

        tk.Label(body, text="버전 번호:", bg=self.p["bg"],
                 fg=self.p["text"]).grid(row=1, column=0, sticky="w", pady=3)
        ver_var = tk.StringVar(value=__version__)
        tk.Entry(body, textvariable=ver_var, width=20, relief="solid",
                 bd=1).grid(row=1, column=1, sticky="w", padx=6)
        # 버전이 파일명에 들어가므로 결과 파일명을 실시간으로 보여준다
        name_lbl = tk.Label(body, text="", bg=self.p["bg"], fg=self.p["primary"],
                            font=self.fonts["sub"], anchor="w")
        name_lbl.grid(row=1, column=2, sticky="w")

        def upd_name(*_a):
            v = ver_var.get().strip()
            name_lbl.config(
                text=(f"→ {updater.exe_filename(v)}" if updater.parse_version(v) != (0,)
                      else "(예: 3.1.0)"),
                fg=(self.p["primary"] if updater.parse_version(v) != (0,)
                    else self.p["muted"]))
        ver_var.trace_add("write", upd_name)
        upd_name()

        tk.Label(body, text="변경 내용:", bg=self.p["bg"],
                 fg=self.p["text"]).grid(row=2, column=0, sticky="nw", pady=3)
        note = tk.Text(body, width=42, height=4, relief="solid", bd=1,
                       font=self.fonts["base"])
        note.grid(row=2, column=1, columnspan=2, sticky="we", padx=6)
        body.columnconfigure(1, weight=1)

        def do_publish():
            exe_path = exe_var.get().strip()
            version = ver_var.get().strip()
            changelog = note.get("1.0", "end").strip()
            if not exe_path or not os.path.isfile(exe_path):
                messagebox.showwarning("확인", "exe 파일을 선택하세요.", parent=win)
                return
            if updater.parse_version(version) == (0,):
                messagebox.showwarning("확인", "버전 번호를 알아볼 수 없습니다.",
                                       parent=win)
                return
            if cur and not updater.is_newer(version, cur.version) and \
                    not messagebox.askyesno(
                        "버전 확인",
                        f"입력한 버전({version})이 현재 게시된 버전({cur.version})"
                        "보다 높지 않습니다.\n그래도 게시할까요?", parent=win):
                return

            def work():
                return updater.publish(self.save_dir, exe_path, version, changelog,
                                       user=self.user)

            def done(ok, res):
                if not ok:
                    self._err("E169", "게시 실패", res, parent=win)
                    return
                win.destroy()
                messagebox.showinfo(
                    "게시 완료",
                    f"버전 {res.version} 을(를) 게시했습니다.\n"
                    f"크기: {res.size / (1024*1024):.1f} MB\n\n"
                    "OneDrive 동기화가 끝나면 다른 사용자들이 다음 프로그램 시작 시 "
                    "자동으로 안내받습니다.")
            self._run_busy("게시 중…", work, done, parent=win)

        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=16, pady=12)
        tk.Button(bt, text="게시", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=18, pady=6, cursor="hand2",
                  command=do_publish).pack(side="right")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=14, pady=6, cursor="hand2",
                  command=win.destroy).pack(side="right", padx=6)

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
        self._view_colors = None            # 폴더 바뀌면 셀 색상 다시 로드
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
            self._err("E132", "복사 실패", e)
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
            self._err("E140", "변환계수 로드 실패", e)
            self.coef_rows = []
        try:
            self.ip_rows = refdata.load_ip(ipp)
        except Exception as e:  # noqa: BLE001
            self._err("E141", "장비 IP 로드 실패", e)
            self.ip_rows = []
        try:
            self.ref_grid, self.ref_colors = refdata.load_reference(rp)
        except Exception as e:  # noqa: BLE001
            self._err("E142", "참고자료 로드 실패", e)
            self.ref_grid, self.ref_colors = [], {}
        try:
            self.special_rows, self.special_colors = refdata.load_special(sp)
        except Exception as e:  # noqa: BLE001
            self._err("E143", "특이사항 로드 실패", e)
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

    # ====================================================================
    #  자동 감시 — 주기 수집·취합 → 변경 시 알림 + 보고서
    # ====================================================================
    def _watch_runner(self):
        """감시를 실제로 돌리고 있는 사람(전역 잠금 보유자). 없으면 None."""
        if not self.save_dir:
            return None
        try:
            st = locking.global_status(self.save_dir, locking.GLOBAL_WATCHER,
                                       self.user)
            return st.info if st.status in ("mine", "other", "self") else None
        except Exception:  # noqa: BLE001
            return None

    def _sync_watch_btn(self):
        """감시 버튼 표시 — 설정은 **공유**이므로 누가 켰든 모두에게 ON 으로 보인다.
        (실제 수집은 잠금을 쥔 1대에서만 돌지만, 상태·알림은 다 같이 본다.)"""
        btn = getattr(self, "_watch_btn", None)
        if btn is None or not self.save_dir:
            return
        try:
            s, _ = watcher.load_settings(self.save_dir)
            on = bool(s.enabled)
            label = "🔔 자동 감시 ON" if on else "🔔 자동 감시"
            if on and not self._watch_owned:
                info = self._watch_runner()
                if info is not None:
                    label = f"🔔 자동 감시 ON ({info.user})"
            btn.config(text=label,
                       bg=(self.p["primary"] if on else self.p["surface"]),
                       fg=("#ffffff" if on else self.p["text"]))
        except Exception:  # noqa: BLE001
            pass

    # ── 다른 사람이 돌린 회차도 모두에게 알린다 ─────────────────────────
    def _watch_seen_key(self) -> str:
        return "watch_seen:" + (self.save_dir or "")

    def _watch_mark_seen(self, last_run: str):
        """이 회차는 확인했다고 기록(사용자 PC 로컬 config — 중복 알림 방지)."""
        try:
            self._cfg[self._watch_seen_key()] = last_run
            save_config(self._cfg)
        except Exception:  # noqa: BLE001
            pass

    def _watch_poll_shared(self):
        """공유 설정을 읽어 **다른 PC 가 돌린 회차**를 감지하고 알린다.

        감시는 1대에서만 돌지만 결과는 모두가 봐야 하므로, 각자 앱이 마지막으로
        본 회차 시각을 로컬에 기억해 두고 새 회차가 생기면 한 번만 알린다.
        """
        if not self.save_dir:
            return
        s, state = watcher.load_settings(self.save_dir)
        if not state.last_run:
            return
        seen = self._cfg.get(self._watch_seen_key(), "")
        if state.last_run == seen:
            return                       # 이미 본 회차
        self._watch_mark_seen(state.last_run)
        if not seen:
            return                       # 첫 실행(기준선) — 알리지 않음
        note = state.last_result or ""
        changed = bool(note) and note not in ("변경 없음", "실행 조건 아님(건너뜀)") \
            and not note.startswith("실패")
        self._sync_watch_btn()
        if changed:
            self._watch_alert(note, watcher.latest_report(self.save_dir),
                              by_other=not self._watch_owned)

    def _watch_dialog(self):
        """자동 감시 설정창 — 주기·시간대·접속 방식·대상 레시피."""
        if not self._need_save_dir():
            return
        s, state = watcher.load_settings(self.save_dir)
        win = tk.Toplevel(self)
        win.title("자동 감시 설정")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.geometry("700x760")
        # 내용이 길어 화면(특히 저해상도·노트북)에서 잘리므로 **전체를 스크롤**시킨다.
        # 버튼줄(bt)은 스크롤 밖 하단에 고정해 항상 보이게 한다.
        outer = tk.Frame(win, bg=self.p["bg"])
        outer.pack(side="top", fill="both", expand=True)
        wcv = tk.Canvas(outer, bg=self.p["bg"], highlightthickness=0)
        wsb = ttk.Scrollbar(outer, orient="vertical", command=wcv.yview)
        body_wrap = tk.Frame(wcv, bg=self.p["bg"])
        wcv.create_window((0, 0), window=body_wrap, anchor="nw", tags="i")
        wcv.configure(yscrollcommand=wsb.set)
        wcv.pack(side="left", fill="both", expand=True)
        wsb.pack(side="right", fill="y")
        body_wrap.bind("<Configure>",
                       lambda e: wcv.configure(scrollregion=wcv.bbox("all")))
        # 가로 폭은 캔버스에 맞춰 늘린다(내부 위젯이 잘리지 않게)
        wcv.bind("<Configure>", lambda e: wcv.itemconfigure("i", width=e.width))
        self._wheelify(wcv)
        page = body_wrap                 # 설정 내용은 전부 여기(스크롤 영역)에 붙인다

        tk.Label(page, text="자동 감시", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(page, text="정해진 주기마다 값을 수집·취합하고, 직전과 달라진 파라미터가 "
                           "있으면\n알림과 변경 보고서를 남깁니다.\n"
                           "창을 닫아도(X) 감시는 백그라운드에서 계속되며, 작업표시줄 "
                           "알림영역(숨겨진 아이콘)의\nPara 아이콘을 누르면 다시 열 수 "
                           "있습니다. 완전히 끄려면 그 아이콘을 우클릭 → '자동 감시 종료'.",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=16)

        body = tk.Frame(page, bg=self.p["bg"])
        body.pack(fill="x", padx=16, pady=10)
        on_var = tk.BooleanVar(value=s.enabled)
        tk.Checkbutton(body, text="자동 감시 사용", variable=on_var, bg=self.p["bg"],
                       fg=self.p["text"], selectcolor=self.p["surface"],
                       font=self.fonts["bold"]).grid(row=0, column=0, sticky="w",
                                                     columnspan=3, pady=(0, 6))
        tk.Label(body, text="주기(시간):", bg=self.p["bg"],
                 fg=self.p["text"]).grid(row=1, column=0, sticky="w")
        iv = tk.StringVar(value=str(int(s.interval_hours)))
        ttk.Combobox(body, textvariable=iv, width=6, state="readonly",
                     values=("1", "2", "3", "6", "12", "24")).grid(row=1, column=1,
                                                                   sticky="w", padx=6)
        tk.Label(body, text="(파라미터는 자주 바뀌지 않아 6시간을 권장)",
                 bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).grid(row=1, column=2, sticky="w")

        tk.Label(body, text="실행 시간대:", bg=self.p["bg"],
                 fg=self.p["text"]).grid(row=2, column=0, sticky="w", pady=(8, 0))
        wrow = tk.Frame(body, bg=self.p["bg"])
        wrow.grid(row=2, column=1, columnspan=2, sticky="w", padx=6, pady=(8, 0))
        ws_var = tk.StringVar(value=str(s.window_start))
        we_var = tk.StringVar(value=str(s.window_end))
        hours = tuple(str(i) for i in range(24))
        ttk.Combobox(wrow, textvariable=ws_var, width=4, state="readonly",
                     values=hours).pack(side="left")
        tk.Label(wrow, text=" 시 ~ ", bg=self.p["bg"], fg=self.p["text"]).pack(side="left")
        ttk.Combobox(wrow, textvariable=we_var, width=4, state="readonly",
                     values=hours).pack(side="left")
        tk.Label(wrow, text="  시 (같게 두면 제한 없음 · 가동 피크 회피용)",
                 bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left")

        # ── 감시 대상 선택: ① 장비 ② 레시피 (둘 다 고른 것만 수집·비교) ──
        all_machines = self._all_machines()
        all_recipes = workdirs.list_recipes(self.save_dir)
        selected_machines = self._pick_list(
            page, " ① 감시할 장비 선택 ", all_machines,
            # 저장된 선택이 없으면(최초) 전체 선택, 이후에는 저장분 복원
            chosen=(s.machines if s.machines else all_machines),
            unit="대", note="선택한 장비만 수집·비교합니다.",
            sub_of=lambda m: refdata.ip_for(self.ip_rows, m) or "(IP 없음)",
            sub_warn=lambda m: not refdata.ip_for(self.ip_rows, m),
            empty_msg="장비 IP 목록이 비어 있습니다. '장비 IP' 탭에서 호기·IP를 "
                      "먼저 등록하세요.", height=140)
        selected_recipes = self._pick_list(
            page, " ② 감시할 레시피 선택 ", all_recipes,
            chosen=(s.recipes if s.recipes else all_recipes),
            unit="개", note="선택한 레시피의 양식만 취합·비교합니다.",
            sub_of=lambda r: self._recipe_form_note(r),
            sub_warn=lambda r: not workdirs.latest_form(self.save_dir, r),
            empty_msg="양식이 없습니다. '양식 만들기'로 레시피 양식을 먼저 만드세요.",
            height=110)

        # 감시 폴더 직접 지정(권장) — 지정하면 폴더 이름을 유추하지 않는다.
        paths_state = {"v": dict(s.recipe_paths or {})}
        prow = tk.Frame(page, bg=self.p["bg"])
        prow.pack(fill="x", padx=16, pady=(0, 6))
        plabel = tk.Label(prow, text="", bg=self.p["bg"], fg=self.p["muted"],
                          font=self.fonts["sub"], anchor="w", justify="left")

        def upd_plabel():
            rp = paths_state["v"] or {}
            n_m = len(rp)
            n_p = sum(len(v) for v in rp.values())
            if n_p:
                plabel.config(text=f"지정됨 — {n_m}개 호기 / 경로 {n_p}건",
                              fg=self.p["primary"])
            else:
                plabel.config(text="미지정 — 폴더 이름으로 자동 매칭합니다"
                                   "(실패 시 그 장비는 건너뜀).", fg=self.p["muted"])

        def pick_paths():
            picked = selected_recipes() or all_recipes
            if not picked:
                messagebox.showinfo("감시 Job 폴더 지정",
                                    "먼저 감시할 레시피를 선택하세요.", parent=win)
                return
            picked_m = selected_machines() or all_machines
            if not picked_m:
                messagebox.showinfo("감시 Job 폴더 지정",
                                    "먼저 감시할 장비를 선택하세요.", parent=win)
                return
            got = self._watch_paths_dialog(picked_m, picked, paths_state["v"],
                                           parent=win)
            if got is not None:
                paths_state["v"] = got
                upd_plabel()
        tk.Button(prow, text="📁 감시 Job 폴더 지정…", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["primary"],
                  font=self.fonts["bold"], padx=12, pady=4, cursor="hand2",
                  command=pick_paths).pack(side="left")
        plabel.pack(side="left", padx=8)
        upd_plabel()

        def selected_targets() -> list:
            """선택된 장비의 (호기, IP) — IP 없는 호기는 제외."""
            out = []
            for m in selected_machines():
                ip = refdata.ip_for(self.ip_rows, m)
                if ip:
                    out.append((m, ip))
            return out

        # ── 접속 방식 — 기본/권장은 net use 없이(기존 연결) ──
        box = tk.LabelFrame(page, text=" ③ 장비 접속 방식 ", bg=self.p["bg"],
                            fg=self.p["text"], font=self.fonts["bold"])
        box.pack(fill="x", padx=16, pady=(4, 8))
        conn = tk.StringVar(value=s.conn_mode)
        tk.Radiobutton(box, text="기존 연결 사용 (net use 없이) — 권장",
                       variable=conn, value=watcher.CONN_SESSION, bg=self.p["bg"],
                       fg=self.p["text"], selectcolor=self.p["surface"],
                       font=self.fonts["bold"]).pack(anchor="w", padx=10, pady=(6, 0))
        tk.Label(box, text="비밀번호를 저장하지 않습니다. 무인 실행할 장비를 탐색기에서\n"
                           "미리 모두 연결(\\\\장비IP\\c$ 로 로그인)해 두세요.",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=32)
        tk.Radiobutton(box, text="net use 로 접속 (비밀번호 필요)",
                       variable=conn, value=watcher.CONN_NETUSE, bg=self.p["bg"],
                       fg=self.p["text"],
                       selectcolor=self.p["surface"]).pack(anchor="w", padx=10)
        tk.Label(box, text="비밀번호는 프로그램이 켜져 있는 동안 메모리에만 유지되고\n"
                           "디스크에 저장하지 않습니다(앱 종료 시 사라짐).",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=32, pady=(0, 6))

        info = tk.Label(page, text=self._watch_status_text(s, state), bg=self.p["bg"],
                        fg=self.p["muted"], font=self.fonts["sub"], justify="left")
        info.pack(anchor="w", padx=16)

        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(side="bottom", fill="x", padx=16, pady=12)

        def check_conn(parent=None, saved_targets=None):
            """연결 점검 — 선택한 장비만 대상. 장비 응답이 없으면 1대당 수십 초씩
            걸리므로 반드시 백그라운드에서 돌린다(GUI 스레드면 '응답 없음')."""
            parent = parent if parent is not None else win
            targets = list(saved_targets) if saved_targets is not None \
                else selected_targets()
            if not targets:
                messagebox.showinfo(
                    "연결 점검",
                    "감시할 장비를 먼저 선택하세요.\n"
                    "(선택한 장비 중 IP가 등록된 장비만 점검합니다.)", parent=parent)
                return

            def work():
                return watcher.check_connections(targets)

            def done(ok, res):
                if not ok:
                    self._err("E158", "연결 점검 실패", res)
                    return
                if res["missing"]:
                    messagebox.showwarning("연결 점검",
                                           watcher.connection_guide(res["missing"]))
                else:
                    messagebox.showinfo("연결 점검",
                                        f"대상 장비 {len(res['ok'])}대 모두 연결되어 "
                                        "있습니다.")
            self._run_busy(f"연결 점검 중… (장비 {len(targets)}대)", work, done,
                           parent=parent)

        def apply_():
            picked = selected_machines()
            picked_r = selected_recipes()
            if on_var.get() and not picked:
                messagebox.showwarning(
                    "장비 미선택",
                    "감시할 장비를 1대 이상 선택하세요.\n"
                    "선택한 장비만 수집·비교합니다.", parent=win)
                return
            if on_var.get() and not picked_r:
                messagebox.showwarning(
                    "레시피 미선택",
                    "감시할 레시피를 1개 이상 선택하세요.\n"
                    "선택한 레시피의 양식만 취합·비교합니다.", parent=win)
                return
            no_ip = [m for m in picked if not refdata.ip_for(self.ip_rows, m)]
            if no_ip and not messagebox.askyesno(
                    "IP 없는 장비",
                    "다음 장비는 IP가 등록되어 있지 않아 감시에서 제외됩니다:\n\n"
                    f"  {', '.join(no_ip)}\n\n계속할까요?", parent=win):
                return
            no_form = [r for r in picked_r
                       if not workdirs.latest_form(self.save_dir, r)]
            if no_form and not messagebox.askyesno(
                    "양식 없는 레시피",
                    "다음 레시피는 양식이 없어 취합에서 건너뜁니다:\n\n"
                    f"  {', '.join(no_form)}\n\n계속할까요?", parent=win):
                return
            s.enabled = bool(on_var.get())
            s.machines = picked                       # ← 감시 대상 장비 저장
            s.recipes = picked_r                      # ← 감시 대상 레시피 저장
            s.recipe_paths = dict(paths_state["v"])   # ← 지정 폴더 저장
            try:
                s.interval_hours = float(iv.get())
            except ValueError:
                s.interval_hours = watcher.DEFAULT_INTERVAL_HOURS
            try:
                s.window_start, s.window_end = int(ws_var.get()), int(we_var.get())
            except ValueError:
                s.window_start = s.window_end = 0
            s.conn_mode = conn.get()
            if s.enabled and not self._watch_acquire():
                return                      # 다른 PC 가 감시 중 — 켜지 않는다
            if not s.enabled:
                self._watch_release()
            watcher.save_settings(self.save_dir, s, state)
            watcher.append_log(self.save_dir,
                               f"설정 변경 — 사용={s.enabled} 장비={len(picked)}대 "
                               f"레시피={len(picked_r)}개 주기={s.interval_hours}h "
                               f"접속={s.conn_mode}")
            self._sync_watch_btn()
            targets = selected_targets()              # 창 닫기 전에 확보
            win.destroy()
            if s.enabled:
                # win 은 이미 닫혔으므로 부모는 본창, 대상은 방금 저장한 선택
                check_conn(parent=self, saved_targets=targets)

        def run_now():
            """즉시 확인 — 주기를 기다리지 않고 지금 1회 수집·비교."""
            picked, picked_r = selected_machines(), selected_recipes()
            if not picked or not picked_r:
                messagebox.showwarning(
                    "즉시 확인",
                    "감시할 장비와 레시피를 먼저 선택하세요.", parent=win)
                return
            if self._watch_busy:
                messagebox.showinfo("즉시 확인",
                                    "이미 감시 회차가 실행 중입니다.", parent=win)
                return
            # 화면에서 고른 값을 그대로 1회 실행에 반영(저장은 '저장' 버튼에서)
            s.machines, s.recipes = picked, picked_r
            s.recipe_paths = dict(paths_state["v"])
            s.conn_mode = conn.get()
            if not self._watch_acquire():
                return                      # 다른 PC 가 감시 중
            win.destroy()
            self._watch_run_once(s)

        tk.Button(bt, text="▶ 즉시 확인", relief="flat", bd=0, bg=self.p["primary_dk"],
                  fg="#ffffff", padx=14, pady=6, cursor="hand2",
                  command=run_now).pack(side="left")
        tk.Button(bt, text="연결 점검", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=14, pady=6, cursor="hand2",
                  command=check_conn).pack(side="left", padx=6)
        tk.Button(bt, text="변경 보고서…", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=14, pady=6, cursor="hand2",
                  command=lambda: (win.destroy(),
                                   self._watch_reports_window())).pack(side="left", padx=6)
        tk.Button(bt, text="저장", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=18, pady=6, cursor="hand2",
                  command=apply_).pack(side="right")

    def _browse_equipment_recipe(self, recipe: str, machine: str | None = None,
                                 parent=None) -> str | None:
        r"""**장비를 직접 훑어** Recipe 폴더를 고르게 한다(양식 만들기와 같은 방식).

        Job 폴더 → Setup/Recipes → Recipe 폴더 순으로 **목록에서 선택**한다.
        경로를 직접 입력할 필요가 없고, 실제로 존재하는 폴더만 보여주므로 오타가 없다.
        machine 을 주면 그 호기를 훑고, 없으면 호기부터 고른다.
        반환: 그 호기의 `\Job\` 기준 상대경로 또는 None(취소).
        """
        from pathlib import Path as _P
        parent = parent or self
        self._chooser_parent = parent

        # ① 어느 장비를 훑을지 — 호기가 지정돼 있으면 그 장비
        if machine:
            m = machine
            ip = refdata.ip_for(self.ip_rows, m)
            if not ip:
                messagebox.showwarning("IP 없음",
                                       f"{m} 의 IP가 '장비 IP' 탭에 없습니다.",
                                       parent=parent)
                return None
        else:
            cand = [(x, refdata.ip_for(self.ip_rows, x))
                    for x in self._all_machines()]
            cand = [(x, ip) for x, ip in cand if ip]
            if not cand:
                messagebox.showwarning("장비 없음",
                                       "'장비 IP' 탭에 호기·IP를 먼저 등록하세요.",
                                       parent=parent)
                return None
            labels = [f"{x}   ({ip})" for x, ip in cand]
            pick = self._pick_list_chooser(
                "machine", f"[{recipe}] 폴더를 확인할 장비 선택", labels, False)
            if not pick:
                return None
            m, ip = cand[labels.index(pick[0])]

        job_root = _P(rf"\\{ip}\c$\Job")
        try:
            if not job_root.is_dir():
                messagebox.showwarning(
                    "접근 불가",
                    f"{m}({ip})의 Job 폴더에 접근할 수 없습니다.\n{job_root}\n\n"
                    r"탐색기에서 \\장비IP\c$ 로 먼저 연결(로그인)한 뒤 다시 시도하세요.",
                    parent=parent)
                return None

            # ② Job 폴더 선택
            jobs = collector.list_dirs(job_root)
            if not jobs:
                messagebox.showwarning("폴더 없음", f"Job 폴더가 비어 있습니다.\n{job_root}",
                                       parent=parent)
                return None
            jn = [d.name for d in jobs]
            pick = self._pick_list_chooser("job", f"[{recipe}] Job 폴더 선택", jn, False,
                note=f"{m} · {job_root}\n"
                     "Job 폴더만 고르면 그 아래 레시피는 자동으로 읽습니다.")
            if not pick:
                return None
            job = jobs[jn.index(pick[0])]

            # ③ Job 폴더만 고르면 끝 — 하위 Setup/Recipes/레시피는 자동으로 찾는다.
            found = collector.find_setup_candidates(job)
            n_recipes = sum(len(collector.list_dirs(r)) for _s, r in found)
            if not found or not n_recipes:
                if not messagebox.askyesno(
                        "Recipes 확인",
                        f"'{job.name}' 아래에서 Recipes 폴더(또는 레시피)를 찾지 "
                        "못했습니다.\n그래도 이 Job 폴더로 지정할까요?", parent=parent):
                    return None
            rel = watcher.job_relative(str(job))
            if not rel:
                messagebox.showwarning("경로 확인",
                                       f"Job 기준 상대경로를 만들지 못했습니다.\n{job}",
                                       parent=parent)
                return None
            if n_recipes:
                names = []
                for _s, r in found:
                    names += [d.name for d in collector.list_dirs(r)]
                messagebox.showinfo(
                    "Job 폴더 지정됨",
                    f"[{m}] {job.name}\n\n이 Job 아래 레시피 {n_recipes}개를 자동으로 "
                    "읽습니다:\n  " + ", ".join(names[:12])
                    + (" …" if len(names) > 12 else ""), parent=parent)
            return rel
        except Exception as e:  # noqa: BLE001
            self._err("E162", "장비 폴더 탐색 실패", e)
            return None

    def _watch_paths_dialog(self, machines, recipes, current: dict,
                            parent=None) -> dict | None:
        r"""**감시 폴더 지정 — 호기별**. 반환 {호기: {레시피: 상대경로}} 또는 None.

        장비마다 Job 폴더 구조가 다르므로(양식 만들기와 동일) 호기 하나를 고르고
        그 호기의 레시피별 폴더를 '장비에서 선택…'으로 정한다.
        같은 구조를 쓰는 장비가 많으면 '다른 호기에 복사'로 한 번에 채울 수 있다.
        """
        parent = parent or self
        data = {m: dict(current.get(m) or {}) for m in machines}
        win = tk.Toplevel(parent)
        win.title("감시 Job 폴더 지정 (호기별)")
        win.configure(bg=self.p["bg"])
        win.transient(parent)
        win.grab_set()
        win.geometry("860x560")
        tk.Label(win, text="호기별 감시 Job 폴더", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(win,
                 text="장비마다 Job 폴더 구조가 달라 **호기별로** 지정합니다.\n"
                      "왼쪽에서 호기를 고르고 '장비에서 선택…'으로 **Job 폴더만** "
                      "고르세요.\n"
                      "그 아래 Setup/Recipes/레시피 폴더는 프로그램이 자동으로 "
                      "찾아 전부 읽습니다.",
                 bg=self.p["bg"], fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=16, pady=(0, 8))

        body = tk.Frame(win, bg=self.p["bg"])
        body.pack(fill="both", expand=True, padx=16)

        # ── 왼쪽: 호기 목록(지정 현황 표시) ──
        left = tk.Frame(body, bg=self.p["bg"])
        left.pack(side="left", fill="y")
        tk.Label(left, text="호기", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["bold"]).pack(anchor="w")
        lb = tk.Listbox(left, font=self.fonts["base"], width=26, height=18,
                        activestyle="none", exportselection=False)
        lb.pack(side="left", fill="y")
        lsb = ttk.Scrollbar(left, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")

        def status_of(m):
            done = sum(1 for r in recipes if data.get(m, {}).get(r))
            return "✔ 전부" if done == len(recipes) else \
                (f"{done}/{len(recipes)}" if done else "미지정")

        def refresh_list(keep=None):
            sel = keep if keep is not None else (lb.curselection() or [0])[0]
            lb.delete(0, "end")
            for m in machines:
                lb.insert("end", f"{m}   [{status_of(m)}]")
            if machines:
                lb.selection_clear(0, "end")
                lb.selection_set(min(sel, len(machines) - 1))
            update_right()

        # ── 오른쪽: 선택한 호기의 레시피별 경로 ──
        right = tk.Frame(body, bg=self.p["bg"])
        right.pack(side="left", fill="both", expand=True, padx=(14, 0))
        head = tk.Label(right, text="", bg=self.p["bg"], fg=self.p["text"],
                        font=self.fonts["bold"], anchor="w")
        head.pack(anchor="w")
        rows_frame = tk.Frame(right, bg=self.p["bg"])
        rows_frame.pack(fill="both", expand=True, pady=6)
        vars_by_recipe = {}

        def cur_machine():
            sel = lb.curselection()
            return machines[sel[0]] if sel else (machines[0] if machines else None)

        def update_right():
            m = cur_machine()
            head.config(text=f"{m} 의 레시피별 감시 Job 폴더" if m else "")
            for w in rows_frame.winfo_children():
                w.destroy()
            vars_by_recipe.clear()
            if not m:
                return
            for i, r in enumerate(recipes):
                tk.Label(rows_frame, text=r, bg=self.p["bg"], fg=self.p["text"],
                         font=self.fonts["bold"], width=12,
                         anchor="w").grid(row=i, column=0, sticky="w", pady=3)
                var = tk.StringVar(value=data.get(m, {}).get(r, ""))
                tk.Entry(rows_frame, textvariable=var, width=44, relief="solid",
                         bd=1).grid(row=i, column=1, sticky="we", padx=6)

                def browse(rr=r, vv=var, mm=m):
                    rel = self._browse_equipment_recipe(rr, machine=mm, parent=win)
                    if rel:
                        vv.set(rel)
                        data.setdefault(mm, {})[rr] = rel
                        refresh_list()
                tk.Button(rows_frame, text="장비에서 선택…", relief="flat", bd=0,
                          bg=self.p["primary"], fg="#ffffff", cursor="hand2",
                          command=browse).grid(row=i, column=2, padx=2)
                vars_by_recipe[r] = var
            rows_frame.columnconfigure(1, weight=1)

        def commit_current():
            """오른쪽 입력칸 내용을 data 에 반영(직접 수정분 포함)."""
            m = cur_machine()
            if not m:
                return
            for r, v in vars_by_recipe.items():
                val = v.get().strip().strip("\\/")
                if val:
                    data.setdefault(m, {})[r] = val
                else:
                    data.get(m, {}).pop(r, None)

        def on_select(_e=None):
            update_right()
        lb.bind("<<ListboxSelect>>", lambda e: (commit_current(), on_select()))

        def copy_to_others():
            m = cur_machine()
            commit_current()
            if not m or not data.get(m):
                messagebox.showinfo("복사", "먼저 이 호기의 폴더를 지정하세요.",
                                    parent=win)
                return
            if not messagebox.askyesno(
                    "다른 호기에 복사",
                    f"{m} 의 경로를 다른 모든 호기에 복사할까요?\n"
                    "폴더 구조가 같은 장비끼리만 쓰세요. 복사 후 호기별로 "
                    "수정할 수 있습니다.", parent=win):
                return
            for other in machines:
                if other != m:
                    data[other] = dict(data[m])
            refresh_list()

        out = {}

        def ok():
            commit_current()
            for m, d in data.items():
                clean = {r: v for r, v in d.items() if v}
                if clean:
                    out[m] = clean
            win.destroy()

        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=16, pady=12)
        tk.Button(bt, text="이 호기 경로를 다른 호기에 복사", relief="flat", bd=0,
                  bg=self.p["surface"], fg=self.p["text"], padx=12, pady=6,
                  cursor="hand2", command=copy_to_others).pack(side="left")
        tk.Label(bt, text="  비워 두면 그 레시피는 기존 방식(이름 자동 매칭)",
                 bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(side="left")
        tk.Button(bt, text="확인", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=18, pady=6, cursor="hand2",
                  command=ok).pack(side="right")
        tk.Button(bt, text="취소", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=14, pady=6, cursor="hand2",
                  command=win.destroy).pack(side="right", padx=6)

        refresh_list(0)
        win.wait_window()
        return out or None

    def _cm_root(self) -> str:
        """Commonality 산출물 루트 — 로컬 작업 폴더 아래 `Commonality/`.
        조사 결과는 개인 작업물이라 공유하지 않으며, Lot 안전복사본은 파일
        수가 많아 OneDrive 에 두면 동기화 사고가 난다."""
        return localdirs.commonality_dir(
            localdirs.ensure(getattr(self, 'local_dir', None)
                             or localdirs.active_root()))

    def _recipe_form_note(self, recipe: str) -> str:
        """레시피 옆에 보여줄 양식 상태(최신 양식 유무)."""
        f = workdirs.latest_form(self.save_dir, recipe)
        return os.path.basename(f) if f else "(양식 없음)"

    def _pick_list(self, parent, title, items, chosen=None, unit="개", note="",
                   sub_of=None, sub_warn=None, empty_msg="", height=140):
        """체크박스 다중 선택 목록(스크롤 + 전체선택/해제 + 카운터).

        감시 설정의 장비/레시피 선택이 같은 모양이라 한 곳으로 모았다.
        반환: selected() — 선택된 항목 목록을 돌려주는 함수.
        """
        items = list(items or [])
        chosen_set = set(chosen if chosen is not None else items)
        box = tk.LabelFrame(parent, text=title, bg=self.p["bg"], fg=self.p["text"],
                            font=self.fonts["bold"])
        box.pack(fill="both", expand=True, padx=16, pady=(4, 6))
        pairs: list = []
        if not items:
            tk.Label(box, text=empty_msg, bg=self.p["bg"], fg=self.p["danger"],
                     font=self.fonts["sub"], justify="left").pack(anchor="w",
                                                                 padx=10, pady=8)
            return lambda: []

        head = tk.Frame(box, bg=self.p["bg"])
        head.pack(fill="x", padx=8, pady=(4, 0))
        if note:
            tk.Label(head, text=note, bg=self.p["bg"], fg=self.p["muted"],
                     font=self.fonts["sub"]).pack(side="left")
        cnt = tk.Label(head, text="", bg=self.p["bg"], fg=self.p["primary"],
                       font=self.fonts["bold"])
        cnt.pack(side="right", padx=6)

        def upd():
            n = sum(1 for v, _ in pairs if v.get())
            cnt.config(text=f"{n} / {len(pairs)}{unit} 선택")

        def set_all(val):
            for v, _ in pairs:
                v.set(val)
            upd()
        tk.Button(head, text="전체 해제", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], font=self.fonts["sub"], cursor="hand2",
                  command=lambda: set_all(False)).pack(side="right", padx=2)
        tk.Button(head, text="전체 선택", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], font=self.fonts["sub"], cursor="hand2",
                  command=lambda: set_all(True)).pack(side="right", padx=2)

        cv = tk.Canvas(box, bg=self.p["bg"], highlightthickness=0, height=height)
        vsb = ttk.Scrollbar(box, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=self.p["bg"])
        cv.create_window((0, 0), window=inner, anchor="nw")
        cv.configure(yscrollcommand=vsb.set)
        cv.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=6)
        vsb.pack(side="right", fill="y", pady=6)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        self._wheelify(cv)
        for i, it in enumerate(items):
            v = tk.BooleanVar(value=(it in chosen_set))
            tk.Checkbutton(inner, text=str(it), variable=v, bg=self.p["bg"],
                           fg=self.p["text"], selectcolor=self.p["surface"],
                           font=self.fonts["bold"], width=14, anchor="w",
                           command=upd).grid(row=i // 2, column=(i % 2) * 2,
                                             sticky="w", pady=1)
            if sub_of is not None:
                try:
                    sub = sub_of(it)
                    warn = bool(sub_warn(it)) if sub_warn else False
                except Exception:  # noqa: BLE001
                    sub, warn = "", False
                tk.Label(inner, text=sub, bg=self.p["bg"],
                         fg=(self.p["danger"] if warn else self.p["muted"]),
                         font=self.fonts["sub"], width=22, anchor="w").grid(
                    row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=(0, 12))
            pairs.append((v, it))
        upd()
        return lambda: [it for v, it in pairs if v.get()]

    def _watch_status_text(self, s, state) -> str:
        tgt = (f"· 감시 장비: {len(s.machines)}대 ({', '.join(s.machines[:6])}"
               f"{' 외' if len(s.machines) > 6 else ''})"
               if s.machines else "· 감시 장비: 아직 선택하지 않았습니다.")
        tgt += ("\n· 감시 레시피: " + ", ".join(s.recipes)) if s.recipes \
            else "\n· 감시 레시피: 아직 선택하지 않았습니다."
        if not state.last_run:
            return tgt + "\n· 아직 실행 이력이 없습니다."
        nxt = watcher.next_run_at(s, state)
        return (tgt
                + f"\n· 마지막 실행: {state.last_run} ({state.last_result or '-'})"
                + f"\n· 다음 예정: {nxt.strftime('%Y-%m-%d %H:%M')}"
                + (f"  · 연속 실패 {state.fail_count}회(재시도 지연 중)"
                   if state.fail_count else ""))

    def _watch_acquire(self, silent: bool = False) -> bool:
        """감시 전역 잠금 — 여러 PC 가 동시에 감시하면 장비에 배수로 접속한다.

        silent=True 는 앱 재시작 후 자동 재개용. 다른 PC 가 이미 감시 중이면
        조용히 실패한다(매 tick 마다 경고창이 뜨면 안 되므로).
        """
        if self._watch_owned:
            return True
        if silent:
            if not self.save_dir:
                return False
            try:
                st = locking.acquire_global(self.save_dir, locking.GLOBAL_WATCHER,
                                            self.user)
            except Exception as e:  # noqa: BLE001
                self._logerr("E153", e)
                return False
            if st.editable:
                self._locks[locking.global_lock_path(
                    self.save_dir, locking.GLOBAL_WATCHER)] = "자동 감시"
                self._watch_owned = True
            return self._watch_owned
        ok = self._acquire_global(locking.GLOBAL_WATCHER, "자동 감시")
        self._watch_owned = ok
        return ok

    def _watch_release(self):
        if self._watch_owned:
            self._release_global(locking.GLOBAL_WATCHER)
            self._watch_owned = False

    def _watch_tick(self):
        """감시 주기 확인(가벼움). 실행 조건이면 1회차를 백그라운드로 돌린다."""
        try:
            if self.save_dir and not self._watch_busy:
                s, state = watcher.load_settings(self.save_dir)
                # 앱을 다시 켰을 때: 설정이 켜져 있으면 감시 잠금을 조용히 다시 잡는다
                # (다른 PC 가 감시 중이면 조용히 실패 — 경고창으로 괴롭히지 않음).
                if s.enabled and not self._watch_owned:
                    if self._watch_acquire(silent=True):
                        self._sync_watch_btn()
                if s.enabled and self._watch_owned and \
                        watcher.should_run(datetime.now(), s, state):
                    self._watch_run_cycle(s, state)
                # 감시를 안 돌리는 PC 도 결과는 같이 본다(새 회차 감지 → 알림)
                if not self._watch_busy:
                    self._watch_poll_shared()
        except Exception as e:  # noqa: BLE001
            self._logerr("E155", e)
        self.after(60_000, self._watch_tick)

    def _watch_cycle_work(self, s):
        """감시 1회차의 순수 작업(수집→취합→비교)을 만들어 돌려준다.

        주기 실행과 '즉시 확인'이 **같은 로직**을 쓰도록 한 곳에 모았다.
        반환: 인자 없는 work() — 백그라운드 스레드에서 호출할 것(GUI 접근 없음).
        """
        # 감시 대상 = 설정에서 고른 장비·레시피(비어 있으면 전체 — 구 설정 하위호환).
        avail_m = set(self._all_machines())
        avail_r = set(workdirs.list_recipes(self.save_dir))
        machines = [m for m in (s.machines or self._all_machines()) if m in avail_m]
        recipes = [r for r in (s.recipes or workdirs.list_recipes(self.save_dir))
                   if r in avail_r]
        prev = workdirs.latest_collate(self.save_dir)
        watcher.append_log(self.save_dir,
                           f"회차 시작 — 장비 {len(machines)}대 "
                           f"({', '.join(machines) if machines else '없음'}) "
                           f"· 레시피 {len(recipes)}개 "
                           f"({', '.join(recipes) if recipes else '없음'})")

        # 취합 파일의 **열은 항상 전체 호기**여야 한다. 선택한 장비만 열로 쓰면
        # 나머지 호기의 기존 값이 통째로 빠져 '삭제됨'으로 오탐된다.
        # 선택은 '어느 장비에서 새로 읽을지'만 정하고, 나머지 호기 값은 직전
        # 취합본에서 그대로 이어받는다.
        all_machines = self._all_machines()
        plan = watcher.plan_from_dict(s.plan)

        def cl(ho, mag):
            return coefstore.lookup(self.coef_rows, ho, mag)

        def work():
            if not recipes:
                raise RuntimeError("양식이 없습니다('양식 만들기' 먼저)")
            if not machines:
                raise RuntimeError("감시 대상 장비가 없습니다(설정에서 선택)")
            # 폴더를 지정한 레시피는 계획이 필요 없다. 지정 안 한 레시피만 계획 필요.
            need_plan = [r for r in recipes
                         if any(not watcher.path_for(s.recipe_paths, m, r)
                                for m in machines)]
            if need_plan and plan is None:
                raise RuntimeError(
                    "다음 레시피의 감시 폴더가 지정되지 않았습니다: "
                    + ", ".join(need_plan)
                    + "\n\n감시 설정의 '📁 감시 폴더 지정…'에서 장비의 Recipe 폴더를 "
                      "골라 주세요(한 번만 지정하면 모든 장비에 적용됩니다).\n"
                      "또는 '파라미터 값 업데이트'를 한 번 수동 실행하면 그때 고른 "
                      "폴더를 무인 회차가 재사용합니다.")
            pivot, skipped = self._watch_collect(machines, s, plan, recipes)
            out = collate.build_collation(self.save_dir, recipes, pivot,
                                          all_machines, prev_collate_path=prev,
                                          coef_lookup=cl)
            made = {r: v for r, v in out.items() if not v.missing_form}
            if not made:
                raise RuntimeError("취합된 레시피가 없습니다")
            st = workdirs.stamp()
            dest = workdirs.collate_path(self.save_dir, st)
            collate.write_collation(dest, made, all_machines)
            res = watcher.compare_and_report(self.save_dir, prev, dest, st)
            res.skipped = skipped
            return res

        return work

    def _watch_finish(self, ok, res, s, state):
        """회차 종료 처리(성공/실패 공통) — 상태 기록·화면 갱신. 반환: 성공 여부."""
        self._watch_busy = False
        if not ok:
            watcher.record_run(self.save_dir, s, state, ok=False, note=str(res))
            watcher.append_log(self.save_dir, f"회차 실패 — {res}")
            self._sync_watch_btn()
            return False
        watcher.record_run(self.save_dir, s, state, ok=True, note=res.summary())
        self._load_latest_collate()
        self._sync_watch_btn()
        return True

    def _watch_run_cycle(self, s, state):
        """주기 회차 — 무인이라 **모달을 띄우지 않고** 변경이 있을 때만 알린다."""
        self._watch_busy = True
        work = self._watch_cycle_work(s)

        def done(ok, res):
            if not self._watch_finish(ok, res, s, state):
                self._logerr("E156", res)
                return
            if res.has_change:
                self._watch_notify(res)
            elif not s.notify_on_change_only:
                self._set_status("자동 감시: 변경 없음")

        self._run_bg(work, done)

    def _watch_run_once(self, s):
        """'즉시 확인' — 주기를 기다리지 않고 지금 1회.

        사람이 눌러서 실행하므로 주기 회차와 달리 **진행 모달을 띄우고, 변경이
        없어도 결과를 알려준다**(눌렀는데 아무 반응이 없으면 안 되므로).
        """
        if self._watch_busy:
            return
        self._watch_busy = True
        _, state = watcher.load_settings(self.save_dir)
        work = self._watch_cycle_work(s)

        def done(ok, res):
            if not self._watch_finish(ok, res, s, state):
                self._err("E156", "즉시 확인 실패", res)
                return
            skipped = getattr(res, "skipped", None) or []
            extra = ("\n\n건너뛴 장비: " + ", ".join(skipped)) if skipped else ""
            if res.has_change:
                self._watch_notify(res)
                return
            messagebox.showinfo(
                "즉시 확인 완료",
                f"수집·비교를 마쳤습니다.\n\n결과: {res.summary()}" + extra)

        self._run_busy("자동 감시 1회 실행 중… (수집→취합→비교)", work, done)

    def _collect_fixed_dir(self, ip, machine, recipe, rel, staging_root,
                           use_netuse, diag):
        r"""**지정된 폴더**에서 설정파일을 읽어온다(이름 유추 없음).

        `\\{IP}\c$\Job\{rel}` 을 그대로 읽는다. 지정 폴더가 Recipe 폴더면 그것을,
        상위 폴더면 그 아래 Recipe 폴더들을 대상으로 한다.
        원본은 읽기 전용(collector.copy_planned 의 안전장치를 그대로 사용).
        반환: staging 폴더 경로(수집 실패면 None).
        """
        from pathlib import Path as _P
        src = _P(watcher.machine_recipe_dir(ip, rel))
        connected = False
        try:
            if use_netuse and collector.is_windows():
                collector.connect_admin_share(ip, "amkor", "")
                connected = True
            if not src.is_dir():
                diag.append(f"{machine}/{recipe}: 지정 폴더 없음({src})")
                return None
            # 지정 폴더가 어느 단계든(Job / Setup / Recipes / Recipe) 알아서 내려간다.
            #   Job 폴더를 지정하는 게 기본 — 그 아래 Setup/Recipes/레시피는 자동 스캔.
            def is_recipe_dir(d):
                return any((d / f).is_file() for f in collector.FIXED_FILES) or \
                    (d / "Zones").is_dir()

            if is_recipe_dir(src):
                targets = [src]                      # Recipe 폴더를 직접 지정한 경우
            else:
                targets = []
                for _setup, recipes_root in collector.find_setup_candidates(src):
                    targets += [d for d in collector.list_dirs(recipes_root)
                                if is_recipe_dir(d)]
                if not targets:                      # Recipes 폴더를 직접 지정한 경우
                    targets = [d for d in collector.list_dirs(src) if is_recipe_dir(d)]
            if not targets:
                diag.append(f"{machine}/{recipe}: 지정 폴더 아래에 레시피(설정파일) "
                            f"없음({src})")
                return None
            planned = collector.plan_files(targets)
            if not planned:
                diag.append(f"{machine}/{recipe}: 복사할 설정파일 없음")
                return None
            # 찢어진 읽기 방지 — 복사 전 서명을 기록해 두고 복사 뒤 비교
            sigs = [(p, watcher.file_sig(p)) for p, _, _ in planned]
            dest = os.path.join(staging_root, _sanitize_name(machine),
                                _sanitize_name(recipe))
            collector.copy_planned(planned, _P(dest),
                                   header_lines=[f"IP={ip}", f"Machine={machine}",
                                                 f"Recipe={recipe}", f"Src={src}"])
            unstable = watcher.unstable_files(sigs)
            if unstable:
                # 장비가 쓰는 중이던 파일이 섞였다 — 이번 회차는 이 레시피를 버린다
                diag.append(f"{machine}/{recipe}: 수집 중 변경된 파일 "
                            f"{len(unstable)}개 → 이번 회차 제외")
                watcher.append_log(self.save_dir,
                                   f"불안정 파일 제외 {machine}/{recipe}: "
                                   + ", ".join(os.path.basename(u)
                                               for u in unstable[:5]))
                return None
            return dest
        except Exception as e:  # noqa: BLE001
            diag.append(f"{machine}/{recipe}: {e}")
            return None
        finally:
            if connected:
                collector.disconnect_admin_share(ip)

    def _watch_collect(self, machines, s, plan, recipes):
        """무인 수집 — 선택한 장비에서 순차로 설정파일을 읽어 파싱 피벗을 만든다.

        · 사람이 없으므로 **선택창을 띄우지 않는다**. 저장된 plan 으로 자동 매칭되지
          않는 장비는 조용히 건너뛰고 로그에 남긴다(추측해서 엉뚱한 폴더를 읽지 않음).
        · 장비 1대씩 순차 접속(동시 접속 금지), 원본은 읽기 전용.
        · 복사 전후 (mtime,size) 가 흔들린 파일은 그 회차에서 제외 — 장비가 쓰는
          중이던 반쪽 파일로 '거짓 변경'을 만들지 않기 위해.
        반환: (pivot_rows, 건너뛴 장비 목록)
        """
        # 임시 수집본은 로컬에만(OneDrive 동기화 폭주 방지) — 회차가 끝나면 지운다
        staging_root = localdirs.new_temp_run(self.local_dir, "감시")
        use_netuse = (s.conn_mode == watcher.CONN_NETUSE)
        sources, skipped = [], []

        def no_chooser(*_a, **_kw):
            return None            # 애매하면 선택하지 않음 → UserCancelled 로 건너뜀

        diag: list = []          # 매칭 실패 사유(로그용)

        def auto_match(job_dirs, levels):
            """무인 Job 폴더 매칭 — 레벨별로 **되는 것만** 골라 준다.

            collector 의 plan 재사용 분기는 레벨 하나라도 실패하면 전체를 포기하므로,
            여기서 레벨 단위로 다시 시도한다:
              1) 저장된 계획의 Job 폴더명(정확→느슨 매칭)
              2) 없으면 레시피(레벨) 이름으로 Job 폴더 찾기 — 후보가 **정확히 1개**일 때만
            둘 다 안 되면 그 레벨은 제외(추측하지 않음). 전부 실패면 빈 매핑 →
            UserCancelled → 그 장비만 건너뛴다.
            """
            out, names_seen = {}, [d.name for d in job_dirs]
            for lvl in levels:
                names = (getattr(plan, "recipe_map", None) or {}).get(lvl) or []
                sel = []
                if names:
                    sel, _missing = collector.match_recipes_by_names(job_dirs, names)
                if not sel:
                    cands = [d for d in job_dirs
                             if collector.contains_keyword(d.name, lvl)]
                    if len(cands) == 1:
                        sel = cands
                    elif cands:
                        diag.append(f"{lvl}: 후보 {len(cands)}개로 애매"
                                    f"({', '.join(c.name for c in cands[:4])})")
                    else:
                        diag.append(f"{lvl}: 해당 Job 폴더 없음")
                if sel:
                    out[lvl] = sel
            if not out and names_seen:
                diag.append("장비 Job 폴더: " + ", ".join(names_seen[:8]))
            return out

        # 지정된 폴더가 있는 레시피는 이름 유추 없이 그 경로만 읽는다(권장 경로).
        # **지정은 호기별**이므로 장비 루프 안에서 조회한다.
        any_fixed = False

        for m in machines:
            ip = refdata.ip_for(self.ip_rows, m)
            if not ip:
                skipped.append(f"{m}(IP 없음)")
                continue
            try:
                def staging_for(_kw, aoi=m):
                    d = os.path.join(staging_root, _sanitize_name(aoi))
                    os.makedirs(d, exist_ok=True)
                    return d
                # ① 이 호기에 폴더를 지정한 레시피 — 지정 경로에서 바로 읽는다.
                fixed = {r: watcher.path_for(s.recipe_paths, m, r) for r in recipes}
                fixed = {r: v for r, v in fixed.items() if v}
                if fixed:
                    any_fixed = True
                for lvl, rel in fixed.items():
                    got = self._collect_fixed_dir(ip, m, lvl, rel, staging_root,
                                                  use_netuse, diag)
                    if got:
                        sources.append((got, lvl, m))
                guess_recipes = [r for r in recipes if r not in fixed]
                if not guess_recipes:
                    continue                  # 이 호기는 전부 지정됨 — 탐색 불필요
                # target_levels/match_recipes 를 줘야 **저장된 recipe_map 재사용
                # 경로**를 탄다(수동 수집이 남긴 Job 폴더명으로 이 장비 폴더를 매칭).
                # 이걸 빼면 job_keyword 가 빈 계획에서 선택창을 요구해 전부 건너뛴다.
                _, _plan, srcs = collector.collect_equipment(
                    ip, staging_for, no_chooser, username="amkor", password=None,
                    use_net_use=use_netuse, plan=plan,
                    confirm=lambda planned: True,     # 무인 — 로컬 staging 복사 승인
                    target_levels=list(guess_recipes), match_recipes=auto_match)
                for d, lvl in srcs:
                    sources.append((d, lvl, m))
            except collector.UserCancelled:
                skipped.append(f"{m}(자동 매칭 실패)")
            except Exception as e:  # noqa: BLE001
                skipped.append(f"{m}({e})")

        if skipped:
            watcher.append_log(self.save_dir, "건너뜀 — " + ", ".join(skipped))
        if diag:
            watcher.append_log(self.save_dir, "매칭 진단 — " + " / ".join(diag[:8]))
        if not sources:
            detail = ("\n· " + "\n· ".join(diag[:6])) if diag else ""
            # 폴더를 지정해 둔 경우에는 '값 업데이트를 하라'고 안내하면 안 된다
            # (계획이 아니라 지정 경로가 문제이므로). 상황에 맞는 안내를 낸다.
            if any_fixed:
                hint = ("\n\n지정한 감시 폴더를 장비에서 찾지 못했습니다.\n"
                        "장비에 그 경로가 실제로 있는지, 연결(탐색기 로그인)이 "
                        "되어 있는지 확인하세요.\n"
                        "'📁 감시 폴더 지정…'에서 호기별로 다시 고를 수 있습니다.")
            else:
                hint = ("\n\n선택한 레시피의 Job 폴더를 장비에서 찾지 못했습니다.\n"
                        "감시 설정의 '📁 감시 폴더 지정…'에서 폴더를 직접 지정하면 "
                        "이름을 유추하지 않아 확실합니다.")
            raise RuntimeError(
                "수집된 장비가 없습니다: " + (", ".join(skipped) or "-") + detail + hint)

        cb, cstate = self._coef_lookup_cb()
        cfgs = []
        for rootp, kw, aoi in sources:
            cfgs += ini_parser.scan_tree(rootp, default_level=kw,
                                         default_equipment=aoi, coef_lookup=cb)
        valid = [c for c in cfgs if rtp.config_valid(c)]
        rows, _ = ini_parser.build_pivot(valid)
        self._coef_save_if_changed(cstate)
        watcher.append_log(self.save_dir,
                           f"수집 완료 — 장비 {len(sources)}건, 파라미터 {len(rows)}행")
        # 파싱이 끝나면 임시 수집본은 더 필요 없다 — 즉시 삭제(누적 방지).
        localdirs.drop(staging_root)
        return rows, skipped

    def _run_bg(self, work, on_done):
        """모달 없이 백그라운드 실행(무인 감시용). GUI 갱신은 on_done 에서만."""
        def runner():
            try:
                res = work()
            except Exception as e:  # noqa: BLE001
                self.after(0, lambda e=e: on_done(False, e))
                return
            self.after(0, lambda: on_done(True, res))
        threading.Thread(target=runner, daemon=True).start()

    def _is_hidden(self) -> bool:
        """창이 트레이로 내려가 있는가(숨김/아이콘화)."""
        try:
            return self.state() == "withdrawn" or not self.winfo_viewable()
        except Exception:  # noqa: BLE001
            return False

    def _watch_notify(self, res):
        """내가 돌린 회차의 변경 알림."""
        self._watch_mark_seen(watcher.load_settings(self.save_dir)[1].last_run)
        self._watch_alert(res.summary(), res.report, by_other=False)

    def _watch_alert(self, summary: str, report: str | None, by_other=False):
        """변경 알림 — **내용은 간단히**(변경 있음/없음 + 요약), 상세는 보고서.

        누르면 자동 감시 창이 열려 보고서를 확인할 수 있다.
        트레이로 내려가 있으면 모달 대신 풍선 알림을 쓴다(숨은 창의 모달은 볼 수 없음).
        """
        who = "다른 PC의 자동 감시" if by_other else "자동 감시"
        self._set_status(f"{who}: {summary}")
        if self._is_hidden() and self._tray is not None:
            self._tray.notify("자동 감시 — 값 변경 감지",
                              f"{summary}\n눌러서 변경 내용을 확인하세요.")
            self._tray.set_tooltip(f"Para — 변경 감지 ({summary})")
            self._pending_report = report
            return
        if messagebox.askyesno(
                "자동 감시 — 값 변경 감지",
                f"{who} 결과 달라진 값이 있습니다.\n\n  {summary}\n\n"
                "자동 감시 창에서 변경 보고서를 확인하시겠습니까?"):
            self._watch_reports_window(select=report)

    def _watch_reports_window(self, select: str | None = None):
        """자동 감시 창 — 회차 상태 + 변경 보고서 목록(열기)."""
        if not self._need_save_dir():
            return
        s, state = watcher.load_settings(self.save_dir)
        reports = watcher.list_reports(self.save_dir)
        win = tk.Toplevel(self)
        win.title("자동 감시 — 변경 보고서")
        win.configure(bg=self.p["bg"])
        win.geometry("720x520")
        tk.Label(win, text="자동 감시 변경 보고서", bg=self.p["bg"], fg=self.p["text"],
                 font=self.fonts["title"]).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(win, text=self._watch_status_text(s, state), bg=self.p["bg"],
                 fg=self.p["muted"], font=self.fonts["sub"],
                 justify="left").pack(anchor="w", padx=16, pady=(0, 8))
        runner = self._watch_runner()
        if runner is not None and not self._watch_owned:
            tk.Label(win, text=f"※ 현재 {runner.user}({runner.host})님 PC에서 감시가 "
                               "실행 중입니다. 결과는 모두가 함께 봅니다.",
                     bg=self.p["bg"], fg=self.p["primary"],
                     font=self.fonts["sub"]).pack(anchor="w", padx=16, pady=(0, 6))

        frame = tk.Frame(win, bg=self.p["bg"])
        frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        lb = tk.Listbox(frame, font=self.fonts["base"], activestyle="none")
        sb = ttk.Scrollbar(frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for p_ in reports:
            lb.insert("end", os.path.basename(p_))
        if reports:
            idx = 0
            if select:
                base = os.path.basename(select)
                for i, p_ in enumerate(reports):
                    if os.path.basename(p_) == base:
                        idx = i
                        break
            lb.selection_set(idx)
            lb.see(idx)
        else:
            tk.Label(win, text="아직 변경 보고서가 없습니다(변경이 없었거나 감시 전).",
                     bg=self.p["bg"], fg=self.p["muted"]).pack(pady=4)

        def open_sel():
            sel = lb.curselection()
            if sel:
                self._open_path(reports[sel[0]])

        bt = tk.Frame(win, bg=self.p["bg"])
        bt.pack(fill="x", padx=16, pady=(0, 12))
        tk.Button(bt, text="📂 보고서 열기", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=16, pady=6, cursor="hand2",
                  command=open_sel).pack(side="left")
        tk.Button(bt, text="폴더 열기", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=14, pady=6, cursor="hand2",
                  command=lambda: self._open_path(
                      watcher.watch_dir(self.save_dir))).pack(side="left", padx=6)
        tk.Button(bt, text="감시 설정…", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=14, pady=6, cursor="hand2",
                  command=lambda: (win.destroy(), self._watch_dialog())).pack(side="left")
        tk.Button(bt, text="닫기", relief="flat", bd=0, bg=self.p["surface"],
                  fg=self.p["text"], padx=14, pady=6, cursor="hand2",
                  command=win.destroy).pack(side="right")
        lb.bind("<Double-Button-1>", lambda e: open_sel())

    def _open_path(self, path):
        """탐색기/기본 프로그램으로 열기(플랫폼별)."""
        try:
            if os.name == "nt":
                os.startfile(path)  # noqa: S606
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:  # noqa: BLE001
            self._err("E157", "열기 실패", e)

    # ====================================================================
    #  동시 접속 제어 — 편집 잠금 / 접속자 세션
    # ====================================================================
    def _set_window_icon(self):
        """창·작업표시줄 아이콘 지정. 실패해도 앱은 그대로 동작한다."""
        p = icon_path()
        if not p:
            return
        try:
            self.iconbitmap(default=p)      # Windows: 자식 창까지 함께 적용
        except Exception:  # noqa: BLE001
            try:
                self.iconbitmap(p)
            except Exception:  # noqa: BLE001
                pass                        # 리눅스 등 .ico 미지원 — 무시

    def _acquire_doc(self, path: str, doc_name: str) -> bool:
        """문서 편집 잠금 시도. True=편집 가능, False=읽기 전용으로 열어야 함.

        타인이 쥐고 있으면 안내창을 띄우고 읽기 전용, 만료된 잠금은 인수 여부를 묻는다.
        """
        if not path:
            return True
        try:
            st = locking.acquire(path, self.user)
            if st.status == "stale":                 # 비정상 종료로 남은 남의 잠금
                if messagebox.askyesno("잠금 만료",
                                       locking.holder_message(st, doc_name)):
                    st = locking.acquire(path, self.user, takeover=True)
            if st.editable:
                self._locks[path] = doc_name
                self._ro_docs.discard(path)
                self._doc_stamps[path] = locking.file_stamp(path)
                return True
            messagebox.showinfo(f"{doc_name} — 읽기 전용",
                                locking.holder_message(st, doc_name))
            self._ro_docs.add(path)
            return False
        except Exception as e:  # noqa: BLE001
            # 잠금 자체가 실패해도 작업은 계속(잠금은 보조장치) — 로그만 남긴다.
            self._logerr("E150", e)
            return True

    def _acquire_global(self, name: str, work_name: str) -> bool:
        """전역 작업 잠금(여러 PC 동시 실행 금지). True=진행 가능."""
        if not self.save_dir:
            return True
        try:
            st = locking.acquire_global(self.save_dir, name, self.user)
            if st.status == "stale" and messagebox.askyesno(
                    "이전 작업 잠금", locking.holder_message(st, work_name)):
                st = locking.acquire_global(self.save_dir, name, self.user,
                                            takeover=True)
            if st.editable:
                self._locks[locking.global_lock_path(self.save_dir, name)] = work_name
                return True
            info = st.info
            who = f"{info.user}({info.host})" if info else "다른 사용자"
            messagebox.showwarning(
                f"{work_name} — 실행 불가",
                f"현재 {who}님 PC에서 [{work_name}] 작업이 실행 중입니다.\n\n"
                "동시에 실행하면 장비에 중복으로 접속하고 결과 파일이 서로 덮어써질 수 "
                "있어 시작하지 않습니다.\n상대 작업이 끝난 뒤 다시 시도해 주세요.")
            return False
        except Exception as e:  # noqa: BLE001
            self._logerr("E153", e)
            return True

    def _release_global(self, name: str) -> None:
        if not self.save_dir:
            return
        try:
            locking.release_global(self.save_dir, name, self.user)
        except Exception as e:  # noqa: BLE001
            self._logerr("E154", e)
        self._locks.pop(locking.global_lock_path(self.save_dir, name), None)

    def _doc_for_view(self, view: str) -> str | None:
        """화면 ↔ 편집 문서 대응(잠금 반납 대상 판단용)."""
        if not self.save_dir:
            return None
        return {"special": refdata.special_path(self.save_dir),
                "reference": refdata.ref_path(self.save_dir),
                "ip": refdata.ip_path(self.save_dir)}.get(view)

    def _release_docs_except(self, view: str) -> None:
        """현재 화면의 문서를 뺀 나머지 편집 잠금 반납.

        한 사람이 여러 문서를 계속 붙들고 있으면 다른 사람이 못 쓰므로, 화면을
        떠나는 즉시 반납한다.
        """
        keep = self._doc_for_view(view)
        for v in ("special", "reference", "ip"):
            p = self._doc_for_view(v)
            if p and p != keep and p in self._locks:
                self._release_doc(p)
            if p and p != keep:
                self._ro_docs.discard(p)

    def _release_doc(self, path: str) -> None:
        if not path:
            return
        try:
            locking.release(path, self.user)
        except Exception as e:  # noqa: BLE001
            self._logerr("E151", e)
        self._locks.pop(path, None)
        self._doc_stamps.pop(path, None)
        self._ro_docs.discard(path)

    def _is_ro_doc(self, path: str) -> bool:
        """이 문서를 읽기 전용으로 열었는가(= 남이 편집 중)."""
        return path in self._ro_docs

    def _ro_banner(self, parent, doc_name: str, path: str) -> None:
        """읽기 전용 안내 배너 — 누가 수정 중인지 상단에 계속 보이게."""
        st = locking.status(path, self.user)
        info = st.info
        who = f"{info.user}({info.host})" if info else "다른 사용자"
        since = f" · {info.time}부터" if info and info.time else ""
        bar = tk.Frame(parent, bg="#fff4e5")
        bar.pack(side="top", fill="x", padx=10, pady=(6, 0))
        tk.Label(bar, text=f"🔒 읽기 전용 — {who}님이 {doc_name}을(를) 수정 중입니다{since}. "
                           "수정하려면 상대가 끝낸 뒤 화면을 다시 열어 주세요.",
                 bg="#fff4e5", fg="#8a5a00", font=self.fonts["sub"],
                 anchor="w", justify="left").pack(side="left", padx=10, pady=5)
        tk.Button(bar, text="다시 시도", relief="flat", bd=0, bg="#fff4e5",
                  fg=self.p["primary"], font=self.fonts["sub"], cursor="hand2",
                  command=self._render).pack(side="right", padx=8)

    def _presence_tick(self):
        """접속자 하트비트 + 내 잠금 갱신 + 만료 세션 정리(주기 실행)."""
        try:
            if self.save_dir:
                locking.touch_session(self.save_dir, self.user, screen=self.view)
                for p in list(self._locks):
                    locking.refresh(p, self.user)
                locking.prune_sessions(self.save_dir)
                self._update_presence_label()
        except Exception as e:  # noqa: BLE001
            self._logerr("E152", e)
        self.after(locking.SESSION_HEARTBEAT_SEC * 1000, self._presence_tick)

    def _update_presence_label(self):
        """상단 접속자 표시 갱신(위젯이 있을 때만)."""
        lbl = getattr(self, "_presence_lbl", None)
        if lbl is None:
            return
        try:
            msg = locking.others_message(self.save_dir, self.user) if self.save_dir else ""
            lbl.config(text=("👥 " + msg) if msg else "👤 나만 접속 중")
        except Exception:  # noqa: BLE001
            pass

    def _show_sessions(self):
        """현재 접속자 목록 창 — 누가 무엇을 잠그고 있는지."""
        if not self._need_save_dir():
            return
        sessions = locking.list_sessions(self.save_dir)
        win = tk.Toplevel(self)
        win.title("현재 접속자")
        win.configure(bg=self.p["bg"])
        win.geometry("560x360")
        tk.Label(win, text="현재 이 저장폴더를 사용 중인 사람", bg=self.p["bg"],
                 fg=self.p["text"], font=self.fonts["bold"]).pack(anchor="w",
                                                                 padx=14, pady=(12, 2))
        tk.Label(win, text="(수정 문서는 1명만 편집할 수 있고, 나머지는 읽기 전용입니다)",
                 bg=self.p["bg"], fg=self.p["muted"],
                 font=self.fonts["sub"]).pack(anchor="w", padx=14)
        cols = ("사용자", "PC", "화면", "접속 시작", "최근 확인")
        tv = ttk.Treeview(win, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (110, 120, 100, 130, 130)):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor="center")
        for s in sessions:
            me = " (나)" if (s.user == self.user and s.pid == os.getpid()) else ""
            tv.insert("", "end", values=(s.user + me, s.host, s.screen or "-",
                                         s.started, s.last_seen))
        tv.pack(fill="both", expand=True, padx=14, pady=10)
        if not sessions:
            tk.Label(win, text="접속자 정보가 없습니다.", bg=self.p["bg"],
                     fg=self.p["muted"]).pack(pady=4)
        tk.Button(win, text="닫기", relief="flat", bd=0, bg=self.p["primary"],
                  fg="#ffffff", padx=16, pady=5, cursor="hand2",
                  command=win.destroy).pack(pady=(0, 12))

    def _save_one(self, path: str, saver) -> bool:
        """문서 1개 저장 — 잠금·외부 변경 재검증 후 기록.

        OneDrive 동기화 지연으로 잠금이 새더라도, 남이 먼저 저장한 내용을 말없이
        덮어쓰지 않도록 여기서 마지막으로 막는다. 반환: 저장했으면 True.
        """
        if self._is_ro_doc(path):
            return False                       # 읽기 전용으로 연 문서는 저장하지 않음
        chk = locking.check_before_save(path, self.user, self._doc_stamps.get(path))
        if not chk["ok"]:
            name = os.path.basename(path)
            if not messagebox.askyesno(
                    "저장 충돌 확인",
                    f"[{name}] 저장 전에 문제가 발견되었습니다.\n\n{chk['reason']}\n\n"
                    "그대로 저장하면 다른 사람의 변경이 사라질 수 있습니다.\n"
                    "저장을 진행할까요?"):
                return False
        saver()
        self._doc_stamps[path] = locking.file_stamp(path)
        return True

    def _save_refdata(self):
        """현재 장비 IP/참고자료/특이사항을 저장 폴더의 파일에 기록(색상 포함).

        읽기 전용으로 연 문서(다른 사람이 편집 중)는 저장하지 않는다.
        """
        if not self.save_dir:
            return
        try:
            self._save_one(refdata.ip_path(self.save_dir),
                           lambda: refdata.save_ip(refdata.ip_path(self.save_dir),
                                                   self.ip_rows))
            self._save_one(refdata.ref_path(self.save_dir),
                           lambda: refdata.save_reference(
                               refdata.ref_path(self.save_dir), self.ref_grid,
                               self.ref_colors))
            self._save_one(refdata.special_path(self.save_dir),
                           lambda: refdata.save_special(
                               refdata.special_path(self.save_dir), self.special_rows,
                               self.special_colors))
        except Exception as e:  # noqa: BLE001
            self._err("E144", "저장 실패", e)

    # ====================================================================
    #  트레이 상주 — 창을 닫아도 자동 감시는 계속 (Windows)
    # ====================================================================
    def _watch_is_on(self) -> bool:
        """설정상 감시가 켜져 있고 이 PC 가 감시 주체인가."""
        if not self.save_dir:
            return False
        try:
            s, _ = watcher.load_settings(self.save_dir)
            return bool(s.enabled) and self._watch_owned
        except Exception:  # noqa: BLE001
            return False

    def _tray_start(self) -> bool:
        """트레이 아이콘 표시(이미 있으면 유지). 실패하면 False."""
        if self._tray is not None:
            return True
        if not tray.available():
            return False
        try:
            icon = tray.TrayIcon(
                "Para — 자동 감시 실행 중",
                on_open=self._restore_from_tray,
                on_exit=self._exit_from_tray,
                on_balloon=self._open_from_balloon,
                schedule=lambda fn: self.after(0, fn),
                icon_path=icon_path())
            if icon.start():
                self._tray = icon
                return True
        except Exception as e:  # noqa: BLE001
            self._logerr("E159", e)
        return False

    def _tray_stop(self):
        if self._tray is not None:
            try:
                self._tray.stop()
            except Exception:  # noqa: BLE001
                pass
            self._tray = None

    def _hide_to_tray(self):
        """창만 숨기고 프로세스는 유지 — 감시 주기(after)가 계속 돈다."""
        # 편집 잠금은 반납한다(창이 안 보이는데 남의 편집을 막고 있으면 안 됨).
        # 감시 전역 잠금은 계속 쥔다 — 이 PC 가 감시 주체이기 때문.
        try:
            for p in list(self._locks):
                if p != locking.global_lock_path(self.save_dir,
                                                 locking.GLOBAL_WATCHER):
                    self._release_doc(p)
        except Exception as e:  # noqa: BLE001
            self._logerr("E151", e)
        self.withdraw()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            try:
                self._tray.notify(
                    "자동 감시 계속",
                    "창을 닫아도 자동 감시는 백그라운드에서 계속됩니다.\n"
                    "트레이 아이콘을 누르면 다시 열 수 있습니다.")
            except Exception:  # noqa: BLE001
                pass
        try:
            watcher.append_log(self.save_dir, "창 닫힘 — 트레이 상주로 감시 계속")
        except Exception:  # noqa: BLE001
            pass

    def _restore_from_tray(self):
        """트레이 아이콘 클릭 → 창 다시 열기."""
        try:
            self.deiconify()
            self.state("normal")
            self.lift()
            self.focus_force()
        except Exception as e:  # noqa: BLE001
            self._logerr("E160", e)

    def _open_from_balloon(self):
        """풍선 알림 본문 클릭 → 창을 열고 **자동 감시 창(보고서)**까지 바로 표시."""
        self._restore_from_tray()
        report = self._pending_report or watcher.latest_report(self.save_dir)
        self._pending_report = None
        self.after(200, lambda: self._watch_reports_window(select=report))

    def _exit_from_tray(self):
        """트레이 메뉴 '자동 감시 종료' → 진짜 종료."""
        self._shutdown()

    def _shutdown(self):
        """실제 종료 — 잠금·세션·트레이 정리."""
        try:
            self._watch_release()
            locking.release_all(list(self._locks), self.user)
            if self.save_dir:
                locking.end_session(self.save_dir, self.user)
                watcher.append_log(self.save_dir, "프로그램 종료 — 자동 감시 중지")
        except Exception:  # noqa: BLE001
            pass
        self._tray_stop()
        self.destroy()

    def _on_close(self):
        """X 버튼 — 감시 중이면 트레이로 내리고, 아니면 종료."""
        if tray.should_stay_resident(self._watch_is_on()) and self._tray_start():
            self._hide_to_tray()
            return
        self._shutdown()



def main():
    app = EquipApp()
    app.mainloop()


if __name__ == "__main__":
    main()
