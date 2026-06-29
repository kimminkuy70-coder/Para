"""downloader 모듈 헤드리스 테스트 — 가짜 트리로 검증(실제 드라이브 불필요).

두 구조 모두 검증:
  A) 구형/심층: <root>/AOI-18/Scanresult/<recipe>/<setup>/<code>/<wafer>/{Zones,RTP,Optic}
  B) 실제(사용자 다운로드): <root>/AOI-20/<recipe>/{x5|x20}/{Zones,RTP,Optic}
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import downloader as dl  # noqa: E402


def _put_config(d: Path, with_zones=True, rtp=True, optic=True):
    d.mkdir(parents=True, exist_ok=True)
    if with_zones:
        (d / "Zones").mkdir(exist_ok=True)
        (d / "Zones" / "z.dat").write_text("zone", encoding="utf-8")
    if rtp:
        (d / "RTP.txt").write_text("[Z]\nAlg = A\nk = 1 ; ( c )", encoding="utf-8")
    if optic:
        (d / "OpticPreset.ini").write_text("[x20]\nMag=20", encoding="utf-8")


def _tree_legacy(root: Path):
    sr = root / "AOI-18" / "Scanresult"
    for wafer in ("WAF1", "WAF2"):
        _put_config(sr / "TB500_PI2 - Multi" / "Setup1" / "VHK-PI2" / wafer)
    _put_config(sr / "TB500_RDL4 - Multi" / "Setup1" / "VHK-RDL4" / "W3", with_zones=False)
    return sr


def _tree_real(root: Path):
    base = root / "AOI-20"
    for recipe in ("TB500_RDL1 - Multi", "TB500_RDL4 - Multi"):
        _put_config(base / recipe / "x5")
        _put_config(base / recipe / "x20")
    return base


def test_discover_legacy():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _tree_legacy(root)
        found = dl.discover(str(root / "AOI-18"))
        assert "TB500_PI2 - Multi" in found
        assert len(found["TB500_PI2 - Multi"]) == 2, found["TB500_PI2 - Multi"]
        c = found["TB500_PI2 - Multi"][0]
        assert c.equipment == "AOI-18" and c.has_rtp
        print(f"  legacy discover OK: PI2={len(found['TB500_PI2 - Multi'])} variant0={c.variant}")


def test_discover_real_x5_x20():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _tree_real(root)
        found = dl.discover(str(root / "AOI-20"))
        assert "TB500_RDL4 - Multi" in found, found.keys()
        variants = sorted(c.variant for c in found["TB500_RDL4 - Multi"])
        assert variants == ["x20", "x5"], variants
        c = found["TB500_RDL4 - Multi"][0]
        assert c.equipment == "AOI-20" and c.has_rtp and c.has_zones and c.has_optic
        print(f"  real x5/x20 discover OK: RDL4 variants={variants}, equip={c.equipment}")


def test_copy_x5_x20_separately():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _tree_real(root)
        dest = Path(tmp) / "dl"
        found = dl.discover(str(root / "AOI-20"))
        for c in found["TB500_RDL4 - Multi"]:
            res = dl.copy_wafer(c, dest)
            assert res["count"] == 3, res          # Zones/z.dat + RTP + Optic
        # 목적지에 x5, x20 폴더가 분리되어 있어야
        rdl4 = dest / "AOI-20" / "TB500_RDL4 - Multi"
        assert (rdl4 / "x5" / "RTP.txt").is_file()
        assert (rdl4 / "x20" / "RTP.txt").is_file()
        print("  copy x5/x20 분리 OK")


def test_source_unchanged():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _tree_real(root)
        dest = Path(tmp) / "dl"
        c = dl.discover(str(root / "AOI-20"))["TB500_RDL4 - Multi"][0]
        src_rtp = c.config_dir / "RTP.txt"
        h = dl.sha256_file(src_rtp)
        dl.copy_wafer(c, dest)
        assert dl.sha256_file(src_rtp) == h and src_rtp.is_file(), "원본 변경됨!"
        print("  원본 무변경 OK")


def test_manual_real_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = _tree_real(root)
        wd = base / "TB500_RDL4 - Multi" / "x20"
        c = dl.parse_manual_wafer(str(wd))
        assert c.variant == "x20" and c.recipe_name == "TB500_RDL4 - Multi"
        assert c.equipment == "AOI-20" and c.has_rtp
        print(f"  manual real path OK: {c.recipe_name}/{c.variant}")


def test_split_paths():
    s = r'P:\AOI-18\x  O:\AOI-24\y'
    parts = dl.split_pasted_windows_paths(s)
    assert len(parts) == 2 and parts[0].startswith("P:") and parts[1].startswith("O:")
    print(f"  split paths OK: {parts}")


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
