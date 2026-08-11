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
COMMONALITY_DIR = "commonality"
COMMONALITY_COMPARE_DIR = "commonality_취합"
COMMONALITY_COMPARE_PREFIX = "취합비교"


def stamp() -> str:
    """생성시간 스탬프(초 단위) — 폴더/파일명 공용."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# create=False 로 부르면 **폴더를 만들지 않고 경로만** 돌려준다.
#   저장폴더는 OneDrive 라 폴더 하나를 만들 때마다 전원에게 동기화된다.
#   양식 만들기를 열었다가 취소하면 빈 `{레시피}/{시간}/관련파일/` 만 남아
#   쓸데없는 동기화가 쌓이므로, 경로 계산은 create=False, 실제 파일을 쓸 때만 생성한다.
def form_root(save_dir: str, create: bool = True) -> str:
    d = os.path.join(save_dir, FORM_DIR)
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def form_recipe_dir(save_dir: str, recipe: str, create: bool = True) -> str:
    d = os.path.join(form_root(save_dir, create), _sanitize(recipe))
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def form_run_dir(save_dir: str, recipe: str, st: str | None = None,
                 create: bool = True) -> str:
    d = os.path.join(form_recipe_dir(save_dir, recipe, create), st or stamp())
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def related_dir(run_dir: str, create: bool = True) -> str:
    d = os.path.join(run_dir, RELATED_DIR)
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def form_final_path(run_dir: str, recipe: str, aoi: str, st: str) -> str:
    return os.path.join(run_dir, f"{_sanitize(recipe)}_{_sanitize(aoi)}호기_참조_{st}.xlsx")


def form_original_path(related: str, recipe: str, aoi: str, st: str) -> str:
    return os.path.join(related, f"{_sanitize(recipe)}_원본_{_sanitize(aoi)}호기_참조_{st}.xlsx")


def form_draft_path(related: str, recipe: str, aoi: str, st: str) -> str:
    return os.path.join(related, f"{_sanitize(recipe)}_수정본_{_sanitize(aoi)}호기_참조_{st}.xlsx")


def form_candidate_path(run_dir: str) -> str | None:
    r"""그 회차의 **전체 후보 목록 엑셀**(초안) 경로. 없으면 None.

    확정 양식에는 체크해서 살린 항목만 들어 있어, 빼 놓은 파라미터를 나중에
    다시 넣으려면 이 초안이 있어야 한다('기존 양식 수정하기').
      · `_원본_` 우선 — 사람이 손대기 전의 전체 목록.
      · 없으면 `_수정본_` — 엑셀에서 행을 지웠을 수 있어 2순위.
    """
    rel = os.path.join(run_dir, RELATED_DIR)
    if not os.path.isdir(rel):
        return None
    try:
        names = sorted(n for n in os.listdir(rel) if n.lower().endswith(".xlsx")
                       and not n.startswith("~$"))
    except OSError:
        return None
    for tag in ("_원본_", "_수정본_"):
        hit = [n for n in names if tag in n]
        if hit:
            return os.path.join(rel, hit[-1])
    return None


def form_version_status(save_dir: str, recipe: str) -> list[dict]:
    """레시피의 버전마다 '후보 목록(원본)이 남아 있는가'를 조사한다 — 최신순.

    반환: [{stamp, final, run_dir, candidate(경로 or None), has_candidate,
            kind('원본'/'수정본'/'')}]
    '기존 양식 수정하기'에서 어느 버전이 **항목을 다시 추가할 수 있는지**
    사람에게 미리 보여 주기 위한 것.
    """
    out = []
    for st, final in list_form_versions(save_dir, recipe):
        run = os.path.dirname(final)
        cand = form_candidate_path(run)
        kind = ""
        if cand:
            kind = "원본" if "_원본_" in os.path.basename(cand) else "수정본"
        out.append({"stamp": st, "final": final, "run_dir": run,
                    "candidate": cand, "has_candidate": bool(cand), "kind": kind})
    return out


def any_candidate_for(save_dir: str, recipe: str) -> str | None:
    """같은 레시피의 **아무 버전에서나** 후보 목록을 찾는다(최신 우선).
    고른 버전에 초안이 없을 때 다른 회차 것을 빌려 쓰기 위한 폴백."""
    for v in form_version_status(save_dir, recipe):
        if v["candidate"]:
            return v["candidate"]
    return None


def recipe_delete_preview(save_dir: str, recipe: str) -> dict:
    """레시피 삭제 전 '무엇이 지워지는가' 요약.

    반환: {recipe, dir, exists, versions, files, bytes}
    사람이 되돌릴 수 없는 삭제를 하기 전에 규모를 정확히 보여 주기 위한 것.
    """
    d = os.path.join(save_dir, FORM_DIR, _sanitize(recipe))
    out = {"recipe": recipe, "dir": d, "exists": os.path.isdir(d),
           "versions": 0, "files": 0, "bytes": 0}
    if not out["exists"]:
        return out
    try:
        out["versions"] = sum(1 for n in os.listdir(d)
                              if os.path.isdir(os.path.join(d, n)))
    except OSError:
        pass
    for dirpath, _dn, files in os.walk(d):
        for f in files:
            out["files"] += 1
            try:
                out["bytes"] += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return out


def move_recipe_dir(save_dir: str, recipe: str, dest: str) -> str | None:
    """`양식/{레시피}/` 를 **dest 로 통째로 옮긴다**(되돌리기용 보관).

    dest 는 반드시 저장폴더 **밖**(로컬)이어야 한다 — 저장폴더 안에 백업을 만들면
    지운 파일이 그대로 다시 동기화돼 지운 의미가 없고 동기화만 늘어난다.
    반환: 옮긴 경로. 레시피 폴더가 없으면 None.
    """
    import shutil
    src = os.path.join(save_dir, FORM_DIR, _sanitize(recipe))
    if not os.path.isdir(src):
        return None
    save_n = os.path.normcase(os.path.abspath(save_dir))
    dest_n = os.path.normcase(os.path.abspath(dest))
    if dest_n == save_n or dest_n.startswith(save_n + os.sep):
        raise ValueError("보관 위치가 저장폴더 안입니다(로컬 폴더여야 합니다)")
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    shutil.move(src, dest)
    return dest


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


# --------------------------------------------------------------------------
# Commonality 조사 경로  {저장폴더}/commonality/{호기}/{생성시간}/
# --------------------------------------------------------------------------
def commonality_root(save_dir: str) -> str:
    d = os.path.join(save_dir, COMMONALITY_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def commonality_run_dir(save_dir: str, machine: str, st: str | None = None) -> str:
    d = os.path.join(commonality_root(save_dir), _sanitize(machine), st or stamp())
    os.makedirs(d, exist_ok=True)
    return d


def commonality_staging(run_dir: str) -> str:
    d = os.path.join(run_dir, STAGING_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def commonality_form_path(run_dir: str, recipe: str, machine: str, st: str) -> str:
    return os.path.join(run_dir, f"양식_{_sanitize(recipe)}_{_sanitize(machine)}_{st}.xlsx")


def commonality_result_path(run_dir: str, recipe: str, machine: str, st: str) -> str:
    return os.path.join(run_dir, f"조사_{_sanitize(machine)}_{_sanitize(recipe)}_{st}.xlsx")


def list_commonality_results(save_dir: str) -> list[str]:
    """저장폴더 아래 모든 호기 결과 엑셀(조사_*.xlsx) 경로 — 최신순."""
    root = os.path.join(save_dir, COMMONALITY_DIR)
    if not os.path.isdir(root):
        return []
    out = []
    for machine in os.listdir(root):
        mdir = os.path.join(root, machine)
        if not os.path.isdir(mdir):
            continue
        for st in os.listdir(mdir):
            run = os.path.join(mdir, st)
            if not os.path.isdir(run):
                continue
            for f in os.listdir(run):
                if f.startswith("조사_") and f.lower().endswith(".xlsx"):
                    out.append(os.path.join(run, f))
    out.sort(key=lambda p: os.path.basename(p), reverse=True)
    return out


def commonality_compare_dir(save_dir: str) -> str:
    d = os.path.join(save_dir, COMMONALITY_COMPARE_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def commonality_compare_path(save_dir: str, st: str | None = None) -> str:
    return os.path.join(commonality_compare_dir(save_dir),
                        f"{COMMONALITY_COMPARE_PREFIX}_{st or stamp()}.xlsx")
