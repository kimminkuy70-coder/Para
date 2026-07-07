"""변환 계수 자동 추정 — RTP.txt(표시값) vs Zone ini(원본값) 비교.

규칙(사용자 제공 detector 이식):
  LINEAR: 계수 = 표시값 / 원본값
  AREA  : 계수 = sqrt(표시값 / 원본값)
알려진 (RTP키 ↔ INI키) 쌍에서 증거를 모아 군집화하고, 1.0 근처(이미 표시단위로
저장된 항목)는 강한 비-1 군집이 있으면 무시한 뒤 가장 강한 군집을 계수로 채택한다.

원본 파일은 읽기만 한다. 계수는 **추천값**으로만 쓰고, 최종 확정은 사용자가 한다.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

# 알려진 매칭 쌍: 섹션 → {linear/area: [(RTP키, INI키)]}
PAIR_RULES = {
    "Surface": {
        "linear": [
            ("Min_Defect_Width_-_Bright", "BrightDiameter"),
            ("Min_Defect_Width_-_Dark", "DarkDiameter"),
            ("Min_Defect_Length_-_Bright", "BrightLength"),
            ("Min_Defect_Length_-_Dark", "DarkLength"),
            ("Clustering_Candidate_Diameter", "ClusterDiameter"),
            ("Clustering_Distance", "ClusterDistance"),
            ("Rich_Events_Cluster_-_Max_Distance", "RichClusterMaxDistance"),
        ],
        "area": [
            ("Min_Defect_Area_-_Bright", "BrightArea"),
            ("Min_Defect_Area_-_Dark", "DarkArea"),
            ("Clustering_Candidate_Area", "ClusterArea"),
            ("Rich_Events_Min_Area", "RichEventsMinArea"),
        ],
    },
    "Surface Feature Filter Width": {
        "linear": [("Low_Value", "LowValue"), ("High_Value", "HighValue")],
        "area": [],
    },
    "Surface Feature Filter Area": {
        "linear": [],
        "area": [("Low_Value", "LowValue"), ("High_Value", "HighValue")],
    },
}

_ALG_MAP = {
    "Surface": "Surface",
    "Genesis": "Genesis",
    "Surface_Feature_Filter_Width": "Surface Feature Filter Width",
    "Surface_Feature_Filter_Area": "Surface Feature Filter Area",
    "Surface_Feature_Filter_Contrast_Average": "Surface Feature Filter Contrast Average",
}


# --------------------------------------------------------------------------
# 파싱
# --------------------------------------------------------------------------
def _parse_value(v: str) -> Any:
    s = str(v).strip()
    try:
        if re.fullmatch(r"[-+]?\d+", s):
            return int(s)
        if re.fullmatch(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", s) or \
                re.fullmatch(r"[-+]?\d+(?:[eE][-+]?\d+)", s):
            return float(s)
    except Exception:  # noqa: BLE001
        pass
    return s


def _strip_comment(line: str) -> str:
    return line.split(";", 1)[0].strip().replace("\\_", "_")


def parse_ini(path: Path) -> tuple[str, dict]:
    """Zone ini → (ZoneName(top), {section: {key: value}})."""
    sections: dict[str, dict] = defaultdict(dict)
    sec = None
    for raw in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and "]" in line:
            sec = line[1:line.index("]")].replace("\\_", "_").strip()
            continue
        clean = _strip_comment(line)
        if sec and "=" in clean:
            k, v = [x.strip() for x in clean.split("=", 1)]
            sections[sec][k] = _parse_value(v)
    top = str(sections.get("General", {}).get("ZoneName") or Path(path).stem.replace("_", " "))
    return top, sections


def _rtp_section_name(raw: str) -> str:
    s = raw.replace("\\_", "_").strip()
    return "Scan Area" if s == "Scan_Area" else s


def parse_rtp(path: Path) -> dict:
    """RTP.txt → {top: {alg: {key: value}}} (표시값)."""
    out: dict = defaultdict(lambda: defaultdict(dict))
    top = alg = None
    for raw in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and "]" in line:
            top = _rtp_section_name(line[1:line.index("]")])
            alg = None
            continue
        clean = _strip_comment(line)
        if not top or "=" not in clean:
            continue
        k, v = [x.strip() for x in clean.split("=", 1)]
        if k == "Alg":
            alg = _ALG_MAP.get(v, v.replace("_", " "))
            out[top].setdefault(alg, {})
            continue
        if alg:
            out[top][alg][k] = _parse_value(v)
    return out


# --------------------------------------------------------------------------
# 계수 로직
# --------------------------------------------------------------------------
def _valid_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def collect_evidence(rtp_data: dict, ini_data_by_top: dict) -> list[dict]:
    evidence = []
    for top in sorted(set(rtp_data) & set(ini_data_by_top)):
        for section, rules in PAIR_RULES.items():
            rsec = rtp_data.get(top, {}).get(section, {})
            isec = ini_data_by_top.get(top, {}).get(section, {})
            for rkey, ikey in rules.get("linear", []):
                rv, iv = rsec.get(rkey), isec.get(ikey)
                if _valid_num(rv) and _valid_num(iv) and rv > 0 and iv > 0:
                    coef = float(rv) / float(iv)
                    if 0.4 <= coef <= 1.2:
                        evidence.append({"Top": top, "Section": section, "Type": "LINEAR",
                                         "RTP Key": rkey, "RTP Value": rv, "INI Key": ikey,
                                         "INI Value": iv, "Coefficient": coef})
            for rkey, ikey in rules.get("area", []):
                rv, iv = rsec.get(rkey), isec.get(ikey)
                if _valid_num(rv) and _valid_num(iv) and rv > 0 and iv > 0:
                    coef = math.sqrt(float(rv) / float(iv))
                    if 0.4 <= coef <= 1.2:
                        evidence.append({"Top": top, "Section": section, "Type": "AREA",
                                         "RTP Key": rkey, "RTP Value": rv, "INI Key": ikey,
                                         "INI Value": iv, "Coefficient": coef})
    return evidence


def cluster_coefficients(evidence: list[dict], tolerance: float = 0.025) -> list[dict]:
    vals = sorted(e["Coefficient"] for e in evidence)
    if not vals:
        return []
    clusters, current = [], [vals[0]]
    for v in vals[1:]:
        if abs(v - statistics.median(current)) <= tolerance:
            current.append(v)
        else:
            clusters.append(current)
            current = [v]
    clusters.append(current)
    out = []
    for cl in clusters:
        med = statistics.median(cl)
        ev = [e for e in evidence if abs(e["Coefficient"] - med) <= tolerance]
        stdev = statistics.pstdev([e["Coefficient"] for e in ev]) if len(ev) > 1 else 0
        out.append({
            "Median": med, "Mean": statistics.mean([e["Coefficient"] for e in ev]),
            "Count": len(ev), "StdDev": stdev,
            "Tops": sorted({e["Top"] for e in ev}),
            "Sections": sorted({e["Section"] for e in ev}),
            "Is Near 1": abs(med - 1.0) <= 0.02, "Evidence": ev})
    dedup = []
    for c in sorted(out, key=lambda x: x["Median"]):
        if not dedup or abs(c["Median"] - dedup[-1]["Median"]) > tolerance:
            dedup.append(c)
        elif c["Count"] > dedup[-1]["Count"]:
            dedup[-1] = c
    return dedup


def decide_coefficient(evidence: list[dict]) -> dict:
    clusters = cluster_coefficients(evidence)
    if not clusters:
        return {"Coefficient": None, "Confidence": "None",
                "Reason": "RTP/INI 대응 증거가 없습니다.", "Clusters": []}
    non_one = [c for c in clusters if not c["Is Near 1"]]
    strong_non_one = [c for c in non_one if c["Count"] >= 3]
    if strong_non_one:
        chosen = max(strong_non_one, key=lambda c: (c["Count"], -c["StdDev"]))
        reason = "1.0 근처(직접단위) 증거는 제외하고 강한 비-1 계수 군집을 선택."
    else:
        chosen = max(clusters, key=lambda c: (c["Count"], -c["StdDev"]))
        reason = "강한 비-1 군집이 없어 가장 강한 군집을 선택."
    coef = chosen["Median"]
    if chosen["Count"] >= 5 and chosen["StdDev"] <= 0.005:
        conf = "High"
    elif chosen["Count"] >= 3 and chosen["StdDev"] <= 0.02:
        conf = "Medium"
    else:
        conf = "Low"
    return {"Coefficient": coef, "Display": round(coef, 2), "Confidence": conf,
            "Reason": reason, "Count": chosen["Count"], "Clusters": clusters,
            "Evidence": evidence}


# --------------------------------------------------------------------------
# 폴더 단위 추정
# --------------------------------------------------------------------------
RTP_FILENAME = "RTP.txt"
_SKIP_INI = {"globalrtp.ini", "opticpreset.ini"}


def find_rtp(config_dir: Path) -> Path | None:
    """recipe 폴더(및 하위)에서 RTP.txt 를 찾는다. 없으면 None."""
    p = Path(config_dir) / RTP_FILENAME
    if p.is_file():
        return p
    hits = sorted(Path(config_dir).rglob(RTP_FILENAME))
    return hits[0] if hits else None


def _zone_inis(config_dir: Path) -> list[Path]:
    return sorted(p for p in Path(config_dir).rglob("*.ini")
                  if p.name.lower() not in _SKIP_INI)


def detect_from_dir(config_dir: str | Path) -> dict:
    """recipe(변형) 폴더 하나에서 계수 추정. RTP.txt 없으면 Coefficient=None."""
    config_dir = Path(config_dir)
    rtp = find_rtp(config_dir)
    if not rtp:
        return {"Coefficient": None, "Confidence": "None",
                "Reason": "RTP.txt 를 찾지 못했습니다.", "Clusters": [], "rtp": None}
    rtp_data = parse_rtp(rtp)
    ini_by_top = {}
    for f in _zone_inis(config_dir):
        top, data = parse_ini(f)
        ini_by_top[top] = data
    decision = decide_coefficient(collect_evidence(rtp_data, ini_by_top))
    decision["rtp"] = str(rtp)
    return decision
