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
        _put_config(sr / "TB500_RDL2 - Multi" / "Setup1" / "VHK-RDL2" / wafer)
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
        assert "TB500_RDL2 - Multi" in found
        assert len(found["TB500_RDL2 - Multi"]) == 2, found["TB500_RDL2 - Multi"]
        c = found["TB500_RDL2 - Multi"][0]
        assert c.equipment == "AOI-18" and c.has_rtp
        print(f"  legacy discover OK: RDL2={len(found['TB500_RDL2 - Multi'])} variant0={c.variant}")


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


def test_discover_at_recipe_level():
    """입력 경로가 호기 위가 아니라 Recipe 폴더 직접이어도 x5/x20 을 잡아야."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = _tree_real(root)
        recipe_path = base / "TB500_RDL4 - Multi"
        found = dl.discover(str(recipe_path))
        assert "TB500_RDL4 - Multi" in found, found.keys()
        variants = sorted(c.variant for c in found["TB500_RDL4 - Multi"])
        assert variants == ["x20", "x5"], variants
        print(f"  recipe-level discover OK: {variants}")


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


def test_copy_never_damages_source_even_if_dest_equals_source():
    """목적지가 원본과 같아도 원본은 절대 지워지거나 바뀌지 않는다.

    · overwrite=True + dst==src : 종전엔 dst.unlink() 로 **원본을 삭제**했다 → 거부한다.
    · overwrite=False + dst==src: 이미 있으므로 `_1` 사본을 만들고 원본은 그대로 둔다
      (collector 와 같은 불변식). 어느 경우든 원본 내용·mtime 은 불변."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "Zones" / "Z.ini"
        src.parent.mkdir(parents=True)
        src.write_text("ORIGINAL", encoding="utf-8")
        before = (src.read_bytes(), src.stat().st_mtime_ns)

        # overwrite=True 는 원본 삭제 위험 → 반드시 거부
        try:
            dl.copy_one_file(src, src, overwrite=True)
        except RuntimeError:
            pass
        else:
            raise AssertionError("overwrite=True 에서 원본==목적지를 거부하지 않음")

        # overwrite=False 는 사본(_1)을 만들고 원본은 보존(예외 없이)
        res = dl.copy_one_file(src, src, overwrite=False)
        assert Path(res["dst"]).resolve() != src.resolve(), res
        assert Path(res["dst"]).is_file(), "사본이 생기지 않음"

        # 어느 경우든 원본은 내용·mtime 그대로여야 한다
        assert src.is_file() and src.read_bytes() == before[0], "원본 내용 변경됨"
        assert src.stat().st_mtime_ns == before[1], "원본 mtime 변경됨"
    print("  원본==목적지라도 원본 무손상(overwrite=True 거부·False 사본) OK")


def test_manual_real_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = _tree_real(root)
        wd = base / "TB500_RDL4 - Multi" / "x20"
        c = dl.parse_manual_wafer(str(wd))
        assert c.variant == "x20" and c.recipe_name == "TB500_RDL4 - Multi"
        assert c.equipment == "AOI-20" and c.has_rtp
        print(f"  manual real path OK: {c.recipe_name}/{c.variant}")


def test_pi_excluded():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = _tree_real(root)
        # PI 계열 폴더도 만들어 둠 → 결과에 나오면 안 됨
        _put_config(base / "TB500_PI2 - Multi" / "PI")
        _put_config(base / "TB500_PI2 - Multi" / "PI_bubble")
        found = dl.discover(str(root / "AOI-20"))
        assert not any("PI" in r for r in found), found.keys()
        assert any("RDL" in r for r in found)
        print(f"  PI 제외 OK: recipes={sorted(found.keys())}")


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
