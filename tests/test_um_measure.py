"""v14.4.1 Defect 분석 µm 표시 · [µm 로 보기] · Defect 박스 · 새 창 크기 측정(소유자 2026-11-23):

- Surface.flt 크기 값(area · BlobBreadth · BlobLength · Box)의 단위 = Slot 기준 픽셀 = RecipesInfo.ini 첫 레시피 Scan2DPixelSize.
  실제 Slot(Recipe 1 x20 0.3859 · Recipe 2 x5 1.538)에서 x5 Defect 의 Box · Area 가 x20 픽셀 기준(3.9855 배)으로 적혀 있었다 → 레시피마다가 아니라 Slot 에 하나.
- 리뷰PC 정보 = 장비 값 그대로 + 괄호 µm, 한 줄 띄우고 'µm 환산 픽셀', 목록 위 'µm 환산 픽셀 : 계수'(소유자 "이렇게만").
- [µm 로 보기](처음 = 켬): 목록 · 필터 · 정렬의 Area · Width. CSV · 엑셀 열은 그대로, Area µm² 값만 Slot 계수로(종전 0.7708 고정).
- '빨간 네모' → 'Defect 박스'(소유자), 크기 = Box × µm 환산 픽셀 ÷ 찍은 레시피 픽셀(종전 x5 Defect 가 4배 크게). GL 측정도 같은 Box.
- 새 창 [크기 측정 (M)]: 사진 원래 픽셀 · 직선 · 원 · 사각형(µm · µm²), 사진 픽셀 크기(찍은 레시피 · Color)는 이 화면에만, 보기만.

시험 자료는 가짜 숫자다(실제 결과 폴더 · 사진은 저장소에 넣지 않는다 — 소유자 지시). JS 는 HTML 에서 꺼내 node 로 돌린다(node 가 없으면 건너뜀).
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_gray_geometry import CONSTS, DIST, FUNCS, HTML, PUB, _const_src, _function_src, _tf  # noqa: E402

MORE_FUNCS = ["sizePix", "pixLine", "boxK", "mzVal"]
MORE_CONSTS = ["PIX", "pixTxt", "um4", "um2", "UM", "umK", "MZ", "MZ_T"]

RINFO = "[Recipe-1]\nName=x20\nScan2DPixelSize=0.3859\nColorPixelSize=0\n[Recipe-2]\nName=x5\nScan2DPixelSize=1.538\nColorPixelSize=0.1725\n"
LIST = "Version=1\n100.200.t.2.jpeg,100000,200000\n"
HARNESS = r"""
const P=JSON.parse(require('fs').readFileSync(0,'utf8'));
var localStorage={getItem:()=>null,setItem:()=>{}};
eval(P.src);
const mkf=(name,data)=>({name,arrayBuffer:async()=>new TextEncoder().encode(data).buffer});
const dir=files=>{const m=new Map();for(const [n,d] of Object.entries(files))m.set(n.toLowerCase(),mkf(n,d));return dirFromFiles('R/W',m)};
(async()=>{const R={};
  // ① RecipesInfo 첫 레시피 = Slot 기준(레시피 2 의 Defect 도 같은 계수), 찍은 레시피 픽셀(변환 파일) ÷ → Defect 박스 배율
  const G=await geoLoad(dir({'ScanResultImageList.txt':P.list,'RecipesInfo.ini':P.rinfo,'frameToChuckPlane.2.ini':P.tf5}),[[100000,200000,2]],false),s={geo:G};
  const sp=sizePix(s);R.sp=[sp.pix,sp.r,sp.name,sp.from,pixTxt(sp)];
  R.k=boxK({scan:s,recipe:2});R.box=35.869*R.k;
  R.um=[746.5536*um2(s),10.6991*sp.pix];
  // ② RecipesInfo 없음 → 변환 파일의 가장 작은 번호 레시피 픽셀 · ③ 자료 없음 → 0.7708(기본값)
  const G2=await geoLoad(dir({'ScanResultImageList.txt':P.list,'frameToChuckPlane.2.ini':P.tf5}),[[100000,200000,2]],false);
  const s2=sizePix({geo:G2});R.noRi=[+s2.pix.toFixed(4),s2.r,s2.from];const s3=sizePix({});R.none=[s3.pix,s3.from];
  // ④ 목록 위 한 줄
  const sb={geo:{_sp:{pix:0.7708,r:1,name:'PI',from:''}}};R.line=[pixLine([s,s]),pixLine([s,sb,sb])];
  // ⑤ [µm 로 보기]: 켬 = [계수², 계수], 끔 = [1, 1]
  R.umOn=umK(s);UM.on=false;R.umOff=umK(s);UM.on=true;
  // ⑥ 크기 측정: 사진 픽셀 1.5 µm · 원본 = 그림(sc 1)
  MZ.px={g:{pix:1.5},c:{pix:0.2}};MZ.sc={g:1,c:2};MZ.which='g';
  R.mz=[mzVal({t:'line',a:[0,0],b:[6,8]}),mzVal({t:'circle',a:[10,10],b:[15,10]}),mzVal({t:'rect',a:[0,0],b:[10,-6]}),mzVal({t:'line',a:[0,0],b:[10,0]},'c')];
  process.stdout.write(JSON.stringify(R));
})().catch(e=>{process.stderr.write(String(e&&e.stack||e));process.exit(1)});
"""


@unittest.skipUnless(shutil.which("node"), "node 없음")
class UmCalcTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        t = HTML.read_text(encoding="utf-8")
        src = "\n".join([_const_src(t, c) for c in CONSTS + MORE_CONSTS] + [_function_src(t, f) for f in FUNCS + MORE_FUNCS])
        pix5 = 1.5368711
        tf5 = _tf(pix5, -pix5 * 1584, -pix5 * 512)
        r = subprocess.run(["node", "-e", HARNESS], input=json.dumps({"src": src, "list": LIST, "rinfo": RINFO, "tf5": tf5}),
                           capture_output=True, text=True, timeout=60)
        if r.returncode:
            raise AssertionError(r.stderr)
        cls.R = json.loads(r.stdout)

    def test_slot_pixel_is_first_recipe(self):
        pix, r, name, frm, txt = self.R["sp"]
        self.assertEqual([pix, r, name, frm], [0.3859, 1, "x20", ""])
        self.assertEqual(txt, "0.3859 µm (Slot 기준 · Recipe 1 x20)")
        a, w = self.R["um"]
        self.assertAlmostEqual(a, 746.5536 * 0.3859 ** 2, places=6)      # 실제 Slot 예: 111.18 µm²(종전 0.7708² → 443.55)
        self.assertAlmostEqual(w, 10.6991 * 0.3859, places=6)

    def test_defect_box_scale(self):
        self.assertAlmostEqual(self.R["k"], 0.3859 / 1.5368711, places=6)  # x5 사진 픽셀로
        self.assertAlmostEqual(self.R["box"], 9.0, delta=0.01)              # 35.869(x20 기준) → x5 사진 9 픽셀

    def test_fallbacks(self):
        self.assertEqual(self.R["noRi"], [1.5369, 2, "RecipesInfo.ini 없음 → 사진 픽셀"])
        self.assertEqual(self.R["none"], [0.7708, "기본값"])

    def test_list_line(self):
        self.assertEqual(self.R["line"], ["µm 환산 픽셀 : 0.3859", "µm 환산 픽셀 : 0.3859 (Slot 1개) · 0.7708 (Slot 1개)"])

    def test_um_toggle_factor(self):
        a, w = self.R["umOn"]
        self.assertAlmostEqual(a, 0.3859 ** 2)
        self.assertAlmostEqual(w, 0.3859)
        self.assertEqual(self.R["umOff"], [1, 1])

    def test_measure_values(self):
        line, circle, rect, color = self.R["mz"]
        self.assertEqual([line["px"], line["um"]], ["10.0 px", "15.00 µm"])
        self.assertEqual(circle["um"], "지름 15.00 µm · 넓이 176.71 µm²")   # π × (5 × 1.5)²
        self.assertEqual([rect["px"], rect["um"]], ["10.0 × 6.0 px", "15.00 × 9.00 µm · 넓이 135.00 µm²"])
        self.assertEqual([color["px"], color["um"]], ["20.0 px", "4.00 µm"])  # Color: 그림 1 픽셀 = 원본 2 픽셀(sc) × 0.2 µm


class UmWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = HTML.read_text(encoding="utf-8")

    def _fn(self, name):
        return _function_src(self.t, name)

    def test_dist_same(self):
        self.assertEqual((DIST / HTML.name).read_bytes(), HTML.read_bytes())

    def test_review_info_lines(self):
        rv = self._fn("rvText")
        self.assertIn("`Area:${rawNum(v.area)} (${um4(v.area*sp.pix*sp.pix)} µm²)`", rv)
        self.assertIn("`Width:${rawNum(v.width)} (${um4(v.width*sp.pix)} µm)`", rv)
        self.assertIn("`Box Height:${rawNum(v.bh)}`,'',`µm 환산 픽셀: ${pixTxt(sp)}`,''", rv)   # 한 줄 띄우고(소유자)
        info = self._fn("infoRows")
        self.assertIn("['µm 환산 픽셀',", info)
        for f in (rv, info):
            self.assertNotIn("찍은 레시피", f)                                     # 찍은 레시피 픽셀 = 크기 측정 화면에만(소유자)

    def test_lists_and_filters(self):
        self.assertIn("+umCkHtml();", _const_src(self.t, "fltRngHtml"))
        self.assertIn('data-umh="a">Area (µm²)</th><th class="num" data-umh="w">Width (µm)</th>', self.t)
        self.assertIn("['Area (µm²)',92,'num','a','a'],['Width (µm)',68,'num','w','w']", self.t)          # 5-1
        self.assertIn("['Area (µm²)',86,'num',null,'a'],['Width (µm)',62,'num',null,'w']", self.t)       # 5-3
        for pre in ("${pre}Pix", "bigPix", "b5Pix", "c5Pix"):
            self.assertIn(f'class="pixln" id="{pre}"', self.t)
        self.assertIn("UM.on=localStorage.getItem('cw.um')!=='0'", self.t)                               # 처음 = 켬
        self.assertIn("if(e.key==='cw.um')umSet(", self.t)                                               # 기본 · 대규모 탭 같이
        for old in ("o.pix*o.pix", "S.o.pix*S.o.pix", "ob.pix*ob.pix"):                                   # Area µm² = Slot 계수(종전 0.7708²)
            self.assertNotIn(old, self.t)
        for f in ("xlRow0", "flRow"):
            self.assertIn("px2=um2(s)", self._fn(f))
        self.assertIn("fv(C.area[i]*um2(s))", self._fn("bigCsv"))
        self.assertIn("fv(C.area[i]*um2(s))", self._fn("pairCsv"))

    def test_defect_box(self):
        for f in ("cgDefHalf", "cgGL", "grayCrop"):
            self.assertIn("boxK(d)", self._fn(f), f)
        self.assertIn('<input type="checkbox" id="pwBox"> Defect 박스</label>', self.t)
        self.assertIn("'Defect 박스 끔'", _const_src(self.t, "pwLegend"))
        self.assertNotIn("빨간 네모", _const_src(self.t, "pwLegend") + _const_src(self.t, "XL_IMG_H"))

    def test_measure_wiring(self):
        init = self.t[self.t.index("function photoWinInit("):self.t.index("\nfunction photoWinFollow")]
        self.assertIn('id="pwMz"', init)
        self.assertIn("if(mzKey(doc,e))return;", init)
        self.assertIn("mzBind(doc);", init)
        self.assertIn("+MZ_HTML;", init)
        self.assertIn("MZ.on=false;", init)                                                              # 새 창은 사진 3칸으로 시작
        show = self.t[self.t.index("async function photoWinShow("):self.t.index("// ── 5-3: 사진 정밀 조사")]
        self.assertIn("if(MZ.on)mzLoad(doc,v);", show)
        self.assertIn(",d,", self._fn("baseView"))
        self.assertIn("d:bigDef(s,i),", self._fn("bigView"))
        self.assertIn("찍은 레시피", self._fn("mzPix") + self.t[self.t.index("// ── 새 창 사진 크기 측정"):self.t.index("const MZ=")])


if __name__ == "__main__":
    unittest.main()
