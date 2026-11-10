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
        # upsert (호기, 변형) → 계수 (MAG 은 참고열)
        assert coefstore.upsert(rows, "AOI-K2", "PI", 0.8456665875666588, mag="3.14")
        assert coefstore.upsert(rows, "AOI-K2", "PI-bubble", 0.7696441409644141,
                                mag="5.0")
        # 중복 upsert(overwrite=False) 는 유지
        assert not coefstore.upsert(rows, "AOI-K2", "PI", 0.99)
        coefstore.save(p, rows)
        rows2 = coefstore.load(p)
        # 변형 매칭(대소문자·구분자 무시: PI-bubble == pi_bubble)
        assert abs(coefstore.lookup(rows2, "aoi_k2", "PI") - 0.8456665875666588) < 1e-9
        assert coefstore.lookup(rows2, "AOI-K2", "pi_bubble") == 0.7696441409644141
        assert coefstore.lookup(rows2, "AOI-K2", "x20") is None
        # 변형 없는 행 = 호기 공통 폴백(변형이 매칭 안 될 때만)
        rows3 = [{"호기": "AOI-7", "MAG": "", "변형": "", "계수": "0.5", "비고": ""}]
        assert coefstore.lookup(rows3, "AOI-7", "PI") == 0.5
        assert coefstore.lookup(rows3, "AOI-7", "") == 0.5
        # 표시용
        mc = coefstore.machine_coefs(rows2, "AOI-K2")
        assert len(mc) == 2 and {m["변형"] for m in mc} == {"PI", "PI-bubble"}
    print("  coefstore OK: 왕복 + (호기,변형) 매칭 lookup(공통 폴백) + 표시용")


def test_scan_tree_per_equipment_coef():
    """coef_lookup 으로 장비별(호기+변형) 계수 적용 — 같은 폴더도 계수 다르게."""
    with tempfile.TemporaryDirectory() as tmp:
        d = _cfg(tmp)
        # 이 폴더가 어떤 변형으로 인식되는지 먼저 본다(폴더 라벨/PI 등)
        base = ini_parser.scan_tree(d, default_level="PI3", default_equipment="AOI-K2")
        variant = base[0].mag        # ParsedConfig.mag = 변형 라벨
        rows = []
        coefstore.upsert(rows, "AOI-K2", variant, 2.0)   # 그 변형에 일부러 2배
        lut = coefstore.make_lookup(rows)
        cfgs = ini_parser.scan_tree(d, default_level="PI3", default_equipment="AOI-K2",
                                    coef_lookup=lut)
        assert cfgs and cfgs[0].mag_value == "3.14"   # MAG 은 참고값으로 여전히 추출
        assert cfgs[0].scale_used == 2.0              # 저장소 계수(호기+변형)가 적용됨
        # 저장소에 없는 호기는 기본 계수(scale) 폴백
        cfgs2 = ini_parser.scan_tree(d, default_level="PI3", default_equipment="AOI-99",
                                     coef_lookup=lut, scale=0.5)
        assert cfgs2[0].scale_used == 0.5
    print("  coefstore OK: scan_tree 장비별(호기+변형) 계수 적용 + 미등록 호기 폴백")


def test_apply_form_scales_overwrites_and_persists():
    """양식에서 **사람이 확정한** 계수는 자동추정값을 덮어쓰고 파일에 반영된다."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, coefstore.COEF_FILENAME)
        rows = []
        coefstore.upsert(rows, "AOI-19", "PI", 0.5, mag="3.14")      # 자동추정값
        coefstore.upsert(rows, "AOI-19", "PI-bubble", 0.9, mag="1.00")

        n = coefstore.apply_form_scales(
            rows, "AOI-19", {"PI": 0.8456665875666588, "PI-bubble": 0.9},
            {"PI": "3.14", "PI-bubble": "1.00"}, note="PI3 양식 확정")
        assert n == 1, "값이 바뀐 1건만 반영(같은 값은 다시 쓰지 않음)"
        assert coefstore.lookup(rows, "AOI-19", "PI") == 0.8456665875666588
        got = [r for r in rows if r["변형"] == "PI"][0]
        assert got["비고"] == "PI3 양식 확정" and got["MAG"] == "3.14"

        # 저장 → 다시 읽어도 유지
        coefstore.save(path, rows)
        assert coefstore.lookup(coefstore.load(path), "AOI-19", "PI") \
            == 0.8456665875666588

        # MAG 를 몰라도(기존 양식 재편집) 변형으로 찾아 갱신
        n2 = coefstore.apply_form_scales(rows, "AOI-19", {"PI-bubble": 0.77}, {},
                                         note="PI3 양식 확정")
        assert n2 == 1
        assert coefstore.lookup(rows, "AOI-19", "PI-bubble") == 0.77
        # 새 변형인데 MAG 도 없으면 만들지 않는다(오타 변형 방지)
        assert coefstore.apply_form_scales(rows, "AOI-19", {"없는변형": 0.1}, {}) == 0
        assert coefstore.apply_form_scales(rows, "", {"PI": 0.1}, {"PI": "3.14"}) == 0
        assert len(rows) == 2
        # 새 변형이라도 MAG(실제 optic)를 알면 만든다
        n3 = coefstore.apply_form_scales(rows, "AOI-19", {"x20": 0.6}, {"x20": "2.0"})
        assert n3 == 1 and coefstore.lookup(rows, "AOI-19", "x20") == 0.6
        assert len(rows) == 3
    print("  coefstore OK: 양식 확정 계수 반영(호기+변형 덮어쓰기·새 변형은 MAG 있을 때만)")

def test_lookup_only_reads():
    """조회는 파일 내용을 바꾸지 않는다 — 없으면 None(추정 금지)."""
    rows = [{"호기": "AOI-13", "MAG": "3.14", "변형": "PI",
             "계수": "0.8456665875666588", "비고": "사람 확정"}]
    before = [dict(r) for r in rows]
    cb = coefstore.make_lookup(rows)
    assert cb("AOI-13", "PI") == 0.8456665875666588
    # 변형이 다르거나 없으면 **None** — 새 행을 만들지 않는다
    assert cb("AOI-13", "x20") is None
    assert cb("AOI-13", "") is None
    assert cb("AOI-99", "PI") is None
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
