"""로컬 작업 폴더 — **OneDrive 밖**에 두는 임시/로그 저장소.

왜 필요한가 (2026-08 보안 경고 대응)
------------------------------------
저장폴더(OneDrive 동기화) 안에 임시파일을 만들면, 파일을 만들고 지울 때마다
OneDrive 가 그것을 동기화해 **공유 사용자 전원의 PC 로 다운로드**된다. 짧은 시간에
파일 수백 개가 오가면 보안 시스템이 'Unusual High-Volume Directory Access' 로
탐지한다(실제로 발생). 그래서 **중간 산물은 로컬에만** 두고, OneDrive 에는
사람이 열어보는 **결과물만** 남긴다.

  OneDrive(공유)  : 취합/양식/변경보고서 엑셀, 장비IP·특이사항·참고자료·변환계수,
                    감시설정, 잠금·접속자(공유가 목적)
  로컬(이 모듈)   : 수집 staging(원본 ini 복사본), 로그, 캐시

기본 위치는 `%LOCALAPPDATA%\\CamtekAOI` 이며, 사용자가 첫 실행 때 바꿀 수 있다
(config `local_dir`). 폴더 구조는 아래 한 곳에서만 정한다.

  {로컬폴더}/
    ├─ Temp/     수집 staging — 작업이 끝나면 지운다(`cleanup_temp`)
    ├─ Logs/     오류·감시 로그
    └─ Cache/    재사용 가능한 캐시(선택)
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

APP_DIRNAME = "CamtekAOI"
TEMP, LOGS, CACHE = "Temp", "Logs", "Cache"
COMMONALITY = "Commonality"      # Commonality 조사 산출물(공유 대상 아님)
DELETED = "삭제보관"              # 삭제한 레시피 양식 폴더의 되돌리기용 보관소

# Temp 아래 회차 폴더를 이 시간이 지나면 청소 대상으로 본다(작업 중인 것 보호).
TEMP_KEEP_HOURS = 6


_ACTIVE_ROOT: str | None = None      # 앱이 확정한 로컬 폴더(설정값)


def set_root(path: str) -> None:
    """앱이 확정한 로컬 폴더를 등록한다(errlog 등 다른 모듈이 참조)."""
    global _ACTIVE_ROOT
    _ACTIVE_ROOT = str(path) if path else None


def active_root() -> str:
    """현재 쓰는 로컬 폴더 — 설정값이 있으면 그것, 없으면 기본값."""
    return _ACTIVE_ROOT or default_root()


def program_root() -> str:
    """프로그램(exe 또는 소스)이 있는 폴더."""
    import sys
    if getattr(sys, "frozen", False):            # PyInstaller 등으로 묶은 exe
        return os.path.dirname(os.path.abspath(sys.executable))
    # 소스 실행: param_manager 의 상위(프로젝트 루트)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def appdata_root() -> str:
    r"""사용자 로컬 앱 폴더(`%LOCALAPPDATA%\CamtekAOI`) — 동기화되지 않는 안전한 위치."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = os.environ.get("XDG_DATA_HOME") or \
            os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, APP_DIRNAME)


def default_root() -> str:
    """기본 로컬 폴더 = **프로그램 옆에 폴더 하나**(사용자 지정 2026-08).

    프로그램 폴더 아래 `CamtekAOI/` 하나에 임시·로그·Commonality 를 모두 넣어
    관리하기 쉽게 한다.

    **주의**: 프로그램 자체가 OneDrive 동기화 폴더 안에 있으면 이 위치도 동기화
    대상이 되어 대량 동기화 사고가 그대로 재발한다. 그런 경우에는 안전한
    `%LOCALAPPDATA%` 로 자동 대체한다(첫 실행 안내에서 바꿀 수 있다).
    """
    here = program_root()
    if is_under_onedrive(here):
        return appdata_root()
    return os.path.join(here, APP_DIRNAME)


def is_under_onedrive(path: str) -> bool:
    """이 경로가 OneDrive 동기화 폴더 안인가(대략적 판정).

    로컬 폴더를 고를 때 실수로 OneDrive 안을 지정하면 문제가 그대로 재발하므로
    미리 경고하기 위한 검사다.
    """
    def norm(x):
        # Windows 가 아니어도(개발/테스트) 같은 판정이 나오도록 직접 정규화
        return str(x or "").replace("\\", "/").rstrip("/").lower()

    p = norm(os.path.abspath(str(path or "")) if not str(path or "").startswith(
        ("\\\\", "//")) else path)
    if "/onedrive" in p or p.startswith("onedrive"):
        return True
    for key in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        v = os.environ.get(key)
        if v and (p == norm(v) or p.startswith(norm(v) + "/")):
            return True
    return False


def ensure(root: str | None = None) -> str:
    """로컬 폴더(+하위 3개)를 만들고 경로를 돌려준다. 실패하면 예외."""
    root = str(root or default_root())
    for sub in ("", TEMP, LOGS, CACHE, COMMONALITY):
        os.makedirs(os.path.join(root, sub) if sub else root, exist_ok=True)
    return root


def temp_dir(root: str) -> str:
    d = os.path.join(root, TEMP)
    os.makedirs(d, exist_ok=True)
    return d


def logs_dir(root: str) -> str:
    d = os.path.join(root, LOGS)
    os.makedirs(d, exist_ok=True)
    return d


def cache_dir(root: str) -> str:
    d = os.path.join(root, CACHE)
    os.makedirs(d, exist_ok=True)
    return d


def commonality_dir(root: str) -> str:
    """Commonality 조사 산출물 폴더 — 결과물이지만 **공유 대상이 아니라** 로컬에 둔다
    (Lot 안전복사본 등 파일 수가 많아 OneDrive 에 두면 동기화가 폭주한다)."""
    d = os.path.join(root, COMMONALITY)
    os.makedirs(d, exist_ok=True)
    return d


def deleted_dir(root: str) -> str:
    """삭제한 레시피 양식 폴더를 옮겨 두는 곳 — **로컬**(되돌리기용).

    저장폴더(OneDrive)에 백업을 만들면 지운 파일이 그대로 다시 동기화돼
    '지웠는데 용량은 그대로 + 동기화 폭주'가 된다. 그래서 반드시 로컬이다.
    """
    d = os.path.join(root, DELETED)
    os.makedirs(d, exist_ok=True)
    return d


def new_deleted_slot(root: str, name: str) -> str:
    """되돌리기용 보관 폴더 `{삭제보관}/{이름}_{시각}` 경로(아직 만들지 않음).
    호출측이 여기로 옮긴다(이미 있으면 뒤에 번호를 붙여 덮어쓰지 않는다)."""
    from . import workdirs
    base = os.path.join(deleted_dir(root),
                        f"{workdirs._sanitize(name)}_{workdirs.stamp()}")
    dest, n = base, 1
    while os.path.exists(dest):
        dest = f"{base}({n})"
        n += 1
    return dest


def new_temp_run(root: str, prefix: str) -> str:
    """작업 1회분 임시 폴더 — `{Temp}/{prefix}_{시각}`. 끝나면 `drop()` 으로 삭제."""
    from . import workdirs
    d = os.path.join(temp_dir(root), f"{prefix}_{workdirs.stamp()}")
    os.makedirs(d, exist_ok=True)
    return d


def drop(path: str) -> bool:
    """임시 폴더 삭제. **Temp 아래가 아니면 지우지 않는다**(실수 방지). 성공 여부."""
    try:
        p = os.path.normcase(os.path.abspath(str(path)))
    except Exception:  # noqa: BLE001
        return False
    if f"{os.sep}{TEMP}{os.sep}".lower() not in p.lower() + os.sep:
        return False
    if not os.path.isdir(p):
        return False
    shutil.rmtree(p, ignore_errors=True)
    return not os.path.isdir(p)


def cleanup_temp(root: str, keep_hours: float = TEMP_KEEP_HOURS) -> int:
    """오래된 회차 폴더 청소(비정상 종료로 남은 것). 반환: 지운 개수.

    작업 중인 폴더를 지우지 않도록 최근 것은 남긴다.
    """
    d = os.path.join(root, TEMP)
    if not os.path.isdir(d):
        return 0
    cutoff = time.time() - keep_hours * 3600
    removed = 0
    for name in os.listdir(d):
        p = os.path.join(d, name)
        try:
            if os.path.isdir(p) and os.path.getmtime(p) < cutoff:
                shutil.rmtree(p, ignore_errors=True)
                if not os.path.isdir(p):
                    removed += 1
        except OSError:
            continue
    return removed


def describe(root: str) -> str:
    """설정 화면에 보여줄 요약(용량·회차 수)."""
    d = os.path.join(root, TEMP)
    n = size = 0
    if os.path.isdir(d):
        for name in os.listdir(d):
            p = os.path.join(d, name)
            if os.path.isdir(p):
                n += 1
                for dirpath, _dn, files in os.walk(p):
                    for f in files:
                        try:
                            size += os.path.getsize(os.path.join(dirpath, f))
                        except OSError:
                            pass
    mb = size / (1024 * 1024)
    return f"임시 작업 폴더 {n}개 · {mb:.1f} MB"
