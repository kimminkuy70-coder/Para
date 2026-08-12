"""변환계수 저장소(변환계수.xlsx) + OpticPreset MAG 추출 + 장비별 계수 적용 테스트."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import coefstore, ini_parser  # noqa: E402

# OpticPreset: Scan2d# 마다 Mag. 최신(KEEP 가진 마지막) 섹션의 Mag 를 읽어야 함.
OPTIC = (
    "[LIGHT]\n"
    "[Scan2d1]\nCameraName = TDI\nMag = 5.0\n"
    "[Scan2d2]\nCameraName = TDI\nMag = 3.14\n"
    "LightSrcDif_ColorFilter = 1\nLightSrcDif_NominalGL = 100\nAlg = Scan2d2\n")
ZONE = "[General]\nZoneName = PI Opening\n[Surface]\nMinDefectWidth_um = 3.5\n"


def _cfg(root, mag_optic=OPTIC):
    d = Path(root) / "cfg"
    (d / "Zones").mkdir(parents=True)
    (d / "Zones" / "Z.ini").write_text(ZONE, encoding="utf-8")
    (d / "OpticPreset.ini").write_text(mag_optic, encoding="utf-8")
    return d


def test_read_optic_mag():
    with tempfile.TemporaryDirectory() as tmp:
        d = _cfg(tmp)
        # 최신 target(Scan2d2, KEEP 보유) 의 Mag = 3.14
        assert ini_parser.read_optic_mag(d) == "3.14"
    print("  coefstore OK: OpticPreset 최신 Scan2d 의 Mag 추출(3.14)")


def test_coefstore_roundtrip_and_lookup():
    with tempfile.TemporaryDirectory() as tmp:
        p = coefstore.coef_path(tmp)
        coefstore.create_blank(p)
        rows = coefstore.load(p)
        assert rows == []
        # upsert (호기, MAG) → 계수
        assert coefstore.upsert(rows, "AOI-K2", "3.14", 0.8456665875666588, "PI")
        assert coefstore.upsert(rows, "AOI-K2", "5.0", 0.7696441409644141, "PI-bubble")
        # 중복 upsert(overwrite=False) 는 유지
        assert not coefstore.upsert(rows, "AOI-K2", "3.14", 0.99, "PI")
        coefstore.save(p, rows)
        rows2 = coefstore.load(p)
        # 숫자 근사 매칭(3.14 == 3.140)
        assert abs(coefstore.lookup(rows2, "aoi_k2", "3.140") - 0.8456665875666588) < 1e-9
        assert coefstore.lookup(rows2, "AOI-K2", "5") == 0.7696441409644141
        assert coefstore.lookup(rows2, "AOI-K2", "9.99") is None
        # 표시용
        mc = coefstore.machine_coefs(rows2, "AOI-K2")
        assert len(mc) == 2 and {m["변형"] for m in mc} == {"PI", "PI-bubble"}
    print("  coefstore OK: 왕복 + (호기,MAG) 근사 매칭 lookup + 표시용")


def test_scan_tree_per_equipment_coef():
    """coef_lookup 으로 장비별(호기+MAG) 계수 적용 — 같은 폴더도 계수 다르게."""
    with tempfile.TemporaryDirectory() as tmp:
        d = _cfg(tmp)
        rows = []
        coefstore.upsert(rows, "AOI-K2", "3.14", 2.0, "PI")   # 일부러 2배
        lut = coefstore.make_lookup(rows)
        cfgs = ini_parser.scan_tree(d, default_level="PI3", default_equipment="AOI-K2",
                                    coef_lookup=lut)
        assert cfgs and cfgs[0].mag_value == "3.14"
        assert cfgs[0].scale_used == 2.0        # 저장소 계수가 적용됨
        # 저장소에 없는 호기는 기본 계수(scale) 폴백
        cfgs2 = ini_parser.scan_tree(d, default_level="PI3", default_equipment="AOI-99",
                                     coef_lookup=lut, scale=0.5)
        assert cfgs2[0].scale_used == 0.5
    print("  coefstore OK: scan_tree 장비별 계수 적용 + 미등록 호기 폴백")


def test_apply_form_scales_overwrites_and_persists():
    """양식에서 **사람이 확정한** 계수는 자동추정값을 덮어쓰고 파일에 반영된다."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, coefstore.COEF_FILENAME)
        rows = []
        coefstore.upsert(rows, "AOI-19", "3.14", 0.5, "PI")      # 자동추정값
        coefstore.upsert(rows, "AOI-19", "1.00", 0.9, "PI-bubble")

        n = coefstore.apply_form_scales(
            rows, "AOI-19", {"PI": 0.8456665875666588, "PI-bubble": 0.9},
            {"PI": "3.14", "PI-bubble": "1.00"}, note="PI3 양식 확정")
        assert n == 1, "값이 바뀐 1건만 반영(같은 값은 다시 쓰지 않음)"
        assert coefstore.lookup(rows, "AOI-19", "3.14") == 0.8456665875666588
        got = [r for r in rows if r["MAG"] == "3.14"][0]
        assert got["비고"] == "PI3 양식 확정" and got["변형"] == "PI"

        # 저장 → 다시 읽어도 유지
        coefstore.save(path, rows)
        assert coefstore.lookup(coefstore.load(path), "AOI-19", "3.14") \
            == 0.8456665875666588

        # MAG 를 모르면(기존 양식을 다시 불러와 고친 경우) 변형으로 찾아 갱신
        n2 = coefstore.apply_form_scales(rows, "AOI-19", {"PI-bubble": 0.77}, {},
                                         note="PI3 양식 확정")
        assert n2 == 1
        assert coefstore.lookup(rows, "AOI-19", "1.00") == 0.77
        # 모르는 호기/변형이면 아무것도 만들지 않는다(엉뚱한 행 방지)
        assert coefstore.apply_form_scales(rows, "AOI-19", {"없는변형": 0.1}, {}) == 0
        assert coefstore.apply_form_scales(rows, "", {"PI": 0.1}, {"PI": "3.14"}) == 0
        assert len(rows) == 2
    print("  coefstore OK: 양식 확정 계수 반영(덮어쓰기·MAG 없으면 변형 매칭)")

def test_value_update_never_writes_coefstore():
    """**값을 읽는 작업은 `변환계수.xlsx` 를 고치지 않는다**(사용자 확정 2026-08).

    실제 사고: 조회 콜백이 (호기,MAG) 를 못 찾으면 RTP.txt 로 계수를 자동 추정해
    파일에 써 넣었다. 장비에서 target optic 이 바뀌면 MAG 이 달라지므로, 사람이
    넣은 값 대신 추정값이 새 행으로 들어가 **값 업데이트를 돌릴 때마다 계수가
    바뀌었다**. 소스 수준에서 다시 들어오지 못하게 막는다.
    """
    import re
    src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "param_manager")
    with open(os.path.join(src_dir, "equip_app.py"), encoding="utf-8") as fh:
        app = fh.read()

    m = re.search(r"def _coef_lookup_cb.*?(?=\n    def )", app, re.S)
    assert m, "_coef_lookup_cb 를 찾지 못함"
    body = m.group(0)
    assert "coefstore.lookup(" in body, "저장소 조회를 하지 않음"
    # 조회 콜백은 **읽기만** 한다
    assert "upsert" not in body, "조회 경로에서 변환계수를 쓰고 있음"
    assert "coef_detector" not in body, "조회 경로에서 계수를 자동 추정하고 있음"
    assert "coefstore.save" not in body, "조회 경로에서 파일을 저장하고 있음"

    # 파일을 쓰는 곳은 **사람이 양식에서 확정할 때 하나뿐**
    writers = [mm.group(0) for mm in
               re.finditer(r"    def _[a-z_]+\(self.*?(?=\n    def )", app, re.S)
               if "coefstore.save(" in mm.group(0)]
    names = [re.match(r"    def (\w+)", w).group(1) for w in writers]
    assert names == ["_coef_from_form"], names
    assert "apply_form_scales" in writers[0], "사람 확정 경로가 아님"

    # 파싱 경로(값 업데이트)는 저장을 부르지 않는다
    pm = re.search(r"def _parse_sources_busy.*?(?=\n    def )", app, re.S)
    assert pm and "coefstore.save" not in pm.group(0), "값 업데이트가 파일을 저장함"

    # 못 찾은 건 조용히 넘기지 말고 알린다
    rm = re.search(r"def _coef_report_missing.*?(?=\n    def )", app, re.S)
    assert rm and "_set_status" in rm.group(0), "계수 없음을 알리지 않음"
    assert "self.after(0" in rm.group(0), "백그라운드에서 tkinter 를 직접 만짐"
    print("  coefstore OK: 값 읽기는 변환계수.xlsx 를 고치지 않음(사람 확정만 씀)")


def test_lookup_only_reads():
    """조회는 파일 내용을 바꾸지 않는다 — 없으면 None(추정 금지)."""
    rows = [{"호기": "AOI-13", "MAG": "3.14", "변형": "PI",
             "계수": "0.8456665875666588", "비고": "사람 확정"}]
    before = [dict(r) for r in rows]
    cb = coefstore.make_lookup(rows)
    assert cb("AOI-13", "3.14") == 0.8456665875666588
    # MAG 이 다르거나 없으면 **None** — 새 행을 만들지 않는다
    assert cb("AOI-13", "3.20") is None
    assert cb("AOI-13", "") is None
    assert cb("AOI-99", "3.14") is None
    assert rows == before, "조회가 저장소를 바꿨다"
    print("  coefstore OK: lookup 은 읽기 전용(없으면 None)")


if __name__ == "__main__":
    fails = 0
    tests = [(n, f) for n, f in list(globals().items())
             if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        print(f"[RUN] {name}")
        try:
            fn()
            print(f"[PASS] {name}\n")
        except Exception as e:  # noqa: BLE001
            fails += 1
            import traceback
            traceback.print_exc()
            print(f"[FAIL] {name}: {e}\n")
    print(f"==== {len(tests) - fails}/{len(tests)} passed ====")
    sys.exit(1 if fails else 0)
