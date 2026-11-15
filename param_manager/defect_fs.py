"""v14 Defect 분석: 화면(AOI Contrast Wizard, iframe)이 고른 폴더를 엔진이 읽어 주는 읽기 전용 다리.

왜: 브라우저의 폴더 고르기(`<input webkitdirectory>`)는 고른 폴더 아래 **모든 파일**(사진 포함)을
'업로드' 목록으로 처리한 뒤에야 페이지에 넘긴다 — 소유자 실측 50만 파일 ≈ 1시간. 폴더 핸들
(showDirectoryPicker)은 빠르지만 Windows 의 Chromium(Edge · Chrome)이 `.ini` 이름을 거부한다
(Chromium 파일 형식 정책에서 ini = Windows DANGEROUS). 그래서 엔진이 폴더 단위로 나열하고 필요한
파일만 읽어 준다(5-1 은 Slot 당 약 10개).

안전(원본 훼손 절대 금지 — 소유자):
- 읽기 전용: `os.scandir` · `os.stat` · `open(..., "rb")` 만. 쓰기 · 지우기 · 옮기기 함수가 없다.
- 뿌리 = 사람이 Windows 고르기 창에서 고른 폴더만(`Roots.add` 는 고르기 결과로만 부른다). 화면은 뿌리 번호와
  그 아래 상대 경로만 보낼 수 있다: 빈 칸 · '.' · '..' · '\\' · ':' · NUL 이 든 조각은 거부 → 뿌리 밖으로 못 나감.
- 긴 경로 · 네트워크 드라이브: Windows 에서 240자 이상이면 확장 경로 접두(colorgray.long_path 와 같은 규칙, #48).
"""
from __future__ import annotations

import os
import secrets
import stat as _stat
import threading
from pathlib import Path

MAX_ROOTS = 64
FILE_MAX = 64 * 1024 * 1024          # 한 파일 최대(사진 ~1.4 MB · s_FrameData ~7 MB 넉넉히). 더 크면 거부(Zones.dat 같은 것은 읽지 않음)
WALK_MAX = 2_000_000                 # Step 1 목록 최대 파일 수(넘으면 truncated)
SKIP_DIRS = {"$recycle.bin", "system volume information"}
_BAD = ("\\", ":", "\x00")


def long_path(p) -> str:
    s = str(p)
    if os.name == "nt" and len(s) >= 240 and not s.startswith("\\\\?\\"):
        s = os.path.abspath(s)
        return "\\\\?\\UNC\\" + s[2:] if s.startswith("\\\\") else "\\\\?\\" + s
    return s


class Roots:
    """사람이 고른 폴더(읽기 뿌리) 목록 — 번호(무작위)로만 부른다."""

    def __init__(self):
        self._lock = threading.Lock()
        self._roots: dict[str, Path] = {}

    def add(self, path) -> dict:
        p = Path(os.path.abspath(str(path).strip().strip('"')))
        if not os.path.isdir(long_path(p)):
            raise ValueError("폴더를 찾을 수 없습니다")
        with self._lock:
            for rid, q in self._roots.items():
                if str(q).lower() == str(p).lower():
                    return dict(id=rid, name=p.name or str(p), path=str(p))
            if len(self._roots) >= MAX_ROOTS:
                self._roots.pop(next(iter(self._roots)))
            rid = secrets.token_hex(8)
            self._roots[rid] = p
        return dict(id=rid, name=p.name or str(p).rstrip("\\/"), path=str(p))

    def get(self, rid: str) -> Path:
        with self._lock:
            p = self._roots.get(str(rid))
        if p is None:
            raise KeyError("root")
        return p


def resolve(root: Path, rel: str) -> Path:
    """뿌리 아래 상대 경로('/' 구분). 뿌리 밖 · 이상한 조각은 ValueError."""
    rel = str(rel or "")
    if len(rel) > 2048:
        raise ValueError("path")
    parts = rel.split("/") if rel else []
    for x in parts:
        # Windows 는 조각 끝의 점 · 공백을 지운다('.. ' = '..') — 점 · 공백만 남는 조각은 모두 거부
        if not x.rstrip(" .") or any(b in x for b in _BAD):
            raise ValueError("path")
    p = Path(root, *parts)
    base, full = os.path.abspath(str(root)), os.path.abspath(str(p))
    if full != base and not full.startswith(base.rstrip("\\/") + os.sep):
        raise ValueError("path")
    return p


def _mtime_ms(st) -> int:
    return int(st.st_mtime * 1000)


def list_dir(path: Path) -> dict:
    """폴더 하나: 하위 폴더 이름 · 파일 [이름, 크기, 수정 ms]. 이름 순(대소문자 무시). 사진 내용은 안 읽음."""
    dirs, files = [], []
    with os.scandir(long_path(path)) as it:
        for e in it:
            try:
                if e.is_dir():                      # 링크 폴더(DFS · NAS)도 따라감(#48)
                    if e.name.lower() not in SKIP_DIRS:
                        dirs.append(e.name)
                elif e.is_file():
                    st = e.stat()
                    files.append([e.name, st.st_size, _mtime_ms(st)])
            except OSError:
                continue
    dirs.sort(key=str.lower)
    files.sort(key=lambda f: f[0].lower())
    return dict(dirs=dirs, files=files)


def stat(path: Path) -> dict:
    st = os.stat(long_path(path))
    kind = "dir" if _stat.S_ISDIR(st.st_mode) else "file" if _stat.S_ISREG(st.st_mode) else "other"
    return dict(kind=kind, size=st.st_size, mtime=_mtime_ms(st), name=path.name)


def open_file(path: Path):
    """(크기, 읽기 전용 파일 객체). 너무 크거나 파일이 아니면 ValueError."""
    st = os.stat(long_path(path))
    if not _stat.S_ISREG(st.st_mode):
        raise ValueError("not_file")
    if st.st_size > FILE_MAX:
        raise ValueError("too_large")
    return st.st_size, open(long_path(path), "rb")


def walk(root: Path, limit: int = WALK_MAX) -> dict:
    """Step 1 ~ 4: 뿌리 아래 모든 파일 [상대 경로, 크기, 수정 ms] — 폴더마다 나열 한 번(파일 내용 안 읽음)."""
    out, truncated, dirs = [], False, 0
    stack = [("", root)]
    seen = set()
    while stack:
        rel, path = stack.pop()
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        dirs += 1
        try:
            d = list_dir(path)
        except OSError:
            continue
        for name, size, mt in d["files"]:
            if len(out) >= limit:
                truncated = True
                break
            out.append([(rel + "/" if rel else "") + name, size, mt])
        if truncated:
            break
        for name in reversed(d["dirs"]):
            stack.append(((rel + "/" if rel else "") + name, path / name))
    return dict(files=out, dirs=dirs, truncated=truncated)
