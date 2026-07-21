"""파라미터 편집기(양식 만들기 / commonality / 기존 양식 수정 공통)의 **GUI 비의존 로직**.

tkinter·tksheet 없이 다음을 담당하여 파일 종류가 달라져도 깨지지 않도록 헤드리스로
테스트한다:
  1) 파싱 rows → 편집기 entries(사용 여부/변환 라벨 결정)
  2) entries → 평면 격자(변형·Zone·Alg 헤더행 + 파라미터행) + 계층 매핑
  3) 확정: 선택 상태 → 저장 records/extracts/계수(기존 confirm 규칙과 동일)
  4) 표시값 계산은 어떤 원본값(빈값·NaN·문자)에도 예외를 내지 않는다(safe_display).

GUI(equip_app._form_param_editor)는 이 모듈을 호출하고, 여기 함수를 tests 가 직접 검증한다.
"""
from __future__ import annotations

import re
from collections import OrderedDict

from . import engine, formbuilder, ini_parser

# 드롭다운 표기(영어 + 괄호 간단 설명). 저장/계산은 앞의 영어(방식)만 사용.
TRANSFORM_KINDS = ["RAW", "LINEAR", "AREA", "BOOL", "REGION", "CLASSIFY"]
TRANSFORM_LABELS = [
    ("RAW", "RAW (원본값 그대로)"),
    ("LINEAR", "LINEAR (선형 · 값×계수)"),
    ("AREA", "AREA (면적 · 값×계수²)"),
    ("BOOL", "BOOL (1→체크 / 0→해제)"),
    ("REGION", "REGION (영역 표시)"),
    ("CLASSIFY", "CLASSIFY (분류 코드)"),
]
LABEL_VALUES = [lbl for _, lbl in TRANSFORM_LABELS]
METHOD_TO_LABEL = {mth: lbl for mth, lbl in TRANSFORM_LABELS}
LABEL_TO_METHOD = {lbl: mth for mth, lbl in TRANSFORM_LABELS}


def method_of(text) -> str:
    """드롭다운 라벨(또는 임의 표기) → 변환방식(영어). 미인식은 앞 알파벳, 없으면 RAW."""
    s = engine._s(text)
    if s in LABEL_TO_METHOD:
        return LABEL_TO_METHOD[s]
    m = re.match(r"[A-Za-z]+", s or "RAW")
    return m.group(0).upper() if m else "RAW"


def label_of(method) -> str:
    """변환방식(영어) → 드롭다운 라벨."""
    return METHOD_TO_LABEL.get(method, method)


def safe_display(raw, method, coef) -> str:
    """표시값 계산. 어떤 원본값이 와도 예외를 내지 않는다(파일마다 다른 값 대비).
    변환에 실패하면 원본값을 그대로 보여준다(편집기 자체가 죽지 않게)."""
    try:
        return engine._s(ini_parser.transform_value(raw, method, coef))
    except Exception:  # noqa: BLE001
        return engine._s(raw)


def build_entries(rows, base_keys=None, default_use=None) -> list[dict]:
    """파싱 rows → 편집기 entries. 사용 여부 규칙:
      base_keys 지정=기존 양식의 사용 키와 일치하면 선택 / default_use 지정=일괄 값 /
      둘 다 없으면 파서 use 플래그(새로 만들기=추천 Y 항목 체크)."""
    entries = []
    for r in rows:
        zone = engine._s(r.get("zone")); alg = engine._s(r.get("alg"))
        param = engine._s(r.get("param")); variant = engine._s(r.get("mag"))
        key = formbuilder._norm_key3(zone, alg, param)
        if base_keys is not None:
            use = key in base_keys
        elif default_use is not None:
            use = default_use
        else:
            use = bool(r.get("use", True))
        raws = r.get("raws") or {}
        raw = next((v for v in raws.values() if engine._s(v) != ""), "")
        ext = dict(r.get("extract") or {})
        mth = method_of(ext.get("transform") or "RAW")
        entries.append({
            "zone": zone, "alg": alg, "variant": variant, "reco": param,
            "raw": raw, "ext": ext, "use": bool(use), "name": param,
            "label": label_of(mth)})
    return entries


def variants_of(entries) -> list[str]:
    out = []
    for e in entries:
        if e["variant"] not in out:
            out.append(e["variant"])
    return out


def build_grid(entries, multi_variant, disp_fn) -> dict:
    """entries → 평면 격자(2차원 data) + 계층 매핑.

    반환 dict:
      data      : [[use(bool), 항목, 분류라벨, 원본값, 표시값], ...]
      kinds     : 각 행 종류 'variant'/'zone'/'alg'/'param'
      row_entry : 시트행 → entry(파라미터 행만)
      descend_param/descend_head : 헤더행 → 하위 파라미터/헤더 시트행
      ancestors : 시트행 → 상위 헤더 시트행
      param_rows/header_rows : 종류별 시트행 인덱스
    disp_fn(entry, label) 는 표시값 문자열(계수 적용)을 돌려준다.
    """
    tree = OrderedDict()
    for e in entries:
        tree.setdefault(e["variant"], OrderedDict()).setdefault(
            e["zone"], OrderedDict()).setdefault(e["alg"], []).append(e)

    data, kinds = [], []
    row_entry, descend_param, descend_head, ancestors = {}, {}, {}, {}

    def add_row(kind, use, label, trans="", raw="", disp="", anc=()):
        i = len(data)
        data.append([bool(use), label, trans, raw, disp])
        kinds.append(kind)
        ancestors[i] = list(anc)
        if kind != "param":
            descend_param[i] = []
            descend_head[i] = []
        return i

    for variant, zones in tree.items():
        vmem = [e for z in zones.values() for a in z.values() for e in a]
        v_anc, v_row = [], None
        if multi_variant:
            v_row = add_row("variant", all(e["use"] for e in vmem),
                            f"변형 : {variant or '(기본)'}")
            v_anc = [v_row]
        for zone, algs in zones.items():
            zmem = [e for a in algs.values() for e in a]
            z_lbl = ("    " if multi_variant else "") + f"Zone : {zone or '(없음)'}"
            z_row = add_row("zone", all(e["use"] for e in zmem), z_lbl, anc=v_anc)
            z_anc = v_anc + [z_row]
            if multi_variant:
                descend_head[v_row].append(z_row)
            for alg, items in algs.items():
                a_ind = "        " if multi_variant else "    "
                a_lbl = a_ind + f"Alg : {alg or '(없음)'}  ({len(items)})"
                a_row = add_row("alg", all(e["use"] for e in items), a_lbl, anc=z_anc)
                a_anc = z_anc + [a_row]
                for h in z_anc:
                    descend_head[h].append(a_row)
                for e in items:
                    pr = add_row("param", e["use"], e["name"], e["label"],
                                 engine._s(e["raw"]), disp_fn(e, e["label"]),
                                 anc=a_anc)
                    row_entry[pr] = e
                    for h in a_anc:
                        descend_param[h].append(pr)

    return {"data": data, "kinds": kinds, "row_entry": row_entry,
            "descend_param": descend_param, "descend_head": descend_head,
            "ancestors": ancestors,
            "param_rows": [i for i, k in enumerate(kinds) if k == "param"],
            "header_rows": [i for i, k in enumerate(kinds) if k != "param"]}


def build_records(selected, level) -> tuple[list[dict], list[dict], dict]:
    """확정 규칙(기존 confirm 과 동일). selected 각 항목:
      {use, name, reco, variant, zone, alg, ext, method(라벨/영어), coef}
    use=False·빈 이름은 제외. 반환 (records, extracts, used_scales)."""
    records, extracts, used_scales = [], [], {}
    for s in selected:
        if not s.get("use"):
            continue
        name = engine._s(s.get("name")).strip() or engine._s(s.get("reco"))
        if not name:
            continue
        method = method_of(s.get("method"))
        v = s.get("variant")
        coef = s.get("coef")
        used_scales[v] = coef
        records.append({"PI": level, "Recipe": v, "Zone": s.get("zone"),
                        "Alg": s.get("alg"), "Parameter": name, "비고": ""})
        ext = dict(s.get("ext") or {})
        ext["transform"] = ini_parser.label_transform(method, coef)
        extracts.append(ext)
    return records, extracts, used_scales
