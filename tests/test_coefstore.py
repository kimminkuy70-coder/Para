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
