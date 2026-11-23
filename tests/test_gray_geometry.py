"""v14.4.1(#89) Defect 분석 Gray 위치 = 기본(Step 1 ~ 4) · 대규모(Step 5) 같은 계산(rev6 HTML 3절 geo*):

- 소유자 "대규모 모드가 Color 정보 파일 없이 흑백도 찾게끔 · 수정된 로직은 대규모, 기본 모드 둘다 동일하게".
- 프레임 크기 · 픽셀 크기는 레시피(배율)마다 다르다(#89 실제 Slot 3장: 3168×1024 · 2848×1024 · 2048×2048, 0.385 ~ 1.69 µm)
  → 변환 offset(= −M·(W/2, H/2)) · s_FrameData frameSize/PixelSize · RecipesInfo.ini Scan2DPixelSize 에서 읽고, 3168×1024 · 0.77 은 마지막 대체값.
- 목록이 없으면 Gray 사진 이름 + s_FrameData(잰 위치)를 Wafer2Table(이름의 정수 좌표)보다 먼저.
- 장비 프레임 기록(Surface.flt frameIdx · xInFrame · yInFrame)이 있으면 그 프레임 · 픽셀(두 번 찍힌 프레임은 Defect 좌표에 맞는 레코드).
- Color 정보 파일이 없으면 Color = Color 사진 이름(X.Y.c.….jpeg), Gray 는 Defect 좌표로.

시험 자료는 가짜 숫자다(실제 결과 폴더는 저장소에 넣지 않는다 — 소유자 지시). JS 는 HTML 에서 꺼내 node 로 돌린다(node 가 없으면 건너뜀).
"""
import json
import re
import shutil
import struct
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "frontend" / "public" / "defect"
DIST = ROOT / "frontend" / "dist" / "defect"
HTML = PUB / "AOI_Contrast_Wizard_rev6.html"

FUNCS = ["tfSize", "tfPix", "parseRecipesInfo", "parseIni", "geoSize", "geoPix", "geoChoose", "geoRect", "geoCount", "geoPlan",
         "geoPtsDefs", "geoRecHit", "geoFrameOf", "geoHit", "cgTfFor", "cgPool", "cgFrames", "cgTfKey", "parseTransform", "readText",
         "geoLoad", "geoFd", "geoGrayNames", "geoFdNear", "geoFramesFromNames", "geoLoadFd", "cgFrameData", "readField",
         "dirFromFiles", "cgColorsFromNames", "cgCropSize"]
CONSTS = ["TYPE_SIZE", "num", "CNAME_RE", "GEO_W", "geoFirst", "geoWhy", "geoModel", "lower", "natCmp", "CG", "pyFloat", "pyRound",
          "cgGet", "cgMap", "CG_TF_NUM"]


def _function_src(text: str, name: str) -> str:
    i = text.index(f"function {name}(")
    if text[max(0, i - 6):i] == "async ":
        i -= 6
    j = text.index("{", text.index(")", text.index("(", i)))
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
    """'const 이름=…;' 한 문장(여러 줄 객체도) — 괄호 깊이 0 의 ';' 또는 줄 끝까지. eval 밖에서 보이게 var 로."""
    m = re.search(rf"^const {name}\s*=", text, re.M)
    if not m:
        raise ValueError(name)
    depth, k = 0, m.end()
    while k < len(text):
        c = text[k]
        if c in "{([":
            depth += 1
        elif c in "})]":
            depth -= 1
        elif c in ";\n" and depth == 0:
            break
        k += 1
    return "var" + text[m.start() + 5:k] + ";"


def _tf(a, ox, oy, rot=0.0):
    return f"[FRAME_2_CHUCK_PLANE]\nScan_X= {a} {rot} {ox}\nScan_Y= {-rot} {a} {oy}\n"


def _frame_data(recs):
    """s_FrameData.dat 192 byte 레코드(실제 결과 폴더 배치, .md 없음): WaferPos 72/80 · TablePos 88/96 · frameIdx 60 · recipe 58 · frameSize 108/112 · PixelSize 120."""
    out = bytearray()
    for r in recs:
        b = bytearray(192)
        struct.pack_into("<B", b, 58, r["rc"])
        struct.pack_into("<i", b, 60, r["fi"])
        struct.pack_into("<dddd", b, 72, r["wx"], r["wy"], r["tx"], r["ty"])
        struct.pack_into("<ii", b, 108, r.get("W", 2048), r.get("H", 2048))
        struct.pack_into("<d", b, 120, r.get("pix", 1.69))
        out += b
    return list(out)


PIX2 = 1.69
TF2048 = _tf(PIX2, -PIX2 * 1024, -PIX2 * 1024)          # 2D+3D 레시피 꼴: 2048×2048 프레임, 프레임 좌표 = 가운데
TF3168 = _tf(0.77, -0.77 * 1584, -0.77 * 512)
LIST = "Version=1\n100.200.t.1.jpeg,100000,200000\n103.200.t.1.jpeg,103000,200000\n"
# Wafer2Table 이 단위 · 0 이면 이름(Table 좌표) = Wafer 좌표 — s_FrameData 의 잰 위치는 이름과 (2, 7) µm 다르게 둔다
W2T = "[WAFER ALIGNMENT]\nWafer2Table_X= 1 0 0\nWafer2Table_Y= 0 1 0\n"
NAMES = ["100000.200000.t.1.jpeg", "103000.200000.t.1.jpeg"]
FD = [  # 같은 frameIdx 7 이 두 번(두 번 찍은 프레임: 480 µm 떨어짐) — 두 번째가 Defect 와 맞음
    dict(rc=1, fi=7, wx=100002.0, wy=200007.0 - 480, tx=100000, ty=199520),
    dict(rc=1, fi=7, wx=100002.0, wy=200007.0, tx=100000, ty=200000),
    dict(rc=1, fi=8, wx=103002.0, wy=200007.0, tx=103000, ty=200000),
]
RINFO = "[Recipe-1]\nName=PI\nScan2DPixelSize=0.7708\nColorPixelSize=0.462\n[Recipe-2]\nName=x5\nScan2DPixelSize=1.538\nColorPixelSize=0.1725\n"

HARNESS = r"""
const P=JSON.parse(require('fs').readFileSync(0,'utf8'));
eval(P.src);
const mkf=(name,data)=>({name,arrayBuffer:async()=>typeof data==='string'?new TextEncoder().encode(data).buffer:new Uint8Array(data).buffer});
const dir=files=>{const m=new Map();for(const [n,d] of Object.entries(files))m.set(n.toLowerCase(),mkf(n,d));return dirFromFiles('R/W',m)};
const pt=(x,y,r)=>[x,y,r];
(async()=>{const R={};
  // ① 2048×2048 프레임(변환 offset 에서): 프레임 아래쪽 절반(py > 1024)도 찾는다 — 종전 3168×1024 고정은 py < 1024 만 받았다
  let G=await geoLoad(dir({'ScanResultImageList.txt':P.list,'frameToChuckPlane.1.ini':P.tf2048}),[pt(100000,200000,1)],false);
  const X=100000+P.pix2*(1500-1024),Y=200000+P.pix2*(1800-1024);
  let h=geoHit(G,X,Y,1,0,0,0);R.big={size:geoSize(G,1),pix:geoPix(G,1),frame:h&&h.frame.file,px:h&&h.px,py:h&&h.py,model:h&&h.model,W:h&&h.W};
  // ② 같은 점이 두 프레임에 들면 가장자리에서 먼 쪽(가운데 쪽)
  h=geoHit(G,101700,200000,1,0,0,0);R.central=h&&[h.frame.file,Math.round(h.px)];
  // ③ 3168×1024 변환: 종전과 같은 크기
  G=await geoLoad(dir({'ScanResultImageList.txt':P.list,'frameToChuckPlane.1.ini':P.tf3168}),[pt(100000,200000,1)],false);R.std=geoSize(G,1);
  // ④ 변환 파일 없음: 가운데 모델 — 픽셀 = s_FrameData → RecipesInfo, 크기 = s_FrameData → 3168×1024
  G=await geoLoad(dir({'ScanResultImageList.txt':P.list,'s_FrameData.dat':P.fd}),[pt(100000,200000,1)],false);
  h=geoHit(G,100000+1.69*100,200000,1,0,0,0);R.centerFd={src:G.src.tf,size:geoSize(G,1),pix:geoPix(G,1),px:h&&h.px,py:h&&h.py,model:h&&h.model};
  G=await geoLoad(dir({'ScanResultImageList.txt':P.list,'RecipesInfo.ini':P.rinfo}),[pt(100000,200000,2)],false);
  R.centerRi={size:geoSize(G,2),pix:geoPix(G,2),pix1:geoPix(G,1),cp:G.rcpix.get(2)};
  // ⑤ 목록 없음: Gray 사진 이름 + s_FrameData(잰 위치)가 Wafer2Table(이름 좌표)보다 먼저
  const nm={};for(const n of P.names)nm[n]='';
  G=await geoLoad(dir({...nm,'Wafer2Table.ini':P.w2t,'s_FrameData.dat':P.fd,'frameToChuckPlane.1.ini':P.tf2048}),[pt(100000,200000,1)],false);
  R.names={src:G.src.frames,first:[G.frames[0].x,G.frames[0].y]};
  G=await geoLoad(dir({...nm,'Wafer2Table.ini':P.w2t,'frameToChuckPlane.1.ini':P.tf2048}),[pt(100000,200000,1)],false);
  R.namesW2t={src:G.src.frames,first:[G.frames[0].x,G.frames[0].y]};
  // ⑥ 장비 프레임 기록: frameIdx 7 · (1500, 1800) → 두 번째 레코드(Defect 좌표와 맞음)의 프레임 · 그 픽셀 그대로
  G=await geoLoad(dir({'ScanResultImageList.txt':P.list2,'frameToChuckPlane.1.ini':P.tf2048,'s_FrameData.dat':P.fd,...nm}),[pt(100000,200000,1)],'now');
  const dX=100002+P.pix2*(1500-1024),dY=200007+P.pix2*(1800-1024);
  h=geoHit(G,dX,dY,1,7,1500,1800);R.rec={model:h&&h.model,px:h&&h.px,py:h&&h.py,frame:h&&h.frame.file,dd:h&&h.dd};
  h=geoHit(G,dX+40,dY,1,7,1500,1800);R.recFar=h&&h.model;    // 5 µm 넘게 안 맞으면 기록을 안 쓰고 계산
  G=await geoLoad(dir({'ScanResultImageList.txt':P.list2,'frameToChuckPlane.1.ini':P.tf2048,'s_FrameData.dat':P.fd}),[pt(100000,200000,1)],'later');
  R.later=[G.recPending,G.fd];await geoLoadFd(G,dir({'s_FrameData.dat':P.fd,...nm}));R.laterAfter=[G.recPending,!!G.fd];
  // ⑦ Color 정보 파일이 없을 때 Color = 사진 이름(+0.5 µm, 레시피 = 이름 끝 번호)
  R.colors=await cgColorsFromNames(dir({'211002.218140.c.1433219536.1.jpeg':'','243057.69051.c.149049453.2.jpeg':'','x.t.1.jpeg':''}));
  R.colors=R.colors.map(c=>[c.file,c.FaultX,c.FaultY,c.RecipeNumber,c.fromName]);
  // ⑧ Crop(Color 시야) = Color 크기 × Color 픽셀 ÷ 그 레시피의 Gray 픽셀
  R.crop=[cgCropSize({},1.5),cgCropSize({ImageSizeX:'1380',ImageSizeY:'1036',PixelSizeX:'0.462',PixelSizeY:'0.462'},0.77),cgCropSize({},1.5,0.1725)];
  R.tfSize=[tfSize({inv:[[1,0],[0,1]],off:[0,0]}),tfSize(parseTransform(P.tf2048))];
  process.stdout.write(JSON.stringify(R));
})().catch(e=>{process.stderr.write(String(e&&e.stack||e));process.exit(1)});
"""


class GeometryJs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if not cls.node:
            return
        text = HTML.read_text(encoding="utf-8")
        src = "\n".join([_const_src(text, n) for n in CONSTS] + [_function_src(text, n) for n in FUNCS])
        list2 = "Version=1\n100000.200000.t.1.jpeg,100002,200007\n103000.200000.t.1.jpeg,103002,200007\n"
        payload = json.dumps({"src": src, "list": LIST, "list2": list2, "tf2048": TF2048, "tf3168": TF3168, "pix2": PIX2,
                              "fd": _frame_data(FD), "w2t": W2T, "names": NAMES, "rinfo": RINFO})
        out = subprocess.run([cls.node, "-e", HARNESS], input=payload, capture_output=True, text=True, timeout=60)
        if out.returncode:
            raise AssertionError(out.stderr)
        cls.r = json.loads(out.stdout)

    def setUp(self):
        if not self.node:
            self.skipTest("node 없음")

    def test_frame_size_from_transform(self):
        b = self.r["big"]
        self.assertEqual(b["size"], {"W": 2048, "H": 2048})
        self.assertAlmostEqual(b["pix"], PIX2, 9)
        self.assertEqual((b["frame"], b["model"], b["W"]), ("100.200.t.1.jpeg", "transform", 2048))
        self.assertAlmostEqual(b["px"], 1500, 6)
        self.assertAlmostEqual(b["py"], 1800, 6)                    # 종전 고정 크기(높이 1024)면 프레임 밖이었다
        self.assertEqual(self.r["central"], ["103.200.t.1.jpeg", 255])    # 두 프레임에 다 듦: 100.200 은 오른쪽 끝에서 18 px, 103.200 은 왼쪽 끝에서 255 px → 가운데 쪽
        self.assertEqual(self.r["std"], {"W": 3168, "H": 1024})
        self.assertEqual(self.r["tfSize"], [None, {"W": 2048, "H": 2048}])   # offset 0(시험용 단위 변환) = 크기 모름 → 종전 3168×1024

    def test_no_transform_center_model(self):
        c = self.r["centerFd"]
        self.assertIn("가운데 모델", c["src"])
        self.assertEqual((c["size"], c["model"]), ({"W": 2048, "H": 2048}, "center"))
        self.assertAlmostEqual(c["pix"], 1.69, 9)
        self.assertAlmostEqual(c["px"], 1024 + 100, 6)              # 가운데 기준(종전 기본 모드 '간단 모델'은 모서리 기준)
        self.assertAlmostEqual(c["py"], 1024, 6)
        ri = self.r["centerRi"]
        self.assertEqual(ri["size"], {"W": 3168, "H": 1024})
        self.assertEqual((ri["pix"], ri["pix1"], ri["cp"]), (1.538, 0.7708, 0.1725))   # RecipesInfo 레시피마다(0.7708 의 출처)

    def test_frames_from_names_prefer_frame_data(self):
        self.assertEqual(self.r["names"]["src"], "Gray 사진 이름 + s_FrameData.dat")
        self.assertEqual(self.r["names"]["first"], [100002.0, 200007.0])          # 잰 위치(같은 Table 좌표면 나중 레코드)
        self.assertEqual(self.r["namesW2t"]["src"], "Gray 사진 이름 + Wafer2Table.ini")
        self.assertEqual(self.r["namesW2t"]["first"], [100000, 200000])

    def test_equipment_frame_record(self):
        r = self.r["rec"]
        self.assertEqual((r["model"], r["px"], r["py"], r["frame"]), ("record", 1500, 1800, "100000.200000.t.1.jpeg"))
        self.assertLess(r["dd"], 0.01)
        self.assertEqual(self.r["recFar"], "transform")
        self.assertEqual(self.r["later"], [True, None])                    # 5-1 은 s_FrameData 를 안 읽음
        self.assertEqual(self.r["laterAfter"], [False, True])              # 5-2 에서 geoLoadFd

    def test_colors_from_names(self):
        self.assertEqual(self.r["colors"], [["211002.218140.c.1433219536.1.jpeg", "211002.5", "218140.5", "1", True],
                                            ["243057.69051.c.149049453.2.jpeg", "243057.5", "69051.5", "2", True]])

    def test_crop_uses_recipe_pixel(self):
        a, b, c = self.r["crop"]
        self.assertEqual((a["cw"], a["ch"]), (430, 323))                   # 1380 × 0.4674 ÷ 1.5
        self.assertEqual((b["cw"], b["ch"]), (828, 622))
        self.assertEqual((c["cw"], c["ch"]), (159, 119))                   # Color 픽셀 = RecipesInfo ColorPixelSize


class GeometryStatic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = HTML.read_text(encoding="utf-8")

    def _fn(self, name):
        return _function_src(self.t, name)

    def test_both_modes_same_function(self):
        self.assertIn("geoHit(G,d.X,d.Y,d.recipe,d.frameIdx,d.xInFrame,d.yInFrame)", self._fn("grayOf"))          # 기본
        self.assertIn("geoHit(g,C.x[i],C.y[i],C.rec[i]", self._fn("cgDefGray"))                                    # 대규모
        self.assertIn("await geoLoad(dirFromFiles(name,files)", self._fn("buildScan"))
        self.assertIn("await geoLoad(hit.d,geoPtsCols(s.cols)", self._fn("cgLoad"))
        for gone in ("function locateGray(", "function cgChoose(", "function cgRect(", "function openWindow(", "const GW=3168"):
            self.assertNotIn(gone, self.t)

    def test_big_mode_without_color_ini(self):
        load = self._fn("cgLoad")
        self.assertNotIn("if(!hit.ci){g.missing.push(CG.CI);g.diag=await cgDiag(root,look);s.warns.push(`매칭 파일 없음", load)
        self.assertIn("g.colors=await cgColorsFromNames(hit.d)", load)
        self.assertIn("colorModel", self.t)
        self.assertIn("if(g.colors.length&&g.colors[0].fromName)", self._fn("cgLink"))   # 사진 이름 Color = 기본 모드 연결(linkColor)

    def test_basic_window_is_shared_window(self):
        self.assertIn("photoWinOpen(listSrc(filtered(),+tr.dataset.k,tog,dOn))", self.t)          # Step 2 쌍별 상세 표
        self.assertEqual(self.t.count("photoWinOpen(baseSrc(P))"), 2)                              # 목록 더블 클릭 · Enter
        self.assertIn("ring:false", self._fn("baseView"))                                         # 기본 모드 = 측정 원 없음(소유자)
        self.assertIn("if(PW.src&&PW.src.key===P&&PW.w&&!PW.w.closed)photoWinShow()", self._fn("showPanel"))
        self.assertIn("step:dir=>panelStep(P,dir)", self._fn("baseSrc"))                          # ↑↓ = ☑ 줄만(목록과 같음)

    def test_dist_matches_public(self):
        self.assertEqual((DIST / HTML.name).read_bytes(), HTML.read_bytes())


if __name__ == "__main__":
    unittest.main()
