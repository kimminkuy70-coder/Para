"""ManReClassify.ini (Classification Editor) 파서 + 양식 만들기 연결.

파일 구조(장비 `\\{IP}\\c$\\Bis\\data\\dds\\ManReClassify.ini`):

    Code=Desc,Status,Priority,Color,KeyCode,KeyModifier,Intern,Display,
         GrabImage,Verify,Extended,MaxCount,CustomerBin0,CustomerBin1,...

여기서 고정하는 규칙(사용자 확정 2026-08):
  ① Max Count = 쉼표 분리 **0-based index 11**
  ② **빈 필드를 보존**한다 — 연속 쉼표를 합치거나 당기면 열이 통째로 밀린다
  ③ Max Count **0 은 유효한 값**(결측 아님)
  ④ Internal Bin = index 12(고객 Bin 배열의 0번), 배열 순서 = [Customers] 순서
  ⑤ 주석은 **줄 맨 앞의 `;`** 만 — 줄 중간의 `;` 는 데이터다
  ⑥ 양식에서 고르는 건 **Max Count 뿐**, 기본은 전부 사용=N
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import collector, ini_parser  # noqa: E402
from param_manager import manreclassify as manre  # noqa: E402

PASS = FAIL = 0

SAMPLE = """; 파일 맨 앞 주석 — 무시해야 한다
[Customers]
0=Internal
1=SINF3D
2=TI-CSPNL
3=CY

[General]
; 아래가 데이터
0=Accept,Good,0,Green,Space,,D1,1,1,1,AB11,0,000,000,000,49
2=Missing Bump,Defect,1,Red,F2,,FQC-01,1,1,1,AB13,10,002,002,002,100
28=B R Other,Defect,100,Olive,None,,FQC-38,1,1,1,CA38,40,100,100,100,100
71=CMP TSV breaking,Defect,73,Red,F1,Alt,,1,1,1,,30,0,0,0,001
99=No Max,Defect,5,Blue,,,,1,1,1,,,7,7,7,7
"""


def run(fn):
    global PASS, FAIL
    print(f"[RUN] {fn.__name__}")
    try:
        fn()
        PASS += 1
        print(f"[PASS] {fn.__name__}\n")
    except Exception as e:  # noqa: BLE001
        FAIL += 1
        import traceback
        print(f"[FAIL] {fn.__name__}: {e}")
        traceback.print_exc()
        print()


def _write(text=SAMPLE) -> Path:
    p = Path(tempfile.mkdtemp()) / manre.FILENAME
    p.write_text(text, encoding="utf-8")
    return p


# --------------------------------------------------------------------------
def test_max_count_is_field_11():
    """Max Count 는 **index 11** — 빈 필드가 있어도 자리가 밀리면 안 된다."""
    p = _write()
    rows = {r.code: r for r in manre.read_rows(p)}
    assert rows["0"].max_count == "0"          # 0 도 유효한 값
    assert rows["2"].max_count == "10"
    assert rows["28"].max_count == "40"
    # 71 번은 Intern(6)·Extended(10)이 비어 있다 — 그래도 11번이 Max Count
    r71 = rows["71"]
    assert r71.at(manre.IDX_INTERN) == "" and r71.at(manre.IDX_EXTENDED) == ""
    assert r71.max_count == "30", r71.fields
    assert r71.at(manre.IDX_KEYMODIFIER) == "Alt"
    print("  Max Count = index 11 (빈 필드가 있어도 고정) OK")


def test_empty_fields_are_preserved():
    """연속된 쉼표를 합치거나 당기면 안 된다 — 필드 개수·위치가 그대로여야."""
    p = _write()
    rows = {r.code: r for r in manre.read_rows(p)}
    # 0=... 는 KeyModifier(5) 한 칸이 비어 있다 → 필드 16개
    assert len(rows["0"].fields) == 16, rows["0"].fields
    assert rows["0"].fields[manre.IDX_KEYMODIFIER] == ""
    # 99 번은 Intern·Extended·MaxCount 3칸이 비어 있다
    assert rows["99"].fields[manre.IDX_MAXCOUNT] == ""
    assert len(rows["99"].fields) == 16, rows["99"].fields
    # 필드를 당겼다면 99번 MaxCount 에 '7'(Bin)이 들어왔을 것이다
    assert rows["99"].max_count != "7"
    print("  빈 필드 보존(당김 없음) OK")


def test_zero_is_valid_not_missing():
    """Max Count 0 은 결측이 아니다 — 목록에 남아야 한다."""
    p = _write()
    got = dict((code, mc) for code, _label, mc in manre.max_counts(p))
    assert got.get("0") == "0", got            # 0 이 살아 있어야
    assert "99" not in got, "빈 값만 빠져야 한다"
    assert set(got) == {"0", "2", "28", "71"}, got
    print("  MaxCount 0 유효 / 빈 값만 제외 OK")


def test_internal_bin_and_customer_order():
    """Internal Bin = index 12, 고객 Bin 순서 = [Customers] 순서."""
    p = _write()
    cust = manre.read_customers(p)
    assert cust == ["Internal", "SINF3D", "TI-CSPNL", "CY"], cust
    rows = {r.code: r for r in manre.read_rows(p)}
    assert rows["2"].internal_bin == "002"
    assert rows["2"].at(manre.IDX_BIN0) == rows["2"].internal_bin
    bins = rows["2"].bins(cust)
    assert bins == {"Internal": "002", "SINF3D": "002",
                    "TI-CSPNL": "002", "CY": "100"}, bins
    # 순서가 곧 의미다 — 정렬하면 안 된다
    assert list(bins) == cust
    print("  Internal Bin(index 12) + 고객 Bin 순서 OK")


def test_comment_only_at_line_start():
    """주석은 **줄 맨 앞의 ';'** 만 — 줄 중간의 ';' 는 Desc 의 일부다."""
    p = _write("[General]\n"
               "; 이 줄은 주석\n"
               "5=Bump; small,Defect,1,Red,F5,,I5,1,1,1,E5,12,005\n")
    rows = manre.read_rows(p)
    assert len(rows) == 1, rows
    assert rows[0].desc == "Bump; small", rows[0].desc
    assert rows[0].max_count == "12", rows[0].fields
    print("  줄 중간 ';' 는 데이터로 보존 OK")


def test_short_row_and_duplicate_code():
    """필드가 모자란 행·중복 코드에도 예외가 없어야 한다."""
    p = _write("[General]\n"
               "7=Short,Defect,1\n"                       # MaxCount 자리 없음
               "8=First,Defect,1,R,F8,,I,1,1,1,E,5,008\n"
               "8=Second,Defect,1,R,F8,,I,1,1,1,E,9,008\n")   # 같은 코드 → 뒤가 이김
    rows = {r.code: r for r in manre.read_rows(p)}
    assert rows["7"].max_count == "" and rows["7"].has_max_count is False
    assert rows["7"].internal_bin == ""                    # 없는 인덱스도 빈 문자열
    assert rows["8"].desc == "Second" and rows["8"].max_count == "9"
    assert len(manre.read_rows(p)) == 2, "중복 코드가 두 줄로 남으면 안 됨"
    print("  짧은 행·중복 코드 안전 OK")


def test_flows_into_form_pivot():
    """양식 만들기 피벗에 **Max Count 만** 들어가고 기본은 사용=N."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "R_PI3" / "PI"
        (d / "Zones").mkdir(parents=True)
        (d / "GlobalRTP.ini").write_text("[GLOBAL_RTP]\nMaxFaultsPerWafer=3000\n",
                                         encoding="utf-8")
        (d / "Zones" / "Z1.ini").write_text(
            "[General]\nZoneName=PI Opening\n[Surface]\nHigh_Delta=25\n",
            encoding="utf-8")
        (d / manre.FILENAME).write_text(SAMPLE, encoding="utf-8")

        # 파서 대상 목록에 들어간다
        names = {p.name for p in ini_parser.config_ini_files(d)}
        assert manre.FILENAME in names, names

        cfgs = ini_parser.scan_tree(d.parent, default_level="PI3",
                                    default_equipment="AOI-13")
        rows, _m = ini_parser.build_pivot(
            [c for c in cfgs if ini_parser.config_valid(c)])
        cls = [r for r in rows if r["zone"] == ini_parser.MANRE_ZONE]
        assert len(cls) == 4, [r["param"] for r in cls]     # MaxCount 있는 행만
        for r in cls:
            assert r["alg"] == ini_parser.MANRE_ALG
            assert r["use"] is False, "기본은 전부 사용=N(사람이 고른다)"
            assert r["extract"]["src_file"] == manre.FILENAME
            assert r["extract"]["section"] == manre.SECTION_GENERAL
            assert r["extract"]["transform"] == "RAW", "개수라 계수 적용 금지"
        by = {r["param"]: list(r["values"].values())[0] for r in cls}
        assert by["0 Accept"] == 0 and by["2 Missing Bump"] == 10, by
        # 설정키(재추출 키) = 분류 Code — 이름을 바꿔도 값이 붙는다
        keys = {r["extract"]["key"] for r in cls}
        assert keys == {"0", "2", "28", "71"}, keys
    print("  양식 피벗 연결(Max Count 만·사용=N·RAW) OK")


def test_commonality_excludes_max_count():
    """commonality 는 ManReClassify(Max Count)를 파싱하지 않는다.

    ManReClassify.ini 는 장비 C드라이브 공용 파일(`c$\\Bis\\data\\dds`)이지
    Scanresult 데이터가 아니다. 슬롯 폴더에 어쩌다 끼어 있어도 commonality 조사
    대상이 아니어야 한다(사용자 확정). 양식 만들기(장비 수집)는 그대로 포함한다."""
    from param_manager import commonality as cm  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as tmp:
        slot = Path(tmp) / "ASD" / "CX01"        # Lot 슬롯 폴더
        (slot / "Zones").mkdir(parents=True)
        (slot / "GlobalRTP.ini").write_text("[GLOBAL_RTP]\nMaxFaultsPerWafer=3000\n",
                                            encoding="utf-8")
        (slot / "Zones" / "Z1.ini").write_text(
            "[General]\nZoneName=PI Opening\n[Surface]\nHigh_Delta=25\n",
            encoding="utf-8")
        # 슬롯에 ManReClassify 가 끼어 있어도(장비가 저장했든 잘못 복사됐든)
        (slot / manre.FILENAME).write_text(SAMPLE, encoding="utf-8")

        # commonality 파싱 대상 목록에서 제외돼야 한다
        got = {p.name for p in ini_parser.config_ini_files(slot, include_manre=False)}
        assert manre.FILENAME not in got, got
        assert "GlobalRTP.ini" in got, "나머지는 그대로 읽혀야 한다"

        # commonality parse_lots → 피벗에 Classification/Max Count 행이 없어야 한다
        pivot, _labels = cm.parse_lots([("ASD", slot)], level="PI3")
        cls = [r for r in pivot if r["zone"] == ini_parser.MANRE_ZONE]
        assert cls == [], [r["param"] for r in cls]

        # 대조: 양식 만들기(기본 include_manre=True)는 그대로 포함한다
        got2 = {p.name for p in ini_parser.config_ini_files(slot)}
        assert manre.FILENAME in got2, got2
    print("  commonality 는 Max Count 제외 / 양식 만들기는 포함 OK")


def test_collector_copies_from_dds_read_only():
    """장비 공용 파일을 `c$\\Bis\\data\\dds` 에서 가져오고 **원본은 건드리지 않는다**."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "c$"
        job = root / "Job" / "PI3_MAIN" / "Setup1" / "Recipes" / "PI"
        (job / "Zones").mkdir(parents=True)
        (job / "GlobalRTP.ini").write_text("[GLOBAL_RTP]\nMaxFaultsPerWafer=3000\n",
                                           encoding="utf-8")
        (job / "Zones" / "Z1.ini").write_text(
            "[General]\nZoneName=Z\n[Surface]\nHigh_Delta=25\n", encoding="utf-8")
        dds = root / "Bis" / "data" / "dds"
        dds.mkdir(parents=True)
        src = dds / manre.FILENAME
        src.write_text(SAMPLE, encoding="utf-8")
        before = src.read_bytes()

        staging = Path(tmp) / "staging"
        planned, _plan, _srcs = collector.collect_equipment(
            "10.0.0.5", staging, lambda k, t, items, m: list(items),
            job_root_override=root / "Job",
            confirm=lambda p: True)
        dests = {d for _s, _r, d in planned}
        assert manre.FILENAME in dests, dests
        assert (staging / "PI" / manre.FILENAME).is_file()
        # 원본 훼손 금지
        assert src.read_bytes() == before

        # 경로 규칙
        p = str(collector.manre_path("10.0.0.5"))
        assert p.startswith("\\\\10.0.0.5\\c$"), p
        for part in manre.FILENAME, "Bis", "dds":
            assert part in p, p
    print("  c$\\Bis\\data\\dds 수집 + 원본 무변경 OK")


def test_missing_file_is_not_fatal():
    """구 장비처럼 파일이 없으면 조용히 건너뛴다(나머지 수집을 막지 않는다)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "c$"
        job = root / "Job" / "PI3_MAIN" / "Setup1" / "Recipes" / "PI"
        (job / "Zones").mkdir(parents=True)
        (job / "GlobalRTP.ini").write_text("[GLOBAL_RTP]\nMaxFaultsPerWafer=3000\n",
                                           encoding="utf-8")
        (job / "Zones" / "Z1.ini").write_text(
            "[General]\nZoneName=Z\n[Surface]\nHigh_Delta=25\n", encoding="utf-8")
        staging = Path(tmp) / "staging"
        planned, _p, _s = collector.collect_equipment(
            "10.0.0.5", staging, lambda k, t, items, m: list(items),
            job_root_override=root / "Job",
            confirm=lambda p: True)
        dests = {d for _s2, _r, d in planned}
        assert manre.FILENAME not in dests
        assert "GlobalRTP.ini" in dests, "나머지 수집은 정상이어야 한다"
    print("  파일 없는 장비도 안전(건너뜀) OK")


if __name__ == "__main__":
    for t in [test_max_count_is_field_11, test_empty_fields_are_preserved,
              test_zero_is_valid_not_missing, test_internal_bin_and_customer_order,
              test_comment_only_at_line_start, test_short_row_and_duplicate_code,
              test_flows_into_form_pivot, test_commonality_excludes_max_count,
              test_collector_copies_from_dds_read_only,
              test_missing_file_is_not_fatal]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
