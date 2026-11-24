---
name: AOI Manager
slug: aoi-manager
category: manufacturing-tool
status: draft            # 소유자 피드백 전 초안 — 확정되면 이 줄을 지운다
last_updated: "2026-11-24"
lang: ko
based_on: "토스 TDS design.md(getdesign.kr)의 구조 · 원칙을 빌리고, 색 · 톤은 AOI Manager v14 화면 그대로"
colors:
  ## 구조 — 슬레이트 (Material Blue Grey 계열, 지금 --navy · --brand2)
  slate-900: "#263238"   # 토스트 · 로그 상자 바탕
  slate-800: "#37474f"   # 머리 막대 · 회사 탭 · 강조 글자 (지금 --navy)
  slate-700: "#455a64"   # 보조 구조 · 정보 상자 아이콘 (지금 --brand2)
  slate-600: "#546e7a"   # 빈 화면 그림
  slate-500: "#607d8b"   # 안내 토스트 아이콘
  slate-100: "#cfd8dc"   # 어두운 바탕 위 보조 글자
  slate-50:  "#eceff1"   # 정보 상자 바탕 · 지금 단계 고리
  ## 강조 — 에메랄드 (지금 --lime · --acc2 · --onacc)
  emerald-800: "#0b5e46" # 민트 바탕 위 글자
  emerald-700: "#047857" # 작은 강조 글자(eyebrow 등)
  emerald-600: "#0d9668" # 주 단추 눌림 · 초점 테두리
  emerald-500: "#10b981" # 주 단추 · 활성 탭 밑줄 · 완료 · 진행 막대
  emerald-200: "#a7e0cb" # 완료 단계 연결선
  emerald-100: "#d6f2e6"
  emerald-50:  "#eafaf3" # 선택 바탕 · 연결됨 배지
  on-emerald:  "#04231a" # 에메랄드 위 글자 (흰 글자 쓰지 않음 — 대비 2.5:1)
  ## 중립 — 회청색 (지금 --ink · --mut · --faint · --line · --band · 바탕)
  grey-900: "#1f2937"    # 본문 글자 (순수 검정 쓰지 않음)
  grey-700: "#425872"    # 표 머리 글자
  grey-600: "#5f6b7a"    # 보조 글자
  grey-500: "#7a8798"    # 아이콘(검색 돋보기 등)
  grey-400: "#94a3b8"    # 흐린 글자 · 자리표시 — 본문에 쓰지 않음(대비 2.6:1)
  grey-300: "#cfd8e3"    # 입력 칸 · 강한 선
  grey-200: "#e6ebf0"    # 기본 선(헤어라인)
  grey-100: "#eef2f4"    # 화면 바탕 · 보조 단추 · 칸 바탕
  grey-50:  "#f7f9fb"    # 표 머리 · 입력 칸 · 띠
  white:    "#ffffff"
  ## 상태
  red-700:    "#a33820"  # 오류 글자
  red-600:    "#c2410c"  # 오류 · 위험 단추 (지금 --bad)
  red-50:     "#fdecea"  # 오류 바탕
  amber-800:  "#79471c"  # 주의 글자
  amber-500:  "#e0a526"  # 재스캔 표시 · 주의 아이콘
  amber-50:   "#fff4e7"  # 주의 바탕
  orange-500: "#e0704b"  # Pass 하지 못한 wafer 표시(그래프 · 점)
  ## 역할 (화면 코드는 이 이름으로 부른다)
  bg-page:      "{colors.grey-100}"
  bg-surface:   "{colors.white}"
  bg-sunken:    "{colors.grey-50}"
  line:         "{colors.grey-200}"
  line-strong:  "{colors.grey-300}"
  text-1:       "{colors.grey-900}"
  text-2:       "{colors.grey-600}"
  text-3:       "{colors.grey-400}"
  text-th:      "{colors.grey-700}"
  brand:        "{colors.slate-800}"
  on-brand:     "{colors.white}"
  on-brand-2:   "{colors.slate-100}"
  accent:       "{colors.emerald-500}"
  accent-press: "{colors.emerald-600}"
  accent-weak:  "{colors.emerald-50}"
  accent-line:  "{colors.emerald-200}"
  accent-text:  "{colors.emerald-800}"
  on-accent:    "{colors.on-emerald}"
  focus:        "{colors.emerald-600}"
  hover:        "rgba(38,50,56,.05)"   # 투명 단추 · 줄에 얹는 덧칠
  press:        "rgba(38,50,56,.10)"   # 누르는 동안 얹는 덧칠
  scrim:        "rgba(31,41,55,.42)"   # 창 뒤 가림막
  st-done:      "{colors.emerald-500}" # 한 번에 완료
  st-rescan:    "{colors.amber-500}"   # 재스캔으로 완료
  st-open:      "{colors.orange-500}"  # Pass하지 못한 wafer 존재
typography:
  font-family: "'Malgun Gothic','맑은 고딕',system-ui,sans-serif"   # 설치 보장, 웹 폰트 금지(오프라인)
  font-mono:   "Consolas,'D2Coding',monospace"
  weights:     [400, 700]                                           # 맑은 고딕은 이 둘뿐
  display:   { size: 28px, weight: 700, line: 1.3,  tracking: -0.02em }   # 페이지 제목 h1
  h2:        { size: 20px, weight: 700, line: 1.35 }                      # 창 제목 · 기다림 카드 제목
  h3:        { size: 16px, weight: 700, line: 1.4 }                       # 카드 제목
  title:     { size: 15px, weight: 700, line: 1.45 }                      # 구역 탭 · 빈 화면 제목
  body:      { size: 14px, weight: 400, line: 1.6 }                       # 기본 본문
  body-s:    { size: 13px, weight: 400, line: 1.55 }                      # 표 · 단추 · 입력 칸
  caption:   { size: 12px, weight: "400 | 700", line: 1.45 }              # 설명 · 라벨 · 배지
  caption-s: { size: 11px, weight: 700, line: 1.4, tracking: 0.14em }     # eyebrow(대문자) · 작은 표시
  kpi:       { size: 30px, weight: 700, line: 1.2, tracking: -0.02em, numeric: tabular-nums }
spacing: [4, 8, 12, 16, 20, 24, 32, 40, 48]   # px, 4 의 배수만
rounded:
  r-xs:   4px    # 표 안 작은 표시
  r-s:    6px    # 배지 · kbd
  r-m:    10px   # 단추(보통) · 입력 칸 · 분절 · 안내 상자 · 호기 칸
  btn-l:  12px   # 큰 단추(44)
  btn-s:  8px    # 작은 단추(28) · 분절 안 단추
  r-l:    14px   # 카드 · 큰 숫자 카드 · 토스트 · 표 틀
  r-xl:   20px   # 창(dialog) · 큰 새 창
  r-full: 999px  # 칩 · 배지 알약 · 스위치 · 연결 배지
elevation:
  card:  none                                                                  # 카드는 1px 선만
  sh-1:  "0 1px 2px rgba(38,50,56,.07), 0 1px 1px rgba(38,50,56,.04)"            # 분절 선택 칸 · 스위치 손잡이
  sh-2:  "0 6px 16px rgba(38,50,56,.10), 0 1px 3px rgba(38,50,56,.06)"           # 펼침 목록 · 진행 패널
  sh-3:  "0 16px 40px rgba(38,50,56,.18), 0 2px 8px rgba(38,50,56,.08)"          # 토스트 · 창
motion:
  ease:      "cubic-bezier(.22,.61,.36,1)"   # 색 · 테두리 바뀜
  ease-soft: "cubic-bezier(.23,1,.32,1)"     # 위치 · 높이 · 그리기 (Kokonut UI · SmoothUI 와 같은 곡선)
  ease-out:  "cubic-bezier(.16,1,.3,1)"      # 나타나는 것(페이지 · 토스트 · 창)
  dur-fast:  120ms                           # 누름(98% 로 작아짐) · 줄 강조
  dur-base:  200ms                           # 마우스 올림 · 탭 글자색 · 아이콘 바뀜
  dur-slow:  320ms                           # 페이지 · 카드 · 토스트 등장
  stagger:   45ms                            # 카드 · 막대가 차례로 들어올 때 간격 (표 줄은 22ms)
  springs:                                   # "강성 감쇠" — designbookmark tokens.css 와 원본 코드 값 그대로
    tab-lead:  "620 36"                      # 탭 밑줄 · 고른 칸의 앞쪽 끝 (--spring-lead)
    tab-trail: "190 19"                      # 뒤쪽 끝 — 늘었다 줄며 따라감 (--spring-trail)
    step-line: "160 22"                      # 단계 표시: 선 길이
    step-fill: "260 24"                      #   끝난 단계 채움
    step-check: "140 20"                     #   체크 그리기(0.12초 뒤)
    step-pop:  "500 14"                      #   지금 단계 튀어 오름(0.7배 · 속도 6에서)
    step-now:  "300 26"                      #   지금 단계 색
    copy-roll: "260 20"                      # 복사: 글자 말림
    copy-icon: "420 18"                      #   아이콘 바뀜
    copy-width: "300 24"                     #   단추 폭 (1.8초 뒤 되돌아감)
    wheel-snap: "472 36.9"                   # 돌림 선택: 한 칸 가기 (원본 = 0.4초 · 튐 0.15)
    wheel-flick: "140 24"                    #   튕긴 뒤 멈추기 (놓을 때 속도 이어받음, 속도 × 0.32초 미끄럼)
    scrub-thumb: "1151 61"                   # 값 끌어 고르기 손잡이 (원본 = 0.25초 · 튐 0.1)
opacity:
  disabled: 0.4   # 부품 전체에 (부분 회색 처리 안 함)
---

# AOI Manager — DESIGN.md

AOI Manager 화면을 고칠 때 사람과 AI가 따르는 디자인 기준이다. 색 · 톤은 v14 화면(슬레이트 구조 + 에메랄드 강조)을 그대로 두고,
토스 TDS 의 구조(역할 토큰 · 평평한 표면 · 헤어라인 · 크기와 짝지은 모서리 · 짧은 전환 · 3점 로더 · 고정폭 숫자)로 정리한다.

> **우선순위**: 소유자 말 → `CLAUDE.md`(기능 · 보안 · 용어 규칙) → 이 문서 → 그 밖. 이 문서와 CLAUDE.md 가 다르면 CLAUDE.md 를 따르고 소유자에게 알린다.
> 예시: `docs/design/AOI_Manager_디자인_예시.html`(Batch Report 분석 · 찾기 · 취합 · Defect 분석 기본 · 대규모 · 자동 분석 · TB500 조회 · KLA 자재 찾기 + 컴포넌트 · 모션 모음).
> 이어서 하기 · 남은 일: `docs/design/이어서_하기.md`.
>
> **예시 파일과 실제 프로그램 화면이 다르면 프로그램이 우선이다.** 예시에서 가져오는 것은 겉모습(색 · 모서리 · 선 · 그림자 · 글자 크기)과 움직임뿐이다.
> 기능 · 화면 구성 · 단계 · 선택지 · 글 · 숫자는 지금 프로그램(`frontend/src/*.tsx`, Defect 분석 HTML rev6)을 그대로 따른다. 알려진 차이는 `docs/design/이어서_하기.md` 의 '예시 ≠ 프로그램' 표.

## 1. 적용 규칙 — 디자인 작업은 기능을 바꾸지 않는다

**바꾸는 것**: CSS 값(색 · 모서리 · 선 · 그림자 · 간격 · 글자 크기 · 전환), CSS 변수, 아이콘 그림(SVG), 모션 부품 다섯 가지(8절) 추가.
모션은 **추가 패키지 없이** 만든다 — Kokonut UI · SmoothUI 원본은 `motion` · Tailwind · `lucide-react` 를 쓰지만, 이 프로젝트는
작은 스프링 함수 하나(`frontend/src/motion.ts`, designbookmark `motion.js` 와 같은 계산)와 CSS 로 같은 타이밍을 낸다(미리보기 HTML 이 그 구현이다).

**바꾸지 않는 것** (화면 시험 `tools/test_desktop_ui.mjs` 가 글자 · 클래스 · `data-tour` 로 화면을 찾는다):
- 클래스 이름 · `id` · `data-tour` · `aria-*` · DOM 구조 · 탭 순서 · 단추 위치. 새 모양에 클래스가 필요하면 **추가만** 한다.
- 화면 글자(제목 · 단추 · 안내 · 오류 문구). 말투를 바꾸고 싶어도 이 작업에서는 고치지 않는다(11절).
- 탭 화면 살려 두기(`kept-screen` · `hidden` · `display:contents`), Defect iframe 높이 맞춤(`para-skin.js` postMessage),
  Mini 판 규칙(`edition.ts` `isMini` · `hasTab`), 엔진 · IPC · Python 코드.

**파일과 순서**
1. `frontend/src/styles.css` 맨 위 `:root` 에 이 문서의 토큰을 넣는다. 옛 이름(`--navy` `--lime` `--acc2` `--onacc` `--ok` `--bad` `--ink` `--mut` `--muted` `--faint` `--line` `--band` `--brand2` `--sh1` `--sh2` `--ease` `--spring`)은
   **새 토큰을 가리키는 별칭으로 남긴다** — 화면별 CSS 가 그 이름을 쓰고 있어 한 번에 지우면 깨진다.
2. 공통 부품(단추 · 입력 · 탭 · 표 · 토스트 · 창 · 단계 표시) → 3. 화면별 범위(`.bv` · `.kla` · `.tb5` · `commonality.css`) 의 고정 색 값을 토큰으로 →
4. `frontend/public/defect/para-skin.css`(Defect 분석 iframe, `body.pskin` 에만 같은 값을 복사 — 원본 HTML 은 손대지 않음).
5. `cd frontend && npm run build` 후 `frontend/dist` 도 커밋(CI 가 확인).
6. 시험: `tests/test_*.py` 하나씩 + `node tools/test_desktop_ui.mjs`(CLAUDE.md 의 명령) — 모두 통과해야 한다.
7. 바꾸기 전 · 후 스크린샷을 모든 맨 위 탭 · 기능 탭과 **Mini 창**에서 찍어 비교한다(글자 크기를 올린 곳은 표 폭이 늘지 않았는지 본다).

**오프라인 · 금지 글자**: 웹 폰트 · CDN 을 쓰지 않는다(런타임 인터넷 금지). 화면 글에 `GitHub` 을 쓰지 않는다. '감시' 대신 '분석 및 취합', `Batch Report` 표기 등 CLAUDE.md 용어를 따른다.

**그대로 두는 예외**
- Recipe 값 비교표(`.comparison-*` 어두운 회색 — 실제 장비 화면처럼 보여야 함).
- 데이터 그래프의 호기 색(`batchData.MACH_PAL` = `batchsaved.MACH_PAL`, 시험이 고정) · Wafer Map 그림 색 · Defect 지도 캔버스 색(iframe `:root` 값).
- 결과 HTML(`report_theme.THEME_CSS`)은 "앱 화면과 같은 모양" 원칙이 있다 — 앱 토큰을 바꾼 뒤 결과 HTML 도 맞출지는 소유자가 정한다(14절).

## 2. 브랜드와 스타일

AOI Manager 는 Camtek · KLA AOI 장비의 파라미터 · Batch Report · Defect 사진을 다루는 사내 오프라인 데스크톱 도구다(Edge 앱 창, 폭 1280~1920).
쓰는 사람은 장비 엔지니어와 리뷰 담당이고, 같은 화면을 매일 반복해서 본다. 화면은 숫자 · 표 · 폴더 경로가 많고, 원본 폴더는 읽기만 한다.

무드는 **조용한 회청색 바탕 + 흰 카드 + 1px 선, 슬레이트 머리 막대, 강조는 에메랄드 하나**다.

원칙 다섯 가지:
1. **강조색은 하나.** 에메랄드는 '지금 할 일'(주 단추), '지금 위치'(활성 탭 밑줄 · 선택), '끝남'(완료 · 진행 막대)에만 쓴다. 그 밖의 강조는 슬레이트 · 굵기 · 크기로 한다.
2. **평평하게.** 카드는 그림자 없이 1px 선. 그림자는 떠 있는 것(펼침 목록 · 토스트 · 창)에만.
3. **상태는 모양으로.** 색 + 글자 + 점(●)을 같이 쓴다. 색만으로 구분하지 않는다.
4. **숫자는 줄 맞춤.** 표 · 큰 숫자 · 진행 수는 `font-variant-numeric: tabular-nums`.
5. **움직임은 부드럽게, 가볍게.** 화면 전체가 스프링 · ease-out 으로 미끄러지듯 움직인다. 단, transform · opacity 만 움직이고, 멈춰 있으면 계산도 멈춘다(렉이 생기면 그 움직임은 뺀다).

토스에서 빌리지 않은 것: 파란 강조색, Pretendard · 토스 서체, 모바일 패턴(바텀시트 · 화면 아래 고정 단추 · 플로팅 탭바), 해요체 말투, 금융 화면 흐름.

## 3. 색

### 3-1. 팔레트
머리말 `colors` 가 기준이다. 구조 = 슬레이트, 강조 = 에메랄드, 중립 = 회청색(파랑 쪽으로 살짝 기운 회색), 상태 = 빨강 · 호박 · 주황.
`red-600 #c2410c` 은 주황에 가까운 빨강이다 — 지금 화면의 오류 색(`--bad`)을 그대로 둔 것이다.

### 3-2. 역할 (화면 코드는 역할 이름으로 부른다)

| 역할 | 값 | 쓰는 곳 |
|---|---|---|
| `bg-page` | grey-100 | 화면 바탕 |
| `bg-surface` | white | 카드 · 표 · 창 · 기능 탭 줄 |
| `bg-sunken` | grey-50 | 표 머리 · 입력 칸(쉴 때) · 시연 칸 |
| `line` / `line-strong` | grey-200 / grey-300 | 기본 선 / 입력 칸 · 칩 테두리 |
| `text-1` / `text-2` / `text-3` | grey-900 / grey-600 / grey-400 | 본문 / 보조 · 설명 / 자리표시 · 비활성 |
| `text-th` | grey-700 | 표 머리 |
| `brand` · `on-brand` · `on-brand-2` | slate-800 · white · slate-100 | 머리 막대 · 회사 탭 · 칩 선택 |
| `accent` · `accent-press` | emerald-500 · emerald-600 | 주 단추 · 활성 밑줄 · 완료 / 눌림 |
| `accent-weak` · `accent-text` | emerald-50 · emerald-800 | 선택 바탕 · 완료 배지 |
| `on-accent` | on-emerald | 에메랄드 위 글자 |
| `focus` | emerald-600 | 키보드 초점 테두리 |
| `hover` · `press` · `scrim` | 슬레이트 덧칠 5% · 10% · 회색 42% | 마우스 올림 · 누름 · 창 가림막 |

### 3-3. 상태 · 데이터 색

| 상태 | 배지 · 안내 바탕 | 글자 | 점 · 그래프 |
|---|---|---|---|
| 완료 · 정상 · 연결됨 | emerald-50 | emerald-800 | `st-done` emerald-500 |
| 주의 · 재스캔으로 완료 | amber-50 | amber-800 | `st-rescan` amber-500 |
| 오류 · Pass 하지 못함 | red-50 | red-700 | `st-open` orange-500 |
| 정보 · 중립 | slate-50 (상자) · grey-100 (배지) | slate-800 / slate-700 | slate-700 |

호기 색(`MACH_PAL`)은 이 표와 별개다 — 바꾸지 않는다.

### 3-4. 옛 값 → 새 토큰 (정리 대상)
지금 `styles.css` 는 고정 색 값이 237종(589번)이다. 세 세대가 섞여 있어 아래처럼 모은다.

| 지금 값 | 어디 | 새 토큰 |
|---|---|---|
| `#a3e635` 라임 + `#12244a` 글자 | 배지 · Zone 머리 · 레시피 줄 · 편집 격자 초점(7곳) | `accent` + `on-accent` |
| `#12244a` · `#1b345f` · `#0f1e3d` 옛 네이비 | 회사 탭 기본값 · 스피너 · 로그 상자 · 그림자 | `brand` / `slate-900` |
| `#31517c` 파랑 | Batch 칩 · 선택 · 체크 색 · 막대 | `brand`(선택 칩) · `slate-700`(정보) · `accent-press`(체크) |
| `#eafaf3` `#f2fbf7` `#effaf5` `#f3fbe4` | 선택 · 활성 바탕 | `accent-weak` |
| `#8fd9bd` `#a7e0cb` `#9fd8b8` `#cde9a8` | 선택 테두리 | `accent` (테두리 1.5px) |
| `#577eb0` | 초점 테두리 | `focus` |
| `#bac7d6` `#b3c0cc` `#cfd8e3` | 입력 · 강한 선 | `line-strong` |
| `#edf2f7` `#edf2f6` `#e3e9ef` `#eef2f6` | 표 머리 · 칸 바탕 · 분절 바탕 | `bg-sunken` / `grey-100` / `grey-200` |
| `#fff7e0` `#fffbea` `#fff4e7` (+ 테두리 `#f1d38a` `#e9c39a`) | 주의 · 설명 상자 | `amber-50` (테두리 없음) |
| `#1f9d55` · `#dc2626` | 자동 분석 켜짐/꺼짐 단추 | `accent` / `red-600` |

### 3-5. 대비 (WCAG, 계산값)
- on-emerald / emerald-500 **6.6:1**, on-emerald / emerald-600(눌림) 4.4:1 — 흰 글자는 2.5:1 이라 에메랄드 위에 쓰지 않는다.
- grey-900 / white 14.7:1, grey-600 / white 5.4:1, grey-600 / grey-100 4.8:1, emerald-700 / grey-100 4.9:1(eyebrow).
- red-600 / white 5.2:1, red-700 / red-50 5.8:1, amber-800 / amber-50 7.1:1, emerald-800 / emerald-50 7.2:1, slate-100 / slate-800 6.7:1.
- 초점 테두리 emerald-600 / white 3.8:1(3:1 이상). grey-400 / white 2.6:1 — 자리표시 · 비활성 전용, 본문 금지.

## 4. 글자

- **서체 = 맑은 고딕**(Windows 설치 보장). 웹 폰트를 넣지 않는다. 맑은 고딕은 **400 · 700 두 굵기뿐**이라 500 · 600 을 쓰지 않는다(`font-synthesis:none`).
- 크기는 머리말 `typography` 9단만 쓴다: 28 · 20 · 16 · 15 · 14 · 13 · 12 · 11 · 큰 숫자 30. **반 픽셀(12.5 · 11.5 · 10.5 · 13.5)과 10px 은 쓰지 않는다.**
  옮길 때: 13.5 → 14, 12.5 → 13, 11.5 → 12, 10.5 · 10 → 11.
- 최소 11px. 11px 은 굵게(700) 쓰고, 대문자 라벨(eyebrow)은 자간 +0.14em.
- 제목은 `text-wrap: balance`, 설명 문단은 최대 72자 폭. 표 · 단추 · 탭 글자는 줄바꿈하지 않는다(`nowrap`, 넘치면 그 칸 안에서 가로 스크롤).
- 숫자: 표 · 큰 숫자 · 진행 수 · 시각 = `tabular-nums`. 경로 · 원문 코드 = `font-mono`.

## 5. 간격

4px 배수만: 4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48.
- 화면 바깥 여백 32(좁은 창 16), 카드 안 여백 22~24(좁은 창 16), 카드 사이 20.
- 카드 안: 제목 아래 16, 무리 사이 16, 라벨과 입력 사이 6, 붙어 있는 단추 사이 8.
- 겹치는 여백은 `margin` 대신 flex/grid `gap` 으로.

## 6. 모서리

크기와 짝지어 쓴다(토스 방식). 큰 것일수록 둥글다.

| 토큰 | 값 | 쓰는 곳 |
|---|---|---|
| `r-xs` | 4 | 표 안 작은 표시 |
| `r-s` | 6 | 배지 · kbd |
| `btn-s` | 8 | 작은 단추(28) · 분절 안 단추 |
| `r-m` | 10 | 보통 단추(36) · 입력 칸 · 분절 틀 · 안내 상자 · 호기 칸 · 회사 탭 위 모서리 |
| `btn-l` | 12 | 큰 단추(44) |
| `r-l` | 14 | 카드 · 큰 숫자 카드 · 표 틀 · 토스트 · 돌림 선택 틀 · 진행 패널 |
| `r-xl` | 20 | 창(dialog) · 큰 새 창(Lot 창 · TB500 Lot History) |
| `r-full` | 999 | 칩 · 연결 배지 · 스위치 · 진행 막대 |

## 7. 깊이 (그림자)

- 기본은 평평하다: 카드 · 표 · 큰 숫자 카드 = 그림자 없음 + 1px `line`.
- `sh-1` = 분절에서 고른 칸 · 스위치 손잡이, `sh-2` = 펼침 목록 · 진행 패널 · 앱 창 틀, `sh-3` = 토스트 · 창.
- 누름은 그림자가 아니라 `press` 덧칠(안쪽 그림자 쓰지 않음). 비활성은 부품 전체 불투명도 0.4.

## 8. 움직임

화면 전체가 **부드럽게** 움직인다. 기준은 세 가지다.
1. 위치 · 크기 · 투명도만 움직인다(`transform` · `opacity`, 꼭 필요할 때만 한 요소의 `width` · `height`). 표 전체 · 그림자 · 큰 면적의 색을 매 프레임 바꾸지 않는다.
2. 스프링 계산은 하나의 rAF 고리에서, **움직일 것이 없으면 쉰다**. 자동으로 도는 것(시연 · 진행 표시)은 화면에 보일 때만 돈다(IntersectionObserver).
3. 렉이 생기면(느린 PC에서 끊김 · 긴 작업 50ms 넘음이 잦음) 그 움직임은 빼고 상태만 바꾼다. `prefers-reduced-motion` 이면 스프링은 튀지 않게(임계 감쇠 = 2√강성), 전환 · 애니메이션은 사실상 끈다.

### 8-1. 화면 전체
| 무엇 | 움직임 |
|---|---|
| 탭 밑줄(2 · 3단계) · 분절의 고른 칸(4단계) | 탭을 옮기면 표시가 미끄러진다. 앞쪽 끝 **620 · 36**, 뒤쪽 끝 **190 · 19** 스프링이라 늘었다 줄며 따라간다(designbookmark `--spring-lead` · `--spring-trail`) |
| 페이지 · 하위 탭 들어올 때 | 카드마다 8px 위에서 떠오르며 나타남, 320ms `ease-out`, 카드 사이 45ms(최대 8장) |
| 표 줄 · 목록 다시 그릴 때 | 줄마다 22ms 간격으로 떠오름, 260ms `ease-soft` |
| 막대 그래프 | 막대가 아래에서 자라남 520ms, 막대 사이 45ms, 숫자는 뒤에 나타남 |
| 큰 숫자 | 결과가 바뀌면 0 → 값으로 700ms 세어 올라감(고정폭) |
| 단추 · 칩 · 큰 숫자 카드 누름 | 98 ~ 99% 로 작아짐 + `press` 덧칠, 120ms |
| 창(dialog) | 열기 = 14px 아래 · 97% 에서 360ms `ease-out`, 닫기 = 160ms 사라짐, 가림막은 같이 옅어짐 |
| 토스트 | 위에서 10px 내려오며 320ms, 나갈 때 오른쪽으로 12px · 200ms, 남은 토스트는 240ms 로 자리 옮김 |
| 스위치 손잡이 | 260ms `ease-soft` |
| 쓰지 않는 것 | 시차(parallax), 반짝이는 뼈대(skeleton shimmer), 화면 전체 흐림, 무한 반복 장식(진행 표시 제외) |

### 8-2. 모션 부품 다섯 가지 (원본 타이밍 그대로)
미리보기 HTML 의 '컴포넌트 · 모션' 화면에 다섯 가지가 실제로 움직인다.

**① 단계 표시 (Step progress)** — 원본 designbookmark `step-progress`
- 모양: 지름 32 원 + 4px 선. 남은 단계 = `grey-100` 원 + 번호, 지금 = `brand` 원 + 흰 번호, 끝남 = `accent` 원 + `on-accent` 체크. 이름은 원 아래 12px(지금까지 = `text-1` 굵게).
- 움직임: 선 길이 **160 · 22**, 끝난 단계 채움 **260 · 24**, 체크는 0.12초 뒤 **140 · 20** 으로 그려짐, 지금 단계는 0.7배에서 속도 6으로 **500 · 14** 튀어 오름, 지금 단계 색 **300 · 26**.
- 끝난 단계 원을 누르면 그 단계로 돌아간다. 원본의 혼자 걷기(자동 재생)는 화면에서 쓰지 않는다.
- 쓰는 곳: Batch Report 찾기 · 취합 4단계, Defect 분석 5-1 ~ 5-3 · Step 1 ~ 4, Wafer Map 수정하기 6단계, 양식 만들기 단계(지금 `.stepper` 자리).

**② 작업 단계 (Agent steps)** — 원본 Kokonut UI `ai-loading`(MIT)
- 모양: 머리 줄 = 지금 단계 이름 + 걸린 시간(끝나면 `조사를 마쳤습니다 · 9초 · 5단계`) + 접기 화살표. 아래 단계 목록: 16px 아이콘(남음 = 6px `grey-300` 점, 진행 = 회전 고리 `emerald-600`, 끝남 = 체크 `emerald-600`, 실패 = ✕ `red-600`) + 이름 + 단계 시간.
- 움직임: 아이콘 바뀜 180ms(흐림 2px → 선명), 체크 그리기 300ms(0.05초 뒤), 단계 사이 선 채움 500ms, 진행 중 단계 글자에 물결(1.6초, 한 글자 0.05초씩), 기록은 고정폭 12px 3줄까지 보이고 새 줄이 오면 300ms 로 밀려 올라감(칸 높이 240ms, 위쪽 흐림), 다 끝나면 0.45초 뒤 목록이 250ms 로 접힘. 곡선 `ease-soft`.
- 지금 화면의 '진행 패널'(`.activity`)과 긴 작업 상태 글을 이 부품으로 바꾼다. 진행 막대(`n / 전체`)와 [중단]은 옆에 그대로 둔다. 멈추면 `멈춘 단계: …` 로 보인다.
- 쓰는 곳: Batch Report 조사, TB500 Review 조회, KLA 캐시 갱신, Defect 폴더 읽기 · 사진 불러오기, Recipe 값 업데이트 수집, OneDrive 캐시 받기.

**③ 돌림 선택 (Wheel picker)** — 원본 Kokonut UI `wheel-picker`(MIT)
- 모양: 3D 원통(한 줄 36px, 20°), 가운데 띠 `grey-100` · 8px 모서리 + 양옆 눈금, 띠 안 글자 = `text-1` 굵게, 밖 = `text-3`, 위아래로 흐려짐. 틀 = 흰 + 1px `line` + `r-l`.
- 움직임: 한 칸으로 가기 **472 · 36.9**(원본 0.4초 · 튐 0.15), 튕기면 놓을 때 속도 × 0.32초만큼 미끄러지다 **140 · 24** 로 멈춤, 끝이 있는 목록은 끝 너머 최대 1.2칸까지 무겁게 끌림. 마우스 휠은 멈추고 0.12초 뒤 가까운 칸으로. 키보드: ↑↓ 한 칸, PageUp/Down 5칸, Home/End.
- 쓰는 곳: 자동 분석 주기(1시간 ~ 매주) · 실행 시각(시 · 5분 단위 분), 감시 시간대. 시간 단위 주기면 시각 원통은 흐리게 잠근다.

**④ 값 끌어 고르기 (Scrubber)** — 원본 SmoothUI `scrubber`(MIT)
- 모양: 높이 36 · 8px 모서리 막대 `grey-100`, 왼쪽 라벨 13 굵게, 오른쪽 값 고정폭 13, 채운 부분 = `brand` 14%, 눈금 = `brand` 25%, 손잡이 = 4×22 `brand` 알약.
- 움직임: 손잡이는 쉴 때 15% · 0.7배, 마우스를 올리거나 끌면 80% · 1배로 **1151 · 61**(원본 0.25초 · 튐 0.1). 누른 자리로 채움 · 손잡이가 150ms `ease-soft` 로 미끄러지고, 끄는 동안은 바로 따라온다. 화살표 키 = 한 칸, Home/End.
- 쓰는 곳: Defect 분석 값 범위(Contrast · Area · Width · Length · GL), 유효 Lot 매수. 값은 반올림하지 않은 실제 값으로 비교한다(v14.3.15 규칙 그대로 — 표시 자릿수만 정함).
- **범위(양방향) 모양** — 값 범위 필터는 이것을 쓴다: `[라벨] [막대: 손잡이 2개] [최소] ~ [최대] [단위]` 한 줄(좁은 창에서는 세 줄).
  - 막대를 누르면 **가까운 손잡이**가 그 자리로 오고, 끌면 따라온다. 두 손잡이는 서로 넘지 않는다. 고른 구간 = `brand` 16%, 범위를 안 걸었으면 막대 전체 `brand` 8%.
  - **숫자 칸이 기준이다** — 지금 화면의 최소 · 최대 숫자 칸(`data-f="c0"` · `"c1"` …)을 그대로 두고 막대를 더한다. 비우면 그쪽 제한 없음, 막대 밖 값(예: Area 최대 500)도 적을 수 있고 손잡이는 끝에 붙는다.
    적고 0.2초 뒤(지금 `fltBind` 와 같은 0.2초) · Enter 는 바로 반영. 손잡이를 끝까지 밀면 칸이 비워진다(= 제한 없음).
  - 범위를 건 줄은 라벨 앞에 `accent` 점 + 진한 글자. [필터 지우기] = 범위 · Recipe · Zone 만 비움(정렬은 그대로 — 지금 규칙).
  - 키보드: 손잡이마다 초점, ←→ 한 칸 · PageUp/Down 10칸 · Home/End.
- **Defect 분석의 두 모드에 같은 필터 부품**(소유자 2026-11-24): 기본(Step 3 · 4 목록 필터)과 대규모(5-1 값 범위, 5-3 GL 범위) 모두 이 범위 부품을 쓴다.

**⑤ 복사 (Copy button)** — 원본 designbookmark `copy-button`
- 모양: 높이 28 · 8px 모서리 `grey-100` 단추, 아이콘 16 + `복사`. 누르면 아이콘이 돌며 작아지고 `emerald-600` 체크가 나오며, 글자가 위로 말려 `복사됨`(`emerald-700`), 단추 폭이 맞춰 늘어남.
- 움직임: 글자 말림 **260 · 20**, 아이콘 **420 · 18**, 폭 **300 · 24**, 1.8초 뒤 되돌아감.
- 클립보드 쓰기가 막히면 `클립보드에 넣지 못했습니다. 경로를 직접 골라 복사해 주세요` 안내 토스트. 원본의 혼자 누르기(자동 재생)는 화면에서 쓰지 않는다.
- 쓰는 곳: 모든 경로 칸(Scanresult · Conder Scan · KLA 폴더 · 로컬 결과 · 저장 폴더), 오류 코드. [폴더 열기] 옆에 둔다.

### 8-3. 기다림 표시 — 기다리는 시간에 따라
| 기다림 | 표시 | 예 |
|---|---|---|
| 1초 안 | 없음 | 탭 전환 · 필터 |
| 몇 초 · 진행률 모름 | **3점 로더**(6px 점 3개, 900ms, 150ms 간격) — 단추 안이면 글자 자리에 | 찾기 · 저장 · 엔진 요청 |
| 진행률 앎 | 진행 막대(8px, `accent`, `scaleX` 300ms) + 고정폭 `n / 전체` | 파일 읽기 · 사진 불러오기 |
| 단계가 있는 긴 작업 | **작업 단계(②)** + 진행 막대 + [중단] | Batch Report 조사 · TB500 조회 · KLA 캐시 갱신 |

## 9. 선 · 모양 · 아이콘

- 기본 선은 1px `line`. 2px 장식 선, **왼쪽 색 띠**(토스트 · 알림 · Lot 묶음 머리 · 목록 카드의 `border-left`)는 쓰지 않는다 — 바탕색 + 동그라미 아이콘으로 바꾼다.
- 선택 · 초점은 1.5px(`border` 1px + `box-shadow` 0.5px): 입력 칸 초점 = `focus`, 고른 호기 칸 · 큰 숫자 카드 = `accent`.
- 그라데이션 쓰지 않는다.
- 아이콘: 24 격자 · 선 1.8 · 둥근 끝 · `currentColor`, 화면에서는 16px(빈 화면 24px). 단추 글자 앞에 붙인다. 화면 글 속 이모지(⚙ 🔎 📥 🛠)는 지금 글을 고치지 않는 원칙(1절)에 따라 **이번 작업에서는 그대로 두고**, 새 단추부터 SVG 아이콘을 쓴다.

## 10. 부품 (지금 클래스 → 새 모양)

| 부품 | 지금 클래스 | 새 모양 |
|---|---|---|
| 머리 막대 | `.topbar` `.brand` `.brand-icon` `.environment` | `brand` 바탕, 아이콘 36 · `r-m` · `accent`, 제목 18/700, 부제 11 `on-brand-2` |
| 1단계 회사 탭 | `.vendor-tabs` | 어두운 막대 위, 활성 = 흰 탭(위 모서리 `r-m`) + `brand` 글자, 공통 탭 앞 1px 구분선 |
| 2단계 기능 탭 | `.navigation` | 흰 막대 + 아래 1px 선, 활성 = `brand` 글자 + **3px `accent` 밑줄**(민트 바탕 없음) — 밑줄은 한 개가 탭 사이를 미끄러짐(8-1) |
| 3단계 구역 탭 | `.bv .maintabs` `.defect-tabs` `.subtabs` `.watch-tabs` `.hub-tabs` | 15/700 + 12 설명, 활성 = 3px `accent` 밑줄(미끄러짐) |
| 4단계 보기 바꾸기 | `.bv .pilltabs` `.bv .seg` `.zone-tabs` | 분절: `grey-200`(카드 안 `grey-100`) 틀 · `r-m`, 고른 칸 = 흰 + `sh-1`(미끄러짐) |
| 페이지 머리 | `.page-heading` `.eyebrow` `.connection` | eyebrow 11/700 +0.14em `emerald-700`, h1 28/700, 설명 14 `text-2`, 연결 배지 = 알약 `accent-weak` + 점 |
| 카드 | `.panel` `.current-settings` `.edit-dialog.inline` `.tb5-box` | 흰 + 1px `line` + `r-l`, 그림자 없음, 제목 16/700 + 설명 13 |
| 큰 숫자 | `.kpis article` `.bv .kpib button` | 카드와 같은 틀, 라벨 12/700, 숫자 30/700 고정폭 + 단위 13, 고른 것 = 1.5px `accent` |
| 주 단추 | `button.primary` | `accent` 바탕 + `on-accent` 글자, 큰 44 · `btn-l`, 눌림 = `accent-press` |
| 보조 단추 | `button`(기본) | `grey-100` 바탕 + `brand` 글자, 선 없음, 36 · `r-m`. **회색 바탕 위에서는** 흰 바탕 + 1px `line-strong`(바깥선 단추) |
| 투명 단추 · 글자 링크 | `.linklike` `.x` | 바탕 없음 + `brand` 글자, 올리면 `hover` 덧칠 / 링크는 밑줄 3px 띄움 |
| 위험 단추 | `button.danger` | `red-600` + 흰 글자 |
| 처리 중 단추 | (새로) `busy` 상태 | 글자 자리에 3점 로더, 폭 그대로 |
| ? 단추 | `.help-btn` | 24 원(큰 것 32), 1px `line-strong`, `text-2` |
| 입력 칸 · 선택 상자 | `input` `select` `textarea` | 38 높이, `bg-sunken` + 1px `line-strong` + `r-m`, 초점 = 흰 + 1.5px `focus`, 오류 = 1.5px `red-600` + 아래 12px `red-700` 글 |
| 검색 칸 | Defect · Batch 목록 검색 | 입력 칸 + 왼쪽 돋보기(`grey-500`) |
| 체크 · 라디오 | `input[type=checkbox]` | 기본 모양 그대로, `accent-color: accent-press`(지금 `#31517c`) |
| 스위치 | `.bv .switch` | 공통 부품으로: 40×24 트랙 `grey-300` → 켜짐 `accent`, 손잡이 18 흰 + `sh-1`, 200ms |
| 칩 | `.chip-pick` `.bv .chip` `.sel-chip` | 30 알약, 흰 + 1px `line-strong`, 고른 것 = `brand` 바탕 + 흰 글자, 개수 = 고정폭 |
| 배지 | `.badge` `.bv span.st` `.tb5-st` | 22 높이 · `r-s` · 12/700, 상태표(3-3) 바탕 + 글자 + 6px 점 |
| 안내 상자 | `.alert` `.warn-box` `.guide-box` `.bv .logic` `.activity-hint` | 바탕색 + 18 동그라미 아이콘, `r-m`, 선 · 왼쪽 띠 없음(info = slate-50, warn = amber-50, bad = red-50, ok = emerald-50) |
| 표 | `table` `.table-scroll` `.tbl` | 틀 1px `line` + `r-m`, 머리 `bg-sunken` · 12/700 `text-th`, 줄 사이 1px `line` 만(세로 선 · 줄무늬 없음), 올리면 `bg-sunken`, 숫자 오른쪽 정렬 |
| 토스트 | `.toaster` `.toast` | 오른쪽 위, `slate-900` 바탕 + 흰 글자 + 20 원 아이콘(완료 `accent`, 오류 `red-600`, 안내 `slate-500`), `r-l` · `sh-3`, 3.2초 |
| 창 | `.edit-dialog` `.tb5-win` `.bv` Lot 창 · 원문 창 | `r-xl` · `sh-3` · 안 여백 24, 제목 20/700, 아래 오른쪽에 [보조] [주] 단추, 가림막 `scrim` + 2px 흐림 |
| 단계 표시 | `.stepper` | **① 단계 표시(8-2)**: 32 원 + 4px 선, 끝남 = `accent` + 그려지는 체크, 지금 = `brand` + 튀어 오름 |
| 진행 막대 | `.progress-bar` `.bv .progress3` `.progress-line` | 8px 알약 트랙 `grey-200` + `accent`, 오른쪽 고정폭 `n / 전체` |
| 진행 패널 · 긴 작업 | `.activity` · 조사 진행 줄 | **② 작업 단계(8-2)**: 오른쪽 아래 카드 `r-l` · `sh-2` 안 또는 화면 카드 안, 지금 회전 스피너 대신 |
| 주기 · 시각 고르기 | 자동 분석 주기 · `batch_time` 선택 상자 | **③ 돌림 선택(8-2)** |
| 값 범위 입력 | Defect 분석 필터 `fltRngHtml` 의 최소 ~ 최대 칸(기본 Step 3 · 4, 대규모 5-1), 5-3 GL 범위, 유효 Lot 매수 | **④ 범위(양방향) 막대 + 숫자 칸(8-2)** — 숫자 칸 · `data-f` 는 그대로 두고 막대를 더함 |
| Defect 분석(기본) 지도 | Step 3 · 4 `makePanel` 의 Wafer map(`bigmap`) | 필터에 맞는 ☑ = `map-dot` 점, ☐ = 회색 고리, 필터 밖 = 옅은 회색 고리(지금 규칙), ☑ Defect 있는 Die = `map-die-hit`, 보고 있는 Defect = `emerald-600` 고리. **새 기능 제안**: 빈 곳을 끌어 영역 안 Defect 만 ☑ (Shift = 더하기) — 14절 |
| Defect 분석(대규모) | Step 5 · 5-1 ~ 5-3 | 지도 없음(지금 그대로). 5-1 필터 + 목록 → 5-2 결과 목록(사진 상태 배지) → 5-3 사진 · GL 범위 · 최종 목록. 단계 표시 = ①(8-2) |
| 경로 복사 | 경로 칸 · `OpenPath` | **⑤ 복사(8-2)** — [폴더 열기] 옆 |
| 빈 화면 | `.empty-state` `.empty-symbol` | 52 칸 `grey-100` · `r-l` 안 24 아이콘, 제목 15/700, 설명 13, 첫 동작 단추 하나 |
| 로그 상자 | `.log-box` | `slate-900` 바탕 + `#dbe7f5` 글자, 고정폭 12 |
| 호기 칸 | `.bv .mbox` `.machine` | 흰 + 1px `line` + `r-m`, 고른 것 = `accent-weak` + 1.5px `accent` |
| 자동 분석 켜기/끄기 | `.onoff` | 스위치 부품으로 바꾸는 안(14절) — 지금 초록/빨강 알약 단추 |
| Recipe 값 비교표 | `.comparison-*` | **예외 · 그대로** |

## 11. 말투

- 지금 화면은 **'-합니다 · -하세요'** 체다(예: `분석 엔진에 다시 연결했습니다.`). 디자인 작업에서는 글을 고치지 않으므로 새로 쓰는 글도 이 말투를 따른다(토스의 해요체로 바꾸지 않는다 — 바꿀지는 소유자가 정한다, 14절).
- 단추는 일어날 일을 그대로 쓴다: `조사 시작` · `Excel 로 저장` · `폴더 열기`. '여기를 누르세요' 같은 글 금지.
- 오류는 무엇이 안 됐고 어떻게 하면 되는지: `AOI-21 에 연결하지 못했습니다. 탐색기에서 \\IP\c$ 를 먼저 열어 주세요.`
- Batch Report 의 Error 원문은 고치지 않고 그대로 보인다(CLAUDE.md). 해석어('회복' · '미해결')를 쓰지 않는다.
- 한 문장 안에 줄표(—)로 덧붙이지 않는다. 과장(최고의 · 혁신적)과 느낌표 금지.

## 12. 하라 · 하지 마라

**하라**
- 화면 코드는 역할 토큰(`--accent` `--line` `--text-2` …)으로 부르고, 팔레트 단계(`--emerald-500`)는 새 역할을 만들 때만 직접 쓴다.
- 주 단추는 화면 구역마다 하나. 나머지는 보조 · 투명 단추.
- 상태는 배지(바탕 + 글자 + 점)로, 숫자는 고정폭으로.
- 넓은 표 · 그래프는 그 칸 안에서 가로 스크롤(페이지 전체가 옆으로 밀리지 않게).
- 키보드 초점은 늘 보이게(`focus` 2px, 2px 띄움).
- 바꾸기 전 · 후 스크린샷과 시험 통과를 같이 남긴다.

**하지 마라**
- 기능 · 글 · 클래스 이름 · DOM 을 디자인 작업에서 바꾸지 마라.
- 웹 폰트 · CDN · 외부 이미지를 넣지 마라.
- 에메랄드를 장식(제목 색 · 아이콘 색 · 배경 큰 면)에 쓰지 마라. 에메랄드 위에 흰 글자를 쓰지 마라.
- 카드마다 그림자를 주지 마라. 왼쪽 색 띠 · 2px 장식 선 · 그라데이션을 쓰지 마라.
- 반 픽셀 글자 크기 · 500/600 굵기를 쓰지 마라.
- 레이아웃을 매 프레임 다시 계산하게 하는 움직임(표 전체 높이 · 여백 · 큰 면 그림자 애니메이션)과 반짝이는 뼈대 · 시차를 쓰지 마라. 튀는 움직임은 8-2 에 적힌 곳(지금 단계 튀어 오름 · 체크 · 복사 아이콘)에만.
- 호기 색 · Recipe 값 비교표 · Wafer Map 그림 색을 이 팔레트로 바꾸지 마라.

## 13. 화면 폭

데스크톱 앱이지만 창을 좁히는 경우가 있어 지금의 세 단계를 그대로 쓴다.

| 폭 | 바뀌는 것 |
|---|---|
| > 1100 | 기본: 큰 숫자 5칸, 그래프 · 요약 2단 |
| ≤ 1100 | 큰 숫자 3칸, 2단 → 1단, 작업 단계 카드 세로로 |
| ≤ 760 | 바깥 여백 16, 머리 막대 오른쪽 글 숨김, 큰 숫자 2칸(첫 칸 한 줄 전체), 탭은 줄 안에서 가로 스크롤, 단계 표시 글자 숨김 |

## 14. 정할 것 (소유자 결정 대기)

1. **모션 부품을 넣을 곳** — 8-2 의 '쓰는 곳'이 초안이다(미리보기 예시 페이지 5개에 넣어 봄). 빼거나 더할 곳을 정한다.
2. **Defect 분석(기본) 지도에서 영역으로 ☑ 고르기** — 지금 기본 모드는 지도 점 누르기 = 그 Defect 보기, ☑ 는 목록에서만 한다. 미리보기처럼 지도 빈 곳을 끌어
   '영역 안 필터에 맞는 Defect 만 ☑'(Shift = 더하기)를 넣을지. **기능 추가라 디자인 작업(1절)과 따로** 한다 — Defect HTML(rev6) 원본과 ccr 브랜치 사본도 같이 고쳐야 한다(CLAUDE.md).
3. **기능 탭 활성 모양** — 밑줄만(이 초안) / 지금처럼 민트 바탕 + 밑줄.
4. **보조 단추** — 회색 채움(이 초안, 토스식) / 지금처럼 흰 바탕 + 선.
5. **토스트** — 짙은 슬레이트(이 초안) / 지금처럼 흰 바탕 + 왼쪽 띠.
6. **옛 파랑 `#31517c`** — Batch 화면의 칩 · 선택을 `brand`(슬레이트)로 모으는 안이 맞는지.
7. **자동 분석 켜기/끄기** — 지금 초록/빨강 알약 단추를 스위치로 바꿀지(글자 `켜짐/꺼짐` 이 시험에 걸려 있는지 먼저 확인).
8. **말투** — '-합니다' 유지(이 초안) / 새 글부터 해요체.
9. **결과 HTML(`report_theme.THEME_CSS`)** — 앱과 같이 바꿀지, 이번에는 앱만 할지.

## 15. 알려진 빈틈

- 입력 칸 테두리 `grey-300` / 흰 바탕 = 1.4:1 로 낮다(지금 화면도 비슷). 칸 바탕(`bg-sunken`)으로 구분하지만, 더 진하게 할지는 미리보기에서 본다.
- 주 단추 눌림(`emerald-600`) 위 글자 대비 4.4:1 — 순간 상태라 그대로 두었다.
- 맑은 고딕이 없는 PC(맥 · 리눅스 미리보기)에서는 대체 서체로 보여 글자 폭이 조금 다르다. 실제 확인은 Windows 에서.
- 모션 부품의 실제 React 구현은 아직 없다(미리보기 HTML 이 기준 구현). 느린 회사 PC 에서 끊김이 없는지는 Windows 실기에서 확인한다.

## 16. 참고

- 토스 TDS design.md — getdesign.kr (구조 · 원칙 참고, 색 · 서체는 쓰지 않음).
- designbookmark.com Motion Studies — Step progress · Copy button 원본, `tokens.css` 스프링 프리셋(lead · trail).
- Kokonut UI(kokonutui.com, MIT) — AI Loading(작업 단계) · Wheel picker. SmoothUI(smoothui.dev, MIT) — Scrubber. 코드를 그대로 가져오지 않고 같은 타이밍으로 다시 만들며, 옮길 때 MIT 저작권 줄을 소스 머리에 남긴다.
- 프로젝트: `CLAUDE.md`, `frontend/src/styles.css`, `frontend/public/defect/para-skin.css`, `tools/test_desktop_ui.mjs`.
