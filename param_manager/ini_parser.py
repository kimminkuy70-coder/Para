"""GlobalRTP.ini / OpticPreset.ini / Zones/*.ini 파서 — extractor(.py) 이식판.

recipe_param_extractor_network_v3.py 의 파싱부를 Para 스키마로 정규화해 이식.
RTP.txt 는 사용하지 않는다(2026-07 확정). 원본은 읽기만 한다.

스키마 매핑 (extractor → 기존 공용 파일):
    상위항목(ZoneName/Global/OpticPreset) → Zone   (Global→GlobalRTP, OpticPreset→LIGHT)
    KNOWN_DISPLAY_MAP 의 zone(섹션 표시명)  → Alg
    표시 Parameter                          → Parameter
    변환값(SCALE 등 적용)                    → 호기 열 값
raw 값/설정파일/섹션/키/변환방식은 ExtractRow 로 보존해 _EXTRACT_MAP 시트에 기록.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import rtp_parser

SCALE = 0.8452

# 파일명이 고정인 설정파일 → 상위항목
FIXED_FILE_TOP = {
    "globalrtp.ini": "Global",
    "opticpreset.ini": "OpticPreset",
}

# 상위항목 → 공용 파일 Zone 라벨 (기존 양식과 통일: 광학/광원은 LIGHT Zone)
TOP_TO_ZONE = {
    "Global": "GlobalRTP",
    "OpticPreset": "LIGHT",
}

# 확정된 PI3 표시 매핑(extractor 검증본): (상위항목, 섹션, 키) → (Alg, 표시명, 단위, 변환)
KNOWN_DISPLAY_MAP = {
    ("Global", "GLOBAL_RTP", "MaxFaultsPerWafer"): ("GlobalRTP", "Max Defects Per Wafer", "", "RAW"),
    ("Global", "GLOBAL_RTP", "MaxFaultsPerDie"): ("GlobalRTP", "Max Defects Per Die", "", "RAW"),
    ("Global", "GLOBAL_RTP", "MaxHistogramOffsetInPercent"): ("GlobalRTP", "Adaptive range [%]", "%", "RAW"),
    ("Global", "GLOBAL_RTP", "ApplyDieCalib"): ("GlobalRTP", "Apply Die Calib", "", "BOOL"),
    ("Global", "GLOBAL_RTP", "ReAlignFrame_Enable"): ("GlobalRTP", "ReAlign Frame", "", "BOOL"),
    ("Global", "GLOBAL_RTP", "ReAlignFrame_MaskedZone"): ("GlobalRTP", "ReAlign Frame Mask Zone", "", "RAW"),
    ("Global", "GLOBAL_RTP", "ReAlignFrame_Test_Mode"): ("GlobalRTP", "test mode cad realign", "", "BOOL"),
    ("Global", "GLOBAL_RTP", "ReAlignFrame_NGC_Sigma"): ("GlobalRTP", "ReAlignFrame NGC Sigma", "", "RAW"),
    ("Global", "GLOBAL_RTP", "DuplicateRange_Pix"): ("GlobalRTP", "Duplicate Range Pix", "pix", "RAW"),
    ("Global", "GLOBAL_RTP", "DuplicateRange_um"): ("GlobalRTP", "Duplicate Range um", "um", "RAW"),
    ("Global", "GLOBAL_RTP", "EDC_Model_Activation"): ("GlobalRTP", "EDC Model Activation", "", "BOOL"),
    ("Global", "GLOBAL_RTP", "ADC_Model_Activation"): ("GlobalRTP", "ADC Model Activation", "", "BOOL"),
    ("Global", "GLOBAL_RTP", "SkipDefectsInCoplanarity"): ("GlobalRTP", "Skip Defects In Coplanarity", "", "BOOL"),

    ("*", "Surface", "BrightArea"): ("Surface", "Min Defect Area - Bright (area, µ)", "area, µ", "AREA_0.8452^2"),
    ("*", "Surface", "BrightDiameter"): ("Surface", "Min Defect Width - Bright", "µ", "LINEAR_0.8452"),
    ("*", "Surface", "BrightLength"): ("Surface", "Min Defect Length - Bright (µ)", "µ", "LINEAR_0.8452"),
    ("*", "Surface", "High_Delta"): ("Surface", "Contrast Delta - Bright", "", "RAW"),
    ("*", "Surface", "DarkArea"): ("Surface", "Min Defect Area - Dark (area, µ)", "area, µ", "AREA_0.8452^2"),
    ("*", "Surface", "DarkDiameter"): ("Surface", "Min Defect Width - Dark", "µ", "LINEAR_0.8452"),
    ("*", "Surface", "DarkLength"): ("Surface", "Min Defect Length - Dark (µ)", "µ", "LINEAR_0.8452"),
    ("*", "Surface", "Low_Delta"): ("Surface", "Contrast Delta - Dark", "", "RAW"),
    ("*", "Surface", "ClusterArea"): ("Surface", "Clustering Candidate Area (area, µ)", "area, µ", "AREA_0.8452^2"),
    ("*", "Surface", "ClusterDiameter"): ("Surface", "Clustering Candidate Diameter (µ)", "µ", "LINEAR_0.8452"),
    ("*", "Surface", "ClusterDistance"): ("Surface", "Clustering Distance (µ)", "µ", "LINEAR_0.8452"),
    ("*", "Surface", "IsolatedZone"): ("Surface", "Isolated Zone", "", "BOOL"),
    ("*", "Surface", "EdgeUncert_Bright"): ("Surface", "Bright Uncertainty", "", "RAW"),
    ("*", "Surface", "EdgeUncert_Dark"): ("Surface", "Dark Uncertainty", "", "RAW"),
    ("*", "Surface", "Elongation"): ("Surface", "Elongation", "", "RAW"),
    ("*", "Surface", "RichEventsMinArea"): ("Surface", "Rich Events Min Area (area, µ)", "area, µ", "AREA_0.8452^2"),
    ("*", "Surface", "RichClusterMaxDistance"): ("Surface", "Rich Events Cluster - Max Distance (µ)", "µ", "LINEAR_0.8452"),
    ("*", "Surface", "RichClusterUnitePolarity"): ("Surface", "Rich Events Cluster Unite Polarities", "", "BOOL"),

    ("*", "Genesis", "BrightSeedTh"): ("Genesis", "Bright Sensitivity", "", "RAW"),
    ("*", "Genesis", "DarkSeedTh"): ("Genesis", "Dark Sensitivity", "", "RAW"),

    ("*", "*", "RegionId"): (None, "Wafer Region", "", "REGION"),
    ("*", "*", "Classify"): (None, "Classification", "", "CLASSIFY"),

    ("*", "Surface Feature Filter Width", "FilterType"): ("Surface Feature Filter Width", "Filter Type", "", "RAW"),
    ("*", "Surface Feature Filter Width", "LowValue"): ("Surface Feature Filter Width", "Low Value (µ)", "µ", "LINEAR_0.8452"),
    ("*", "Surface Feature Filter Width", "HighValue"): ("Surface Feature Filter Width", "High Value (µ)", "µ", "LINEAR_0.8452"),
    ("*", "Surface Feature Filter Area", "FilterType"): ("Surface Feature Filter Area", "Filter Type", "", "RAW"),
    ("*", "Surface Feature Filter Area", "LowValue"): ("Surface Feature Filter Area", "Low Value (area, µ)", "area, µ", "AREA_0.8452^2"),
    ("*", "Surface Feature Filter Area", "HighValue"): ("Surface Feature Filter Area", "High Value (area, µ)", "area, µ", "AREA_0.8452^2"),
    ("*", "Surface Feature Filter Contrast Average", "FilterType"): ("Surface Feature Filter Contrast Average", "Filter Type", "", "RAW"),
    ("*", "Surface Feature Filter Contrast Average", "LowValue"): ("Surface Feature Filter Contrast Average", "Low Value", "", "RAW"),
    ("*", "Surface Feature Filter Contrast Average", "HighValue"): ("Surface Feature Filter Contrast Average", "High Value", "", "RAW"),
}


# --------------------------------------------------------------------------
# 값 파싱/변환
# --------------------------------------------------------------------------
def parse_raw_value(text: str) -> Any:
    s = str(text).strip()
    try:
        if re.fullmatch(r"[-+]?\d+", s):
            return int(s)
        if re.fullmatch(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", s) or re.fullmatch(r"[-+]?\d+(?:[eE][-+]?\d+)", s):
            return float(s)
    except Exception:  # noqa: BLE001
        pass
    return s


def transform_value(raw_value: Any, transform: str) -> Any:
    """변환방식(RAW/BOOL/REGION/CLASSIFY/LINEAR/AREA)에 따라 표시값 계산."""
    t = (transform or "RAW").strip().upper()
    try:
        num = float(raw_value)
    except Exception:  # noqa: BLE001
        num = None
    if t == "BOOL":
        if num is None:
            return raw_value
        return "Checked" if int(round(num)) == 1 else "Unchecked"
    if t == "REGION":
        return "Default Region" if num is not None and int(round(num)) == 0 else raw_value
    if t == "CLASSIFY":
        if num is not None:
            n = int(round(num))
            if n == -1:
                return "-"
            if n == 28:
                return "28-B R Other"
        return raw_value
    if t == "LINEAR_0.8452":
        return round(num * SCALE, 6) if num is not None else raw_value
    if t in ("AREA_0.8452^2", "AREA_0.8452**2"):
        return round(num * SCALE * SCALE, 6) if num is not None else raw_value
    return raw_value


def lookup_display(top: str, section: str, param: str) -> tuple[str, str, str, str]:
    """(상위항목, 섹션, 키) → (Alg, 표시 Parameter, 단위, 변환방식)."""
    for key in [(top, section, param), ("*", section, param), ("*", "*", param)]:
        if key in KNOWN_DISPLAY_MAP:
            alg, display, unit, trans = KNOWN_DISPLAY_MAP[key]
            return alg or section, display, unit, trans
    alg = "GlobalRTP" if section == "GLOBAL_RTP" else section
    return alg, param.replace("_", " "), "", "RAW"


# --------------------------------------------------------------------------
# ini 파일 파싱
# --------------------------------------------------------------------------
def strip_comment(line: str) -> str:
    return line.split(";", 1)[0].strip()


def infer_top_item(file_path: Path, sections: dict) -> str:
    lower = file_path.name.lower()
    if lower in FIXED_FILE_TOP:
        return FIXED_FILE_TOP[lower]
    # 복사 시 중복 회피로 붙는 _2 접미사(GlobalRTP_2.ini 등)도 고정명으로 인식
    base = re.sub(r"_\d+$", "", file_path.stem.lower()) + file_path.suffix.lower()
    if base in FIXED_FILE_TOP:
        return FIXED_FILE_TOP[base]
    zone_name = sections.get("General", {}).get("ZoneName")
    if zone_name not in (None, ""):
        return str(zone_name)
    return file_path.stem.replace("_", " ").strip()


def parse_ini_sections(file_path: Path) -> dict[str, dict[str, Any]]:
    """ini → {섹션: {키: 값}}. extractor 와 동일 규칙(';' 주석, '\\_' 복원)."""
    sections: dict[str, dict[str, Any]] = {}
    current = None
    with file_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("[") and "]" in line:
                current = line[1:line.index("]")].replace("\\_", "_").strip()
                sections.setdefault(current, {})
                continue
            clean = strip_comment(line).replace("\\_", "_")
            if not clean or "=" not in clean or current is None:
                continue
            k, v = [x.strip() for x in clean.split("=", 1)]
            sections[current][k] = parse_raw_value(v)
    return sections


@dataclass
class ExtractRow:
    """파싱된 파라미터 1개 — Para 스키마 필드 + 재추출용 원본 메타."""
    zone: str            # 공용 파일 Zone (= 상위항목, Global→GlobalRTP 등)
    alg: str             # 공용 파일 Alg (= 표시 매핑의 섹션 표시명)
    param: str           # 공용 파일 Parameter (= 표시명)
    value: Any           # 표시값(변환 적용)
    unit: str = ""
    # ↓ _EXTRACT_MAP 보존용(값 재추출 키)
    src_file: str = ""   # 설정파일명 (GlobalRTP.ini / OpticPreset.ini / xxx.ini)
    section: str = ""    # 설정 Section
    key: str = ""        # 설정 Parameter(원본 키)
    raw: Any = None      # Raw Value
    transform: str = "RAW"
    source_path: str = ""


def parse_ini_file(file_path: Path) -> list[ExtractRow]:
    """설정파일 1개 → ExtractRow 목록."""
    sections = parse_ini_sections(file_path)
    top = infer_top_item(file_path, sections)
    zone = TOP_TO_ZONE.get(top, top)
    out: list[ExtractRow] = []
    for section, kv in sections.items():
        for key, raw in kv.items():
            alg, display, unit, trans = lookup_display(top, section, key)
            out.append(ExtractRow(
                zone=zone, alg=alg, param=display,
                value=transform_value(raw, trans), unit=unit,
                src_file=file_path.name, section=section, key=key,
                raw=raw, transform=trans, source_path=str(file_path)))
    return out


# --------------------------------------------------------------------------
# 폴더 스캔 (config 폴더 = GlobalRTP.ini/OpticPreset.ini/Zones 를 가진 폴더)
# --------------------------------------------------------------------------
def is_config_dir(d: Path) -> bool:
    return ((d / "GlobalRTP.ini").is_file() or (d / "OpticPreset.ini").is_file()
            or (d / "Zones").is_dir())


def config_ini_files(d: Path) -> list[Path]:
    """config 폴더의 파싱 대상 ini 목록.
    staging(평탄 복사)과 장비 원본(Zones 하위) 구조 둘 다 지원."""
    files = sorted([p for p in d.glob("*.ini") if p.is_file()],
                   key=lambda x: x.name.lower())
    zones = d / "Zones"
    if zones.is_dir():
        files += sorted([p for p in zones.glob("*.ini") if p.is_file()],
                        key=lambda x: x.name.lower())
    return files


def find_config_dirs(root: Path, max_depth: int = 6) -> list[Path]:
    out: list[Path] = []

    def walk(d: Path, depth: int):
        if depth > max_depth:
            return
        if is_config_dir(d):
            out.append(d)
            return                      # config 폴더 아래로는 더 안 내려감
        try:
            for p in sorted(d.iterdir()):
                if p.is_dir():
                    walk(p, depth + 1)
        except OSError:
            return
    walk(Path(root), 0)
    return out


_PI_LEVEL_RE = re.compile(r"(?i)PI\s*([1-9])")
_RDL_LEVEL_RE = re.compile(r"(?i)RDL\s*([1-9])")


def detect_level(text: str) -> tuple[str, str]:
    """이름 문자열에서 (layer, 레시피레벨) 추출. 예: 'R_TB500_LIVE_PI3 …' → (PI, PI3)."""
    m = _RDL_LEVEL_RE.search(text)
    if m:
        return "RDL", "RDL" + m.group(1)
    m = _PI_LEVEL_RE.search(text)
    if m:
        return "PI", "PI" + m.group(1)
    if re.search(r"(?i)(?<![A-Za-z])PI(?![A-Za-z0-9])", text):
        return "PI", "PI"
    return "", ""


def detect_variant(config_dir: Path, layer: str) -> str:
    """변형 판정 — 폴더명 우선, RDL 은 OpticPreset Scan2d Mag 폴백.
    라벨은 기존 양식과 통일: PI / PI-bubble / x5 / x20."""
    name = config_dir.name
    nm = re.sub(r"[^a-z0-9]", "", name.lower())
    if "bubble" in nm:
        return "PI-bubble"
    if re.fullmatch(r"x?\d+", nm):
        return "x" + re.sub(r"\D", "", nm)
    if layer == "PI":
        # PI / PI3 처럼 레벨 폴더 자체가 기본(비-bubble) 레시피인 경우
        if re.fullmatch(r"pi\d*", nm):
            return "PI"
        return ""
    mag = rtp_parser.detect_mag_from_optic(config_dir)
    return mag or ""


def detect_meta(config_dir: Path, default_level: str = "",
                default_equipment: str = "") -> dict:
    """폴더 경로에서 equipment/layer/레벨/변형 추정. default_* 는 수집 단계에서
    이미 알고 있는 값(IP→AOI, Job 키워드)을 우선 적용하기 위한 것."""
    joined = "/".join([config_dir.name] + [a.name for a in config_dir.parents])
    equip = default_equipment
    if not equip:
        m = rtp_parser._AOI_RE.search(joined)
        if m:
            equip = m.group(0).upper().replace("_", "-")
    layer = recipe = ""
    if default_level:
        layer = "RDL" if default_level.upper().startswith("RDL") else "PI"
        recipe = default_level.upper()
    else:
        layer, recipe = detect_level(joined)
    variant = detect_variant(config_dir, layer)
    if layer == "RDL" and not variant:
        variant = ""
    return {"equipment": equip, "layer": layer, "recipe": recipe, "mag": variant}


@dataclass
class ParsedConfig:
    """rtp_parser.ParsedConfig 와 동일 인터페이스(config_valid 재사용 가능)."""
    equipment: str
    layer: str
    recipe: str
    mag: str
    config_dir: Path
    rows: list[ExtractRow] = field(default_factory=list)


def scan_tree(root: str | Path, default_level: str = "",
              default_equipment: str = "") -> list[ParsedConfig]:
    """폴더트리 → config 폴더별 ParsedConfig (ini 소스 전용, RTP.txt 미사용)."""
    res: list[ParsedConfig] = []
    for cdir in find_config_dirs(Path(root)):
        meta = detect_meta(cdir, default_level, default_equipment)
        rows: list[ExtractRow] = []
        for f in config_ini_files(cdir):
            rows += parse_ini_file(f)
        res.append(ParsedConfig(meta["equipment"], meta["layer"], meta["recipe"],
                                meta["mag"], cdir, rows))
    return res


# --------------------------------------------------------------------------
# 통합표(피벗) — rtp_parser.build_pivot 과 같은 형태 + extract 메타 보존
# --------------------------------------------------------------------------
def build_pivot(configs: list[ParsedConfig]) -> tuple[list[dict], list[str]]:
    machines: list[str] = []
    table: dict[tuple, dict] = {}
    for cfg in configs:
        if cfg.equipment and cfg.equipment not in machines:
            machines.append(cfg.equipment)
        for r in cfg.rows:
            key = (cfg.layer, cfg.recipe, cfg.mag, r.zone, r.alg, r.param)
            ent = table.setdefault(key, {
                "unit": r.unit, "values": {}, "raws": {},
                "extract": {"src_file": r.src_file, "section": r.section,
                            "key": r.key, "transform": r.transform,
                            "source_path": r.source_path},
            })
            ent["values"][cfg.equipment] = r.value
            ent["raws"][cfg.equipment] = r.raw
    rows = []
    for (layer, recipe, mag, zone, alg, param), ent in table.items():
        rows.append({"layer": layer, "recipe": recipe, "mag": mag, "zone": zone,
                     "alg": alg, "param": param, "desc_en": "", "unit": ent["unit"],
                     "values": ent["values"], "raws": ent["raws"],
                     "extract": ent["extract"]})
    return rows, machines
