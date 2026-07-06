"""버전 저장 규칙 — "항상 새 버전으로 저장, 이전 버전 보존"(AOI 스펙 1.1.1.1.4).

취합 엑셀(호기별 값)·양식 파일을 저장할 때 이전 버전을 지우지 않고 계속 쌓아
나중에 엑셀로 열람/비교할 수 있게 한다. 버전 파일은 원본 옆 `버전/{stem}/` 폴더에
`{stem}_v{NNN}_{YYYYMMDD_HHMMSS}{ext}` 형식으로 둔다.

규칙을 바꿀 일이 생기면 이 모듈만 고친다.
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime

VERSIONS_DIR = "버전"
_VER_RE = re.compile(r"_v(\d+)_\d{8}_\d{6}(?:_\d+)?$", re.I)


def version_dir(canonical_path: str) -> str:
    """canonical 파일 기준 버전 보관 폴더(`버전/{stem}/`). 없으면 만든다."""
    d = os.path.dirname(os.path.abspath(canonical_path))
    stem, _ = os.path.splitext(os.path.basename(canonical_path))
    vdir = os.path.join(d, VERSIONS_DIR, _sanitize(stem))
    os.makedirs(vdir, exist_ok=True)
    return vdir


def _sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", str(name)).strip().strip(".") or "item"


def _parse_version(fname: str, stem: str) -> int | None:
    base, _ = os.path.splitext(fname)
    if not base.lower().startswith(stem.lower()):
        return None
    m = _VER_RE.search(base)
    return int(m.group(1)) if m else None


def list_versions(canonical_path: str) -> list[str]:
    """이 canonical 파일의 버전 파일 경로들 — 버전번호 오름차순(오래된→최신)."""
    vdir = version_dir(canonical_path)
    stem, ext = os.path.splitext(os.path.basename(canonical_path))
    found: list[tuple[int, str]] = []
    for f in os.listdir(vdir):
        if not f.lower().endswith(ext.lower()):
            continue
        n = _parse_version(f, stem)
        if n is not None:
            found.append((n, os.path.join(vdir, f)))
    found.sort(key=lambda x: (x[0], x[1]))
    return [p for _, p in found]


def latest_version(canonical_path: str) -> str | None:
    vs = list_versions(canonical_path)
    return vs[-1] if vs else None


def next_version_number(canonical_path: str) -> int:
    vs = list_versions(canonical_path)
    if not vs:
        return 1
    stem = os.path.splitext(os.path.basename(canonical_path))[0]
    nums = [_parse_version(os.path.basename(p), stem) or 0 for p in vs]
    return (max(nums) if nums else 0) + 1


def next_version_path(canonical_path: str, stamp: str | None = None) -> str:
    """다음에 저장할 새 버전 파일 경로(아직 만들지 않음, 충돌 회피까지)."""
    vdir = version_dir(canonical_path)
    stem, ext = os.path.splitext(os.path.basename(canonical_path))
    n = next_version_number(canonical_path)
    ts = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(vdir, f"{stem}_v{n:03d}_{ts}{ext}")
    k = 2
    while os.path.exists(dest):
        dest = os.path.join(vdir, f"{stem}_v{n:03d}_{ts}_{k}{ext}")
        k += 1
    return dest


def save_new_version(canonical_path: str, stamp: str | None = None) -> str:
    """현재 canonical 파일을 새 버전으로 복사 보관. 반환: 버전 파일 경로.
    (canonical 파일 자체는 그대로 두고, 버전 폴더에 사본을 남긴다.)"""
    if not os.path.isfile(canonical_path):
        raise FileNotFoundError(canonical_path)
    dest = next_version_path(canonical_path, stamp)
    shutil.copy2(canonical_path, dest)
    return dest


def label_for(canonical_path: str, version_path: str) -> str:
    """버전 선택창에 보여줄 사람용 라벨: 'v003  (2026-07-06 14:30:00)'."""
    stem = os.path.splitext(os.path.basename(canonical_path))[0]
    base = os.path.splitext(os.path.basename(version_path))[0]
    m = _VER_RE.search(base)
    if not m:
        return os.path.basename(version_path)
    n = int(m.group(1))
    ts = re.search(r"(\d{8})_(\d{6})", base)
    when = ""
    if ts:
        d, t = ts.group(1), ts.group(2)
        when = f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:4]}:{t[4:]}"
    return f"v{n:03d}  ({when})" if when else f"v{n:03d}"
