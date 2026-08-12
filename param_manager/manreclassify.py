r"""ManReClassify.ini — AOI 장비 Classification Editor 설정 파서.

위치: `\\{장비_IP}\c$\Bis\data\dds\ManReClassify.ini`
      (레시피 폴더가 아니라 **장비 1대에 하나**인 공용 설정이다.)

파일 구조
---------
`[General]` 섹션의 활성 데이터 행:

    Code=Desc,Status,Priority,Color,KeyCode,KeyModifier,Intern,Display,
         GrabImage,Verify,Extended,MaxCount,CustomerBin0,CustomerBin1,...

  · 등호 **왼쪽**이 분류 Code.
  · 등호 오른쪽을 쉼표로 나눈 **0-based index 11 이 Max Count**.
  · Max Count 다음(index 12)부터 고객별 Bin 이고, 그 순서는 `[Customers]`
    섹션의 고객번호 순서와 같다. index 12(첫 번째)가 Internal Bin.

왜 공용 ini 파서를 쓰지 않는가 (중요)
--------------------------------------
`ini_parser.parse_ini_sections` 는
  ① `strip_comment` 로 줄 **중간**의 `;` 뒤를 잘라내고,
  ② `\_` → `_` 치환을 하며,
  ③ 값을 숫자로 형변환한다.
이 파일에서는 셋 다 데이터를 망가뜨린다. 주석은 **줄 맨 앞의 `;`** 만이고,
Desc 에는 어떤 문자든 들어올 수 있다. 그래서 전용 리더를 쓴다.

절대 지킬 것
------------
· **빈 필드를 보존한다.** 연속된 쉼표(`,,`)를 합치거나 뒤 필드를 앞으로 당기면
  열이 통째로 밀려 Max Count 자리에 엉뚱한 값이 온다.
· **Max Count 0 은 유효한 값**이다(결측 아님). 빈 문자열만 결측으로 본다.
· 원본은 읽기만 한다(복사본을 읽는 기존 방식 그대로).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FILENAME = "ManReClassify.ini"
SECTION_GENERAL = "General"
SECTION_CUSTOMERS = "Customers"

# 0-based 필드 인덱스. 양식에서 고르는 건 Max Count 뿐이지만, 나머지가 무엇인지
# 알아야 열이 밀렸을 때 알아챌 수 있어 전부 적어 둔다(Classification Editor 화면 순서).
IDX_DESC = 0            # 분류명 (Desc 열)
IDX_STATUS = 1          # Good / Defect — 이 코드가 양품인지 불량인지
IDX_PRIORITY = 2        # 우선순위(같은 결함이 여러 코드에 걸릴 때 작은 값이 우선)
IDX_COLOR = 3           # 리뷰 화면 표시 색
IDX_KEYCODE = 4         # 단축키(F1, Space …)
IDX_KEYMODIFIER = 5     # 단축키 조합(Shift/Ctrl/Alt) — 화면의 'Shift + F8' 은 4+5
IDX_INTERN = 6          # 사내 내부 코드(FQC-00 …)
IDX_DISPLAY = 7         # 리뷰 목록에 표시할지(체크박스)
IDX_GRABIMAGE = 8       # 이 분류일 때 이미지를 저장할지
IDX_VERIFY = 9          # 검증(재확인) 대상인지
IDX_EXTENDED = 10       # 확장 코드(AB11 …)
IDX_MAXCOUNT = 11       # ★ Max Count — 양식에서 고르는 값
IDX_BIN0 = 12           # 고객 Bin 시작. 첫 번째(=index 12)가 Internal Bin.

FIELD_NAMES = {
    IDX_DESC: "Desc", IDX_STATUS: "Status", IDX_PRIORITY: "Priority",
    IDX_COLOR: "Color", IDX_KEYCODE: "KeyCode", IDX_KEYMODIFIER: "KeyModifier",
    IDX_INTERN: "Intern", IDX_DISPLAY: "Display", IDX_GRABIMAGE: "GrabImage",
    IDX_VERIFY: "Verify", IDX_EXTENDED: "Extended", IDX_MAXCOUNT: "MaxCount",
}

_SECTION_RE = re.compile(r"^\[(?P<name>[^\]]*)\]\s*$")


@dataclass
class ClassRow:
    """분류 코드 1개."""
    code: str
    fields: list = field(default_factory=list)   # 쉼표 분리 원본(빈 필드 보존)

    def at(self, idx: int) -> str:
        """인덱스 필드. 없으면 빈 문자열(짧은 행도 예외 없이)."""
        return self.fields[idx] if 0 <= idx < len(self.fields) else ""

    @property
    def desc(self) -> str:
        return self.at(IDX_DESC)

    @property
    def status(self) -> str:
        return self.at(IDX_STATUS)

    @property
    def max_count(self) -> str:
        """Max Count **원문**. 0 도 유효한 값이라 빈 문자열만 결측으로 본다."""
        return self.at(IDX_MAXCOUNT)

    @property
    def has_max_count(self) -> bool:
        return self.max_count.strip() != ""

    @property
    def internal_bin(self) -> str:
        """Internal Bin = Max Count 다음 첫 값(고객 Bin 배열의 0번)."""
        return self.at(IDX_BIN0)

    def bins(self, customers: list) -> dict:
        """고객별 Bin — `[Customers]` 순서대로 이름을 붙여 돌려준다."""
        out = {}
        for i, name in enumerate(customers):
            out[name] = self.at(IDX_BIN0 + i)
        return out

    @property
    def label(self) -> str:
        """양식에 쓸 표시 이름 — '2 Missing Bump'(코드 + 분류명)."""
        d = self.desc.strip()
        return f"{self.code} {d}".strip() if d else self.code


def _read_sections(path) -> dict:
    """ini → {섹션: [(키, 값원문)]}. **가공 없이** 원문을 그대로 보존한다.

    · 주석은 **줄 맨 앞의 `;`** 만(줄 중간의 `;` 는 데이터다).
    · 값은 형변환하지 않는다(쉼표 분리 전이라 문자열이어야 한다).
    · 같은 키가 두 번 나오면 뒤엣것이 이긴다(장비 파일 관례) — 목록으로 받아
      호출측이 판단할 수 있게 순서를 유지한다.
    """
    out: dict = {}
    cur = None
    with Path(path).open("r", encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue                      # 빈 줄 · 주석 줄(맨 앞 ';')
            m = _SECTION_RE.match(stripped)
            if m:
                cur = m.group("name").strip()
                out.setdefault(cur, [])
                continue
            if cur is None or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            out[cur].append((k.strip(), v))   # 값은 strip 하지 않는다(빈 필드 보존)
    return out


def read_customers(path) -> list:
    """`[Customers]` 섹션의 고객 이름 — **파일에 적힌 순서 그대로**.

    고객별 Bin 배열이 이 순서와 같으므로 순서가 곧 의미다(정렬하면 안 된다).
    키가 번호(`0=SINF3D`)면 번호 순으로, 아니면 나온 순서대로.
    """
    secs = _read_sections(path)
    items = secs.get(SECTION_CUSTOMERS) or []
    numbered, plain = [], []
    for k, v in items:
        name = v.strip()
        if re.fullmatch(r"\d+", k.strip()):
            numbered.append((int(k.strip()), name or k.strip()))
        else:
            plain.append(name or k.strip())
    if numbered:
        return [n for _i, n in sorted(numbered, key=lambda t: t[0])]
    return plain


def read_rows(path) -> list:
    """`[General]` 의 분류 행 목록. 빈 필드까지 그대로 보존한다."""
    secs = _read_sections(path)
    out, seen = [], {}
    for code, value in (secs.get(SECTION_GENERAL) or []):
        if not code:
            continue
        # **쉼표 분리만** 한다 — 빈 필드를 없애거나 당기면 열이 통째로 밀린다.
        fields = value.split(",")
        row = ClassRow(code=code, fields=fields)
        if code in seen:                      # 같은 코드가 또 나오면 뒤엣것이 이긴다
            out[seen[code]] = row
        else:
            seen[code] = len(out)
            out.append(row)
    return out


def read_file(path) -> dict:
    """한 번에 읽기 — {"rows": [ClassRow], "customers": [이름]}."""
    return {"rows": read_rows(path), "customers": read_customers(path)}


def max_counts(path) -> list:
    """(코드, 표시이름, Max Count 원문) 목록 — Max Count 가 **있는 행만**.

    0 은 유효한 값이라 포함한다. 빈 문자열만 뺀다.
    """
    return [(r.code, r.label, r.max_count) for r in read_rows(path)
            if r.has_max_count]


def is_manre_file(path) -> bool:
    """복사 시 붙는 `_2` 접미사(ManReClassify_2.ini)도 같은 파일로 인식."""
    stem = Path(path).stem.lower()
    base = re.sub(r"_\d+$", "", stem)
    return base == Path(FILENAME).stem.lower()
