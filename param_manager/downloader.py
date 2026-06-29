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
    """Recipe 하위에서 발견한 설정 1벌(다운로드 후보).

    variant = Recipe 아래 구분 경로. 실제 데이터에선 보통 'x5' / 'x20' (배율),
    구형/심층 구조에선 'Setup1/VHK-RDL4/07335326EWE7' 처럼 될 수 있다.
    이 variant 가 프로그램의 Recipe 변형(PI/PI_bubble, x5/x20)에 대응한다.
    config_dir = RTP.txt/OpticPreset.ini/Zones 가 들어있는 폴더.
    """
    equipment: str
    recipe_name: str
    variant: str
    config_dir: Path
    modified_time: float = 0.0
    has_zones: bool = False
    has_rtp: bool = False
    has_optic: bool = False

    # 하위호환(수동 파싱이 채울 수 있음)
    setup: str = ""
    recipe_code: str = ""
    wafer: str = ""

    @property
    def label(self) -> str:
        from datetime import datetime
        ts = datetime.fromtimestamp(self.modified_time).strftime("%Y-%m-%d %H:%M") if self.modified_time else ""
        tags = [t for t, on in (("Zones", self.has_zones), ("RTP", self.has_rtp),
                                ("Optic", self.has_optic)) if on]
        return f"{self.variant or self.config_dir.name}  [{', '.join(tags) or '없음'}]  {ts}"


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
    """수동 입력 경로 → 후보. Scanresult 구조면 그걸로, 아니면 폴더명을 variant 로."""
    wd = Path(path_text)
    if not wd.exists() or not wd.is_dir():
        raise FileNotFoundError(f"경로가 없거나 폴더가 아닙니다: {wd}")
    z, r, o = _targets_in(wd)
    try:
        mt = wd.stat().st_mtime
    except OSError:
        mt = 0.0
    try:
        meta = parse_scanresult_path(path_text)
        variant = "/".join(x for x in (meta["setup"], meta["recipe_code"], meta["wafer"]) if x)
        return WaferCandidate(meta["equipment"], meta["recipe_name"], variant or wd.name,
                              wd, mt, z, r, o, meta["setup"], meta["recipe_code"], meta["wafer"])
    except ValueError:
        # Scanresult 구조가 아니면(예: ...\\TB500_RDL4 - Multi\\x20) 폴더명으로 추정
        recipe = wd.parent.name if wd.parent.name else ""
        return WaferCandidate(_equipment_of(wd), recipe, wd.name, wd, mt, z, r, o)


# --------------------------------------------------------------------------
# 자동 탐색 (구조 깊이에 유연 — x5/x20 직하부터 Setup/code/wafer 심층까지)
# --------------------------------------------------------------------------
_AOI_RE = re.compile(r"(?i)^AOI[-_]?\w+$")
_RECIPE_RE = re.compile(r"(?i)^TB500[_ ].+")


def _equipment_of(path: Path) -> str:
    """경로 조상 중 'AOI-xx' 형태 폴더명을 호기로 추정."""
    for parent in [path, *path.parents]:
        if _AOI_RE.match(parent.name):
            return parent.name
    return ""


def _has_target_dir(d: Path) -> bool:
    z, r, o = _targets_in(d)
    return z or r or o


def _find_recipe_dirs(root: Path, recipes: list[str] | None, max_depth: int = 4) -> list[Path]:
    """root 아래에서 Recipe 폴더(지정 목록 또는 TB500_* )를 깊이 제한 탐색."""
    wanted = set(recipes or [])
    found: list[Path] = []
    seen = set()

    def walk(d: Path, depth: int):
        if depth > max_depth:
            return
        try:
            entries = [p for p in d.iterdir() if p.is_dir()]
        except OSError:
            return
        for p in entries:
            is_recipe = (p.name in wanted) or (not wanted and _RECIPE_RE.match(p.name)) \
                or (_RECIPE_RE.match(p.name) is not None)
            if is_recipe and p not in seen:
                seen.add(p)
                found.append(p)
            else:
                walk(p, depth + 1)
    walk(root, 0)
    return found


def _find_config_dirs(recipe_dir: Path, max_depth: int = 4) -> list[tuple[str, Path]]:
    """Recipe 폴더 아래에서 RTP/Optic/Zones 를 직접 가진 폴더(변형)들을 찾는다.
    반환: [(variant_label, dir)]. variant = recipe_dir 기준 상대경로(예: 'x5')."""
    out: list[tuple[str, Path]] = []

    def walk(d: Path, depth: int):
        if depth > max_depth:
            return
        if _has_target_dir(d):
            rel = d.relative_to(recipe_dir)
            out.append((str(rel) if str(rel) != "." else d.name, d))
            return  # 대상 폴더를 찾으면 그 아래로 더 내려가지 않음
        try:
            subs = [p for p in d.iterdir() if p.is_dir() and p.name.lower() != TARGET_FOLDER_NAME.lower()]
        except OSError:
            return
        for p in subs:
            walk(p, depth + 1)

    # Recipe 폴더 자체가 바로 대상일 수도, 하위(x5/x20 등)일 수도
    if _has_target_dir(recipe_dir):
        out.append((recipe_dir.name, recipe_dir))
    else:
        try:
            for p in (x for x in recipe_dir.iterdir() if x.is_dir()):
                walk(p, 1)
        except OSError:
            pass
    return out


def find_wafer_candidates(recipe_dir: Path, equipment: str, recipe_name: str) -> list[WaferCandidate]:
    out: list[WaferCandidate] = []
    for variant, d in _find_config_dirs(recipe_dir):
        z, r, o = _targets_in(d)
        try:
            mt = d.stat().st_mtime
        except OSError:
            mt = 0.0
        out.append(WaferCandidate(equipment, recipe_name, variant, d, mt, z, r, o))
    out.sort(key=lambda c: (c.variant.lower(), -c.modified_time))
    return out


def discover(root_text: str, recipes: list[str] | None = None) -> dict[str, list[WaferCandidate]]:
    """호기/상위 경로 → {recipe_name: [후보(변형)들...]}.

    - Scanresult 폴더가 있으면 그 아래를, 없으면 입력 경로 자체를 기준으로 탐색.
    - Recipe 아래의 x5/x20 같은 변형을 각각 후보로 잡는다(구조 깊이에 유연).
    """
    root = Path(root_text)
    # Scanresult 가 바로 아래 있으면 사용(구형 구조 호환)
    sr = root / "Scanresult"
    if sr.is_dir():
        root = sr
    if not root.exists():
        raise FileNotFoundError(f"경로가 없습니다: {root}")
    equipment = _equipment_of(root) or root.name
    result: dict[str, list[WaferCandidate]] = {}
    for recipe_dir in _find_recipe_dirs(root, recipes):
        cands = find_wafer_candidates(recipe_dir, equipment, recipe_dir.name)
        if cands:
            result.setdefault(recipe_dir.name, []).extend(cands)
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
    base = download_root / safe_name(cand.equipment) / safe_name(cand.recipe_name)
    for part in str(cand.variant).replace("\\", "/").split("/"):
        if part and part != ".":
            base = base / safe_name(part)
    return base


def copy_wafer(cand: WaferCandidate, download_root: Path,
               overwrite: bool = False, verify: bool = False) -> dict:
    """선택된 설정폴더의 대상만 복사. 복사 결과/목적지 폴더 반환."""
    download_root = Path(download_root)
    wafer_root = cand.config_dir
    if not wafer_root.exists() or not wafer_root.is_dir():
        raise FileNotFoundError(f"설정 폴더가 없습니다: {wafer_root}")
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
