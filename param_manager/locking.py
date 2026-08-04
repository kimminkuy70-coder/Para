"""동시 접속 제어 — 문서 편집 잠금(소프트 락) + 접속자 세션 목록.

여러 사람이 같은 저장폴더(OneDrive 동기화)를 열고 쓰는 상황을 전제로 한다.

  · 읽기 전용 화면(파라미터 값 확인)은 잠그지 않는다.
  · **수정하는 문서**(장비 IP/특이사항/참고자료/변환계수/양식/취합)는 1명만 편집.
    다른 사람이 잡고 있으면 안내 후 **읽기 전용**으로 연다.
  · 감시·취합처럼 "동시에 여러 PC에서 돌면 안 되는 작업"은 **전역 잠금** 1개.

OneDrive 한계(중요)
-------------------
OneDrive 는 동기화 지연이 있어 A 가 만든 잠금 파일이 B 에게 즉시 보이지 않는다.
따라서 이 잠금은 **충돌을 크게 줄이는 장치이지 수학적 상호배제가 아니다.**
그래서 3중으로 방어한다:

  1) 획득 직후 재확인(`_verify_owner`) — 동시 획득 일부를 검출해 양보.
  2) **저장 직전 재검증**(`check_before_save`) — 잠금이 새더라도 남의 저장을
     덮어써 데이터를 잃는 것만은 막는다(최후 방어선).
  3) OneDrive 충돌본 탐지(`conflict_copies`) — 이미 벌어진 충돌을 즉시 알림.

잠금 파일은 `engine` 의 기존 소프트 락(`.editlock`, `LOCK_STALE_MINUTES=30`)을
그대로 재사용한다(형식 호환).
"""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import engine

# 세션(접속자) 등록 폴더 — 저장폴더 안에 숨김성 폴더로 둔다.
SESSIONS_DIRNAME = "_세션"

# 세션 하트비트 주기와 만료. 갱신이 끊긴 세션은 만료로 보고 목록에서 제외한다.
SESSION_HEARTBEAT_SEC = 60
SESSION_STALE_MINUTES = 5

# 잠금 획득 직후 재확인까지의 대기(초). OneDrive 동시 획득 검출용.
VERIFY_DELAY_SEC = 0.4

# 전역 잠금 이름(파일 단위가 아니라 '작업' 단위)
GLOBAL_WATCHER = "자동감시"
GLOBAL_COLLATE = "값취합"


# --------------------------------------------------------------------------
# 상태 표현
# --------------------------------------------------------------------------
@dataclass
class LockState:
    """잠금 확인/획득 결과.

    status: free(비어있음) / mine(내가 보유) / other(타인 보유) / stale(만료)
    editable: 편집 가능 여부(= 내가 잠금을 쥐었는가)
    info: 현재 잠금 보유자(engine.LockInfo) 또는 None
    """
    status: str
    editable: bool
    info: engine.LockInfo | None = None
    path: str = ""

    @property
    def held_by_other(self) -> bool:
        return self.status == "other"


def _is_mine(info: engine.LockInfo | None, user: str) -> bool:
    """내 잠금인가 — 같은 사용자 + 같은 PC + 같은 프로세스."""
    return bool(info and info.user == user and info.host == socket.gethostname()
                and info.pid == os.getpid())


def _same_person(info: engine.LockInfo | None, user: str) -> bool:
    """같은 사람이 같은 PC 에서 잡은 잠금인가(프로세스는 다를 수 있음).
    앱이 비정상 종료된 뒤 같은 사람이 다시 열었을 때 자기 잠금을 이어받게 한다."""
    return bool(info and info.user == user and info.host == socket.gethostname())


# --------------------------------------------------------------------------
# 문서 잠금
# --------------------------------------------------------------------------
def status(path: str, user: str) -> LockState:
    """현재 잠금 상태만 확인(획득하지 않음).

    상태값:
      free  — 잠금 없음
      mine  — 내 프로세스가 보유(편집 가능)
      self  — **같은 사람·같은 PC의 다른 프로세스**가 보유. 앱이 비정상 종료된 뒤
              다시 열면 여기 해당한다. 자기 잠금이므로 바로 이어받는다
              (그러지 않으면 본인이 30분간 자기 문서에 못 들어간다).
      stale — 타인 잠금이지만 만료됨(인수 여부는 사용자 확인)
      other — 타인이 유효하게 보유(읽기 전용)
    """
    info = engine.read_lock(path)
    if info is None:
        return LockState("free", False, None, path)
    if _is_mine(info, user):
        return LockState("mine", True, info, path)
    if _same_person(info, user):
        return LockState("self", False, info, path)
    if info.is_stale():
        return LockState("stale", False, info, path)
    return LockState("other", False, info, path)


def _verify_owner(path: str, user: str) -> bool:
    """잠금을 쓴 직후 정말 내 것으로 남았는지 재확인(OneDrive 동시 획득 검출).

    거의 동시에 두 사람이 획득하면 나중에 쓴 쪽이 파일을 덮어쓴다. 잠깐 기다렸다
    다시 읽어 내 것이 아니면 **양보**한다(읽기 전용으로 떨어짐).
    """
    if VERIFY_DELAY_SEC > 0:
        time.sleep(VERIFY_DELAY_SEC)
    return _is_mine(engine.read_lock(path), user)


def acquire(path: str, user: str, takeover: bool = False) -> LockState:
    """편집 잠금 획득 시도.

    takeover=True 면 **만료된** 잠금을 인수한다(유효한 타인 잠금은 인수하지 않음).
    반환 LockState.editable 이 True 일 때만 편집을 허용할 것.
    """
    st = status(path, user)
    if st.status == "mine":
        engine.write_lock(path, user)          # 갱신(시간 연장)
        return LockState("mine", True, engine.read_lock(path), path)
    if st.status == "other":
        return st                              # 타인 보유 — 읽기 전용
    if st.status == "stale" and not takeover:
        return st                              # 만료됨 — 인수 여부는 호출자가 결정
    # free / self / (takeover 된 stale) → 획득 진행.
    # self = 내가 쓰던 잠금이 남은 것이므로 확인 없이 이어받는다.
    engine.write_lock(path, user)
    if not _verify_owner(path, user):
        # 동시 획득 — 상대에게 양보하고 읽기 전용으로
        return status(path, user)
    return LockState("mine", True, engine.read_lock(path), path)


def refresh(path: str, user: str) -> bool:
    """편집 중 잠금 갱신(만료 오판 방지). 내 잠금일 때만 갱신하고 성공 여부 반환."""
    if _is_mine(engine.read_lock(path), user):
        engine.write_lock(path, user)
        return True
    return False


def release(path: str, user: str) -> None:
    """내 잠금만 해제(engine.release_lock 은 pid 까지 확인)."""
    engine.release_lock(path, user)


def release_all(paths, user: str) -> None:
    """여러 잠금 일괄 해제 — 앱 종료 시 사용. 실패해도 나머지는 계속 해제."""
    for p in paths or []:
        try:
            release(p, user)
        except Exception:  # noqa: BLE001
            pass


def holder_message(state: LockState, doc_name: str = "이 문서") -> str:
    """사용자에게 보여줄 안내문 — 누가/언제부터 수정 중인지."""
    info = state.info
    if info is None:
        return f"{doc_name}을(를) 편집합니다."
    when = info.time or "?"
    who = f"{info.user}({info.host})"
    if state.status == "stale":
        return (f"{who}님이 {when}부터 {doc_name}을(를) 잡고 있었지만 "
                f"{engine.LOCK_STALE_MINUTES}분 넘게 갱신되지 않았습니다.\n"
                "비정상 종료로 보입니다. 편집을 이어받을까요?")
    return (f"{who}님이 {when}부터 {doc_name}을(를) 수정하고 있습니다.\n\n"
            "읽기 전용으로 엽니다. 수정하려면 상대가 끝낸 뒤 다시 열어 주세요.")


# --------------------------------------------------------------------------
# 저장 직전 재검증 — OneDrive 로 잠금이 새더라도 덮어쓰기 손실만은 막는다
# --------------------------------------------------------------------------
def file_stamp(path: str) -> tuple[float, int] | None:
    """파일의 (mtime, size). 없으면 None. 편집 시작 시 기록해 둔다."""
    try:
        stt = os.stat(path)
        return (stt.st_mtime, stt.st_size)
    except OSError:
        return None


def check_before_save(path: str, user: str,
                      opened_stamp: tuple[float, int] | None) -> dict:
    """저장 직전 안전 점검.

    반환 {"ok": bool, "reason": str, "changed": bool, "lock": LockState,
          "conflicts": [경로...]}
      · changed=True  → 내가 연 뒤 파일이 바뀜(다른 사람이 먼저 저장)
      · ok=False      → 그대로 저장하면 남의 변경을 덮어씀. 사용자 확인 필요.
    """
    st = status(path, user)
    now_stamp = file_stamp(path)
    changed = (opened_stamp is not None and now_stamp is not None
               and now_stamp != opened_stamp)
    conflicts = conflict_copies(path)
    reasons = []
    if changed:
        reasons.append("내가 연 뒤 파일이 변경되었습니다(다른 사람이 먼저 저장).")
    if st.status == "other":
        info = st.info
        who = f"{info.user}({info.host})" if info else "다른 사용자"
        reasons.append(f"잠금이 {who}님에게 넘어가 있습니다.")
    if conflicts:
        reasons.append(f"OneDrive 충돌본이 {len(conflicts)}개 발견되었습니다.")
    return {"ok": not reasons, "reason": "\n".join(reasons), "changed": changed,
            "lock": st, "conflicts": conflicts}


def conflict_copies(path: str) -> list[str]:
    """OneDrive 충돌 사본 탐지(engine 재사용). 엑셀이 아니면 빈 목록."""
    try:
        if not str(path).lower().endswith((".xlsx", ".xlsm")):
            return []
        return engine.find_conflict_copies(path)
    except Exception:  # noqa: BLE001
        return []


# --------------------------------------------------------------------------
# 전역 잠금(작업 단위) — 자동 감시/취합처럼 여러 PC 동시 실행 금지
# --------------------------------------------------------------------------
def global_lock_path(save_dir: str, name: str) -> str:
    """전역 잠금 파일 경로. 실제 문서가 아니므로 `_잠금` 폴더에 둔다."""
    d = os.path.join(save_dir, SESSIONS_DIRNAME)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{name}.lock")


def acquire_global(save_dir: str, name: str, user: str,
                   takeover: bool = False) -> LockState:
    """전역 작업 잠금 획득(예: 자동 감시는 1대 PC 에서만)."""
    return acquire(global_lock_path(save_dir, name), user, takeover=takeover)


def release_global(save_dir: str, name: str, user: str) -> None:
    release(global_lock_path(save_dir, name), user)


def global_status(save_dir: str, name: str, user: str) -> LockState:
    return status(global_lock_path(save_dir, name), user)


# --------------------------------------------------------------------------
# 접속자 세션 목록
# --------------------------------------------------------------------------
@dataclass
class SessionInfo:
    user: str
    host: str
    pid: int
    started: str
    last_seen: str
    screen: str = ""

    @property
    def label(self) -> str:
        return f"{self.user}({self.host})"

    def is_stale(self, minutes: int = SESSION_STALE_MINUTES) -> bool:
        try:
            dt = datetime.strptime(self.last_seen, "%Y-%m-%d %H:%M:%S")
        except Exception:  # noqa: BLE001
            return True
        return datetime.now() - dt > timedelta(minutes=minutes)


def sessions_dir(save_dir: str) -> str:
    d = os.path.join(save_dir, SESSIONS_DIRNAME)
    os.makedirs(d, exist_ok=True)
    return d


def _session_filename(user: str, host: str, pid: int) -> str:
    safe = "".join(c for c in f"{user}@{host}#{pid}"
                   if c.isalnum() or c in "-_@#.가-힣") or "session"
    return safe + ".json"


def session_path(save_dir: str, user: str) -> str:
    return os.path.join(sessions_dir(save_dir),
                        _session_filename(user, socket.gethostname(), os.getpid()))


def touch_session(save_dir: str, user: str, screen: str = "") -> str:
    """내 세션 등록/갱신(하트비트). 주기적으로 호출. 실패해도 앱은 계속 동작."""
    p = session_path(save_dir, user)
    started = ""
    try:
        with open(p, encoding="utf-8") as fh:
            started = json.load(fh).get("started", "")
    except Exception:  # noqa: BLE001
        started = ""
    payload = {"user": user, "host": socket.gethostname(), "pid": os.getpid(),
               "started": started or engine.now_str(),
               "last_seen": engine.now_str(), "screen": screen}
    try:
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
    except OSError:
        pass
    return p


def end_session(save_dir: str, user: str) -> None:
    """앱 종료 시 내 세션 제거."""
    try:
        os.remove(session_path(save_dir, user))
    except OSError:
        pass


def list_sessions(save_dir: str, include_stale: bool = False) -> list[SessionInfo]:
    """현재 접속자 목록(갱신이 끊긴 세션은 기본 제외). 최근 접속 순."""
    out: list[SessionInfo] = []
    d = os.path.join(save_dir, SESSIONS_DIRNAME)
    if not os.path.isdir(d):
        return out
    for name in os.listdir(d):
        if not name.lower().endswith(".json"):
            continue
        try:
            with open(os.path.join(d, name), encoding="utf-8") as fh:
                v = json.load(fh)
            s = SessionInfo(user=str(v.get("user", "?")), host=str(v.get("host", "?")),
                            pid=int(v.get("pid", 0)), started=str(v.get("started", "")),
                            last_seen=str(v.get("last_seen", "")),
                            screen=str(v.get("screen", "")))
        except Exception:  # noqa: BLE001
            continue
        if include_stale or not s.is_stale():
            out.append(s)
    out.sort(key=lambda s: s.last_seen, reverse=True)
    return out


def prune_sessions(save_dir: str) -> int:
    """만료된 세션 파일 정리. 반환: 삭제 개수."""
    d = os.path.join(save_dir, SESSIONS_DIRNAME)
    if not os.path.isdir(d):
        return 0
    removed = 0
    for name in os.listdir(d):
        if not name.lower().endswith(".json"):
            continue
        p = os.path.join(d, name)
        try:
            with open(p, encoding="utf-8") as fh:
                v = json.load(fh)
            s = SessionInfo(user=str(v.get("user", "?")), host=str(v.get("host", "?")),
                            pid=int(v.get("pid", 0)), started=str(v.get("started", "")),
                            last_seen=str(v.get("last_seen", "")))
        except Exception:  # noqa: BLE001
            continue
        if s.is_stale():
            try:
                os.remove(p)
                removed += 1
            except OSError:
                pass
    return removed


def others_message(save_dir: str, user: str) -> str:
    """'현재 접속: …' 한 줄 요약(나 제외). 아무도 없으면 빈 문자열."""
    me_host, me_pid = socket.gethostname(), os.getpid()
    others = [s for s in list_sessions(save_dir)
              if not (s.user == user and s.host == me_host and s.pid == me_pid)]
    if not others:
        return ""
    return "현재 접속: " + " · ".join(s.label for s in others)
