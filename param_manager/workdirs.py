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


# ==========================================================================
# 3차 재설계 — 저장 폴더 기준 구조
#   {저장폴더}/양식/{레시피}/{생성시간}/{레시피}_{호기}호기_참조_{시간}.xlsx
#                                       └ 관련파일/(원본 ini·원본·수정본)
#   {저장폴더}/파라미터 값 취합/파라미터 값 취합_{생성시간}.xlsx
# ==========================================================================
FORM_DIR = "양식"
COLLATE_DIR = "파라미터 값 취합"
RELATED_DIR = "관련파일"
COLLATE_PREFIX = "파라미터 값 취합"


def stamp() -> str:
    """생성시간 스탬프(초 단위) — 폴더/파일명 공용."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def form_root(save_dir: str) -> str:
    d = os.path.join(save_dir, FORM_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def form_recipe_dir(save_dir: str, recipe: str) -> str:
    d = os.path.join(form_root(save_dir), _sanitize(recipe))
    os.makedirs(d, exist_ok=True)
    return d


def form_run_dir(save_dir: str, recipe: str, st: str | None = None) -> str:
    d = os.path.join(form_recipe_dir(save_dir, recipe), st or stamp())
    os.makedirs(d, exist_ok=True)
    return d


def related_dir(run_dir: str) -> str:
    d = os.path.join(run_dir, RELATED_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def form_final_path(run_dir: str, recipe: str, aoi: str, st: str) -> str:
    return os.path.join(run_dir, f"{_sanitize(recipe)}_{_sanitize(aoi)}호기_참조_{st}.xlsx")


def form_original_path(related: str, recipe: str, aoi: str, st: str) -> str:
    return os.path.join(related, f"{_sanitize(recipe)}_원본_{_sanitize(aoi)}호기_참조_{st}.xlsx")


def form_draft_path(related: str, recipe: str, aoi: str, st: str) -> str:
    return os.path.join(related, f"{_sanitize(recipe)}_수정본_{_sanitize(aoi)}호기_참조_{st}.xlsx")


def list_recipes(save_dir: str) -> list[str]:
    """양식 폴더 아래 레시피 폴더 이름 목록(정렬)."""
    root = os.path.join(save_dir, FORM_DIR)
    if not os.path.isdir(root):
        return []
    return sorted(n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n)))


def list_form_versions(save_dir: str, recipe: str) -> list[tuple[str, str]]:
    """레시피의 (생성시간, 확정 양식 경로) 목록 — 최신순. 확정본 없는 폴더는 제외."""
    rdir = os.path.join(save_dir, FORM_DIR, _sanitize(recipe))
    if not os.path.isdir(rdir):
        return []
    out = []
    for st in os.listdir(rdir):
        run = os.path.join(rdir, st)
        if not os.path.isdir(run):
            continue
        finals = [f for f in os.listdir(run)
                  if f.lower().endswith(".xlsx") and os.path.isfile(os.path.join(run, f))]
        if finals:
            out.append((st, os.path.join(run, sorted(finals)[0])))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


def latest_form(save_dir: str, recipe: str) -> str | None:
    vs = list_form_versions(save_dir, recipe)
    return vs[0][1] if vs else None


def collate_root(save_dir: str) -> str:
    d = os.path.join(save_dir, COLLATE_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def collate_path(save_dir: str, st: str | None = None) -> str:
    return os.path.join(collate_root(save_dir), f"{COLLATE_PREFIX}_{st or stamp()}.xlsx")


def list_collate_files(save_dir: str) -> list[str]:
    """파라미터 값 취합 파일 경로 목록 — 최신순(파일명 스탬프 기준)."""
    root = os.path.join(save_dir, COLLATE_DIR)
    if not os.path.isdir(root):
        return []
    files = [os.path.join(root, f) for f in os.listdir(root)
             if f.lower().endswith(".xlsx") and f.startswith(COLLATE_PREFIX)]
    files.sort(reverse=True)
    return files


def latest_collate(save_dir: str) -> str | None:
    files = list_collate_files(save_dir)
    return files[0] if files else None
