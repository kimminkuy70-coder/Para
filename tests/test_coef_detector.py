"""coef_detector 테스트 — RTP.txt(표시값) vs ini(원본값)로 계수 역추정."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import coef_detector as cd  # noqa: E402

ZONE_INI = """[General]
ZoneName = PI_Opening
[Surface]
BrightDiameter = 50
BrightLength = 100
DarkLength = 200
BrightArea = 100
DarkArea = 400
[Surface Feature Filter Width]
LowValue = 2.598604
[Surface Feature Filter Area]
LowValue = 16.881851
"""

# 표시값 = 원본 × 0.77 (LINEAR) 또는 × 0.77² (AREA). Width-Bright 는 near-1(=원본) 미끼.
RTP_TXT = """[PI_Opening]
Alg = Surface
Min_Defect_Width_-_Bright = 50
Min_Defect_Length_-_Bright = 77
Min_Defect_Length_-_Dark = 154
Min_Defect_Area_-_Bright = 59.29
Min_Defect_Area_-_Dark = 237.16
Alg = Surface_Feature_Filter_Width
Low_Value = 2.0
Alg = Surface_Feature_Filter_Area
Low_Value = 10.0
"""


def _mk(root):
    d = Path(root) / "PI"
    (d / "Zones").mkdir(parents=True)
    (d / "GlobalRTP.ini").write_text("[GLOBAL_RTP]\nMaxFaultsPerWafer=3000\n", encoding="utf-8")
    (d / "RTP.txt").write_text(RTP_TXT, encoding="utf-8")
    (d / "Zones" / "PI_Opening.ini").write_text(ZONE_INI, encoding="utf-8")
    return d


def test_detect_077():
    with tempfile.TemporaryDirectory() as tmp:
        d = _mk(tmp)
        dec = cd.detect_from_dir(d)
        assert dec["Coefficient"] is not None
        assert abs(dec["Coefficient"] - 0.77) < 0.005, dec["Coefficient"]
        assert dec["Display"] == 0.77
        assert dec["Confidence"] in ("High", "Medium")
        # near-1(Width-Bright)은 채택 군집에서 빠져야 → 채택 Count ≥ 5(비-1)
        assert dec["Count"] >= 5, dec["Count"]
    print(f"  coef_detector OK: 0.77 추정(conf={('High/Medium')}) + near-1 제외")


def test_no_rtp_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "PI"
        (d / "Zones").mkdir(parents=True)
        (d / "Zones" / "PI_Opening.ini").write_text(ZONE_INI, encoding="utf-8")
        dec = cd.detect_from_dir(d)
        assert dec["Coefficient"] is None
        assert dec["rtp"] is None
    print("  coef_detector OK: RTP.txt 없으면 Coefficient=None")


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
