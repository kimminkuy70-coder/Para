"""파라미터 값 취합(AOI 스펙 1.1.1.1.2/3) — 헤드리스 로직.

양식 파일(final)의 파라미터 목록을 기준으로, 여러 장비에서 파싱한 값을
**호기별 열**로 채운 취합 결과를 레시피(PI#/RDL#)마다 만든다.

핵심: 양식의 'Parameter' 는 사람이 장비 화면 이름으로 바꿔놨을 수 있으므로
표시 이름으로 매칭하면 안 된다. 양식의 `_EXTRACT_MAP`(설정 Section/Parameter)과
Zone 을 이용해 **원본 설정키 기준**으로 매칭한다(이름 변경에 견고). 없으면 이름 폴백.

양식에 있는데 실제 파싱값에 없는 항목 = **불일치**(GUI 가 경고 + 표기 + 생성여부 확인).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import engine, extract_io


def norm_key(name: str) -> str:
    """매칭용 정규화 — 한글 보존(사람이 붙인 한글 파라미터명 대응)."""
    return re.sub(r"[^0-9a-z가-힣µ]", "", str(name).lower())


@dataclass
class CollateRecipe:
    """레시피 레벨 1개(PI3 등)에 대한 취합 결과."""
    level: str
    sheet: str                              # PI_ALL / RDL_ALL
    records: list[dict] = field(default_factory=list)   # 양식 행 + 호기 값
    extracts: list[dict] = field(default_factory=list)  # records 병렬 재추출 메타
    machines: list[str] = field(default_factory=list)
    mismatches: list[dict] = field(default_factory=list)  # 파싱값 못 찾은 양식 행
    extra: list[dict] = field(default_factory=list)        # 양식에 없는 파싱 항목
    matched_rows: int = 0
    filled_cells: int = 0


def _key(pi, variant, zone, section, param) -> tuple:
    return (engine._s(pi).strip().lower(), engine._s(variant).strip().lower(),
            norm_key(zone), norm_key(section), norm_key(param))


def _name_key(pi, variant, zone, alg, param) -> tuple:
    return (engine._s(pi).strip().lower(), engine._s(variant).strip().lower(),
            norm_key(zone), norm_key(alg), norm_key(param))


def _build_parsed_index(pivot_rows: list[dict]) -> tuple[dict, dict, list[str]]:
    """파싱 피벗 → (설정키 인덱스, 이름 인덱스, 호기목록).
    각 값은 {'values': {호기: 값}, 'row': 원본 피벗행}."""
    by_ext: dict[tuple, dict] = {}
    by_name: dict[tuple, dict] = {}
    machines: list[str] = []
    for r in pivot_rows:
        ext = r.get("extract") or {}
        for m in (r.get("values") or {}):
            if m and m not in machines:
                machines.append(m)
        ek = _key(r.get("recipe"), r.get("mag"), r.get("zone"),
                  ext.get("section"), ext.get("key"))
        by_ext.setdefault(ek, r)
        nk = _name_key(r.get("recipe"), r.get("mag"), r.get("zone"),
                       r.get("alg"), r.get("param"))
        by_name.setdefault(nk, r)
    return by_ext, by_name, machines


def collate(form_path: str, pivot_rows: list[dict],
            selected_levels: list[str] | None = None) -> list[CollateRecipe]:
    """양식 파일 + 파싱 피벗 → 레시피별 취합 결과 목록(파일은 아직 안 씀).

    selected_levels: 처리할 레시피 레벨(PI3/RDL4…) 화이트리스트. None 이면 전부.
    """
    repo = engine.ParamRepository(form_path)
    repo.load()
    emap = extract_io.read_extract_map(form_path)         # Row_ID → 설정키 메타
    by_ext, by_name, parsed_machines = _build_parsed_index(pivot_rows)

    # 레시피 레벨(PI 열)별로 양식 행 묶기
    groups: dict[str, list] = {}
    for pr in repo.rows:
        level = engine._s(pr.get("PI")).strip() or "레벨미상"
        groups.setdefault(level, []).append(pr)

    used_parsed_keys: set = set()
    results: list[CollateRecipe] = []
    for level, prs in groups.items():
        if selected_levels and level not in selected_levels:
            continue
        sheet = "RDL_ALL" if level.upper().startswith("RDL") else "PI_ALL"
        res = CollateRecipe(level=level, sheet=sheet, machines=list(parsed_machines))
        for pr in prs:
            meta = emap.get(pr.row_id, {})
            variant = engine._s(pr.get("Recipe"))
            zone = engine._s(pr.get("Zone"))
            match = None
            if meta.get("section") or meta.get("key"):
                match = by_ext.get(_key(level, variant, zone,
                                        meta.get("section"), meta.get("key")))
            if match is None:                            # 이름 기반 폴백
                match = by_name.get(_name_key(level, variant, zone,
                                              pr.get("Alg"), pr.get("Parameter")))
            rec = {f: pr.get(f) for f in engine.META_FIELDS}
            ext = {"src_file": meta.get("src_file", ""),
                   "section": meta.get("section", ""), "key": meta.get("key", ""),
                   "raw": meta.get("raw", ""), "transform": meta.get("transform", "RAW"),
                   "source_path": ""}
            if match is None:
                res.mismatches.append({
                    "level": level, "recipe": variant, "zone": zone,
                    "alg": engine._s(pr.get("Alg")),
                    "param": engine._s(pr.get("Parameter")),
                    "reason": "장비 파싱값에서 해당 설정키를 찾지 못함"})
                rec["Status"] = "불일치"
            else:
                res.matched_rows += 1
                nk = _name_key(match.get("recipe"), match.get("mag"),
                               match.get("zone"), match.get("alg"), match.get("param"))
                used_parsed_keys.add(nk)
                for m, v in (match.get("values") or {}).items():
                    if m and engine._s(v) != "":
                        rec[m] = v
                        res.filled_cells += 1
            res.records.append(rec)
            res.extracts.append(ext)

        # 양식에 없는 파싱 항목(참고용 신규) — 이 레벨에 해당하는 것만
        for r in pivot_rows:
            if engine._s(r.get("recipe")).strip() != level:
                continue
            nk = _name_key(r.get("recipe"), r.get("mag"), r.get("zone"),
                           r.get("alg"), r.get("param"))
            if nk in used_parsed_keys:
                continue
            res.extra.append({"level": level, "recipe": engine._s(r.get("mag")),
                              "zone": engine._s(r.get("zone")),
                              "alg": engine._s(r.get("alg")),
                              "param": engine._s(r.get("param"))})
        results.append(res)
    return results


def write_collated(res: CollateRecipe, dest_xlsx: str, source: str = "",
                   user: str | None = None, mark_mismatch: bool = True) -> str:
    """취합 결과 1개(레시피)를 공용 양식(PI_ALL/RDL_ALL) + `_EXTRACT_MAP` 로 저장.
    mark_mismatch=True 면 불일치 행의 비고에 [불일치] 표기를 남긴다."""
    records = [dict(r) for r in res.records]
    if mark_mismatch:
        for r in records:
            if engine._s(r.get("Status")) == "불일치":
                note = engine._s(r.get("비고"))
                r["비고"] = ("[불일치] " + note).strip()
    for r in records:
        r.pop("Status", None)                    # 표시 스키마엔 Status 열이 없음
    extract_io.write_snapshot(
        dest_xlsx, records, machines=res.machines, sheet_name=res.sheet,
        extracts=res.extracts, stage="collate", level=res.level,
        source=source, user=user)
    return dest_xlsx
