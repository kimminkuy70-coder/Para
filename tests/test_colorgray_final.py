"""v14 Defect 분석: 최종 목록 CSV(대규모 Defect 분석 5-3 저장) → 기존 Color·Gray 매칭이 그 Defect 만 추출 + 최종 목록 엑셀.

- CSV 열 이름 = HTML(AOI Contrast Wizard) FL_HEAD 와 같은 약속.
- 매칭 폴더: 전체 경로는 그대로, 상대 경로(HTML 을 브라우저로 따로 연 경우)는 고른 폴더와 붙여 찾음.
- 프로그램 매칭에 있는 Color → 그 결과, 없으면 CSV 의 Gray 위치(HTML 계산값), 둘 다 없으면 이유.
- 최종 목록 엑셀 = HTML 최종 목록 엑셀과 같은 열 · 사진 3장, CSV 차례, 원본 무변경.
"""
import base64
import csv
import hashlib
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from param_manager import colorgray as cg  # noqa: E402
from param_manager.desktop_colorgray import DesktopColorGray, KINDS_FINAL, KINDS_OUT  # noqa: E402
from colorgray_fixture import COLOR_JPEG, make_wafer  # noqa: E402

# HTML(AOI_Contrast_Wizard_rev6.html) FL_HEAD — 바꾸면 둘 다(시험이 dist 의 HTML 과 대조)
FL_HEAD = ['5-1 #', 'Lot', 'Slot', 'ID', '장비 스캔 분류', '리뷰 결과', 'Recipe', 'Contrast(실제)', '상태', 'Area µm²', 'Width', 'Length',
           'BoxW', 'BoxH', 'Wafer X', 'Wafer Y', 'Die (장비 Col, Row)', 'Die (맵 X, Y)', '흑백 GL 평균 (원)', 'Color 파일', 'Color 전체 경로', 'Gray 파일',
           'Gray 전체 경로', 'GrayPX(3168x1024기준)', 'GrayPY(3168x1024기준)', 'CropW', 'CropH', '매칭폴더', '매칭폴더(고른 폴더부터)',
           'Lot 경로', 'Zone', 'Region', '판정 비트', '분류 코드', 'Zone 이름', '판정 종류']


class _Config:
    def __init__(self, root):
        self.root = root

    def local_state(self):
        return {"root": self.root}


def _digest(folder):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(folder).rglob("*") if p.is_file()}


def _csv(rows):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow(FL_HEAD)
    for r in rows:
        w.writerow([r.get(h, "") for h in FL_HEAD])
    return "﻿" + out.getvalue()


class FinalListTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.rcp = self.base / "RCP"
        self.w1 = make_wafer(self.rcp / "LOT_A", "W01")
        self.w2 = make_wafer(self.rcp / "LOT_A", "W02")
        (self.w2 / "frameToChuckPlane.ini").unlink()            # 프로그램 매칭 불가 Slot → CSV 값으로 대체
        self.html = Path(__file__).resolve().parents[1] / "frontend" / "public" / "defect" / "AOI_Contrast_Wizard_rev6.html"

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self, absolute=True):
        f = lambda w: str(w) if absolute else "RCP/LOT_A/" + w.name   # noqa: E731
        return [
            {"5-1 #": "3", "Lot": "LOT_A", "Slot": "W01", "ID": "7", "장비 스캔 분류": "B R Other", "리뷰 결과": "Accept", "Recipe": "1",
             "Contrast(실제)": "41.5", "BoxW": "12", "BoxH": "8", "Color 파일": "C1.jpg", "Gray 파일": "F1.t.1.jpg",
             "GrayPX(3168x1024기준)": "1100", "GrayPY(3168x1024기준)": "200", "매칭폴더": f(self.w1) if absolute else "",
             "매칭폴더(고른 폴더부터)": "RCP/LOT_A/W01", "Zone": "0", "판정 종류": "Event Defect"},
            {"5-1 #": "1", "Lot": "LOT_A", "Slot": "W02", "ID": "2", "Color 파일": "C1.jpg", "Gray 파일": "F2.t.1.jpg",
             "GrayPX(3168x1024기준)": "100", "GrayPY(3168x1024기준)": "200", "CropW": "60", "CropH": "40", "BoxW": "5", "BoxH": "5",
             "매칭폴더": f(self.w2) if absolute else "", "매칭폴더(고른 폴더부터)": "RCP/LOT_A/W02"},
            {"5-1 #": "2", "Lot": "LOT_A", "Slot": "W01", "ID": "9", "Color 파일": "C3.jpg", "매칭폴더": f(self.w1) if absolute else "",
             "매칭폴더(고른 폴더부터)": "RCP/LOT_A/W01"},                                       # Color 파일 없음
            {"5-1 #": "4", "Lot": "LOT_B", "Slot": "W09", "ID": "1", "Color 파일": "X.jpg",
             "매칭폴더": str(self.base / "nowhere") if absolute else "", "매칭폴더(고른 폴더부터)": "RCP/LOT_B/W09"},
        ]

    def test_html_columns_are_the_contract(self):
        txt = self.html.read_text(encoding="utf-8")
        start = txt.index("const FL_HEAD=[") + len("const FL_HEAD=")
        head = eval(txt[start:txt.index("];", start) + 1])   # noqa: S307 - 시험: JS 배열 글(문자열만)
        self.assertEqual(head, FL_HEAD)
        self.assertIn(cg.FINAL_COLOR_COL, head)
        self.assertTrue(all(c in head for c in cg.FINAL_FOLDER_COLS))

    def test_parse_and_folder_rules(self):
        rows = cg.parse_final_csv(_csv(self.rows()))
        self.assertEqual([r["Color 파일"] for r in rows], ["C1.jpg", "C1.jpg", "C3.jpg", "X.jpg"])
        with self.assertRaises(ValueError):
            cg.parse_final_csv("a,b\n1,2\n")                     # 우리 형식이 아님
        rel = cg.parse_final_csv(_csv(self.rows(absolute=False)))
        self.assertIsNone(cg.final_folder(rel[0]))               # 상대 경로 = 고른 폴더가 있어야
        self.assertEqual(cg.final_folder(rel[0], self.base), self.w1)        # 고른 폴더 = RCP 의 위
        self.assertEqual(cg.final_folder(rel[0], self.rcp), self.w1)         # 고른 폴더 = RCP 자체
        self.assertIsNone(cg.final_folder(rel[3], self.rcp))

    def test_flow_only_listed_defects_final_workbook(self):
        before = _digest(self.rcp)
        a = DesktopColorGray(_Config(str(self.base / "local")))
        r = a.final_csv({"text": _csv(self.rows()), "name": "최종목록_20261115_101010.csv"})
        self.assertEqual((r["rows"], r["missing"], r["need_root"]), (4, 1, False))
        self.assertEqual(sorted(w["path"] for w in r["wafers"]), sorted([str(self.w1), str(self.w2)]))
        job = a.start({"wafers": [w["path"] for w in r["wafers"]], "output": ""})["job"]
        recs = {w["name"]: w["records"] for w in job["wafers"]}
        self.assertEqual([x["color"] for x in recs["W01"]], ["C1.jpg"])               # CSV 의 Color 만(C2 · C3 는 빠짐)
        self.assertEqual(recs["W01"][0]["box"], [12, 8])
        self.assertEqual((recs["W02"][0]["gray"], recs["W02"][0]["px"], recs["W02"][0]["crop_w"]), ("F2.t.1.jpg", 100, 60))   # CSV 값
        self.assertEqual(job["final"]["rows"], 4)
        with self.assertRaises(ValueError):                                            # 다른 길로 만든 기록에는 최종 사진 안 받음
            DesktopColorGray(_Config(str(self.base / "l2"))).put({"wafer": 0, "record": 0, "kind": "color_view", "data": ""})
        names = [w["name"] for w in job["wafers"]]
        for wi, w in enumerate(job["wafers"]):
            for ri, _ in enumerate(w["records"]):
                for kind in KINDS_OUT + KINDS_FINAL:
                    extra = {"box": [1, 2, 3, 4]} if kind == "crop" else {}
                    a.put({"wafer": wi, "record": ri, "kind": kind, "data": base64.b64encode(COLOR_JPEG).decode(), **extra})
            a.finish({"wafer": wi})
        fin = a.final_finish({})
        self.assertEqual((fin["rows"], fin["done"], fin["missing"]), (4, 2, 2))
        book = Path(fin["workbook"])
        self.assertEqual(book.name, "최종목록_최종목록_20261115_101010.xlsx")
        self.assertTrue(str(book).startswith(str(self.base / "local")))
        import openpyxl
        ws = openpyxl.load_workbook(book).active
        head = [c.value for c in ws[1]]
        self.assertEqual(head, [c[0] for c in cg.FINAL_COLS])
        self.assertEqual(head[8:11], ["Color", "Gray Crop (Defect 박스)", "Gray 프레임 (Defect 박스 · 노란 상자 = Crop 범위)"])
        body = [[c.value for c in row] for row in ws.iter_rows(min_row=2)]
        self.assertEqual([b[0] for b in body], [1, 2, 3, 4])                           # CSV 차례(5-1 #)
        st = {b[0]: (b[head.index("상태")], b[head.index("Gray 위치 계산")], b[head.index("사진 없음 이유")]) for b in body}
        self.assertEqual(st[3][:2], ("추출 완료", "Para 프로그램"))
        self.assertEqual(st[1][:2], ("추출 완료", "최종 목록 CSV 값(HTML 계산)"))
        self.assertTrue(st[2][2].startswith("Color 파일 없음: C3.jpg"), st[2])
        self.assertTrue(st[4][2].startswith("매칭 폴더를 찾지 못함"), st[4])
        self.assertEqual(body[2][head.index("Box W×H")], "12×8")
        self.assertEqual(body[2][head.index("Contrast(실제)")], 41.5)
        self.assertEqual((body[2][head.index("장비 스캔 분류")], body[2][head.index("리뷰 결과")]), ("B R Other", "Accept"))
        with zipfile.ZipFile(book) as z:
            self.assertEqual(len([n for n in z.namelist() if n.startswith("xl/media/")]), 6)   # 사진 3장 × 2줄
        self.assertEqual(_digest(self.rcp), before)                                    # 원본 읽기만
        self.assertEqual(sorted(names), ["W01", "W02"])

    def test_old_class_column_names_still_read(self):
        """v14.1.5: '첫번째 분류' → '장비 스캔 분류', '재분류' → '리뷰 결과'. v14.1.4 이하 HTML 이 저장한 CSV 의 옛 열 이름도 읽는다."""
        self.assertNotIn("첫번째 분류", [c[0] for c in cg.FINAL_COLS])
        self.assertNotIn("재분류", [c[0] for c in cg.FINAL_COLS])
        old = {"5-1 #": "1", "첫번째 분류": "B R Other", "재분류": "Accept"}
        self.assertEqual(cg._final_value({"row": old}, "장비 스캔 분류"), "B R Other")
        self.assertEqual(cg._final_value({"row": old}, "리뷰 결과"), "Accept")
        new = {"장비 스캔 분류": "X", "리뷰 결과": "Y", "첫번째 분류": "old"}
        self.assertEqual(cg._final_value({"row": new}, "장비 스캔 분류"), "X")              # 새 이름이 먼저

    def test_relative_paths_need_the_chosen_folder(self):
        a = DesktopColorGray(_Config(str(self.base / "local")))
        r = a.final_csv({"text": _csv(self.rows(absolute=False))})
        self.assertEqual((r["missing"], r["need_root"], r["wafers"]), (4, True, []))
        r = a.final_csv({"text": _csv(self.rows(absolute=False)), "root": str(self.rcp)})
        self.assertEqual((r["missing"], len(r["wafers"])), (1, 2))
        with self.assertRaises(ValueError):                                            # 결과를 원본 안에 쓰지 않음
            a.start({"wafers": [w["path"] for w in r["wafers"]], "output": str(self.w1 / "out")})


if __name__ == "__main__":
    unittest.main(verbosity=1)
