"""v14.3.12 Defect 분석 wafer map = 웨이퍼 맵(Export Wafer Map) 기준 — 소유자 2026-11-18(#82 후속):

- "사용자가 die 위치를 읽을 때는 웨이퍼 맵 기준 — 웨이퍼 맵 표시할 때는 웨이퍼 맵 기준으로 계산해서 표시해".
- 번호: X = 장비 Col − cMin(왼쪽 0), Y = rMax − 장비 Row(아래 0) — 'Wafer Map 수정하기' 탭 그림과 같은 읽는 법.
  그림: 맨 위 줄 = 장비 Row 가장 작은 줄(rMin). 범위 = ProductInfo [ExportData] cMin~cMax · rMin~rMax(없으면 s_DieLocation 범위).
- 장비 Col = floor(X / XDieIndex)(CustomerDiePitch 보다 먼저), Die = s_DieLocation 만, 원 중심 = Wafer2Table 역변환.
- Flat Pos 3 = Notch 아래(소유자 확인), 다른 값은 '미확인' — 오른쪽 위 태그.
- 장비 Col/Row 는 마우스 · 상세 창에만. CSV · 엑셀은 장비 번호 열 그대로 + 맵 번호 열 추가(소유자 "바꾸지는 말고 추가로").
- 종전 샘플 맵 올리기 · sampleFit · Notch 고르기 · 지름/Edge 입력 · 맵 파일 비교는 지웠다.

시험 자료는 가짜 숫자다(실제 결과 폴더 · 맵 파일은 저장소에 넣지 않는다 — 소유자 지시).
JS 함수는 HTML 에서 꺼내 node 로 돌린다(node 가 없으면 그 시험만 건너뜀).
"""
import json
import re
import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from param_manager import colorgray as cg  # noqa: E402

PUB = ROOT / "frontend" / "public" / "defect"
DIST = ROOT / "frontend" / "dist" / "defect"
HTML = PUB / "AOI_Contrast_Wizard_rev6.html"

FUNCS = ["parseIni", "parseProduct", "dieOf", "parseDieLoc", "parseW2T", "mapFrame", "mapDie", "toMap", "flatTag",
         "parseScanLog", "badDiesOf"]
CONSTS = ["pick", "num", "dieTxt", "dieEq", "FLAT_DIR", "WAFER_R"]


def _function_src(text: str, name: str) -> str:
    i = text.index(f"function {name}(")
    j = text.index("{", text.index(")", i))
    depth = 0
    for k in range(j, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                return text[i:k + 1]
    raise ValueError(name)


def _const_src(text: str, name: str) -> str:
    m = re.search(rf"^const {name}=.*$", text, re.M)
    if not m:
        raise ValueError(name)
    return "var" + m.group(0)[5:]          # eval 안의 const 는 밖에서 안 보이므로 var 로


PRODUCT = """[GENERAL]
ExportFlatPos=3
AlignmentDieCol=4
AlignmentDieRow=3
[Geometric]
CustomerDiePitch_X=10010
CustomerDiePitch_Y=20020
XDieIndex=10000
YDieIndex=20000
Cols=12
Rows=10
Offset X=0
Offset Y=0
Flat Pos=3
[ExportData]
RefDieX=1
RefDieY=1
cMin=3
cMax=7
rMin=2
rMax=5
"""
# 가짜 Die 배치(장비 Col, Row): 맨 위 줄(rMin=2)은 3칸, 맨 아래 줄(rMax=5)은 1칸 — 위아래가 다른 모양
CELLS = [(c, 2) for c in (4, 5, 6)] + [(c, 3) for c in range(3, 8)] + [(c, 4) for c in range(3, 8)] + [(5, 5)]
W2T = "[WAFER ALIGNMENT]\nWafer2Table_X= 1 0 -50000\nWafer2Table_Y= 0 1 -80000\n"


def _dieloc_bytes(cells):
    out = bytearray()
    for c, r in cells:
        rec = bytearray(128)
        struct.pack_into("<dd", rec, 8, (c + .5) * 10000, (r + .5) * 20000)
        out += rec
    return list(out)


HARNESS = r"""
const P=JSON.parse(require('fs').readFileSync(0,'utf8'));
eval(P.src);
const loc=parseDieLoc(new Uint8Array(P.loc).buffer,null);
const prod=parseProduct(P.product),noExp=parseProduct(P.product.replace(/\[ExportData\][\s\S]*$/,''));
const s={product:prod,dieLoc:loc,w2t:parseW2T(P.w2t)},f=mapFrame(s);
const r={pitch:[f.px,f.py],range:[f.cMin,f.cMax,f.rMin,f.rMax],src:f.src,cells:f.cells.size,center:[f.cx,f.cy],csrc:f.csrc,flat:f.flat,warns:f.warns.length};
r.top=mapDie(55000,45000,s);r.bottom=mapDie(55000,105000,s);r.out=mapDie(35000,45000,s);r.txt=dieTxt(r.top);r.eq=dieEq(r.top);
r.map=toMap(55000,45000,f);
const s2={product:noExp,dieLoc:loc};const f2=mapFrame(s2);r.fallback={src:f2.src,range:[f2.cMin,f2.cMax,f2.rMin,f2.rMax]};
const s3={product:noExp};r.noNumber=dieTxt(mapDie(55000,45000,s3));
const bad=parseProduct(P.product.replace('cMax=7','cMax=8'));r.mismatch=mapFrame({product:bad,dieLoc:loc}).warns.length;
r.tags=[[3],[1],[3,1],[]].map(v=>flatTag(new Set(v)));
const a=Math.PI/36,c=Math.cos(a),sn=Math.sin(a),w=[123456,98765],t=[-(c*w[0]+sn*w[1]),-(-sn*w[0]+c*w[1])];
r.rot=parseW2T(`Wafer2Table_X= ${c} ${sn} ${t[0]}\nWafer2Table_Y= ${-sn} ${c} ${t[1]}`);
// v14.3.13 불량 Die: 리뷰 끝(VerifyDone=1) · 장비 BadDies 와 수가 같을 때만
const defs=[{x:55000,y:45000,reclassify:-9},{x:55000,y:45000,reclassify:0},{x:35000,y:65000,reclassify:0}];
const sl=t=>parseScanLog('[Version]\nName=10\n[General]\n'+t+'\n[2D]\nBadDies=99\n');
const bd=L=>{const o=badDiesOf({...s,defects:defs,scanLog:L});return {keys:[...o.keys],ok:o.ok,why:o.why}};
r.scanLog=sl('ScanDies=14\nBadDies=1\nDefectsNum=1\nVerifyDone=1\nGrabbingImageSucceeced=1');
r.badOk=bd(r.scanLog);r.badUnreviewed=bd(sl('BadDies=1\nVerifyDone=0\nGrabbingImageSucceeced=0'));
r.badMismatch=bd(sl('BadDies=3\nVerifyDone=1'));r.badNoLog=bd(null);
process.stdout.write(JSON.stringify(r));
"""


class MapRulesJs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if not cls.node:
            return
        text = HTML.read_text(encoding="utf-8")
        src = "\n".join([_const_src(text, n) for n in CONSTS] + [_function_src(text, n) for n in FUNCS])
        payload = json.dumps({"src": src, "product": PRODUCT, "loc": _dieloc_bytes(CELLS), "w2t": W2T})
        out = subprocess.run([cls.node, "-e", HARNESS], input=payload, capture_output=True, text=True, timeout=60)
        if out.returncode:
            raise AssertionError(out.stderr)
        cls.r = json.loads(out.stdout)

    def setUp(self):
        if not self.node:
            self.skipTest("node 없음")

    def test_frame_from_productinfo(self):
        r = self.r
        self.assertEqual(r["pitch"], [10000, 20000])                 # XDieIndex 먼저(CustomerDiePitch 아님)
        self.assertEqual(r["range"], [3, 7, 2, 5])
        self.assertIn("ExportData", r["src"])
        self.assertEqual(r["cells"], len(CELLS))
        self.assertEqual((r["center"], r["csrc"]), ([50000, 80000], "Wafer2Table"))
        self.assertEqual((r["flat"], r["warns"]), (3, 0))

    def test_wafer_map_numbers(self):
        r = self.r
        top, bottom, out = r["top"], r["bottom"], r["out"]
        # 장비 Col 5 · Row 2(= rMin, 맵 맨 위 줄) → X 2 · Y 3(아래부터 0 이라 맨 위 = 3)
        self.assertEqual((top["col"], top["row"], top["x"], top["y"], top["inDie"]), (5, 2, 2, 3, True))
        # 장비 Row 5(= rMax) → 맨 아래 줄 Y 0
        self.assertEqual((bottom["row"], bottom["x"], bottom["y"]), (5, 2, 0))
        # Die 안 위치 = 맵 방향(그 Die 왼쪽 아래에서): 장비 Y 가 Die 아래쪽에서 5000 → 맵에서는 위로 15000
        self.assertEqual((round(top["dx"]), round(top["dy"])), (5000, 15000))
        self.assertEqual((out["x"], out["y"], out["inDie"]), (0, 3, False))   # 장비 Col 3 · Row 2 = s_DieLocation 에 없음
        self.assertEqual((r["txt"], r["eq"]), ("2, 3", "장비 Col 5, Row 2"))
        self.assertEqual([round(v) for v in r["map"]], [25000, 75000])         # 맵 그림 좌표: 맨 위 줄은 위쪽

    def test_fallbacks(self):
        r = self.r
        self.assertEqual(r["fallback"]["range"], [3, 7, 2, 5])
        self.assertIn("s_DieLocation", r["fallback"]["src"])
        self.assertEqual(r["noNumber"], "장비 Col 5, Row 2")                  # 맵 기준을 못 정하면 장비 번호를 이름 붙여
        self.assertEqual(r["mismatch"], 1)                                     # [ExportData] ≠ s_DieLocation → 알림

    def test_flat_pos_tag(self):
        t = self.r["tags"]
        self.assertEqual((t[0]["txt"], t[0]["down"]), ("Flat Pos 3 · Notch ↓ 아래", True))
        self.assertEqual((t[1]["txt"], t[1]["down"]), ("Flat Pos 1 · Notch 미확인", False))
        self.assertIn("섞임", t[2]["txt"])
        self.assertEqual(t[3]["txt"], "Flat Pos ? · Notch 미확인")

    def test_wafer2table_center_with_rotation(self):
        self.assertAlmostEqual(self.r["rot"]["x"], 123456, places=3)
        self.assertAlmostEqual(self.r["rot"]["y"], 98765, places=3)


    def test_bad_die_only_when_reviewed_and_matches_scanlog(self):
        r = self.r
        self.assertEqual(r["scanLog"], {"verify": 1, "bad": 1, "defects": 1, "dies": 14, "grab": 1})   # [General] 만(뒤 [2D] 아님)
        self.assertEqual((r["badOk"]["keys"], r["badOk"]["ok"]), (["2,3"], True))         # reclassify 0 은 불량 아님
        u = r["badUnreviewed"]                                                              # 리뷰 전 · 이미지 찍기 멈춤
        self.assertFalse(u["ok"])
        self.assertIn("리뷰 전", u["why"])
        self.assertIn("이미지 찍기 중간에 멈춤", u["why"])
        self.assertEqual((r["badMismatch"]["ok"], r["badMismatch"]["why"]), (False, "장비 BadDies 3 ≠ 계산 1"))
        self.assertEqual((r["badNoLog"]["ok"], r["badNoLog"]["why"]), (False, "ScanLog.ini 없음"))


class MapStatic(unittest.TestCase):
    def setUp(self):
        self.html = HTML.read_text(encoding="utf-8")

    def test_old_map_logic_removed(self):
        code = self.html[self.html.index("<script"):]                  # 머리 주석(변경 기록)은 빼고
        for gone in ("function sampleFit", "function dieCells", "function notchInfo", 'id="mapBtn"', 'id="notch"', 'id="waferD"',
                     'id="edgeEx"', "cw.sampleMap", "parseWaferMap", "Params_WaferInfo.ini [Geometric] Center"):
            self.assertNotIn(gone, code)
        self.assertNotIn("psample", (PUB / "para-skin.js").read_text(encoding="utf-8"))
        self.assertNotIn("psample", (PUB / "para-skin.css").read_text(encoding="utf-8"))
        self.assertIn("아래부터 0", self.html[self.html.index('id="mapHelp"'):][:400])

    def test_exports_keep_equipment_and_add_map_columns(self):
        head = json.loads(self.html[self.html.index("const FL_HEAD=") + len("const FL_HEAD="):].split(";")[0].replace("'", '"'))
        k = head.index("Die (장비 Col, Row)")
        self.assertEqual(head[k + 1], "Die (맵 X, Y)")
        xl = self.html[self.html.index("XL_COLS=["):self.html.index("XL_ORIG=")]
        self.assertIn("['Die (장비 Col, Row)',110],['Die (맵 X, Y)',110]", xl)
        titles = [c[0] for c in cg.FINAL_COLS]
        self.assertEqual(titles[titles.index("Die (장비 Col, Row)") + 1], "Die (맵 X, Y)")
        self.assertIn("'DieCol','DieRow','Die맵X','Die맵Y'", self.html)          # 5-1 · 결과 CSV
        self.assertIn("'장비Col','장비Row'];", self.html)                        # Step 3 상세 CSV(끝에 추가)

    def test_screen_lists_use_map_numbers(self):
        self.assertIn("['Die (맵 X, Y)',120,'',null]", self.html)                 # 5-1 목록
        self.assertNotIn("['Die (장비 Col, Row)',140,'',null]", self.html)
        self.assertIn(">Die (맵 X, Y)</th>", self.html)                         # 쌍별 상세 표

    def test_dist_matches_public(self):
        for n in ("AOI_Contrast_Wizard_rev6.html", "para-skin.js", "para-skin.css"):
            if (DIST / n).exists():
                self.assertEqual((DIST / n).read_bytes(), (PUB / n).read_bytes(), n)

    def test_update_dialog_has_no_version_line(self):
        tsx = (ROOT / "frontend" / "src" / "AppUpdate.tsx").read_text(encoding="utf-8")
        self.assertNotIn("지금 버전 {info.current}", tsx)
        self.assertNotIn("'GitHub 릴리스'", tsx)


if __name__ == "__main__":
    unittest.main()
