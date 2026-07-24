r"""장비 네트워크(\\IP\c$\Job) 수집기 — recipe_param_extractor_network_v3.py 이식.

절대 안전 규칙 (원본 보호):
  장비 경로의 원본 파일은 절대 수정/삭제/덮어쓰기/이름변경/이동하지 않는다.
  허용: 목록 조회, 읽기 열기, 로컬 staging 으로 복사. 금지: 그 외 전부.

접속 로그 관련 (IT 감사 대응):
  \\IP\c$ 는 관리공유라 회사 SIEM 에 접속이 기록될 수 있다. 탐색기 수동 접속과
  동일한 SMB 접속이지만, 자동화 빈도가 눈에 띄지 않도록:
    - 장비 1대씩 순차 접속, 작업 후 즉시 net use /delete
    - \Job 하위만 접근(전역 재귀 탐색 금지)
    - 파일 복사 간 COPY_DELAY_SEC 지연
    - use_net_use=False 모드: 탐색기에서 이미 연결한 세션을 그대로 사용(수동과 동일)

GUI 와의 결합을 피하기 위해 선택(chooser) 은 콜백으로 주입한다:
    chooser(kind, title, items, multi) -> 선택 항목(리스트) 또는 None(취소)
    kind: "job" | "setup" | "recipe"
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

COPY_DELAY_SEC = 0.10
# RTP.txt 도 함께 복사한다 — 변환 계수 자동 추정(coef_detector)에 사용.
# ActiveScenarioOptics.ini(신 SW 만 존재) — 현재 스캔된 Scan2d optic 지정. 있을 때만 복사.
FIXED_FILES = ["GlobalRTP.ini", "OpticPreset.ini", "RTP.txt", "ActiveScenarioOptics.ini"]
LOG_NAME = "_수집로그.txt"


def is_windows() -> bool:
    return sys.platform.startswith("win")


class UserCancelled(RuntimeError):
    pass


# --------------------------------------------------------------------------
# net use 연결 (Windows 전용, 비밀번호는 메모리에만)
# --------------------------------------------------------------------------
def connect_admin_share(ip: str, username: str, password: str) -> str:
    share = rf"\\{ip}\c$"
    cmd = ["net", "use", share, "*", f"/user:{username}", "/persistent:no"]
    result = subprocess.run(cmd, input=password + "\n", text=True,
                            capture_output=True, shell=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"net use 연결 실패: {ip}\n{result.stdout}\n{result.stderr}")
    return share


def disconnect_admin_share(ip: str) -> None:
    share = rf"\\{ip}\c$"
    subprocess.run(["net", "use", share, "/delete", "/y"],
                   text=True, capture_output=True, shell=False)


def split_ips(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,;\s]+", str(text or "").strip()) if x.strip()]


# --------------------------------------------------------------------------
# 폴더 트리 판독 (읽기 전용)
# --------------------------------------------------------------------------
def list_dirs(path: Path) -> list[Path]:
    try:
        return sorted([p for p in path.iterdir() if p.is_dir()],
                      key=lambda x: x.name.lower())
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"폴더 목록을 읽지 못했습니다: {path}\n{e}")


def find_setup_candidates(job_folder: Path) -> list[tuple[Path, Path]]:
    """Job 폴더 아래에서 (Setup 폴더, Recipes 폴더) 후보를 찾는다.
    선택한 Job 폴더 하위 2단계까지만 — c$ 전역 재귀 탐색 금지."""
    candidates = []
    direct = job_folder / "Recipes"
    if direct.is_dir():
        candidates.append((job_folder, direct))
    for child in list_dirs(job_folder):
        r = child / "Recipes"
        if r.is_dir():
            candidates.append((child, r))
    if not candidates:
        for level1 in list_dirs(job_folder):
            for level2 in list_dirs(level1):
                r = level2 / "Recipes"
                if r.is_dir():
                    candidates.append((level2, r))
    return candidates


# --------------------------------------------------------------------------
# 키워드/계획 기반 자동 선택 (2대째부터 자동화)
# --------------------------------------------------------------------------
def norm_match(text: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", "", str(text or "").lower())


def contains_keyword(name: str, keyword: str) -> bool:
    return bool(keyword) and norm_match(keyword) in norm_match(name)


def auto_detect_job_keyword(job_name: str) -> str:
    """Job 폴더명에서 재사용 키워드(PI3/RDL4 등) 추출. 못 찾으면 ''."""
    text = str(job_name or "")
    for pat in (r"PI\s*\d+", r"RDL\s*\d+"):
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return re.sub(r"\s+", "", m.group(0)).upper()
    return ""


def match_by_keyword(items: list[Path], keyword: str) -> list[Path]:
    if not keyword:
        return []
    return [p for p in items if contains_keyword(p.name, keyword)]


def level_folder_match(folder_name: str, level: str) -> bool:
    """레벨(레시피)명의 **모든 단어 토큰**이 폴더명 안에 있으면 매칭(순서 무관).
    예: level='Enhanced PI3' ↔ 'R_TB500_LIVE_PI3 - Enhanced' → 참(enhanced·pi3 둘 다 포함).
    'Enhanced PI2' ↔ 위 폴더 → 거짓(pi2 없음)."""
    nn = re.sub(r"[^a-z0-9]", "", str(folder_name).lower())
    toks = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in re.split(r"\s+", str(level))]
    toks = [t for t in toks if t]
    return bool(toks) and all(t in nn for t in toks)


def match_recipes_by_names(recipe_dirs: list[Path],
                           names: list[str]) -> tuple[list[Path], list[str]]:
    """계획된 Recipe 폴더명(정확 일치 → 느슨한 포함 매칭)으로 선택.
    반환: (선택된 폴더, 매칭 실패 이름)."""
    by_name = {p.name: p for p in recipe_dirs}
    selected, missing = [], []
    for name in names:
        if name in by_name:
            selected.append(by_name[name])
            continue
        loose = [p for p in recipe_dirs
                 if contains_keyword(p.name, name) or contains_keyword(name, p.name)]
        if len(loose) == 1:
            selected.append(loose[0])
        else:
            missing.append(name)
    return selected, missing


@dataclass
class CollectPlan:
    """첫 장비에서 확정한 선택을 다음 장비에 재사용하기 위한 계획."""
    job_keyword: str = ""
    job_name: str = ""
    setup_name: str = ""
    recipe_names: list[str] = field(default_factory=list)
    # 레시피(레벨)별 폴더 매칭 재사용: {레벨: [폴더명]} (복수 레시피 수집용)
    recipe_map: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# 복사 대상 계획 + 읽기전용 복사
# --------------------------------------------------------------------------
def plan_files(recipe_dirs: list[Path]) -> list[tuple[Path, str, str]]:
    """선택된 Recipe 폴더들 → [(원본경로, 레시피명, 저장파일명)].
    고정명 2종 + Zones/*.ini 만 — extractor 와 동일."""
    planned = []
    for recipe_dir in recipe_dirs:
        for fixed in FIXED_FILES:
            p = recipe_dir / fixed
            if p.is_file():
                planned.append((p, recipe_dir.name, fixed))
        zones = recipe_dir / "Zones"
        if zones.is_dir():
            for p in sorted(zones.glob("*.ini"), key=lambda x: x.name.lower()):
                # Zones 하위구조 보존(파서가 폴더 바로 아래 .ini 는 고정2만 읽음).
                planned.append((p, recipe_dir.name, f"Zones/{p.name}"))
    return planned


def _sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", str(name)).strip().strip(".") or "item"


def _assert_local_write_target(path: Path) -> None:
    """안전장치: 쓰기 대상(staging)은 반드시 로컬이어야 한다.
    네트워크(UNC `\\\\server\\...` 또는 `//`) 경로면 거부해 **장비 원본을 보호**한다."""
    s = str(path)
    if s.startswith("\\\\") or s.startswith("//"):
        raise RuntimeError(
            "안전장치: 네트워크(UNC) 경로에는 절대 쓰지 않습니다(장비 원본 보호).\n"
            f"쓰기 대상이 로컬이어야 합니다: {path}")


def copy_planned(planned: list[tuple[Path, str, str]], staging_root: Path,
                 header_lines: list[str] | None = None) -> tuple[int, Path]:
    """계획 목록을 staging 으로 복사(원본 읽기 전용) + 로그 기록.
    반환: (복사 개수, 로그 경로)."""
    staging_root = Path(staging_root)
    _assert_local_write_target(staging_root)          # 원본(네트워크)에 쓰기 원천 차단
    staging_root.mkdir(parents=True, exist_ok=True)
    log_path = staging_root / LOG_NAME
    copied = 0
    with log_path.open("w", encoding="utf-8") as log:
        log.write("READ ONLY COPY LOG\n")
        log.write(f"When={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        for line in header_lines or []:
            log.write(line.rstrip("\n") + "\n")
        for src, recipe_name, dest_name in planned:
            dest_dir = staging_root / _sanitize(recipe_name)
            dest = dest_dir / dest_name              # dest_name 에 'Zones/' 가 있을 수 있음
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                stem, suffix = dest.stem, dest.suffix
                n = 2
                while (dest.parent / f"{stem}_{n}{suffix}").exists():
                    n += 1
                dest = dest.parent / f"{stem}_{n}{suffix}"
            # READ-ONLY SOURCE ACCESS: 원본은 읽기만, 쓰기는 로컬 dest 에만.
            # 원본과 동일 경로 덮어쓰기 금지(이중 안전장치).
            if Path(src).resolve() == dest.resolve():
                raise RuntimeError(f"안전장치: 원본과 동일 경로에 쓰기 금지: {src}")
            shutil.copy2(src, dest)                    # src 는 읽기만, dest(로컬)에만 씀
            copied += 1
            log.write(f"COPIED: {src} -> {dest}\n")
            if COPY_DELAY_SEC > 0:
                time.sleep(COPY_DELAY_SEC)
    return copied, log_path


# --------------------------------------------------------------------------
# 장비 1대 수집 (chooser 콜백 주입 — GUI/테스트에서 선택 방식 결정)
# --------------------------------------------------------------------------
def collect_equipment(ip: str, staging_root: Path, chooser,
                      username: str = "amkor", password: str | None = None,
                      use_net_use: bool = True,
                      plan: CollectPlan | None = None,
                      job_root_override: Path | None = None,
                      confirm=None,
                      target_levels: list[str] | None = None,
                      match_recipes=None,
                      ) -> tuple[list[tuple[Path, str, str]], CollectPlan, list]:
    """장비 1대에서 Recipe 파일 수집 계획을 세우고 staging 으로 복사.

    chooser(kind, title, items, multi) -> list[Path] | None(취소).
    plan 이 있으면 Job(키워드)/Setup/Recipe 를 자동 매칭하고, 애매하면 chooser 로.
    staging_root 는 경로 또는 콜러블(job_keyword) -> 경로 — 레시피 레벨(PI3/RDL4)이
    Job 선택 후에야 확정되므로, 레벨별 폴더 배치는 콜러블로 지연 결정한다.

    target_levels 를 주면(값 업데이트에서 고른 레시피들) **레시피(레벨)별로 장비
    폴더를 매칭**한다: match_recipes(all_recipe_dirs, target_levels) -> {레벨: [Path]}.
    각 레벨은 staging 아래 별도 하위폴더(레벨명)로 복사돼 파싱 시 그 레벨로 인식된다.

    job_root_override 는 테스트용(로컬 가짜 트리).
    반환: (복사된 계획 목록, 다음 장비용 CollectPlan, sources) —
      sources = [(staging_폴더, 레벨_또는_job키워드)] (호기별 소스, 파싱 default_level 로 사용).
    """
    connected = False
    if use_net_use:
        if not is_windows():
            raise RuntimeError("net use 접속은 Windows 에서만 지원됩니다.")
        connect_admin_share(ip, username, password or "")
        connected = True
    try:
        job_root = job_root_override or Path(rf"\\{ip}\c$\Job")
        if not job_root.exists():
            raise RuntimeError(f"Job 폴더가 없거나 접근할 수 없습니다: {job_root}")

        # 1) Job 폴더 목록
        job_dirs = list_dirs(job_root)

        # === 레시피(레벨)별 Job 폴더 매칭 모드 (복수 레시피) ===
        # 레시피 레벨(PI2/PI3/PI4 …)이 서로 **다른 Job 폴더**에 있으므로, Job 단계에서
        # 레벨마다 폴더를 매칭하고 그 Job 안의 Recipe 를 전부 수집한다.
        if target_levels and match_recipes is not None:
            mapping = None
            if plan and plan.recipe_map:              # 이전 장비 매칭 재사용(Job명 기준)
                m, ok = {}, True
                for lvl in target_levels:
                    sel, missing = match_recipes_by_names(
                        job_dirs, plan.recipe_map.get(lvl) or [])
                    if not sel or missing:
                        ok = False
                        break
                    m[lvl] = sel
                if ok:
                    mapping = m
            if mapping is None:
                mapping = match_recipes(job_dirs, list(target_levels))   # {레벨:[Job]}
                if not mapping:
                    raise UserCancelled("레시피↔Job 폴더 매칭이 취소되었습니다.")
            base = Path(staging_root("")) if callable(staging_root) else Path(staging_root)
            per_level, planned_all = [], []
            for lvl, jobs in mapping.items():
                recipe_dirs = []
                for job in jobs:
                    cands = find_setup_candidates(job)
                    if not cands:
                        continue
                    if len(cands) == 1:
                        recipes_root = cands[0][1]
                    else:
                        picked = chooser(
                            "setup", f"'{lvl}' · {job.name} — Setup/Recipes 선택",
                            [s for s, _ in cands], False)
                        if not picked:
                            raise UserCancelled("Setup 선택이 취소되었습니다.")
                        recipes_root = next(r for s, r in cands if s == picked[0])
                    recipe_dirs += list_dirs(recipes_root)
                pl = plan_files(recipe_dirs)
                if not pl:
                    continue
                per_level.append((lvl, base / _sanitize(lvl), pl,
                                  [j.name for j in jobs]))
                planned_all += pl
            if not planned_all:
                raise RuntimeError("복사할 설정 파일(GlobalRTP/OpticPreset/Zones)이 없습니다.")
            if confirm is not None and not confirm(planned_all):
                raise UserCancelled("사용자가 복사를 취소했습니다.")
            sources, recipe_map = [], {}
            for lvl, ldir, pl, jobnames in per_level:
                copy_planned(pl, ldir, header_lines=[
                    f"IP={ip}", f"JobRoot={job_root}", f"Level={lvl}",
                    f"Jobs={jobnames}"])
                sources.append((str(ldir), lvl))
                recipe_map[lvl] = jobnames
            new_plan = CollectPlan(job_keyword="", recipe_map=recipe_map)
            return planned_all, new_plan, sources

        # === 단일 모드(기존): Job 1개 → Setup → Recipe ===
        job_folder = None
        if plan and plan.job_keyword:
            hits = match_by_keyword(job_dirs, plan.job_keyword)
            if len(hits) == 1:
                job_folder = hits[0]
            elif hits:
                job_dirs = hits
        if job_folder is None:
            picked = chooser("job", f"Job 폴더 선택 ({job_root})", job_dirs, False)
            if not picked:
                raise UserCancelled("Job 폴더 선택이 취소되었습니다.")
            job_folder = picked[0]
        job_keyword = (plan.job_keyword if plan and plan.job_keyword
                       else auto_detect_job_keyword(job_folder.name))

        setup_candidates = find_setup_candidates(job_folder)
        if not setup_candidates:
            raise RuntimeError(f"Recipes 폴더를 찾지 못했습니다: {job_folder}")
        chosen = None
        if plan and plan.setup_name:
            for setup, recipes in setup_candidates:
                if setup.name == plan.setup_name:
                    chosen = (setup, recipes)
                    break
        if chosen is None and len(setup_candidates) == 1:
            chosen = setup_candidates[0]
        if chosen is None:
            picked = chooser("setup", "Setup/Recipes 후보 선택",
                             [s for s, _ in setup_candidates], False)
            if not picked:
                raise UserCancelled("Setup 선택이 취소되었습니다.")
            chosen = next((s, r) for s, r in setup_candidates if s == picked[0])
        setup_folder, recipes_root = chosen

        all_recipes = list_dirs(recipes_root)
        base = Path(staging_root(job_keyword)) if callable(staging_root) \
            else Path(staging_root)
        header = [
            f"IP={ip}", f"JobRoot={job_root}", f"JobFolder={job_folder}",
            f"SetupFolder={setup_folder}", f"RecipesRoot={recipes_root}",
        ]
        selected = None
        if plan and plan.recipe_names:
            sel, missing = match_recipes_by_names(all_recipes, plan.recipe_names)
            if not missing:
                selected = sel
        if selected is None:
            selected = chooser("recipe", f"Recipe 폴더 선택 ({recipes_root})",
                               all_recipes, True)
            if not selected:
                raise UserCancelled("Recipe 선택이 취소되었습니다.")

        planned = plan_files(selected)
        if not planned:
            raise RuntimeError("복사할 설정 파일(GlobalRTP/OpticPreset/Zones)이 없습니다.")
        if confirm is not None and not confirm(planned):
            raise UserCancelled("사용자가 복사를 취소했습니다.")
        copy_planned(planned, base, header_lines=header)
        new_plan = CollectPlan(
            job_keyword=job_keyword,
            job_name=job_folder.name, setup_name=setup_folder.name,
            recipe_names=[p.name for p in selected])
        return planned, new_plan, [(str(base), job_keyword)]
    finally:
        if connected:
            disconnect_admin_share(ip)
