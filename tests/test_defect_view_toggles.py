"""v14.1.5 Defect 분석(대규모) 화면 — 소유자 세션 대화(2026-11-16):

- 새 창으로 크게 보기: 흑백 사진(Gray Crop · Gray 프레임)의 Defect 박스 켜고 끄기([Defect 박스](v14.4.1 이름 — 종전 빨간 네모) · B 키, 이 PC 에 기억).
- 5-3 흑백 GL 측정 = 따로 테두리 박스 + [⭕ 측정 원 보기](측정 원만 켜고 끔, GL 값은 그대로).
- '첫번째 분류' → '장비 스캔 분류', '재분류' → '리뷰 결과'(화면 · CSV · 엑셀 전부).
- 5-1 필터 = 줄마다 제목 · 내용(Lot · Slot / Lot 제외 / 장비 스캔 분류 / 리뷰 결과 / 값 범위 / Recipe / 정렬), 값 범위 4개 한 줄, 분류 칸 = 같은 너비 격자.

실제로 그려지는지는 tools/test_desktop_ui.mjs(진짜 서버 + 엔진)가 본다. 여기서는 HTML · 겉모습 파일의 약속만.
"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUB, DIST = ROOT / "frontend" / "public" / "defect", ROOT / "frontend" / "dist" / "defect"
HTML = PUB / "AOI_Contrast_Wizard_rev6.html"


class _Ids(HTMLParser):
    """id → 조상 id 목록."""
    def __init__(self):
        super().__init__()
        self.stack, self.parents, self.classes = [], {}, {}
    VOID = {"input", "br", "meta", "link", "img", "hr", "source", "col", "area", "base", "wbr"}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.parents[a["id"]] = [i for _, i in self.stack if i]
            self.classes[a["id"]] = (a.get("class") or "").split()
        if tag not in self.VOID:
            self.stack.append((tag, a.get("id")))

    def handle_endtag(self, tag):
        for k in range(len(self.stack) - 1, -1, -1):
            if self.stack[k][0] == tag:
                del self.stack[k:]
                break


class DefectViewToggles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = HTML.read_text(encoding="utf-8")
        body = cls.t[cls.t.index("<body>"):cls.t.index("<script>")]
        cls.ids = _Ids()
        cls.ids.feed(body)

    def test_public_and_dist_same(self):
        for name in ("AOI_Contrast_Wizard_rev6.html", "para-skin.css", "para-skin.js"):
            self.assertEqual((PUB / name).read_bytes(), (DIST / name).read_bytes(), name)

    def test_old_class_names_gone(self):
        # 옛 이름은 '종전' 을 밝히는 설명 줄에만 남는다
        for n, line in enumerate(self.t.splitlines(), 1):
            if "첫번째" in line or "재분류" in line:
                self.assertIn("종전", line, f"{n}: {line[:120]}")
        for name in ("FL_HEAD=[", "XL_COLS=[", "VA=makeVT", "VB=makeVT", "VC=makeVT"):   # 정의 줄(다른 곳의 설명 · 사용은 빼고)
            i = self.t.index(name)
            seg = self.t[i:self.t.index("\n", i)]
            self.assertIn("장비 스캔 분류", seg, name)
            self.assertIn("리뷰 결과", seg, name)
        self.assertEqual(self.t.count("'장비스캔분류','리뷰결과'"), 2)          # 목록 CSV · 결과 CSV 머리

    def test_gl_box(self):
        p = self.ids.parents
        for i in ("glShow", "glR", "glSet", "glRun", "glSt", "glBar", "glHist", "glSort", "glRngAll"):
            self.assertIn("glBox", p[i], i)
        self.assertIn("b5p3", p["glBox"])
        self.assertIn("glbox", self.ids.classes["glBox"])
        self.assertIn(".glbox{border:", self.t)
        # 측정 원 = GLC.show(이 PC 에 기억), 그림 함수는 opt.ring 일 때만 원을 그린다
        self.assertIn("GLC.show=localStorage.getItem('cw.glShow')!=='0'", self.t)
        self.assertIn("if(opt.ring)glRing(", self.t)
        self.assertIn("if(d&&o.ring)glRing(", self.t)
        self.assertIn("if(opt.box)mark=cgDefBox(", self.t)
        self.assertIn("if(o.box)cgDefBox(", self.t)
        # 격자 작은 사진은 원 있는 것 · 없는 것 둘 다 준비(켜고 끌 때 사진을 다시 읽지 않음)
        self.assertIn("t={c,g,g0,gl,err}", self.t)

    def test_gl_run_final_list_only(self):
        # Para #84: [흑백 GL 측정] = 최종 목록(☑) 중 흑백 사진이 있는 Defect 만(종전 = 5-3 목록 전체 c5Pool)
        self.assertIn("const glTargets=()=>(C5.base||[]).filter(p=>p.pick&&glCan(p));", self.t)
        i = self.t.index("async function glRun(")
        body = self.t[i:self.t.index("\n", self.t.index("const G=new Map()", i))]
        self.assertIn("glTargets()", body)
        self.assertNotIn("c5Pool()", body)
        self.assertIn("C5.base=P.filter(p=>on.has(p.st));C5.items=glApply(C5.base);", self.t)

    def test_photo_window_red_box(self):
        i = self.t.index("function photoWinInit(")
        init = self.t[i:self.t.index("\nfunction photoWinFollow", i)]
        self.assertIn('id="pwBox"', init)
        self.assertIn("else if(k==='b'){pwBoxSet(!PWB.on)", init)
        self.assertIn("PWB.on=localStorage.getItem('cw.pwBox')!=='0'", self.t)
        show = self.t[self.t.index("async function photoWinShow("):self.t.index("// ── 5-3: 사진 정밀 조사")]
        # v14.4.1(#89): 기본 · 대규모 같은 창 — 측정 원은 칸 자료(v.ring)가 정함(기본 모드 = 없음, 대규모 = 5-3 [측정 원 보기])
        self.assertEqual(show.count("{box:PWB.on,ring:ring()}"), 4)            # 처음 그림 2 + 다시 그림 2
        self.assertIn("_redraw=", show)
        # 5-3 칸 · 엑셀 사진은 Defect 박스 그대로(새 창에서만 끔)
        xl = self.t[self.t.index("async function xlPhotos("):self.t.index("/** 엑셀 열:")]
        self.assertNotIn("box:", xl)

    def test_filter_rows(self):
        p = self.ids.parents
        for i in ("bigLot", "bigSlot", "bigLotBox", "bigCls", "bigFltIn", "bigFltRcp", "bigFltSort", "bigCsv"):
            self.assertIn("bigFlt", p[i], i)
        self.assertIn("fgrid", self.ids.classes["bigFlt"])
        heads = re.findall(r'<span class="fh">([^<]+)</span>', self.t[self.t.index('id="bigFlt"'):self.t.index('id="bigCnt"')])
        self.assertEqual(heads, ["Lot · Slot", "Lot 제외", "값 범위", "Recipe", "Zone", "정렬"])   # 분류 두 줄은 bigFacetFill 이 그림
        self.assertIn("grp(1,'장비 스캔 분류',", self.t)
        self.assertIn("grp(2,'리뷰 결과',", self.t)
        self.assertIn(".fgrid .chipgrid{", self.t)
        css = (PUB / "para-skin.css").read_text(encoding="utf-8")
        self.assertIn("body.pskin .fgrid .frow{", css)
        self.assertIn("body.pskin .glbox{", css)
        # Step 3 · 4 필터 줄은 종전 그대로(한 줄 조각을 이어 붙임)
        self.assertIn("function fltHtml(){return fltRngHtml()+fltRcpHtml()+fltZnHtml()+fltSortHtml()+fltClrHtml()}", self.t)


class Defect53Layout(unittest.TestCase):
    """v14.1.6(소유자): 하나씩 크게 → 리스트, 격자로 여러 개 → 격자 구조, 보기 = 줄바꿈 · 박스, 이 목록 사진 모두 미리 준비 → 사진 모두 불러오기(다른 색),
    [← 5-2] · [화면 테마] · [사진을 같은 창에서 보기] 삭제, 보이는 목록 모두 → 전체 선택, 모두 해제 → 전체 해제, 최종 목록 개수 = 배지."""
    @classmethod
    def setUpClass(cls):
        cls.t = HTML.read_text(encoding="utf-8")
        cls.ids = _Ids()
        cls.ids.feed(cls.t[cls.t.index("<body>"):cls.t.index("<script>")])
        cls.css = (PUB / "para-skin.css").read_text(encoding="utf-8")
        cls.js = (PUB / "para-skin.js").read_text(encoding="utf-8")

    def test_labels(self):
        self.assertIn('<button data-v5="one" aria-pressed="true">리스트</button><button data-v5="grid">격자 구조</button>', self.t)
        self.assertIn('class="c5load"', self.t)
        self.assertIn(">사진 모두 불러오기</button>", self.t)
        self.assertIn('id="c5pickAll" title="지금 보이는 목록을 모두 최종 목록에 넣습니다(☑)">전체 선택</button><button id="c5pickNone">전체 해제</button>', self.t)
        for old in ("하나씩 크게", "격자로 여러 개", "이 목록 사진 모두 미리 준비", "보이는 목록 모두", "보기:", "사진 준비 끝"):
            self.assertNotIn(old, self.t, old)

    def test_view_box_and_no_back_button(self):
        self.assertIn("c5stF", self.ids.parents)
        self.assertNotIn("toB2b", self.ids.parents)
        self.assertNotIn("#toB2b", self.t)
        box = self.t[self.t.index('<div class="c5stbox"'):self.t.index('id="c5stF"')]
        self.assertIn(">보기</b>", box)
        self.assertIn(".c5stbox{", self.t)
        self.assertIn("body.pskin .c5stbox{", self.css)

    def test_pick_badge(self):
        self.assertIn("$('#c5pickN').classList.toggle('on',n>0)", self.t)
        self.assertIn(".c5pick.on{", self.t)
        self.assertIn("body.pskin .c5pick.on{", self.css)
        self.assertIn("body.pskin button.c5load{", self.css)

    def test_header_theme_and_same_window_gone_in_program(self):
        self.assertIn("body.pskin #themeBtn,body.pskin header label:has(#inWin){display:none!important}", self.css)
        self.assertIn("d.documentElement.dataset.theme = 'light';", self.js)
        self.assertIn("localStorage.setItem('cw.inWin', '0')", self.js)
        self.assertNotIn("같은 창에서 보기', '사진을", self.js)



class GlDialogAndColors(unittest.TestCase):
    """v14.1.7(소유자): 측정 원 그리기 창이 커서 잘림 → 보이는 높이에 맞춤, 사진 양옆 ‹ › 로 다른 예시 사진, 색은 테마(남색 · 초록 + 회색)로 — 알록달록 정리."""
    @classmethod
    def setUpClass(cls):
        cls.t = HTML.read_text(encoding="utf-8")
        cls.css = (PUB / "para-skin.css").read_text(encoding="utf-8")

    def test_dialog_fits_and_arrows(self):
        dlg = self.t[self.t.index('<div class="busy gldlg" id="glDlg"'):self.t.index('<div class="busy" id="busy"')]
        self.assertLess(dlg.index('id="glPrev"'), dlg.index('id="glCv"'))
        self.assertLess(dlg.index('id="glCv"'), dlg.index('id="glNext"'))
        self.assertIn('id="glDPos"', dlg)
        self.assertIn("$('#glPrev').onclick=()=>glDlgStep(-1);$('#glNext').onclick=()=>glDlgStep(1);", self.t)
        self.assertIn("e.key==='ArrowLeft'||e.key==='ArrowRight'", self.t)
        self.assertIn(".gldlg .bx{width:min(660px,100%);max-height:100%;overflow:auto}", self.t)
        # 프로그램 화면 안(2026-11-25 ~): 100vh = 진짜 화면 높이(종전 iframe 때는 --vh)
        self.assertIn("body.pskin .gldlg .bx{max-height:calc(100vh - 24px)", self.css)
        self.assertIn("body.pskin .gldlg #glCv{width:min(528px,calc(100vh - 300px)", self.css)

    def test_theme_colors(self):
        for loud in ("#4f46e5", "#a3e635", "📥", "🟥", "⭕ 측정 원"):
            self.assertNotIn(loud, self.t + self.css, loud)
        self.assertNotIn("#22d3ee;background", self.css)                    # 측정 원 보기 = 테마 초록
        self.assertIn("body.pskin .glbox{border-color:var(--line);border-left-color:var(--navy);", self.css)
        self.assertIn("body.pskin .c5pick.on{background:var(--navy);", self.css)
        self.assertIn("body.pskin .fgrid .chipgrid .clsck:has(input:checked){border-color:var(--bd2);background:var(--panel)}", self.css)



class ListSearchAndPick(unittest.TestCase):
    """v14.1.8(소유자 검토 · 확정): 모든 스텝 목록 위 돋보기 검색(모든 열 값 + 사진 파일 이름, Enter = 바로 · 입력 멈추면 자동),
    목록마다 ☑ + 전체 선택 · 전체 해제 + [처음엔 모두 ☑](기본 켬, 5-3 최종 목록도), 다음 단계 · CSV · 최종 목록 = 보이는(필터 · 검색) ☑ 줄."""
    @classmethod
    def setUpClass(cls):
        cls.t = HTML.read_text(encoding="utf-8")
        cls.ids = _Ids()
        cls.ids.feed(cls.t[cls.t.index("<body>"):cls.t.index("<script>")])
        cls.css = (PUB / "para-skin.css").read_text(encoding="utf-8")

    def test_bars_above_every_list(self):
        p = self.ids.parents
        for bar, sec in (("bigLs", "b5p1"), ("b5Ls", "b5p2"), ("c5Ls", "b5p3"), ("detLs", "step3")):
            self.assertIn(sec, p[bar], bar)
        self.assertLess(self.t.index('id="bigLs"'), self.t.index('id="bigList"'))
        self.assertLess(self.t.index('id="b5Ls"'), self.t.index('id="b5list"'))
        self.assertLess(self.t.index('id="c5Ls"'), self.t.index('id="c5one"'))
        self.assertLess(self.t.index('id="detLs"'), self.t.index('id="detTbl"'))
        self.assertIn("lsHtml(pre+'Ls',", self.t)                                  # Step 3 · 4 목록(패널)
        for bar in ("bigLs", "b5Ls", "detLs"):                                     # ☑ 줄
            seg = self.t[self.t.index(f'id="{bar}"'):]
            seg = seg[:seg.index("</div>")]
            for k in ('data-ls="all"', 'data-ls="none"', 'data-ls="def"', 'class="lsn"'):
                self.assertIn(k, seg, (bar, k))
        self.assertIn('<input type="checkbox" data-ls="def" checked> 처음엔 모두 ☑', self.t)     # 5-3 최종 목록 줄
        self.assertIn("body.pskin .lsq{", self.css)

    def test_search_rules(self):
        self.assertIn("if(e.key==='Enter'){go();e.preventDefault()}", self.t)
        self.assertIn("tm=setTimeout(go,wait())", self.t)
        self.assertIn("BIG.view.total>100000?700:LS.delay", self.t)                # 큰 목록은 조금 더 기다림
        self.assertIn("const qAll=(T,txt)=>{for(const w of T)if(!txt.includes(w))return false;return true}", self.t)
        # 모든 열 값 + 사진 이름
        self.assertIn("rec.c&&rec.c.file?qm(rec.c.file)", self.t)                  # 5-1 Color 사진
        b5 = self.t[self.t.index("const b5Text=p=>"):self.t.index("const c5Pool=")]
        for k in ("fv(C.c[i])", "fv(C.w[i])", "p.c&&p.c.file", "p.g&&`${p.g.file}", "pcPath(p.g.path)", "p.cerr"):
            self.assertIn(k, b5, k)
        for fn in ("function panelText(", "function detText("):
            seg = self.t[self.t.index(fn):]
            seg = seg[:seg.index("\n}") if "\n}" in seg[:600] else 900]
            self.assertIn("g&&g.frame&&g.frame.file", seg, fn)

    def test_pick_rules(self):
        self.assertIn("LS.def=localStorage.getItem('cw.lsDef')!=='0'", self.t)        # 처음엔 모두 ☑ = 기본 켬
        self.assertIn("if(s.pk[i])items.push(", self.t)                             # 5-1 → 5-2 = 보이는 ☑
        self.assertIn("const c5Pool=()=>BIG.pairs?B5.items.filter(p=>p.on2&&p.st!=='skip'):[];", self.t)   # 5-2 → 5-3
        self.assertIn("p.pick=v===undefined?LS.def:v", self.t)                      # 5-3 최종 목록 처음 = 옵션
        self.assertIn("const pickList=()=>C5.items.filter(p=>p.pick);", self.t)     # 최종 목록 = 5-3 에 보이는 ☑
        self.assertIn("csvText(filtered().filter(dOn))", self.t)                    # 쌍별 상세 표 CSV = 보이는 ☑
        self.assertIn("P.items.filter(it=>pOn(P,it))", self.t)                      # Step 3 · 4 CSV = ☑
        self.assertIn("function panelStep(P,dir)", self.t)                          # ↑↓ 는 ☑ 만



class ExcelOriginalImages(unittest.TestCase):
    """v14.3.17(#86): 최종 목록 엑셀 [원본 이미지로 저장] — Color 열 = 원본으로 바꿈, 흑백 원본 2열(Crop · 프레임) 추가, 끄면 종전 열 그대로.
    + [🗂 최종 목록 사진 파일.zip 저장] — color · gray · gray crop 폴더, 원본은 읽기만 · 바이트 그대로 복사."""
    @classmethod
    def setUpClass(cls):
        cls.t = HTML.read_text(encoding="utf-8")

    def test_checkbox_and_memory(self):
        self.assertIn('<input type="checkbox" id="c5xlOrig"> 원본 이미지로 저장', self.t)
        self.assertNotIn("원본 이미지도 넣기", self.t)
        self.assertIn("XLO.on=localStorage.getItem('cw.xlOrig')==='1'", self.t)    # 기본 끔
        self.assertIn("$('#c5xlOrig').onchange=e=>xlOrigSet(e.target.checked)", self.t)

    def test_original_bytes_unchanged(self):
        i = self.t.index("async function xlOrig(")
        f = self.t[i:self.t.index("\n/** 엑셀 열:", i)]
        self.assertIn("new Uint8Array(await f.arrayBuffer())", f)
        self.assertIn("if(ext){bm.close&&bm.close();return {data,w,h,ext,orig:true}}", f)   # JPEG · PNG = 파일 그대로
        self.assertNotIn("xlJpeg", f)

    def test_columns(self):
        # Color 열은 원본으로 바꾸고(추가 열 아님), 흑백 표시 열은 두고 원본 2열을 Gray 프레임 뒤에
        self.assertIn("const xlCols=orig=>orig?[...XL_COLS.slice(0,XL_CI),XL_CO,...XL_COLS.slice(XL_CI+1,XL_OI),...XL_ORIG,...XL_COLS.slice(XL_OI)]:XL_COLS;", self.t)
        self.assertIn("XL_ORIG=[['Gray Crop 원본 (흑백 원본을 자른 그림 · 표시 없음)',250,'go'],['Gray 프레임 원본 (파일 그대로 · 표시 없음)',570,'fo']]", self.t)
        self.assertIn("XL_CO=['Color 원본 (파일 그대로)',250,'c']", self.t)
        self.assertNotIn("'co'],", self.t)
        self.assertIn("if(o.co)o.c=o.co", self.t)                                 # Color 칸 그림 = 원본
        self.assertIn("if(orig)o.go=await cropPng(k.raw)", self.t)                # 흑백 원본 Crop = raw(표시 없음)
        self.assertIn("const blob=xlsxBlob('최종 목록',COLS,rows,pics);", self.t)
        self.assertIn('<Default Extension="png" ContentType="image/png"/>', self.t)
        self.assertIn("`xl/media/image${k+1}.${p.ext||'jpeg'}`", self.t)

    def test_zip_button(self):
        self.assertIn('<button id="c5saveZip" disabled', self.t)
        self.assertIn("🗂 최종 목록 사진 파일.zip 저장</button>", self.t)
        self.assertIn("$('#c5saveZip').disabled=!n;", self.t)
        self.assertIn("$('#c5saveZip').onclick=()=>c5SaveZip();", self.t)
        i = self.t.index("async function c5SaveZip(")
        f = self.t[i:self.t.index("\n// ── xlsx 만들기", i)]
        for d in ("'color/'", "'gray/'", "'gray crop/'"):
            self.assertIn(d, f)
        self.assertIn("origBytes(s,r.c.file)", f)
        self.assertIn("origBytes(s,r.hit.frame.file)", f)
        self.assertIn("cgCropCanvas(bm,r.hit,r.crop||cgCropSize({}),null,null)", f)   # 표시 없음
        self.assertNotIn("createWritable", self.t[self.t.index("async function origBytes("):i])   # 원본은 읽기만
        self.assertNotIn("removeEntry", f)


if __name__ == "__main__":
    unittest.main()
