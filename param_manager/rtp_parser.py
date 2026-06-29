"""RTP.txt / 폴더트리 파서 — 다운받아 둔 원본을 화면 양식으로 분석.

흐름
  1) parse_rtp(path)        : RTP.txt 한 개 → [(zone, alg, param_raw, value, desc_en, unit)]
  2) detect_layer_recipe_mag: 폴더명 + OpticPreset 의 Scan2d Mag 로 Layer/Recipe/배율 추정
  3) scan_tree(root)        : 폴더트리 전체 → 호기별 레코드 + 통합표(피벗)
  4) load_template()        : 추천 양식/사전(rtp_template.json) 로드 — 추천이름·비고(설명번역)

원본은 읽기만 한다. 네트워크 접속 없음.
"""

from __future__ import annotations

import configparser
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import engine

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TEMPLATE_PATH = os.path.join(DATA_DIR, "rtp_template.json")

_AOI_RE = re.compile(r"(?i)AOI[-_]?\w+")
# Recipe 종류 추정용
_PI_RE = re.compile(r"(?i)PI([234])\b|_PI([234])|(?<![A-Za-z])PI(?![A-Za-z0-9])")
_RDL_RE = re.compile(r"(?i)RDL([1234])")


# --------------------------------------------------------------------------
# RTP.txt 파싱
# --------------------------------------------------------------------------
@dataclass
class RtpRow:
    zone: str
    alg: str
    param_raw: str
    value: str
    desc_en: str = ""
    unit: str = ""


def _clean_value(rest: str) -> tuple[str, str, str]:
    """'value ; in {unit} ( desc~code )' → (value, unit, desc_en)."""
    value = rest.split(";", 1)[0].strip()
    unit = ""
    um = re.search(r"in \{([^}]*)\}", rest)
    if um:
        unit = um.group(1).strip()
    desc = ""
    dm = re.search(r"\(([^)]*)\)", rest)
    if dm:
        desc = dm.group(1).strip().split("~")[0].strip()
    return value, unit, desc


def parse_rtp(path: str | Path) -> list[RtpRow]:
    zone = alg = None
    out: list[RtpRow] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            m = re.match(r"^\[(.+?)\]", s)
            if m:
                zone = m.group(1).strip()
                alg = None
                continue
            if "=" not in s:
                continue
            key, rest = s.split("=", 1)
            key = key.strip()
            if key == "Alg":
                alg = rest.strip()
                continue
            if zone is not None:
                value, unit, desc = _clean_value(rest)
                out.append(RtpRow(zone, alg or "", key, value, desc, unit))
    return out


# --------------------------------------------------------------------------
# 이름 정규화(raw → 화면 표시명)  — 템플릿의 'RTP 파라미터'와 맞추기 위함
# --------------------------------------------------------------------------
_UNIT_SUB = [
    (r"\[Microns\]", "[µm]"), (r"\[Micron\]", "[µm]"),
    (r"\[microns\]", "[µm]"), (r"_\(deg\)", " (deg)"),
]


def display_name(raw: str) -> str:
    s = raw
    for pat, rep in _UNIT_SUB:
        s = re.sub(pat, rep, s)
    s = s.replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_key(name: str) -> str:
    """매칭용 정규화 키(대소문자/공백/기호 무시)."""
    return re.sub(r"[^a-z0-9µ]", "", str(name).lower())


# --------------------------------------------------------------------------
# Layer / Recipe / 배율 추정
# --------------------------------------------------------------------------
def detect_mag_from_optic(config_dir: Path) -> str:
    """OpticPreset.ini 의 Scan2d(TDI) Mag 로 x5/x20 판정. 실패 시 ''"""
    p = config_dir / "OpticPreset.ini"
    if not p.is_file():
        return ""
    try:
        cfg = configparser.ConfigParser(strict=False)
        cfg.optionxform = str
        cfg.read(p, encoding="utf-8")
    except Exception:
        return ""
    best = ""
    for sec in cfg.sections():
        if re.match(r"(?i)scan2d", sec):
            mag = cfg[sec].get("Mag", "")
            cam = cfg[sec].get("CameraName", "")
            if cam.upper() == "TDI" and mag:
                try:
                    return f"x{int(round(float(mag)))}"
                except ValueError:
                    best = mag
    return best


def detect_meta(config_dir: Path) -> dict:
    """폴더 경로 + OpticPreset 로 layer/recipe/mag/equipment 추정."""
    name = config_dir.name                       # 예: x5, x20, R_TB500_LIVE_PI4
    parent = config_dir.parent.name              # 예: TB500_RDL4 - Multi
    joined = f"{parent}/{name}"
    equip = ""
    for anc in [config_dir, *config_dir.parents]:
        m = _AOI_RE.search(anc.name)
        if m:
            equip = m.group(0).upper().replace("_", "-")
            break
    # 배율
    mag = ""
    if re.fullmatch(r"(?i)x?\d+", name):
        mag = "x" + re.sub(r"\D", "", name)
    else:
        mag = detect_mag_from_optic(config_dir)
    # Layer / Recipe
    layer = recipe = ""
    rdl = _RDL_RE.search(joined)
    if rdl:
        layer, recipe = "RDL", "RDL" + rdl.group(1)
    else:
        pim = re.search(r"(?i)PI([234])", joined)
        if pim:
            layer, recipe = "PI", "PI" + pim.group(1)
        elif re.search(r"(?i)\bPI\b", joined):
            layer, recipe = "PI", "PI"
    return {"equipment": equip, "layer": layer, "recipe": recipe,
            "mag": mag if layer == "RDL" else "-"}


# --------------------------------------------------------------------------
# 폴더트리 스캔
# --------------------------------------------------------------------------
def _is_config_dir(d: Path) -> bool:
    return (d / "RTP.txt").is_file()


def find_config_dirs(root: Path, max_depth: int = 6) -> list[Path]:
    out: list[Path] = []

    def walk(d: Path, depth: int):
        if depth > max_depth:
            return
        if _is_config_dir(d):
            out.append(d)
            # RTP 가진 폴더 아래로는 더 안 내려감(Zones 등 제외)
            return
        try:
            for p in sorted(d.iterdir()):
                if p.is_dir():
                    walk(p, depth + 1)
        except OSError:
            return
    walk(root, 0)
    return out


@dataclass
class ParsedConfig:
    equipment: str
    layer: str
    recipe: str
    mag: str
    config_dir: Path
    rows: list[RtpRow] = field(default_factory=list)


def scan_tree(root: str | Path) -> list[ParsedConfig]:
    """폴더트리 → 각 RTP.txt 보유 폴더를 ParsedConfig 로."""
    root = Path(root)
    res: list[ParsedConfig] = []
    for cdir in find_config_dirs(root):
        meta = detect_meta(cdir)
        res.append(ParsedConfig(meta["equipment"], meta["layer"], meta["recipe"],
                                meta["mag"], cdir, parse_rtp(cdir / "RTP.txt")))
    return res


# --------------------------------------------------------------------------
# 통합표(피벗): (layer,recipe,mag,zone,alg,param) → {호기: 값}
# --------------------------------------------------------------------------
def build_pivot(configs: list[ParsedConfig]) -> tuple[list[dict], list[str]]:
    machines: list[str] = []
    table: dict[tuple, dict] = {}
    for cfg in configs:
        if cfg.equipment and cfg.equipment not in machines:
            machines.append(cfg.equipment)
        for r in cfg.rows:
            key = (cfg.layer, cfg.recipe, cfg.mag, r.zone, r.alg, display_name(r.param_raw))
            ent = table.setdefault(key, {"desc_en": r.desc_en, "unit": r.unit, "values": {}})
            ent["values"][cfg.equipment] = r.value
    rows = []
    for (layer, recipe, mag, zone, alg, param), ent in table.items():
        rows.append({"layer": layer, "recipe": recipe, "mag": mag, "zone": zone,
                     "alg": alg, "param": param, "desc_en": ent["desc_en"],
                     "unit": ent["unit"], "values": ent["values"]})
    return rows, machines


# --------------------------------------------------------------------------
# 추천 양식/사전 (B 통일안)
# --------------------------------------------------------------------------
_TEMPLATE_CACHE = None


def load_template() -> list[dict]:
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is None:
        try:
            with open(TEMPLATE_PATH, encoding="utf-8") as fh:
                _TEMPLATE_CACHE = json.load(fh)
        except Exception:
            _TEMPLATE_CACHE = []
    return _TEMPLATE_CACHE


def template_index() -> dict:
    """(layer,recipe,mag,zone_norm,alg_norm,param_norm) → 템플릿 항목(추천이름/비고)."""
    idx = {}
    for t in load_template():
        k = (t.get("layer"), t.get("recipe"), t.get("mag"),
             norm_key(t.get("zone")), norm_key(t.get("alg")), norm_key(t.get("param")))
        idx[k] = t
    return idx


def refresh_values(repo, folder: str | Path) -> dict:
    """이미 만든 양식(repo)의 구조는 그대로 두고, 폴더의 최신 파일에서 호기별
    값만 다시 채운다. 매칭 키 = (PI=Recipe, Recipe=배율, Zone, Alg, Parameter).
    새 호기가 나타나면 열을 추가한다. 반환: 갱신 통계."""
    rows, machines = build_pivot(scan_tree(folder))
    idx = {}
    for r in rows:
        k = (engine._s(r["recipe"]), engine._s(r["mag"]),
             norm_key(r["zone"]), norm_key(r["alg"]), norm_key(r["param"]))
        idx[k] = r

    # 새 호기 열 보장
    for m in machines:
        if m and m not in repo.aoi_units:
            repo.aoi_units.append(m)
            for pr in repo.rows:
                pr.aoi_units = list(repo.aoi_units)
                pr.values.setdefault(m, None)

    upd_rows = upd_cells = unmatched = 0
    for pr in repo.rows:
        k = (engine._s(pr.get("PI")), engine._s(pr.get("Recipe")),
             norm_key(pr.get("Zone")), norm_key(pr.get("Alg")), norm_key(pr.get("Parameter")))
        r = idx.get(k)
        if not r:
            unmatched += 1
            continue
        changed = False
        for m, v in r["values"].items():
            if engine._s(v) == "":
                continue
            if engine._s(pr.get(m)) != engine._s(v):
                pr.set(m, v)
                upd_cells += 1
                changed = True
        if changed:
            upd_rows += 1
    return {"updated_rows": upd_rows, "updated_cells": upd_cells,
            "unmatched_rows": unmatched, "machines": machines,
            "folder_items": len(idx)}


def recommend(layer, recipe, mag, zone, alg, param) -> dict | None:
    """파싱된 항목에 대해 추천이름/비고(설명번역) 찾기. 없으면 None."""
    idx = template_index()
    k = (layer, recipe, mag, norm_key(zone), norm_key(alg), norm_key(param))
    if k in idx:
        return idx[k]
    # 배율/recipe 무시하고 zone/alg/param 만으로도 시도(번역 재활용)
    for t in load_template():
        if (norm_key(t.get("zone")) == norm_key(zone)
                and norm_key(t.get("alg")) == norm_key(alg)
                and norm_key(t.get("param")) == norm_key(param)):
            return t
    return None
