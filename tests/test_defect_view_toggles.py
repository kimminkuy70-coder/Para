"""v14.1.5 Defect 분석(대규모) 화면 — 소유자 세션 대화(2026-11-16):

- 새 창으로 크게 보기: 흑백 사진(Gray Crop · Gray 프레임)의 Defect 빨간 네모 켜고 끄기([🟥 빨간 네모] · B 키, 이 PC 에 기억).
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
        for name in ("FL_HEAD", "XL_COLS", "VA=makeVT", "VB=makeVT", "VC=makeVT"):
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

    def test_photo_window_red_box(self):
        i = self.t.index("function photoWinInit(")
        init = self.t[i:self.t.index("\nfunction photoWinFollow", i)]
        self.assertIn('id="pwBox"', init)
        self.assertIn("else if(k==='b'){pwBoxSet(!PWB.on)", init)
        self.assertIn("PWB.on=localStorage.getItem('cw.pwBox')!=='0'", self.t)
        show = self.t[self.t.index("async function photoWinShow("):self.t.index("// ── 5-3: 사진 정밀 조사")]
        self.assertEqual(show.count("{box:PWB.on}"), 4)                        # 처음 그림 2 + 다시 그림 2
        self.assertIn("_redraw=", show)
        # 5-3 칸 · 엑셀 사진은 빨간 네모 그대로(새 창에서만 끔)
        xl = self.t[self.t.index("async function xlPhotos("):self.t.index("/** 엑셀 열:")]
        self.assertNotIn("box:", xl)

    def test_filter_rows(self):
        p = self.ids.parents
        for i in ("bigLot", "bigSlot", "bigLotBox", "bigCls", "bigFltIn", "bigFltRcp", "bigFltSort", "bigCsv"):
            self.assertIn("bigFlt", p[i], i)
        self.assertIn("fgrid", self.ids.classes["bigFlt"])
        heads = re.findall(r'<span class="fh">([^<]+)</span>', self.t[self.t.index('id="bigFlt"'):self.t.index('id="bigCnt"')])
        self.assertEqual(heads, ["Lot · Slot", "Lot 제외", "값 범위", "Recipe", "정렬"])   # 분류 두 줄은 bigFacetFill 이 그림
        self.assertIn("grp(1,'장비 스캔 분류',", self.t)
        self.assertIn("grp(2,'리뷰 결과',", self.t)
        self.assertIn(".fgrid .chipgrid{", self.t)
        css = (PUB / "para-skin.css").read_text(encoding="utf-8")
        self.assertIn("body.pskin .fgrid .frow{", css)
        self.assertIn("body.pskin .glbox{", css)
        # Step 3 · 4 필터 줄은 종전 그대로(한 줄 조각을 이어 붙임)
        self.assertIn("function fltHtml(){return fltRngHtml()+fltRcpHtml()+fltSortHtml()+fltClrHtml()}", self.t)


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
        # 프로그램 안: iframe 의 100vh 는 내용 전체 높이 → 보이는 높이(--vh)로
        self.assertIn("body.pskin .gldlg .bx{max-height:calc(var(--vh,100vh) - 24px)", self.css)
        self.assertIn("body.pskin .gldlg #glCv{width:min(528px,calc(var(--vh,100vh) - 300px)", self.css)

    def test_theme_colors(self):
        for loud in ("#4f46e5", "#a3e635", "📥", "🟥", "⭕ 측정 원"):
            self.assertNotIn(loud, self.t + self.css, loud)
        self.assertNotIn("#22d3ee;background", self.css)                    # 측정 원 보기 = 테마 초록
        self.assertIn("body.pskin .glbox{border-color:var(--line);border-left-color:var(--navy);", self.css)
        self.assertIn("body.pskin .c5pick.on{background:var(--navy);", self.css)
        self.assertIn("body.pskin .fgrid .chipgrid .clsck:has(input:checked){border-color:var(--bd2);background:var(--panel)}", self.css)



if __name__ == "__main__":
    unittest.main()
