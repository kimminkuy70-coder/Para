"""editor_model 헤드리스 테스트 — GUI 편집기(양식 만들기/commonality/기존 양식 수정)의
파일 비의존 로직이 **어떤 파싱 결과가 와도** 깨지지 않고 확정 규칙이 정확한지 검증.

tkinter/tksheet 없이 테스트 가능 → 실기 GUI 를 못 돌려도 '다른 파일에서 오작동'을
이 계층에서 잡는다. (GUI 는 이 함수들을 그대로 호출한다.)
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import editor_model as em  # noqa: E402
from param_manager import engine, formbuilder, ini_parser  # noqa: E402

PASS = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"[PASS] {msg}")


def _row(zone, alg, param, mag="", raws=None, transform="RAW", use=True):
    return {"zone": zone, "alg": alg, "param": param, "mag": mag,
            "raws": raws if raws is not None else {"AOI-1": "10"},
            "extract": {"key": param, "section": alg, "src_file": "z.ini",
                        "transform": transform, "source_path": ""},
            "use": use}


# ── 확정 시뮬레이션: 격자 data 를 '사용자가 본 화면'으로 보고 selected 재구성 ──
def _confirm_from_grid(grid, coef_map, name_edits=None, method_edits=None,
                       check_edits=None):
    """grid + (선택적) 사용자 편집(이름/드롭다운/체크) → editor_model.build_records 입력."""
    data = grid["data"]
    name_edits = name_edits or {}
    method_edits = method_edits or {}
    check_edits = check_edits or {}
    selected = []
    for r in grid["param_rows"]:
        e = grid["row_entry"][r]
        selected.append({
            "use": check_edits.get(r, data[r][0]),
            # 새 열 구성: [use, 원본항목(col1), 장비화면이름(col2), 변환(col3), 원본값, 표시값]
            "name": name_edits.get(r, data[r][2]),
            "reco": e["reco"], "variant": e["variant"],
            "zone": e["zone"], "alg": e["alg"], "ext": e["ext"],
            "method": method_edits.get(r, data[r][3]),
            "coef": coef_map.get(e["variant"], ini_parser.DEFAULT_SCALE)})
    return selected


def test_build_entries_use_rules():
    rows = [_row("Z", "A", "P1", use=True), _row("Z", "A", "P2", use=False)]
    # 파서 플래그
    ents = em.build_entries(rows)
    assert [e["use"] for e in ents] == [True, False]
    # default_use 일괄
    assert all(e["use"] for e in em.build_entries(rows, default_use=True))
    assert not any(e["use"] for e in em.build_entries(rows, default_use=False))
    # base_keys 일치만
    k1 = formbuilder._norm_key3("Z", "A", "P1")
    ents3 = em.build_entries(rows, base_keys={k1})
    assert ents3[0]["use"] is True and ents3[1]["use"] is False
    ok("build_entries: 파서플래그 / default_use / base_keys 규칙")


def test_transform_label_roundtrip():
    for method, _lbl in em.TRANSFORM_LABELS:
        lbl = em.label_of(method)
        assert em.method_of(lbl) == method, (method, lbl)
    # 임의 표기·라벨 없는 계수 라벨도 방식 복원
    assert em.method_of("AREA_0.77^2") == "AREA"
    assert em.method_of("linear something") == "LINEAR"
    assert em.method_of("") == "RAW"
    assert em.method_of(None) == "RAW"
    ok("변환 라벨 ↔ 방식 왕복 + 임의표기 복원")


def test_safe_display_never_raises():
    coef = 0.8456665875666588
    weird = ["", None, "abc", "3.14", "0", "1", "  ", "12,000", "1e3", "-5",
             "NaN", "inf", "-inf", "２３", "１", "true"]
    methods = ["RAW", "LINEAR", "AREA", "BOOL", "REGION", "CLASSIFY",
               "LINEAR_0.8", "weird", ""]
    for raw in weird:
        for m in methods:
            v = em.safe_display(raw, m, coef)   # 예외가 나면 여기서 터짐
            assert isinstance(v, str)
    # 정상값은 실제 변환값과 일치
    assert em.safe_display("10", "LINEAR", 2.0) == engine._s(
        ini_parser.transform_value("10", "LINEAR", 2.0))
    ok("safe_display: NaN/inf/문자/빈값 등 어떤 원본값에도 예외 없음")


def test_build_grid_single_variant():
    rows = [_row("Z1", "A1", "P1"), _row("Z1", "A1", "P2"), _row("Z1", "A2", "P3"),
            _row("Z2", "A3", "P4")]
    ents = em.build_entries(rows, default_use=True)
    grid = em.build_grid(ents, multi_variant=False, disp_fn=lambda e, l: "d")
    kinds = grid["kinds"]
    assert "variant" not in kinds                    # 단일 변형=변형 헤더 없음
    assert kinds.count("param") == 4                 # 파라미터 4개 정확히
    assert kinds.count("zone") == 2 and kinds.count("alg") == 3
    # 각 파라미터는 한 번씩만
    names = [grid["data"][r][1] for r in grid["param_rows"]]
    assert sorted(names) == ["P1", "P2", "P3", "P4"]
    # descend_param: 각 alg 헤더 아래 자기 파라미터만
    for h, kids in grid["descend_param"].items():
        if kinds[h] == "alg":
            za = grid["data"][h][1]
            assert all(kinds[k] == "param" for k in kids)
    # ancestors: 파라미터의 조상은 zone+alg 헤더(2개, 단일변형)
    for r in grid["param_rows"]:
        anc = grid["ancestors"][r]
        assert len(anc) == 2 and {kinds[a] for a in anc} == {"zone", "alg"}
    ok("build_grid(단일 변형): 파라미터 유일·헤더 계층·조상 매핑")


def test_build_grid_multi_variant_and_header_use():
    rows = [_row("Z", "A", "P1", mag="x5", use=True),
            _row("Z", "A", "P2", mag="x5", use=False),
            _row("Z", "A", "P3", mag="x20", use=True)]
    ents = em.build_entries(rows)
    grid = em.build_grid(ents, multi_variant=True, disp_fn=lambda e, l: "")
    kinds = grid["kinds"]
    assert kinds.count("variant") == 2               # x5, x20
    # 변형 헤더 use = 하위 전부 사용일 때만 True
    v_rows = [i for i, k in enumerate(kinds) if k == "variant"]
    for vr in v_rows:
        kids = grid["descend_param"][vr]
        expect = all(grid["data"][k][0] for k in kids)
        assert grid["data"][vr][0] == expect
    # x5 변형(P1 True, P2 False) 헤더 = False, x20(P3 True) = True
    label_use = {grid["data"][vr][1]: grid["data"][vr][0] for vr in v_rows}
    assert label_use["변형 : x5"] is False and label_use["변형 : x20"] is True
    # 변형 헤더 조상 없음, 파라미터 조상 3개(variant/zone/alg)
    for r in grid["param_rows"]:
        assert len(grid["ancestors"][r]) == 3
    ok("build_grid(다변형): 변형 헤더 집계·조상 3계층")


def test_build_records_selection_and_transform():
    rows = [_row("Z", "A", "P1", raws={"AOI-1": "10"}, transform="LINEAR"),
            _row("Z", "A", "P2", raws={"AOI-1": "20"}, transform="AREA"),
            _row("Z", "A", "P3", raws={"AOI-1": "30"}, transform="RAW")]
    ents = em.build_entries(rows, default_use=True)
    coef_map = {"": 0.77}
    grid = em.build_grid(ents, False,
                         lambda e, l: em.safe_display(e["raw"], em.method_of(l),
                                                      coef_map[e["variant"]]))
    # 전부 선택
    recs, exts, scales = em.build_records(_confirm_from_grid(grid, coef_map), "PI3")
    assert len(recs) == 3 and len(exts) == 3
    assert all(r["PI"] == "PI3" for r in recs)
    assert scales == {"": 0.77}
    # 변환 라벨이 계수 반영해 저장되는지(label_transform)
    tfs = {r["Parameter"]: e["transform"] for r, e in zip(recs, exts)}
    assert tfs["P1"] == ini_parser.label_transform("LINEAR", 0.77)
    assert tfs["P2"] == ini_parser.label_transform("AREA", 0.77)
    assert tfs["P3"] == ini_parser.label_transform("RAW", 0.77)
    ok("build_records: 전체 선택·PI 레벨·변환라벨(계수 반영)")


def test_build_records_partial_and_edits():
    rows = [_row("Z", "A", "P1"), _row("Z", "A", "P2"), _row("Z", "A", "P3")]
    ents = em.build_entries(rows, default_use=True)
    grid = em.build_grid(ents, False, lambda e, l: "")
    pr = grid["param_rows"]
    coef_map = {"": ini_parser.DEFAULT_SCALE}
    # 가운데 항목 체크 해제 + 첫 항목 이름 변경 + 마지막 드롭다운을 BOOL 로 변경
    recs, exts, _ = em.build_records(_confirm_from_grid(
        grid, coef_map,
        check_edits={pr[1]: False},
        name_edits={pr[0]: "  새이름  "},
        method_edits={pr[2]: em.label_of("BOOL")}), "RDL2")
    assert len(recs) == 2                              # 해제된 P2 제외
    assert recs[0]["Parameter"] == "새이름"            # 공백 제거
    assert exts[-1]["transform"] == ini_parser.label_transform(
        "BOOL", ini_parser.DEFAULT_SCALE)
    assert all(r["PI"] == "RDL2" for r in recs)
    ok("build_records: 부분선택·이름편집(트림)·드롭다운 변경 반영")


def test_build_records_empty_name_falls_back_and_none_selected():
    rows = [_row("Z", "A", "P1")]
    ents = em.build_entries(rows, default_use=True)
    grid = em.build_grid(ents, False, lambda e, l: "")
    pr = grid["param_rows"]
    coef_map = {"": 1.0}
    # 이름을 공백으로 비워도 reco(원래 param)로 복구
    recs, _, _ = em.build_records(_confirm_from_grid(
        grid, coef_map, name_edits={pr[0]: "   "}), "PI3")
    assert len(recs) == 1 and recs[0]["Parameter"] == "P1"
    # 아무것도 선택 안 하면 빈 결과
    recs2, exts2, sc2 = em.build_records(_confirm_from_grid(
        grid, coef_map, check_edits={pr[0]: False}), "PI3")
    assert recs2 == [] and exts2 == [] and sc2 == {}
    ok("build_records: 빈 이름→reco 복구 · 미선택→빈 결과")


def test_edge_shapes_do_not_crash():
    # 다른 파일에서 올 법한 극단 케이스: 빈 zone/alg, None raws, 결측 extract,
    # 중복 파라미터, 미인식 transform, 유니코드/공백 이름.
    rows = [
        _row("", "", "", raws={}),                       # 전부 빈값
        {"zone": None, "alg": None, "param": None},      # 키 결측
        _row("존", "알", "한글파라미터", raws={"AOI-9": "  "}),
        _row("Z", "A", "dup"), _row("Z", "A", "dup"),    # 중복
        _row("Z", "A", "weird", transform="누가봐도이상"),
        _row("Z", "A", "nanp", raws={"AOI-1": "NaN"}, transform="BOOL"),
    ]
    ents = em.build_entries(rows, default_use=True)
    grid = em.build_grid(ents, False,
                         lambda e, l: em.safe_display(e["raw"], em.method_of(l), 0.8))
    # 표시값 전부 문자열, 예외 없음
    for r in grid["param_rows"]:
        assert isinstance(grid["data"][r][4], str)
    recs, exts, _ = em.build_records(
        _confirm_from_grid(grid, {"": 0.8}), "기타레벨")
    # 중복 파라미터도 각각 레코드로(사용자가 이름을 나중에 바꾸는 전제)
    assert sum(1 for r in recs if r["Parameter"] == "dup") == 2
    assert all(r["PI"] == "기타레벨" for r in recs)      # 커스텀 레벨 허용
    ok("극단 입력(빈값/결측/중복/미인식/NaN): 격자·확정 무해")


def test_real_parser_rows_through_editor():
    """실제 ini 파서 산출물을 편집기 로직에 그대로 흘려 무해·왕복 확인."""
    GLOBAL_RTP = "[GLOBAL_RTP]\nMaxFaultsPerWafer = 3000\nApplyDieCalib = 1\n"
    ZONE_INI = ("[General]\nZoneName = PI Opening\n[Surface]\n"
                "High_Delta = 25\nBrightLength = 5\n")
    OPTIC = "[General]\nName = p\n[Scan2d]\nMag = 5\nCameraName = TDI\nScanSpeed = 80\n"
    with tempfile.TemporaryDirectory() as tmp:
        rec = Path(tmp) / "AOI-13" / "PI3" / "PI"
        rec.mkdir(parents=True)
        (rec / "GlobalRTP.ini").write_text(GLOBAL_RTP, encoding="utf-8")
        (rec / "OpticPreset.ini").write_text(OPTIC, encoding="utf-8")
        (rec / "Zones").mkdir()
        (rec / "Zones" / "Z1.ini").write_text(ZONE_INI, encoding="utf-8")
        rows, machines = ini_parser.build_pivot(ini_parser.scan_tree(Path(tmp)))
        assert rows and machines == ["AOI-13"]
        ents = em.build_entries(rows)                    # 파서 use 플래그 그대로
        grid = em.build_grid(ents, len(em.variants_of(ents)) > 1,
                             lambda e, l: em.safe_display(e["raw"],
                                                          em.method_of(l), 0.85))
        assert grid["param_rows"], "파라미터 행이 있어야"
        # 확정: 파서가 Y표시한(use=True) 항목만 레코드로
        recs, exts, _ = em.build_records(
            _confirm_from_grid(grid, {v: 0.85 for v in em.variants_of(ents)}), "PI3")
        assert len(recs) == sum(1 for e in ents if e["use"])
        assert len(exts) == len(recs)
        ok("실제 파서 rows → 편집기 격자·확정 왕복(파서 Y 항목만 저장)")


def test_excel_close_returns_to_program():
    """엑셀에서 편집하다가 **엑셀 창을 닫으면 프로그램 창으로 돌아와야** 한다.
    (GUI 는 이 환경에서 못 띄우므로 감시 로직이 붙어 있는지 소스로 고정한다.)"""
    import os as _os
    import re as _re
    src_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                             "param_manager", "equip_app.py")
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    # 파일 잠금(엑셀이 열어 둠) 판정 + 닫힘 감시 + 창 복귀 헬퍼
    for name in ("def _file_in_use", "def _watch_excel_close", "def _return_from_excel"):
        assert name in src, f"{name} 이(가) 없음"
    # 양식 만들기 / commonality 두 확정 대화상자 모두에 감시가 붙어야 한다
    for fn in ("_form_finalize_dialog", "_cm_form_finalize_dialog"):
        m = _re.search(r"def %s.*?(?=\n    def )" % fn, src, _re.S)
        assert m, f"{fn} 을(를) 찾지 못함"
        body = m.group(0)
        assert "_watch_excel_close(draft, win, back)" in body, \
            f"{fn}: 엑셀 닫힘 감시가 없음"
        assert "_return_from_excel(" in body, f"{fn}: 창 복귀 처리가 없음"
    ok("엑셀 닫으면 프로그램 창 복귀(양식 만들기 + commonality)")


def test_optic_default_has_no_coefficient():
    """OpticPreset 항목의 **기본 변환방식은 RAW**(계수 미적용) — 사용자 확정.
    필요하면 편집기 '변환' 열에서 사람이 바꾼다."""
    from param_manager import ini_parser as ip
    for key in ("Id", "ZWafer", "FocusPosAboveChuck", "CreationMeasureDistance1",
                "CreationMeasureIntensity2", "LightSrcDif_NominalGL"):
        assert ip.resolve_transform(key, "RAW") == "RAW", key
        assert ip.transform_value("100", "RAW", 0.5) == "100"
    # µ 표기가 있는 이름만 변환된다(Zones 의 µm 파라미터)
    assert ip.resolve_transform("Min Defect Width (µm)", "RAW") == "LINEAR"
    ok("OpticPreset 기본 = 계수 미적용(RAW), µ 이름만 변환")

def test_orig_shows_raw_ini_name_display_shows_mapped():
    """이름이 매핑된 항목: '원본 항목' 열 = 실제 ini 키, '장비 화면 항목 이름' = 표시명.
    (KNOWN_DISPLAY_MAP 으로 BrightSeedTh→'Bright Sensitivity' 처럼 바뀐 항목 대비)"""
    rows = [
        {"zone": "Genesis", "alg": "Genesis", "mag": "PI",
         "param": "Bright Sensitivity", "raws": {"AOI-1": "99"}, "use": True,
         "extract": {"src_file": "GlobalRTP.ini", "section": "Genesis",
                     "key": "BrightSeedTh", "transform": "RAW"}},
        {"zone": "Surface", "alg": "Surface", "mag": "PI",
         "param": "Bright Uncertainty", "raws": {"AOI-1": "0"}, "use": True,
         "extract": {"src_file": "GlobalRTP.ini", "section": "Surface",
                     "key": "EdgeUncert_Bright", "transform": "RAW"}},
    ]
    ents = em.build_entries(rows)
    assert ents[0]["orig"] == "BrightSeedTh" and ents[0]["name"] == "Bright Sensitivity"
    assert ents[1]["orig"] == "EdgeUncert_Bright"
    grid = em.build_grid(ents, False, lambda e, l: "")
    for r in grid["param_rows"]:
        row = grid["data"][r]
        e = grid["row_entry"][r]
        assert row[1] == e["orig"]        # col1 = 원본 항목(실제 ini 키)
        assert row[2] == e["name"]        # col2 = 장비 화면 항목 이름(표시명)
        assert row[1] != row[2]           # 매핑된 항목은 서로 다르다
    # 매칭은 여전히 설정키(ext) 기준 — 표시 이름을 바꿔도 원본 키 보존
    recs, exts, _ = em.build_records(_confirm_from_grid(grid, {"PI": 0.8}), "PI3")
    assert exts[0]["key"] == "BrightSeedTh"
    ok("원본 항목=실제 ini 키 / 장비 화면 이름=표시명(매핑 반영) 분리")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n==== {PASS}/{PASS} passed ====")
