"""장비 폴더(Scanresult)에서 파라미터 원본 파일을 안전하게 가져오는 모듈.

업로드된 두 다운로드 스크립트(수동 경로 지정형 / 호기 자동 탐색형)를 합쳐
GUI 에서 호출할 수 있는 함수형 계층으로 정리한 것.

설계 원칙(회사 보안 준수)
  - 원본은 읽기만 한다. 원본을 수정/삭제/이름변경하지 않는다.
  - 원본 폴더에는 아무것도 만들지 않는다(로그/임시파일 포함). 목적지에만 쓴다.
  - Wafer 폴더 전체를 복사하지 않는다. Zones 폴더 + RTP.txt + OpticPreset.ini 만.
  - 네트워크 접속 없음. 매핑된 공유드라이브(P:, O: 등)의 로컬 파일 복사뿐.

흐름
  1) discover(aoi_root): 호기 경로 → Recipe(PI2~4/RDL1~4)별 Wafer '후보 전체' 목록
     (사람이 후보 중 고를 수 있도록 1개만 고르지 않고 모두 반환)
  2) parse_manual_wafer(path): 후보에 없을 때 사람이 직접 넣은 Wafer 경로 파싱
  3) copy_wafer(cand, dest_root): 선택된 Wafer 에서 대상만 안전 복사 + 복사 경로 반환
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

# 다운로드 대상(Wafer 폴더 바로 아래)
TARGET_FOLDER_NAME = "Zones"
TARGET_FILES = ["RTP.txt", "OpticPreset.ini"]

# 자동 탐색 대상 Recipe (필요 시 사용자가 추가/수정 가능하도록 모듈 변수로 노출)
TARGET_RECIPE_NAMES = [
    "TB500_PI2 - Multi",
    "TB500_PI3 - Multi",
    "TB500_PI4 - Multi",
    "TB500_RDL1 - Multi",
    "TB500_RDL2 - Multi",
    "TB500_RDL3 - Multi",
    "TB500_RDL4 - Multi",
]


# --------------------------------------------------------------------------
# 데이터 구조
# --------------------------------------------------------------------------
@dataclass
class WaferCandidate:
    """Recipe 하위에서 발견한 Wafer 1개(다운로드 후보)."""
    equipment: str
    recipe_name: str
    setup: str
    recipe_code: str
    wafer: str
    wafer_dir: Path
    modified_time: float = 0.0
    has_zones: bool = False
    has_rtp: bool = False
    has_optic: bool = False

    @property
    def label(self) -> str:
        from datetime import datetime
        ts = ""
        if self.modified_time:
            ts = datetime.fromtimestamp(self.modified_time).strftime("%Y-%m-%d %H:%M")
        tags = []
        if self.has_zones:
            tags.append("Zones")
        if self.has_rtp:
            tags.append("RTP")
        if self.has_optic:
            tags.append("Optic")
        return f"{self.wafer}  [{', '.join(tags) or '없음'}]  {ts}  ({self.setup}/{self.recipe_code})"


# --------------------------------------------------------------------------
# 경로 유틸
# --------------------------------------------------------------------------
def safe_name(text: str) -> str:
    """Windows 폴더명 금지문자를 '_' 로. (목적지 폴더 생성용; 원본명 불변)"""
    if not text:
        return "_UNKNOWN_"
    return re.sub(r'[<>:"/\\|?*]', "_", text)


def split_pasted_windows_paths(text: str) -> list[str]:
    """한 줄/여러 줄로 붙여넣은 Windows 경로들을 드라이브문자 기준으로 분리."""
    if not text:
        return []
    text = text.strip()
    normalized = re.sub(r'(?<!^)(?=[A-Za-z]:\\)', '\n', text)
    out = []
    for line in normalized.splitlines():
        line = line.strip().strip('"').strip("'")
        if line:
            out.append(line)
    return out


def get_scanresult_root(aoi_root_text: str) -> Path:
    """호기 경로 → Scanresult 경로. 이미 Scanresult 면 그대로."""
    aoi_root = Path(aoi_root_text)
    root = aoi_root if aoi_root.name.lower() == "scanresult" else aoi_root / "Scanresult"
    if not root.exists():
        raise FileNotFoundError(f"Scanresult 경로가 없습니다: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Scanresult 경로가 폴더가 아닙니다: {root}")
    return root


def parse_scanresult_path(path_text: str) -> dict:
    """수동 입력된 Wafer 경로를 'Scanresult' 기준으로 파싱."""
    win = PureWindowsPath(path_text)
    parts = list(win.parts)
    lower = [p.lower() for p in parts]
    if "scanresult" not in lower:
        raise ValueError(f"Scanresult 폴더를 찾을 수 없습니다: {path_text}")
    i = lower.index("scanresult")
    equipment = parts[i - 1] if i - 1 >= 0 else ""
    recipe_name = parts[i + 1] if len(parts) > i + 1 else ""
    setup = parts[i + 2] if len(parts) > i + 2 else ""
    recipe_code = parts[i + 3] if len(parts) > i + 3 else ""
    wafer = parts[i + 4] if len(parts) > i + 4 else ""
    if not all([equipment, recipe_name, setup, recipe_code, wafer]):
        raise ValueError(f"필수 경로 구조가 부족합니다: {path_text}")
    return {"equipment": equipment, "recipe_name": recipe_name, "setup": setup,
            "recipe_code": recipe_code, "wafer": wafer}


def _targets_in(wafer_dir: Path) -> tuple[bool, bool, bool]:
    return ((wafer_dir / TARGET_FOLDER_NAME).is_dir(),
            (wafer_dir / "RTP.txt").is_file(),
            (wafer_dir / "OpticPreset.ini").is_file())


def parse_manual_wafer(path_text: str) -> WaferCandidate:
    """수동 입력 Wafer 경로 → 후보 객체(존재/대상 확인 포함)."""
    meta = parse_scanresult_path(path_text)
    wd = Path(path_text)
    if not wd.exists() or not wd.is_dir():
        raise FileNotFoundError(f"Wafer 경로가 없거나 폴더가 아닙니다: {wd}")
    z, r, o = _targets_in(wd)
    try:
        mt = wd.stat().st_mtime
    except OSError:
        mt = 0.0
    return WaferCandidate(meta["equipment"], meta["recipe_name"], meta["setup"],
                          meta["recipe_code"], meta["wafer"], wd, mt, z, r, o)


# --------------------------------------------------------------------------
# 자동 탐색
# --------------------------------------------------------------------------
def find_wafer_candidates(recipe_root: Path, equipment: str, recipe_name: str) -> list[WaferCandidate]:
    """Recipe 폴더 아래 Setup→RecipeCode→Wafer 3단계만 훑어 후보 수집(전체 rglob 안 함)."""
    out: list[WaferCandidate] = []
    if not recipe_root.exists() or not recipe_root.is_dir():
        return out
    for setup_dir in recipe_root.iterdir():
        if not setup_dir.is_dir():
            continue
        for code_dir in setup_dir.iterdir():
            if not code_dir.is_dir():
                continue
            for wafer_dir in code_dir.iterdir():
                if not wafer_dir.is_dir():
                    continue
                z, r, o = _targets_in(wafer_dir)
                if not (z or r or o):
                    continue
                try:
                    mt = wafer_dir.stat().st_mtime
                except OSError:
                    mt = 0.0
                out.append(WaferCandidate(equipment, recipe_name, setup_dir.name,
                                          code_dir.name, wafer_dir.name, wafer_dir, mt, z, r, o))
    # 최신순(사람이 고르기 쉽게)
    out.sort(key=lambda c: c.modified_time, reverse=True)
    return out


def discover(aoi_root_text: str, recipes: list[str] | None = None) -> dict[str, list[WaferCandidate]]:
    """호기 경로 → {recipe_name: [후보...]} (각 Recipe 후보 전체, 최신순)."""
    recipes = recipes or TARGET_RECIPE_NAMES
    root = get_scanresult_root(aoi_root_text)
    equipment = root.parent.name
    result: dict[str, list[WaferCandidate]] = {}
    for recipe in recipes:
        result[recipe] = find_wafer_candidates(root / recipe, equipment, recipe)
    return result


# --------------------------------------------------------------------------
# 안전 복사
# --------------------------------------------------------------------------
def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def get_non_conflict_path(dst: Path) -> Path:
    if not dst.exists():
        return dst
    i = 1
    while True:
        cand = dst.parent / f"{dst.stem}_{i}{dst.suffix}"
        if not cand.exists():
            return cand
        i += 1


def copy_one_file(src: Path, dst: Path, overwrite: bool = False, verify: bool = False) -> dict:
    """원본 read-only, 목적지에 .part→replace 로 안전 복사."""
    if not src.is_file():
        raise FileNotFoundError(f"원본 파일이 아닙니다: {src}")
    before = sha256_file(src) if verify else None
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not overwrite:
        dst = get_non_conflict_path(dst)
    tmp = dst.with_name(dst.name + ".part")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(src, tmp)        # 원본은 읽기만, 목적지에만 씀
    if dst.exists() and overwrite:
        dst.unlink()
    tmp.replace(dst)
    if verify:
        if before != sha256_file(src):
            raise RuntimeError(f"원본 해시가 복사 전후 달라짐(확인 필요): {src}")
    return {"src": str(src), "dst": str(dst)}


def collect_target_items(wafer_root: Path) -> tuple[Path, list[Path]]:
    """Wafer 폴더에서 복사 대상만 수집(Zones 내부 전체 + RTP + Optic)."""
    zones = wafer_root / TARGET_FOLDER_NAME
    files: list[Path] = []
    if zones.is_dir():
        for p in zones.rglob("*"):
            if p.is_file():
                files.append(p)
    for name in TARGET_FILES:
        p = wafer_root / name
        if p.is_file():
            files.append(p)
    return zones, files


def dest_base_for(cand: WaferCandidate, download_root: Path) -> Path:
    return (download_root / safe_name(cand.equipment) / safe_name(cand.recipe_name)
            / safe_name(cand.setup) / safe_name(cand.recipe_code) / safe_name(cand.wafer))


def copy_wafer(cand: WaferCandidate, download_root: Path,
               overwrite: bool = False, verify: bool = False) -> dict:
    """선택된 Wafer 의 대상만 복사. 복사 결과/목적지 폴더 반환."""
    download_root = Path(download_root)
    wafer_root = cand.wafer_dir
    if not wafer_root.exists() or not wafer_root.is_dir():
        raise FileNotFoundError(f"Wafer 경로가 없습니다: {wafer_root}")
    dst_base = dest_base_for(cand, download_root)
    zones, files = collect_target_items(wafer_root)
    rows = []
    for src in files:
        if zones.is_dir() and zones in src.parents:
            dst = dst_base / src.relative_to(wafer_root)   # Zones 내부 구조 유지
        else:
            dst = dst_base / src.name
        rows.append(copy_one_file(src, dst, overwrite, verify))
    return {"dest": str(dst_base), "files": rows, "count": len(rows)}
