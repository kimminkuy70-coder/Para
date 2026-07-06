"""수집/초안/확정/백업 파일의 폴더 배치 규칙 (2026-07 사용자 확정).

공용 파일이 D:\\OneDrive\\공용\\TB500_PI.xlsx 라면:

    D:\\OneDrive\\공용\\
    ├─ 백업\\TB500_PI_20260706_143000.xlsx      ← 값 갱신 직전 자동 백업
    ├─ initial\\PI3\\AOI-13\\20260706_1430\\    ← staging(원본 복사) + 01_초안
    └─ final\\PI3\\AOI-13\\20260706_1430\\      ← 02_확정

initial/final → 레시피레벨(PI#/RDL#) → 호기 → 실행일시 순서.
폴더 규칙 변경 시 이 모듈만 고치면 된다.
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime

BACKUP_DIR = "백업"
INITIAL_DIR = "initial"
FINAL_DIR = "final"
STAGING_DIR = "staging"


def run_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def _sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", str(name)).strip().strip(".") or "item"


def base_dir_for(shared_xlsx: str) -> str:
    """공용 파일 경로 → 수집 폴더들의 루트(=공용 파일이 있는 폴더)."""
    return os.path.dirname(os.path.abspath(shared_xlsx))


def _run_dir(base: str, stage: str, level: str, aoi: str, stamp: str) -> str:
    d = os.path.join(base, stage, _sanitize(level or "레벨미상"),
                     _sanitize(aoi or "호기미상"), stamp)
    os.makedirs(d, exist_ok=True)
    return d


def initial_run_dir(base: str, level: str, aoi: str, stamp: str | None = None) -> str:
    return _run_dir(base, INITIAL_DIR, level, aoi, stamp or run_stamp())


def final_run_dir(base: str, level: str, aoi: str, stamp: str | None = None) -> str:
    return _run_dir(base, FINAL_DIR, level, aoi, stamp or run_stamp())


def staging_dir(initial_dir: str) -> str:
    d = os.path.join(initial_dir, STAGING_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def backup_shared_file(shared_xlsx: str) -> str:
    """값 갱신 직전 공용 파일 백업 사본 생성. 반환: 백업 파일 경로."""
    if not os.path.isfile(shared_xlsx):
        raise FileNotFoundError(shared_xlsx)
    bdir = os.path.join(base_dir_for(shared_xlsx), BACKUP_DIR)
    os.makedirs(bdir, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(shared_xlsx))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(bdir, f"{stem}_{ts}{ext}")
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(bdir, f"{stem}_{ts}_{n}{ext}")
        n += 1
    shutil.copy2(shared_xlsx, dest)
    return dest
