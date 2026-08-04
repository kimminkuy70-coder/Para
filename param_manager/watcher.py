"""자동 감시 — 주기적으로 값을 수집·취합하고 **변경분 보고서**를 남긴다.

배경
----
지금까지는 사람이 '값 업데이트'를 누르고, '이력 확인'에서 파일 2개를 직접 골라야
변경을 볼 수 있었다. 이 모듈은 그 과정을 **주기 실행 + 변경 시 알림 + 보고서**로 바꾼다.

장비 비방해 원칙 (가동 중인 장비를 절대 방해하지 않는다)
-------------------------------------------------------
  · **원본은 읽기만** — 쓰기는 저장폴더(로컬)에만. collector 의 기존 3중 안전장치
    (UNC 쓰기 거부/dest≠src/copy2)를 그대로 탄다.
  · **찢어진 읽기 방지** — 장비가 쓰는 도중 읽으면 반쪽 파일을 읽어 '거짓 변경'이
    된다. 복사 전후 (mtime, size) 를 비교해 흔들린 파일은 그 회차에서 제외한다.
  · **재시도 몰아치기 금지** — 실패해도 즉시 재시도하지 않고 다음 주기로 미룬다
    (`backoff_until`). 장비가 바쁠 때 부하를 더하지 않기 위해서다.
  · **시간대 창** — 가동 피크를 피하도록 실행 시간대를 제한할 수 있다.
  · **중복 실행 금지** — 여러 PC 가 동시에 감시하면 장비에 배수로 접속한다.
    전역 잠금은 `locking.GLOBAL_WATCHER` 로 GUI 가 건다.

접속 방식
---------
기본은 **net use 없이(기존 세션)** — 사람이 탐색기로 미리 연결해 둔 상태를 쓴다.
비밀번호를 디스크에 저장하지 않기 위한 선택이며, 설정으로 net use 도 고를 수 있다.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from . import engine, history as history_mod, workdirs

# 설정 파일(저장폴더 안) — 사람이 열어볼 수 있게 JSON.
SETTINGS_NAME = "감시설정.json"
WATCH_DIRNAME = "자동감시"
LOG_NAME = "감시로그.txt"

# 접속 방식
CONN_SESSION = "session"       # 기본·권장: net use 없이 기존 연결 사용
CONN_NETUSE = "netuse"         # net use 로 직접 접속(비밀번호 필요, 메모리에만)

DEFAULT_INTERVAL_HOURS = 6
# 연속 실패 시 다음 시도까지 미루는 시간(주기의 배수). 몰아치기 방지.
BACKOFF_STEPS = [1, 2, 4, 8]


# --------------------------------------------------------------------------
# 설정 / 상태
# --------------------------------------------------------------------------
@dataclass
class WatchSettings:
    enabled: bool = False
    interval_hours: float = DEFAULT_INTERVAL_HOURS
    conn_mode: str = CONN_SESSION
    # 실행 허용 시간대(24h). start==end 면 제한 없음.
    window_start: int = 0
    window_end: int = 0
    recipes: list = field(default_factory=list)      # 빈 목록 = 전체
    machines: list = field(default_factory=list)     # 빈 목록 = 참고자료 전체
    notify_on_change_only: bool = True               # 변경 없으면 알리지 않음

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "interval_hours": self.interval_hours,
                "conn_mode": self.conn_mode, "window_start": self.window_start,
                "window_end": self.window_end, "recipes": list(self.recipes),
                "machines": list(self.machines),
                "notify_on_change_only": self.notify_on_change_only}

    @staticmethod
    def from_dict(d: dict) -> "WatchSettings":
        d = d or {}
        s = WatchSettings()
        s.enabled = bool(d.get("enabled", False))
        try:
            s.interval_hours = float(d.get("interval_hours", DEFAULT_INTERVAL_HOURS))
        except (TypeError, ValueError):
            s.interval_hours = DEFAULT_INTERVAL_HOURS
        if s.interval_hours <= 0:
            s.interval_hours = DEFAULT_INTERVAL_HOURS
        s.conn_mode = d.get("conn_mode") or CONN_SESSION
        try:
            s.window_start = int(d.get("window_start", 0)) % 24
            s.window_end = int(d.get("window_end", 0)) % 24
        except (TypeError, ValueError):
            s.window_start = s.window_end = 0
        s.recipes = list(d.get("recipes") or [])
        s.machines = list(d.get("machines") or [])
        s.notify_on_change_only = bool(d.get("notify_on_change_only", True))
        return s


@dataclass
class WatchState:
    last_run: str = ""          # 마지막 실행 시각
    fail_count: int = 0         # 연속 실패 횟수(backoff 계산용)
    last_result: str = ""

    def to_dict(self) -> dict:
        return {"last_run": self.last_run, "fail_count": self.fail_count,
                "last_result": self.last_result}

    @staticmethod
    def from_dict(d: dict) -> "WatchState":
        d = d or {}
        s = WatchState()
        s.last_run = str(d.get("last_run", ""))
        try:
            s.fail_count = int(d.get("fail_count", 0))
        except (TypeError, ValueError):
            s.fail_count = 0
        s.last_result = str(d.get("last_result", ""))
        return s


def settings_path(save_dir: str) -> str:
    return os.path.join(save_dir, SETTINGS_NAME)


def watch_dir(save_dir: str) -> str:
    d = os.path.join(save_dir, WATCH_DIRNAME)
    os.makedirs(d, exist_ok=True)
    return d


def report_path(save_dir: str, st: str | None = None) -> str:
    return os.path.join(watch_dir(save_dir), f"변경보고서_{st or workdirs.stamp()}.xlsx")


def log_path(save_dir: str) -> str:
    return os.path.join(watch_dir(save_dir), LOG_NAME)


def load_settings(save_dir: str) -> tuple[WatchSettings, WatchState]:
    """설정+상태 읽기. 파일이 없거나 깨져도 기본값으로 동작한다."""
    try:
        with open(settings_path(save_dir), encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:  # noqa: BLE001
        d = {}
    return (WatchSettings.from_dict(d.get("settings")),
            WatchState.from_dict(d.get("state")))


def save_settings(save_dir: str, settings: WatchSettings,
                  state: WatchState | None = None) -> str:
    p = settings_path(save_dir)
    payload = {"settings": settings.to_dict(),
               "state": (state or WatchState()).to_dict()}
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return p


def append_log(save_dir: str, line: str) -> None:
    """감시 로그 한 줄 추가. 실패해도 감시는 계속된다."""
    try:
        with open(log_path(save_dir), "a", encoding="utf-8") as fh:
            fh.write(f"[{engine.now_str()}] {line}\n")
    except OSError:
        pass


# --------------------------------------------------------------------------
# 실행 시점 판단
# --------------------------------------------------------------------------
def in_window(now: datetime, settings: WatchSettings) -> bool:
    """실행 허용 시간대인가. start==end 면 제한 없음(항상 True).
    end < start 면 자정을 넘는 창(예: 22시~06시)."""
    s, e = settings.window_start % 24, settings.window_end % 24
    if s == e:
        return True
    h = now.hour
    return (s <= h < e) if s < e else (h >= s or h < e)


def _parse_dt(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except Exception:  # noqa: BLE001
        return None


def next_run_at(settings: WatchSettings, state: WatchState,
                now: datetime | None = None) -> datetime:
    """다음 실행 예정 시각. 마지막 실행이 없으면 '지금'(즉시 1회).

    연속 실패가 쌓이면 backoff 로 더 미룬다(장비에 몰아치지 않기 위해).
    now 를 받는 이유: 기준 시각을 호출자가 정해야 판단이 결정적이 된다.
    """
    last = _parse_dt(state.last_run)
    if last is None:
        return now or datetime.now()
    mult = BACKOFF_STEPS[min(state.fail_count, len(BACKOFF_STEPS) - 1)] \
        if state.fail_count else 1
    return last + timedelta(hours=settings.interval_hours * mult)


def should_run(now: datetime, settings: WatchSettings, state: WatchState) -> bool:
    """이번 tick 에 실행할지. 꺼져 있거나 시간대 밖이면 실행하지 않는다."""
    if not settings.enabled:
        return False
    if not in_window(now, settings):
        return False
    return now >= next_run_at(settings, state, now)


# --------------------------------------------------------------------------
# 찢어진 읽기 방지 — 복사 전후 파일이 흔들렸는지 확인
# --------------------------------------------------------------------------
def file_sig(path) -> tuple | None:
    """(mtime, size). 없으면 None."""
    try:
        stt = os.stat(path)
        return (stt.st_mtime, stt.st_size)
    except OSError:
        return None


def unstable_files(pairs) -> list[str]:
    """[(원본경로, 복사전_sig)] → 복사 뒤 값이 달라진(=쓰는 중이던) 원본 목록.

    장비가 파일을 쓰는 도중 복사하면 내용이 반쪽일 수 있다. 그런 파일은 이번
    회차 결과에서 빼야 '없는 변경'이 보고되지 않는다.
    """
    out = []
    for src, before in pairs or []:
        after = file_sig(src)
        if before is None or after is None or before != after:
            out.append(str(src))
    return out


def drop_unstable(sources: list, unstable: list[str]) -> list:
    """수집 소스 목록에서 불안정 파일이 속한 항목을 제외."""
    bad = {os.path.normcase(os.path.abspath(p)) for p in unstable or []}
    if not bad:
        return list(sources or [])
    keep = []
    for item in sources or []:
        p = item[0] if isinstance(item, (tuple, list)) else item
        try:
            ap = os.path.normcase(os.path.abspath(str(p)))
        except Exception:  # noqa: BLE001
            keep.append(item)
            continue
        if not any(b == ap or b.startswith(ap + os.sep) for b in bad):
            keep.append(item)
    return keep


# --------------------------------------------------------------------------
# 변경 판정 + 보고서
# --------------------------------------------------------------------------
@dataclass
class CycleResult:
    ran: bool = False
    changed: int = 0
    added: int = 0
    removed: int = 0
    report: str = ""
    collate_file: str = ""
    skipped: list = field(default_factory=list)
    error: str = ""

    @property
    def has_change(self) -> bool:
        return bool(self.changed or self.added or self.removed)

    def summary(self) -> str:
        if self.error:
            return f"실패: {self.error}"
        if not self.ran:
            return "실행 조건 아님(건너뜀)"
        if not self.has_change:
            return "변경 없음"
        parts = []
        if self.changed:
            parts.append(f"값변경 {self.changed}건")
        if self.added:
            parts.append(f"추가 {self.added}건")
        if self.removed:
            parts.append(f"삭제 {self.removed}건")
        return " · ".join(parts)


def compare_and_report(save_dir: str, prev_collate: str | None,
                       new_collate: str, st: str | None = None) -> CycleResult:
    """직전 취합 ↔ 새 취합 비교 → 변경 있으면 보고서 엑셀 생성.

    첫 실행(직전 취합 없음)은 비교 대상이 없으므로 '변경 없음'으로 둔다.
    """
    res = CycleResult(ran=True, collate_file=new_collate)
    if not prev_collate or not os.path.exists(prev_collate):
        append_log(save_dir, "첫 취합 — 비교 대상 없음(기준선 생성)")
        return res
    diff = history_mod.diff_files(prev_collate, new_collate)
    res.changed = sum(1 for c in diff.changes if c.kind == "값변경")
    res.added = sum(1 for c in diff.changes if c.kind == "추가") + len(diff.added_rows)
    res.removed = (sum(1 for c in diff.changes if c.kind == "삭제")
                   + len(diff.removed_rows))
    if res.has_change:
        dest = report_path(save_dir, st)
        history_mod.write_diff_excel(diff, dest,
                                     old_label=os.path.basename(prev_collate),
                                     new_label=os.path.basename(new_collate))
        res.report = dest
    append_log(save_dir, f"비교 완료 — {res.summary()}"
                         + (f" · 보고서 {os.path.basename(res.report)}"
                            if res.report else ""))
    return res


def record_run(save_dir: str, settings: WatchSettings, state: WatchState,
               ok: bool, note: str = "") -> WatchState:
    """회차 결과를 상태에 반영하고 저장. 실패는 fail_count 를 올려 backoff 를 키운다."""
    state.last_run = engine.now_str()
    state.fail_count = 0 if ok else state.fail_count + 1
    state.last_result = note
    save_settings(save_dir, settings, state)
    return state


# --------------------------------------------------------------------------
# 접속 안내 (기본: net use 없이)
# --------------------------------------------------------------------------
def job_path_for(ip: str) -> str:
    return rf"\\{ip}\c$\Job"


SMB_PORT = 445
PROBE_TIMEOUT_SEC = 1.5      # 호스트 1대당 TCP 응답 대기(짧게 — 화면이 멈추면 안 됨)


def probe_host(ip: str, timeout: float = PROBE_TIMEOUT_SEC) -> bool:
    """장비가 SMB 포트로 살아 있는지 **짧은 타임아웃**으로 확인.

    `Path(r'\\\\IP\\c$\\Job').exists()` 는 타임아웃 지정이 불가능해서, 꺼져 있거나
    막힌 장비 1대에 20~40초씩 잡아먹는다(호기 수만큼 곱해져 화면이 멈춘다).
    그래서 먼저 TCP 로 1.5초만 두드려 보고, 죽어 있으면 즉시 미연결로 판정한다.
    """
    ip = str(ip or "").strip()
    if not ip:
        return False
    try:
        with socket.create_connection((ip, SMB_PORT), timeout=timeout):
            return True
    except Exception:  # noqa: BLE001
        return False


def check_connections(targets: list, timeout: float = PROBE_TIMEOUT_SEC,
                      progress=None, should_stop=None) -> dict:
    """[(호기, IP)] → {"ok": [...], "missing": [...], "stopped": bool}.

    net use 없이(기존 세션) 접근 가능한지만 확인한다 — **읽기 시도조차 하지 않고**
    도달 여부만 본다. 무인 실행 도중 조용히 실패하는 것을 막기 위한 사전 점검.

    호출 규약(화면 멈춤 방지):
      · **반드시 백그라운드 스레드에서 호출한다**(GUI 스레드 금지).
      · progress(done, total, machine) 로 진행 상황을 알린다.
      · should_stop() 이 True 면 즉시 중단한다(사용자 취소).
    """
    targets = list(targets or [])
    ok, missing = [], []
    total = len(targets)
    stopped = False
    for i, (machine, ip) in enumerate(targets, start=1):
        if should_stop is not None and should_stop():
            stopped = True
            break
        if progress is not None:
            try:
                progress(i, total, machine)
            except Exception:  # noqa: BLE001
                pass
        reachable = False
        if probe_host(ip, timeout):          # 살아 있을 때만 실제 경로 확인
            try:
                reachable = Path(job_path_for(ip)).exists()
            except Exception:  # noqa: BLE001
                reachable = False
        (ok if reachable else missing).append((machine, ip))
    return {"ok": ok, "missing": missing, "stopped": stopped}


def connection_guide(missing: list) -> str:
    """연결 안 된 장비 안내문 — 무인 모드 기본이 '기존 세션'이므로 사람이 미리 연결해야 한다."""
    if not missing:
        return ""
    names = ", ".join(f"{m}({ip})" for m, ip in missing)
    return ("무인 실행 모드는 비밀번호를 저장하지 않기 위해 **기존 연결(net use 없이)** 을 "
            "사용합니다.\n다음 장비가 아직 연결되어 있지 않습니다:\n\n"
            f"  {names}\n\n"
            "탐색기 주소창에 \\\\장비IP\\c$ 를 입력해 미리 연결(로그인)해 두신 뒤 "
            "감시를 시작하세요.\n연결해 두지 않으면 해당 장비는 매 회차 건너뜁니다.")
