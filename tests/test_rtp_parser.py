"""rtp_parser 헤드리스 테스트 — 합성 RTP 트리로 검증(업로드 데이터 비의존)."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import rtp_parser as rp  # noqa: E402

SAMPLE_RTP = """[PostProcess]   ; Zone name
Alg = Coplanarity
Plane_Id = 0 ;  ( Coplanarity PlaneId~255 )
Coplanarity_USL = 50 ;  ( Maximum allowed coplanarity value [micron].~8454143 )

[ScanArea]   ; Zone name
Alg = Surface
Contrast_Delta_-_Bright = 35 ;  ( Detection - Minimum bright defect contrast~8454143 )
Min_Defect_Length_-_Bright = 5.02 ;  in {µ} ( Filtering -Min length~8454143 )
"""

OPTIC_X20 = "[General]\n[AutoFocus]\nMag=3.14\nCameraName=STIL\n[Scan2d]\nMag=20\nCameraName=TDI\n"
OPTIC_X5 = "[General]\n[Scan2d]\nMag=5\nCameraName=TDI\n"


def _mk(d: Path, rtp=SAMPLE_RTP, optic=OPTIC_X20):
    d.mkdir(parents=True, exist_ok=True)
    (d / "RTP.txt").write_text(rtp, encoding="utf-8")
    (d / "OpticPreset.ini").write_text(optic, encoding="utf-8")
    (d / "Zones").mkdir(exist_ok=True)


def test_parse_rtp():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "RTP.txt"
        p.write_text(SAMPLE_RTP, encoding="utf-8")
        rows = rp.parse_rtp(p)
        assert len(rows) == 4, rows
        r = rows[0]
        assert r.zone == "PostProcess" and r.alg == "Coplanarity" and r.param_raw == "Plane_Id"
        assert r.value == "0"
        last = rows[-1]
        assert last.zone == "ScanArea" and last.unit == "µ"
        print(f"  parse_rtp OK: {len(rows)} rows, alg={rows[0].alg}")


def test_display_name():
    assert rp.display_name("Plane_Id") == "Plane Id"
    assert rp.display_name("Inner_Radius_[Microns]") == "Inner Radius [µm]"
    assert rp.display_name("Contrast_Delta_-_Bright") == "Contrast Delta - Bright"
    print("  display_name OK")


def test_detect_meta_mag():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "AOI-20" / "TB500_RDL4 - Multi"
        _mk(base / "x5", optic=OPTIC_X5)
        _mk(base / "x20", optic=OPTIC_X20)
        m5 = rp.detect_meta(base / "x5")
        m20 = rp.detect_meta(base / "x20")
        assert m5 == {"equipment": "AOI-20", "layer": "RDL", "recipe": "RDL4", "mag": "x5"}, m5
        assert m20["mag"] == "x20" and m20["recipe"] == "RDL4"
        print(f"  detect_meta OK: x5={m5['mag']} x20={m20['mag']} equip={m5['equipment']}")


def test_detect_meta_pi():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "AOI-15" / "R_TB500_LIVE_PI4"
        _mk(d, optic=OPTIC_X20)
        meta = rp.detect_meta(d)
        assert meta["layer"] == "PI" and meta["recipe"] == "PI4" and meta["mag"] == "-", meta
        print(f"  detect_meta PI OK: {meta['recipe']}")


def test_scan_and_pivot():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _mk(root / "AOI-20" / "TB500_RDL4 - Multi" / "x5", optic=OPTIC_X5)
        _mk(root / "AOI-20" / "TB500_RDL4 - Multi" / "x20", optic=OPTIC_X20)
        _mk(root / "AOI-21" / "TB500_RDL4 - Multi" / "x5", optic=OPTIC_X5)
        cfgs = rp.scan_tree(root)
        assert len(cfgs) == 3, cfgs
        rows, machines = rp.build_pivot(cfgs)
        assert set(machines) == {"AOI-20", "AOI-21"}, machines
        # x5 행 하나 — AOI-20, AOI-21 둘 다 값 있어야
        x5 = [r for r in rows if r["mag"] == "x5" and r["param"] == "Plane Id"][0]
        assert set(x5["values"]) == {"AOI-20", "AOI-21"}, x5["values"]
        print(f"  scan+pivot OK: configs={len(cfgs)} rows={len(rows)} machines={machines}")


def test_parse_optic_light():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        d = root / "AOI-20" / "TB500_RDL4 - Multi" / "x20"
        _mk(d, optic="[General]\nSignature=3\n[Scan2d]\nMag=20\nCameraName=TDI\nExposure=200\n")
        cfgs = rp.scan_tree(root)
        rows, _ = rp.build_pivot(cfgs)
        light = [r for r in rows if r["zone"] == "LIGHT"]
        assert light, "LIGHT zone 있어야"
        algs = {r["alg"] for r in light}
        assert "Scan2d" in algs and "General" in algs, algs
        mag = [r for r in light if r["param"] == "Mag"][0]
        assert "20" in mag["values"].values()
        print(f"  optic→LIGHT OK: {len(light)}개, algs={sorted(algs)}")


def test_template_recommend():
    tmpl = rp.load_template()
    assert len(tmpl) > 1000, len(tmpl)
    # 번들된 통일안에서 PostProcess/Coplanarity/Plane Id 가 비고(번역) 가져야
    rec = rp.recommend("PI", "PI2", "-", "PostProcess", "Coplanarity", "Plane Id")
    assert rec is not None and rec.get("desc_kr"), rec
    print(f"  template recommend OK: 항목수={len(tmpl)} 'Plane Id' 비고={rec['desc_kr']!r}")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            print(f"[RUN] {t.__name__}")
            t()
            print(f"[PASS] {t.__name__}\n")
        except Exception as e:  # noqa: BLE001
            failed += 1
            import traceback
            print(f"[FAIL] {t.__name__}: {e}")
            traceback.print_exc()
            print()
    print(f"==== {len(tests) - failed}/{len(tests)} passed ====")
    sys.exit(1 if failed else 0)
