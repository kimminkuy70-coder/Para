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

# 변환 계수(픽셀→µ). 장비/레시피(변형)마다 다르므로 사용자가 양식 만들 때 고른다.
# 정확값(사용자 확정): 기본형 0.8456665875666588, 다른 배율 0.7696441409644141
# (장비 화면 'RTP {0.77}' 이 후자의 반올림 표기).
DEFAULT_SCALE = 0.8456665875666588
KNOWN_SCALES = [0.8456665875666588, 0.7696441409644141]
SCALE = DEFAULT_SCALE   # 하위호환 별칭(과거 코드/테스트에서 참조)

# ManReClassify.ini(Classification Editor) — 양식에서 고르는 값은 **Max Count 뿐**
# (사용자 확정 2026-08). 나머지 필드(Status/Priority/Color/단축키/Display/GrabImage/
# Verify/Extended/고객 Bin)는 manreclassify.py 에 뜻을 적어 두었고 양식에는 넣지 않는다.
# 코드가 수십 개라 기본은 전부 **사용=N** — 사람이 볼 것만 체크한다.
MANRE_ZONE = "Classification"
MANRE_ALG = "Max Count"

# 파일명이 고정인 설정파일 → 상위항목
FIXED_FILE_TOP = {
    "globalrtp.ini": "Global",
    "opticpreset.ini": "OpticPreset",
    # 장비 공용 분류 설정(c$\Bis\data\dds) — 수집기가 레시피 폴더로 복사해 온다.
    "manreclassify.ini": "ManReClassify",
}

# 상위항목 → 공용 파일 Zone 라벨 (기존 양식과 통일: 광학/광원은 LIGHT Zone)
TOP_TO_ZONE = {
    "Global": "GlobalRTP",
    "OpticPreset": "LIGHT",
    "ManReClassify": MANRE_ZONE,
}

# GlobalRTP Zone: 양식 초안에서 기본 사용=Y 로 둘 파라미터(표시명). 나머지는 N(검토용).
GLOBALRTP_KEEP = {"Max Defects Per Wafer", "Max Defects Per Die"}

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


def transform_value(raw_value: Any, transform: str, scale: float = DEFAULT_SCALE) -> Any:
    """변환방식(RAW/BOOL/REGION/CLASSIFY/LINEAR/AREA)에 따라 표시값 계산.
    LINEAR→×scale, AREA→×scale². scale 은 변형(레시피)마다 다를 수 있어 인자로 받는다."""
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
    if t.startswith("LINEAR"):        # LINEAR_* (계수는 인자 scale 사용)
        return round(num * scale, 6) if num is not None else raw_value
    if t.startswith("AREA"):          # AREA_*(면적: scale²)
        return round(num * scale * scale, 6) if num is not None else raw_value
    return raw_value


def label_transform(transform: str, scale: float) -> str:
    """변환방식 라벨에 **실제 사용한 계수**를 반영(KNOWN_DISPLAY_MAP의 0.8452 표기 대체).
    LINEAR/AREA 만 계수 표기, 나머지(RAW/BOOL/…)는 그대로."""
    t = (transform or "RAW").strip().upper()
    if t.startswith("LINEAR"):
        return f"LINEAR_{scale:.16g}"
    if t.startswith("AREA"):
        return f"AREA_{scale:.16g}^2"
    return transform


def scale_from_label(transform: str) -> float | None:
    """변환방식 라벨(예: 'LINEAR_0.845..' / 'AREA_0.770..^2')에서 계수 추출. 없으면 None.
    양식의 변환방식 열에 사람이 박아둔 계수를 값 업데이트가 그대로 재적용할 때 사용."""
    m = re.search(r"(?:LINEAR|AREA)[_\s]*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)",
                  str(transform or ""), flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _has_micron(name: str) -> bool:
    """파라미터(표시)명에 µ(마이크로) 표기가 있는가 — 변환 대상 판정용."""
    s = str(name)
    return "µ" in s or "μ" in s      # µ(U+00B5) / μ(U+03BC)


def resolve_transform(display: str, transform: str) -> str:
    """계수 변환 여부는 **표시명에 µ(마이크로)가 있는지**로 결정(사용자 규칙 2026-07).
    - BOOL/REGION/CLASSIFY 는 그대로(특수 변환).
    - µ 있으면 변환: 'area' 포함 시 AREA(면적), 아니면 LINEAR.
    - µ 없으면 RAW(변환 안 함) — 예: 'Min Defect Width - Bright'.
    """
    t = (transform or "RAW").strip().upper()
    if t in ("BOOL", "REGION", "CLASSIFY"):
        return transform
    if _has_micron(display):
        if t.startswith("AREA") or "area" in str(display).lower():
            return "AREA"
        return "LINEAR"
    return "RAW"


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
    use_default: bool = True   # 양식 초안에서 '사용' 기본값(False=N, 사람이 검토)


# OpticPreset.ini LIGHT/Scan2d 통일 (사용자 확정 2026-07)
#   - Scan2d 섹션(이름 [Scan2d] 또는 [Scan2d#]) 중 **KEEP 키를 가진 마지막(맨 아래)** =
#     최신(target). 그 섹션의 KEEP 9개만 사용=Y, 나머지·다른 섹션은 사용=N(검토용).
#   - '최신 Scan2d 이름'은 target 섹션의 'Alg' 키 값(없으면 섹션명). 합성 파라미터 행으로
#     추가하되 **첫 KEEP 행 바로 위**에 놓는다. alg 는 'Scan2d' 로 통일.
OPTIC_ALG = "Scan2d"
SCAN2D_LATEST_PARAM = "Scan2d 최신 항목 이름"
OPTIC_SCAN2D_KEEP = {
    "LightSrcDif_ColorFilter", "LightSrcDif2_ColorFilter", "LightSrcRef_ColorFilter",
    "LightSrcDif_NominalGL", "LightSrcDif2_NominalGL", "LightSrcRef_NominalGL",
    "LightSrcDif_NominalGL_On", "LightSrcDif2_NominalGL_On", "LightSrcRef_NominalGL_On",
}
_SCAN2D_SEC_RE = re.compile(r"(?i)^scan2d\d*$")   # [Scan2d] 또는 [Scan2d#]

# 신 SW 버전: 현재 스캔된 optic 을 ActiveScenarioOptics.ini 로 지정한다(사용자 확정 2026-07).
#   ScenarioName=Scan2d 항목의 OpticsName/OpticId 가 '지금 쓰는 Scan2d optic' 을 가리킨다.
#   이 파일이 있으면 그 값으로 OpticPreset.ini 의 해당 섹션을 골라 target 으로 삼고,
#   없으면(구 SW) 기존 방식(TDI/광원키/마지막 Scan2d)을 그대로 쓴다.
ACTIVE_SCENARIO_FILE = "ActiveScenarioOptics.ini"
_ACTIVE_SCAN2D_SCENARIO = "scan2d"                 # ScenarioName 매칭(대소문자 무시)
_OPTIC_ID_KEYS = ("OpticId", "OpticsId", "OpticID", "Id", "Guid", "OpticGUID", "OpticGuid")
_OPTIC_NAME_KEYS = ("OpticsName", "OpticName", "Name")

# 옵틱 이름 끝에 '복사 금지' 표시가 붙은 것은 **target 후보에서 뺀다**(2026-08 확정).
#   OpticPreset.ini 에는 리뷰·얼라인·clean reference 등 여러 역할의 optic 이 섞여
#   있고 순서가 역할과 무관하다. 장비 쪽에서 이 표시를 붙여 둔 optic 은 쓰면 안 되는
#   것이므로 '마지막 광원 섹션' 규칙에 걸려 잘못 뽑히지 않게 먼저 걸러낸다.
#   느낌표 개수·대소문자·앞뒤 공백은 무시한다(사람이 손으로 붙이는 표시라 흔들린다).
OPTIC_EXCLUDE_SUFFIX = "_@NEVER COPY THIS!!!!!"
_OPTIC_EXCLUDE_RE = re.compile(r"(?i)_@\s*NEVER\s+COPY\s+THIS\s*!*\s*$")


def optic_excluded(section: str, kv: dict | None = None) -> bool:
    """이 optic 섹션이 '복사 금지' 표시된 것인가(= target 후보에서 제외).
    표시는 섹션 이름에 붙는 게 보통이지만, 이름 키(OpticsName/Name/Alg)에만
    붙어 있는 경우도 있어 함께 본다."""
    names = [section]
    if kv:
        names += [kv.get(k) for k in _OPTIC_NAME_KEYS] + [kv.get("Alg")]
    return any(_OPTIC_EXCLUDE_RE.search(str(n).strip())
               for n in names if n not in (None, ""))


def _optic_candidates(sections: dict) -> dict:
    """'복사 금지' 표시를 뺀 optic 섹션들(순서 유지). 전부 빠지면 빈 dict."""
    return {s: kv for s, kv in (sections or {}).items() if not optic_excluded(s, kv)}


OPTIC_OTHER_SUFFIX = " (미선택)"          # target 이 아닌 optic 의 Alg 표기


def _other_optic_alg(section: str) -> str:
    """target 이 아닌 optic 섹션의 Alg 표기 = 섹션 이름 그대로.

    단 이름이 하필 `Scan2d`(=`OPTIC_ALG`) 면 **target 행과 Alg 가 같아져 피벗에서
    한 줄로 합쳐진다**(값이 서로 덮어써짐). 그때만 꼬리표를 붙여 갈라 놓는다.
    """
    if str(section).strip().lower() == OPTIC_ALG.lower():
        return f"{section}{OPTIC_OTHER_SUFFIX}"
    return section


RECIPES_INFO_FILE = "RecipesInfo.ini"       # 다중 레시피(2개+) 스캔 폴더에만 존재


def read_recipes_info(config_dir) -> list[dict] | None:
    """RecipesInfo.ini → [{index, name, prefix}] (index 순). 레시피가 2개 이상일 때만
    반환(다중 레시피 = 양식 여러 개), 1개 이하/파일없음이면 None.
    prefix: 인덱스1 = ''(무접두 파일), 인덱스 N(>=2) = 'RecipeN-'(예 Recipe2-OpticPreset.ini)."""
    for name in (RECIPES_INFO_FILE, RECIPES_INFO_FILE.lower()):
        p = Path(config_dir) / name
        if p.is_file():
            try:
                sections = parse_ini_sections(p)
            except Exception:  # noqa: BLE001
                return None
            recs = []
            for sec, kv in sections.items():
                m = re.match(r"(?i)^recipe-(\d+)$", str(sec).strip())
                if not m:
                    continue
                idx = int(m.group(1))
                nm = str(kv.get("Name", "") or "").strip() or f"Recipe{idx}"
                recs.append({"index": idx, "name": nm,
                             "prefix": "" if idx == 1 else f"Recipe{idx}-"})
            recs.sort(key=lambda r: r["index"])
            return recs if len(recs) >= 2 else None
    return None


def read_active_scan2d(config_dir, prefix: str = "") -> tuple[str, str] | None:
    """ActiveScenarioOptics.ini 에서 ScenarioName=Scan2d 항목의 (OpticsName, OpticId).
    파일이 없거나(구 SW) 유효한 Scan2d 항목이 없으면 None. 여러 개면 마지막(최신) 유효 항목.
    prefix 를 주면 `{prefix}ActiveScenarioOptics.ini`(다중 레시피 Recipe N) 를 읽는다."""
    cands = ([f"{prefix}{ACTIVE_SCENARIO_FILE}"] if prefix
             else [ACTIVE_SCENARIO_FILE, ACTIVE_SCENARIO_FILE.lower()])
    for name in cands:
        p = Path(config_dir) / name
        if p.is_file():
            try:
                sections = parse_ini_sections(p)
            except Exception:  # noqa: BLE001
                return None
            hit = None
            for kv in sections.values():
                if str(kv.get("ScenarioName", "")).strip().lower() == _ACTIVE_SCAN2D_SCENARIO:
                    nm = str(kv.get("OpticsName", "") or "").strip()
                    oid = str(kv.get("OpticId", "") or "").strip()
                    if nm or oid:
                        hit = (nm, oid)            # 마지막 유효 항목 우선(최신)
            return hit
    return None


def _match_active_section(sections: dict, name: str, oid: str) -> str | None:
    """OpticPreset 섹션 중 ActiveScenarioOptics 의 OpticsName/OpticId 에 맞는 섹션.
    우선순위: 1) 섹션 이름 == OpticsName  2) 섹션 내 OpticId 키 == OpticId
              3) 섹션 내 Name/OpticsName 키 == OpticsName."""
    n = (name or "").strip().casefold()
    i = (oid or "").strip().casefold()
    if n:                                          # 1) 섹션명 == OpticsName
        for s in sections:
            if str(s).strip().casefold() == n:
                return s
    if i:                                          # 2) OpticId 키 매칭
        for s, kv in sections.items():
            for k in _OPTIC_ID_KEYS:
                v = kv.get(k)
                if v is not None and str(v).strip().casefold() == i:
                    return s
    if n:                                          # 3) Name/OpticsName 키 == OpticsName
        for s, kv in sections.items():
            for k in _OPTIC_NAME_KEYS:
                v = kv.get(k)
                if v is not None and str(v).strip().casefold() == n:
                    return s
    return None


def _pick_optic_target(sections: dict, active: tuple[str, str] | None = None) -> str | None:
    """최신(target) 섹션을 고른다(사용자 확정 2026-07):
    0순위 = **ActiveScenarioOptics.ini 의 Scan2d optic 매칭**(신 SW — active 주어질 때).
    1순위 = **CameraName=TDI 섹션 중 마지막**(광원 키 있으면 그 중 마지막).
    이름은 장비마다 다를 수 있어([Scan2d#]·[Engineer optic] 등) 이름이 아니라
    'TDI 카메라 + 광원 키를 가진 마지막 [섹션]' 으로 고른다. TDI 없으면 광원 키 마지막.

    **먼저 '복사 금지'(`_@NEVER COPY THIS!!!!!`) 표시된 optic 을 후보에서 뺀다**
    (2026-08 추가). 그 뒤 규칙은 종전과 완전히 같다.
    """
    sections = _optic_candidates(sections)
    if not sections:
        return None
    if active is not None:                         # 신 SW: 지정된 Scan2d optic 우선
        m = _match_active_section(sections, active[0], active[1])
        if m is not None:
            return m                               # 매칭되면 그 섹션이 target(권위)
        # 매칭 실패 → 아래 기존 방식으로 폴백(파일은 있으나 섹션 못 찾은 경우)
    names = list(sections)

    def _is_tdi(s):
        return str(sections[s].get("CameraName", "")).strip().upper() == "TDI"

    def _has_keep(s):
        return any(k in OPTIC_SCAN2D_KEEP for k in sections[s])

    # 1순위: CameraName=TDI 섹션 (광원 키 있으면 우선) 중 마지막
    tdi = [s for s in names if _is_tdi(s)]
    tdi_keep = [s for s in tdi if _has_keep(s)]
    if tdi_keep:
        return tdi_keep[-1]
    if tdi:
        return tdi[-1]
    # 2순위: 광원 키를 가진 마지막 섹션 — 이름 무관
    with_keep = [s for s in names if _has_keep(s)]
    if with_keep:
        return with_keep[-1]
    # 3순위(하위호환): Scan2d 이름 섹션 마지막
    scan = [s for s in names if _SCAN2D_SEC_RE.match(s)]
    if scan:
        return scan[-1]
    # 4순위: 그래도 없으면 마지막 섹션
    return names[-1]


def read_optic_mag(config_dir: Path, prefix: str = "") -> str:
    """OpticPreset.ini 의 **최신 Scan2d(target) 섹션 Mag 값**(예: '3.14') 반환.
    변환계수 키(호기+MAG)용 — 없으면 ''. OpticPreset 은 레시피(PI/PI-bubble)마다 다르다.
    prefix 를 주면 `{prefix}OpticPreset.ini`(다중 레시피 Recipe N) 를 읽는다."""
    opt = f"{prefix}OpticPreset.ini"
    cands = ([opt] if prefix else ("OpticPreset.ini", "opticpreset.ini"))
    for name in cands:
        p = Path(config_dir) / name
        if p.is_file():
            try:
                sections = parse_ini_sections(p)
            except Exception:  # noqa: BLE001
                return ""
            target = _pick_optic_target(sections, read_active_scan2d(config_dir, prefix))
            if target is not None:
                mag = sections[target].get("Mag")
                if mag not in (None, ""):
                    return str(mag).strip()
            # target 못 잡아도 아무 Scan2d 의 Mag('복사 금지' 표시는 여기서도 제외)
            for s, kv in _optic_candidates(sections).items():
                if _SCAN2D_SEC_RE.match(s) and kv.get("Mag") not in (None, ""):
                    return str(kv["Mag"]).strip()
            break
    # 하위 폴더(Zones 등이 아닌 실제 OpticPreset)도 탐색
    hits = sorted(Path(config_dir).rglob(opt))
    if hits and hits[0] != Path(config_dir) / opt:
        return read_optic_mag(hits[0].parent, prefix)
    return ""


def _parse_optic(file_path: Path, sections: dict, zone: str = "LIGHT",
                 active: tuple[str, str] | None = None,
                 scale: float = DEFAULT_SCALE) -> list[ExtractRow]:
    """OpticPreset.ini 전용 — 최신 Scan2d 통일 + 합성 행(첫 KEEP 위) + 나머지 N.
    active = ActiveScenarioOptics.ini 의 (OpticsName, OpticId) — 있으면 그 optic 을 target."""
    target = _pick_optic_target(sections, active)
    # 최신 이름: target 안 'Alg' 키 값 우선(원 요청: LIGHT의 Alg 값이 Scan2d#), 없으면 섹션명
    latest_name = ""
    if target is not None:
        latest_name = str(sections[target].get("Alg") or target)

    def _synth() -> ExtractRow:
        return ExtractRow(
            zone=zone, alg=OPTIC_ALG, param=SCAN2D_LATEST_PARAM, value=latest_name,
            unit="", src_file=file_path.name, section=target or "", key=SCAN2D_LATEST_PARAM,
            raw=latest_name, transform="RAW", source_path=str(file_path), use_default=True)

    out: list[ExtractRow] = []
    for section, kv in sections.items():
        # target 이 아닌 optic 섹션도 **목록에는 남긴다**(사용=N, 사용자 확정 2026-08).
        #   종전에는 이름이 [Scan2d]/[Scan2d3] 형인 것만 통째로 버렸는데, 옵틱 이름이
        #   자유로운 장비에서는 [Align optic] 같은 건 남고 [Scan2d1] 만 사라져
        #   **같은 '비선택 옵틱'인데 이름 규칙에 따라 보였다 안 보였다** 했다.
        #   이제 전부 보이고, 기본 체크(사용=Y)만 target 에 준다.
        is_target = (section == target)
        synth_done = False
        for key, raw in kv.items():
            if is_target and key == "Alg":
                continue                          # Alg 키는 합성행 값으로만 사용
            # 잡키(Id/ZWafer/FocusPosAboveChuck/CreationMeasure*/GUID)도 **버리지
            # 않는다**(사용자 확정 2026-08) — 양식에서 체크박스로 고를 수 있으므로
            # 파서가 미리 지우면 필요할 때 쓸 수가 없다. 대신 사용=N 으로만 둔다.
            keep = is_target and key in OPTIC_SCAN2D_KEEP
            if keep and not synth_done:            # 첫 KEEP 바로 위에 합성행
                out.append(_synth())
                synth_done = True
            alg = OPTIC_ALG if is_target else _other_optic_alg(section)
            # 변환 판정은 다른 파일과 동일한 규칙(표시명에 µ 있으면 변환).
            # OpticPreset 키는 표시명 매핑이 없어 대개 RAW 지만, 사람이 양식
            # 편집기의 '변환' 열에서 LINEAR/AREA 로 바꾸면 그 방식이
            # `_EXTRACT_MAP` 에 저장돼 **값 업데이트·commonality 결과 모두**
            # 계수가 적용된 값으로 채워진다(collate.collate_recipe).
            trans = resolve_transform(key, "RAW")
            out.append(ExtractRow(
                zone=zone, alg=alg, param=key,
                value=transform_value(raw, trans, scale), unit="",
                src_file=file_path.name, section=section, key=key, raw=raw,
                transform=trans, source_path=str(file_path), use_default=keep))
        if is_target and not synth_done and latest_name:   # KEEP 없으면 섹션 끝에
            out.append(_synth())
    return out


def _parse_manre(file_path: Path) -> list[ExtractRow]:
    """ManReClassify.ini → **Max Count 행만** ExtractRow 로.

    양식에서 고르는 건 '어떤 분류의 Max Count 를 볼지' 뿐이다(사용자 확정).
    나머지 필드(Status/Priority/Color/단축키/Display/GrabImage/Verify/Extended/
    고객 Bin)는 `manreclassify.py` 에 뜻을 적어 두었지만 양식에는 넣지 않는다.

    · 코드가 수십 개라 기본은 전부 **사용=N** — 사람이 볼 것만 체크한다.
    · Max Count **0 도 유효**하므로 값이 있으면 다 넣는다(빈 문자열만 뺀다).
    · 변환은 RAW — 개수라서 픽셀→µ 계수를 적용하면 안 된다.
    """
    from . import manreclassify as manre
    out: list[ExtractRow] = []
    try:
        rows = manre.read_rows(file_path)
    except OSError:
        return out
    for r in rows:
        if not r.has_max_count:
            continue
        out.append(ExtractRow(
            zone=MANRE_ZONE, alg=MANRE_ALG, param=r.label,
            value=parse_raw_value(r.max_count), unit="",
            src_file=file_path.name, section=manre.SECTION_GENERAL, key=r.code,
            raw=parse_raw_value(r.max_count), transform="RAW",
            source_path=str(file_path), use_default=False))
    return out


def is_manre_file(file_path: Path) -> bool:
    """복사 중복회피 접미사(ManReClassify_2.ini)도 같은 파일로 인식."""
    from . import manreclassify as manre
    return manre.is_manre_file(file_path)


def _is_optic_file(file_path: Path, prefix: str = "") -> bool:
    base = re.sub(r"_\d+$", "", file_path.stem.lower())
    return base == f"{prefix}opticpreset".lower()


def parse_ini_file(file_path: Path, scale: float = DEFAULT_SCALE,
                   recipe_prefix: str = "") -> list[ExtractRow]:
    """설정파일 1개 → ExtractRow 목록. scale = LINEAR/AREA 변환 계수(변형별).
    recipe_prefix 를 주면 그 레시피의 OpticPreset/ActiveScenarioOptics 를 대상으로 판정."""
    # ManReClassify.ini 는 값이 **쉼표로 나뉜 위치 기반**이라 공용 ini 파서를 쓰면
    # 안 된다(줄 중간 ';' 절단·형변환으로 열이 밀린다). 전용 파서로 보낸다.
    if is_manre_file(file_path):
        return _parse_manre(file_path)
    sections = parse_ini_sections(file_path)
    # OpticPreset: 신 SW 는 ActiveScenarioOptics.ini 로 Scan2d optic 지정, 구 SW 는
    # 마지막 광원 섹션(이름 무관) 통일 규칙 적용.
    if _is_optic_file(file_path, recipe_prefix):
        active = read_active_scan2d(file_path.parent, recipe_prefix)
        if _pick_optic_target(sections, active) is not None:
            return _parse_optic(file_path, sections, active=active, scale=scale)
    top = infer_top_item(file_path, sections)
    zone = TOP_TO_ZONE.get(top, top)
    is_global = (top == "Global")            # GlobalRTP.ini
    out: list[ExtractRow] = []
    for section, kv in sections.items():
        for key, raw in kv.items():
            alg, display, unit, trans = lookup_display(top, section, key)
            trans = resolve_transform(display, trans)   # µ 있으면 변환, 없으면 RAW
            # GlobalRTP: Max Defects Per Die/Wafer 만 기본 Y, 나머지는 N(검토용)
            use = (display in GLOBALRTP_KEEP) if is_global else True
            out.append(ExtractRow(
                zone=zone, alg=alg, param=display,
                value=transform_value(raw, trans, scale), unit=unit,
                src_file=file_path.name, section=section, key=key,
                raw=raw, transform=label_transform(trans, scale),  # 실제 계수 반영
                source_path=str(file_path), use_default=use))
    return out


# --------------------------------------------------------------------------
# 폴더 스캔 (config 폴더 = GlobalRTP.ini/OpticPreset.ini/Zones 를 가진 폴더)
# --------------------------------------------------------------------------
def is_config_dir(d: Path) -> bool:
    return ((d / "GlobalRTP.ini").is_file() or (d / "OpticPreset.ini").is_file()
            or (d / "Zones").is_dir())


def config_ini_files(d: Path, prefix: str = "") -> list[Path]:
    """config 폴더의 파싱 대상 ini 목록.
    **폴더 바로 아래는 GlobalRTP.ini / OpticPreset.ini 만**(그 외 다른 .ini 는 제외 —
    양식에 쓸데없는 항목이 끼지 않게), **Zones/ 하위는 .ini 전부**.
    복사 중복회피로 붙는 _N 접미사(GlobalRTP_2.ini 등)도 고정명으로 인식.
    prefix 를 주면 그 레시피의 파일(`{prefix}OpticPreset.ini`, `{prefix}Zones/*.ini`,
    GlobalRTP 는 접두본 우선·없으면 공유)만 반환한다(다중 레시피 Recipe N)."""
    d = Path(d)
    if prefix:                            # 다중 레시피: 해당 레시피 파일만
        files: list[Path] = []
        for gname in (f"{prefix}GlobalRTP.ini", "GlobalRTP.ini"):  # 접두본 우선, 없으면 공유
            gp = d / gname
            if gp.is_file():
                files.append(gp)
                break
        op = d / f"{prefix}OpticPreset.ini"
        if op.is_file():
            files.append(op)
        zdir = d / f"{prefix}Zones"
        if zdir.is_dir():
            files += sorted([p for p in zdir.glob("*.ini") if p.is_file()],
                            key=lambda x: x.name.lower())
        return files
    fixed = set(FIXED_FILE_TOP)          # {"globalrtp.ini", "opticpreset.ini"}
    files = []
    for p in sorted(d.glob("*.ini"), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        base = re.sub(r"_\d+$", "", p.stem.lower()) + p.suffix.lower()
        if p.name.lower() in fixed or base in fixed:
            files.append(p)
    zones = d / "Zones"
    if zones.is_dir():
        files += sorted([p for p in zones.glob("*.ini") if p.is_file()],
                        key=lambda x: x.name.lower())
    return files


def config_valid(cfg) -> bool:
    """이 config 폴더를 불러올 수 있는가 — **실제로 파싱된 항목이 있으면 유효**.

    구 규칙(`rtp_parser.config_valid`)은 변형 이름이 PI/PI-bubble/x5/x20 중
    하나여야 통과시켰다. 그래서 `2D+3D_CAMTEK` 처럼 이름만 다른 정상 폴더가
    전부 걸러져 "인식된 설정(config) 폴더가 없습니다" 가 났다(2026-08).
    이름 규칙 대신 **내용**으로 판단한다(변형 라벨은 폴더명을 그대로 쓴다).
    """
    return bool(getattr(cfg, "rows", None))


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


def detect_variant(config_dir: Path, layer: str, folder_fallback: bool = True) -> str:
    """변형(Recipe 열) 라벨 판정.

    익숙한 이름은 기존 양식과 통일한다: PI / PI-bubble / x5 / x20.
    **그 외에는 폴더 이름을 그대로 라벨로 쓴다**(2026-08 변경). 장비마다 레시피
    폴더 이름이 `2D+3D_CAMTEK`·`2D+3D_CAMTEK_BUMP`·`DUMMY` 처럼 제각각이라,
    이름이 규칙에 안 맞는다고 버리면 구조가 멀쩡한 폴더도 통째로 못 읽는다
    (실제로 "인식된 설정(config) 폴더가 없습니다" 가 났다).
    폴더 이름 자체가 레시피를 구분하는 정보이므로 라벨로 쓰는 편이 맞다.
    """
    name = str(config_dir.name).strip()
    nm = re.sub(r"[^a-z0-9]", "", name.lower())
    if "bubble" in nm:
        return "PI-bubble"
    if re.fullmatch(r"x?\d+", nm):
        return "x" + re.sub(r"\D", "", nm)
    if layer == "PI":
        # PI / PI3 처럼 레벨 폴더 자체가 기본(비-bubble) 레시피인 경우
        if re.fullmatch(r"pi\d*", nm):
            return "PI"
        return _folder_label(name) if folder_fallback else ""
    mag = rtp_parser.detect_mag_from_optic(config_dir)     # RDL 은 배율 우선
    return mag or (_folder_label(name) if folder_fallback else "")


def _folder_label(name: str) -> str:
    """폴더 이름을 변형 라벨로 — 공백만 정리(내용은 그대로 보여 준다)."""
    return re.sub(r"\s+", " ", str(name or "").strip())


def detect_meta(config_dir: Path, default_level: str = "",
                default_equipment: str = "", folder_variant: bool = True) -> dict:
    """폴더 경로에서 equipment/layer/레벨/변형 추정. default_* 는 수집 단계에서
    이미 알고 있는 값(IP→AOI, Job 키워드)을 우선 적용하기 위한 것.

    folder_variant=False 면 **변형을 폴더명으로 대체하지 않는다**. commonality 는
    config 폴더가 Lot 의 슬롯 폴더(CX01 …)라서 폴더명을 변형으로 쓰면 Lot 마다
    변형이 달라져 값이 한 줄로 모이지 않는다."""
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
    variant = detect_variant(config_dir, layer, folder_fallback=folder_variant)
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
    mag_value: str = ""        # OpticPreset Scan2d 의 실제 Mag(예: '3.14') — 계수 키
    scale_used: float = DEFAULT_SCALE   # 이 폴더에 적용된 변환계수


def scan_tree(root: str | Path, default_level: str = "",
              default_equipment: str = "", scale: float = DEFAULT_SCALE,
              scales: dict | None = None, coef_lookup=None,
              recipe_prefix: str = "",
              folder_variant: bool = True) -> list[ParsedConfig]:
    """폴더트리 → config 폴더별 ParsedConfig (ini 소스 전용, RTP.txt 미사용).

    변환계수 결정 우선순위(장비 렌즈 특성 = 호기×변형 마다 다름):
      1) coef_lookup(equipment, variant) 가 값을 주면 그걸 사용,
      2) 없으면 scales[변형라벨](구 방식), 3) 그래도 없으면 scale(기본).
    coef_lookup 은 '변환계수.xlsx'(호기+변형) 를 읽는 콜백(GUI/호출측이 주입).
    MAG(mag_value)는 참고·표시용으로만 계속 뽑는다(매칭에는 쓰지 않는다)."""
    scales = scales or {}
    res: list[ParsedConfig] = []
    for cdir in find_config_dirs(Path(root)):
        meta = detect_meta(cdir, default_level, default_equipment,
                           folder_variant=folder_variant)
        mag_value = read_optic_mag(cdir, recipe_prefix)   # 표시·참고용(계수 키 아님)
        use_scale = None
        if coef_lookup is not None:
            try:
                use_scale = coef_lookup(meta["equipment"], meta["mag"])
            except Exception:  # noqa: BLE001
                use_scale = None
        if use_scale is None:
            use_scale = scales.get(meta["mag"], scale)
        rows: list[ExtractRow] = []
        for f in config_ini_files(cdir, recipe_prefix):
            rows += parse_ini_file(f, use_scale, recipe_prefix=recipe_prefix)
        res.append(ParsedConfig(meta["equipment"], meta["layer"], meta["recipe"],
                                meta["mag"], cdir, rows, mag_value=mag_value,
                                scale_used=use_scale))
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
                "unit": r.unit, "values": {}, "raws": {}, "mags": {},
                "use": r.use_default,
                "extract": {"src_file": r.src_file, "section": r.section,
                            "key": r.key, "transform": r.transform,
                            "source_path": r.source_path},
            })
            ent["values"][cfg.equipment] = r.value
            ent["raws"][cfg.equipment] = r.raw
            ent["mags"][cfg.equipment] = cfg.mag_value   # 장비별 MAG(계수 재적용용)
    rows = []
    for (layer, recipe, mag, zone, alg, param), ent in table.items():
        rows.append({"layer": layer, "recipe": recipe, "mag": mag, "zone": zone,
                     "alg": alg, "param": param, "desc_en": "", "unit": ent["unit"],
                     "values": ent["values"], "raws": ent["raws"], "mags": ent["mags"],
                     "use": ent["use"], "extract": ent["extract"]})
    return rows, machines
