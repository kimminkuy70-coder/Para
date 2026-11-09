"""AOI_Contrast_Wizard.html 시험 자료(Para #50) — 합성 결과 폴더 2개를 {경로: base64} JSON 으로 출력한다.
실제 고객 데이터가 아니다. JPEG 는 tests/colorgray_fixture.py 의 작은 그림을 재사용한다."""
import base64, json, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from colorgray_fixture import COLOR_JPEG, GRAY_JPEG  # noqa: E402


def rec(i, x, y, area=82.0, contrast=34.4512, bw=6.0, bh=5.0, recipe=1):
    b = bytearray(152)
    struct.pack_into("<hhi", b, 0, 0, 0, 1)
    struct.pack_into("<dddd", b, 8, x, y, x + 0.25, y + 0.25)
    struct.pack_into("<iii", b, 40, i, 100 + i, 0)
    struct.pack_into("<BBB", b, 60, 0, 0, recipe)
    struct.pack_into("<ddddd", b, 64, bw, bh, area, 7.5, 9.25)
    struct.pack_into("<d", b, 136, contrast)
    struct.pack_into("<i", b, 144, 3)
    return bytes(b)


MD = """<?xml version="1.0"?><Record size="152">
<Field name="x" type="double" offset="8"/><Field name="y" type="double" offset="16"/>
<Field name="Contrast" type="double" offset="136"/><Field name="area" type="double" offset="80"/></Record>"""
PRODUCT = "[Product]\nCustomerDiePitch_X=37249.0\nCustomerDiePitch_Y=44905.8\nCols=10\nRows=9\nOffsetX=0\nOffsetY=0\n"
COLORS = ("[C1.c.1.jpeg]\nFaultX=1100\nFaultY=200\nIndex=2\nRecipeNumber=1\n"
          "[Section2]\nFileName=C2.c.1.jpeg\nDefectIndex=3\n")
FRAMES = "Version=1\nF1.t.1.jpeg,0,0\nF2.t.1.jpeg,1000,0\n"
TRANSFORM = "Scan_X=1 0 0\nScan_Y=0 1 0\n"


def scan(name, defects, count):
    out = {f"{name}/Surface.flt": b"".join(rec(*d) for d in defects),
           f"{name}/Surface.flt.md": MD.encode(), f"{name}/ProductInfo.ini": PRODUCT.encode(),
           f"{name}/ColorImageGrabingInfo.ini": COLORS.encode(), f"{name}/ScanResultImageList.txt": FRAMES.encode(),
           f"{name}/frameToChuckPlane.ini": TRANSFORM.encode(), f"{name}/ScanLog.txt": f"Surface defects: {count}\n".encode(),
           f"{name}/F1.t.1.jpeg": GRAY_JPEG, f"{name}/F2.t.1.jpeg": GRAY_JPEG,
           f"{name}/C1.c.1.jpeg": COLOR_JPEG, f"{name}/C2.c.1.jpeg": COLOR_JPEG}
    return out


files = {}
# 기준 CA20: 1 = Die 검증 예, 2 = Gray 프레임 안 + Color 좌표 연결, 3 = Gray 범위 밖(Index 3 으로 Color 연결), 4 = 먼 곳
files.update(scan("Lot/CA20", [(1, 200498, 279473), (2, 1100, 200), (3, 5000, 5000, 120, 40.0), (4, 90000, 90000, 50, 31.0)], 4))
# 비교 CA27: 1 · 2 와 2 µm 안(유지), 신규 1개. ScanLog 수를 일부러 틀리게(교차 검증 경고)
files.update(scan("Lot/CA27", [(1, 200499, 279473.5), (2, 1100.5, 200, 82, 36.0), (9, 7000, 7000, 60, 45.0)], 5))
files["Lot/CA27/bad/Surface.flt"] = b"\0" * 150   # 잘못된 Record Size
print(json.dumps({k: base64.b64encode(v).decode() for k, v in files.items()}))
