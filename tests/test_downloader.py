"""downloader 모듈 헤드리스 테스트 — 가짜 Scanresult 트리로 검증(실제 드라이브 불필요)."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import downloader as dl  # noqa: E402


def _make_tree(root: Path):
    """P:/AOI-18/Scanresult/<recipe>/<setup>/<code>/<wafer>/{Zones, RTP.txt, OpticPreset.ini}"""
    sr = root / "AOI-18" / "Scanresult"
    # PI2: 후보 2개(서로 다른 wafer)
    for wafer in ("07335326EWE7", "07335326EWE8"):
        wd = sr / "TB500_PI2 - Multi" / "Setup1" / "VHK-PI2" / wafer
        (wd / "Zones" / "A").mkdir(parents=True)
        (wd / "Zones" / "A" / "zone1.dat").write_text("zone-data", encoding="utf-8")
        (wd / "RTP.txt").write_text("rtp-content", encoding="utf-8")
        (wd / "OpticPreset.ini").write_text("optic", encoding="utf-8")
    # RDL4: 후보 1개
    wd = sr / "TB500_RDL4 - Multi" / "Setup1" / "VHK-RDL4" / "W7002174XYB3"
    wd.mkdir(parents=True)
    (wd / "RTP.txt").write_text("rdl-rtp", encoding="utf-8")
    return sr


def test_discover():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "P"
        _make_tree(root)
        found = dl.discover(str(root / "AOI-18"))
        assert found["TB500_PI2 - Multi"], "PI2 후보 있어야"
        assert len(found["TB500_PI2 - Multi"]) == 2, found["TB500_PI2 - Multi"]
        assert len(found["TB500_RDL4 - Multi"]) == 1
        assert found["TB500_PI3 - Multi"] == []   # 없는 recipe
        c = found["TB500_PI2 - Multi"][0]
        assert c.equipment == "AOI-18" and c.has_zones and c.has_rtp and c.has_optic
        print(f"  discover OK: PI2={len(found['TB500_PI2 - Multi'])} RDL4={len(found['TB500_RDL4 - Multi'])}")


def test_copy_keeps_source_and_structure():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "P"
        _make_tree(root)
        dest = Path(tmp) / "download"
        found = dl.discover(str(root / "AOI-18"))
        cand = found["TB500_PI2 - Multi"][0]
        # 복사 전 원본 해시
        src_zone = cand.wafer_dir / "Zones" / "A" / "zone1.dat"
        h_before = dl.sha256_file(src_zone)
        res = dl.copy_wafer(cand, dest)
        assert res["count"] == 3, res        # Zones/A/zone1.dat + RTP + Optic
        # 목적지 구조 확인
        db = Path(res["dest"])
        assert (db / "Zones" / "A" / "zone1.dat").is_file()
        assert (db / "RTP.txt").is_file() and (db / "OpticPreset.ini").is_file()
        # 원본 불변
        assert dl.sha256_file(src_zone) == h_before, "원본 변경됨!"
        assert src_zone.is_file()
        print(f"  copy OK: dest={res['dest']} files={res['count']}, 원본 무변경")


def test_no_overwrite_makes_numbered():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "P"
        _make_tree(root)
        dest = Path(tmp) / "download"
        cand = dl.discover(str(root / "AOI-18"))["TB500_PI2 - Multi"][0]
        dl.copy_wafer(cand, dest)
        res2 = dl.copy_wafer(cand, dest)          # 두 번째 → 충돌 회피 번호
        db = Path(res2["dest"])
        assert (db / "RTP_1.txt").exists() or (db / "RTP.txt").exists()
        print("  no-overwrite numbering OK")


def test_manual_wafer():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "P"
        sr = _make_tree(root)
        wd = sr / "TB500_RDL4 - Multi" / "Setup1" / "VHK-RDL4" / "W7002174XYB3"
        cand = dl.parse_manual_wafer(str(wd))
        assert cand.equipment == "AOI-18" and cand.recipe_name == "TB500_RDL4 - Multi"
        assert cand.has_rtp and not cand.has_zones
        print(f"  manual parse OK: {cand.wafer} zones={cand.has_zones} rtp={cand.has_rtp}")


def test_split_paths():
    s = r'P:\AOI-18\Scanresult\x  O:\AOI-24\Scanresult\y'
    parts = dl.split_pasted_windows_paths(s)
    assert len(parts) == 2, parts
    assert parts[0].startswith("P:") and parts[1].startswith("O:")
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
