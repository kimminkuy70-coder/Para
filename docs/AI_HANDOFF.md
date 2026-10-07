# AI 공통 인수인계

## 최신 재개 — Para #17 Batch Report 캐시와 함께 AI 에게 줄 계산 지침 (2026-10-07 KST, `version_v12`)

- GitHub 이슈 #17: "배치레포트 캐시파일과 같이 AI한테 주어야 할 지침 만들어봐. 프로그램 계산 방식을 그대로 새 AI한테 전달하고 싶어. 양이 많으면 txt 로(클로드 링크는 접속 못함)."
- 새 문서 `docs/ai_guide/BatchReport_캐시_분석지침.txt`(코드 변경 없음): #16 zip 구조(manifest · 누적 JSON schema 1 · 사람선택), 레코드 만들기(같은 호기 digest 중복 제거 · 범위 필터),
  공통 파싱(normalize_key · 시간/날짜/숫자), `lotmodel`(S/M · Lot 코드 · 3D · Lot ID 판독 오차 · 슬롯 · 원인/연쇄/중단/스킵 · outcome · 묶음 12h/48h · Lot · wafer 판정 · 사람 선택),
  `batchview`(레시피 · 정상 25매 · 1장 처리 시간 · Defect 과다 기준 · split · 손실 배분 · 조치 대기 · 점검 · U 행), `batchsaved` 합산(가동률 · 정상/실제 WPH · 생산능력 · 처리량 감소),
  Lot 추적 숫자, `recipecompare`, 옛 `batchreport.compute` M 지표, 주의 사항, 최소 Python 로더 예시.
- **앱 계산식을 바꾸면 이 지침도 같이 고친다**(batchsaved/batchcharts 와 같은 원칙). zip 에 자동으로 넣지는 않았다(#16 '용도 언급 금지' 지시 — 넣을지는 사용자 결정).
- 검증: 문서만 추가 — 각 정의를 `lotmodel.py` · `batchview.py` · `batchsaved.py` · `recipecompare.py` · `batchreport.py` 코드와 대조. `tools/check_project.py`(tkinter 없는 기존 1건만 실패).

## 최신 재개 — Para #16 Batch Report 취합 캐시 내보내기(zip) · 폴더 열기 (2026-10-07 KST, `version_v12`)

- GitHub 이슈 #16: "배치 리포트 취합한 캐시들을 export 하는 기능 — 배치레포트들의 데이터가 모두 취합된 .zip, 폴더 열기 기능도. 프로그램에서는 export 한다고만(용도 언급 금지)."
- 엔진 `param_manager/desktop_batch.py` `cache_export` + IPC `batch_cache_export`(`desktop_ipc.py`): `배치분석/누적/*.json` 전부 → `배치분석/내보내기/BatchReport_캐시_*.zip`
  (`누적/<호기>_<해시8>.json` · `사람선택/batch_lot_choices.json` · `manifest.json`). 캐시가 없으면 "먼저 [조사 시작]" 오류. 최근 3개 보관. 연결경로 검사에 `내보내기` 폴더 추가.
- `desktop_open.py`: `.zip` 은 reveal 만 허용 → 캐시 zip · 진단 로그 zip 의 '폴더에서 보기'가 이제 동작(전에는 확장자 거부).
- 화면 `frontend/src/Batch.tsx`: 조사 범위 패널 아래 [Batch Report 캐시 내보내기 (zip)] · [폴더 열기] · 결과 경로/수/크기.
- 검증: `tests/test_cache_export.py`(빈 캐시 오류 · zip 내용/manifest · 깨진 캐시 건너뜀 · 최근 3개 · reveal 허용/열기 거부 · IPC) · test_desktop_open · test_recipecompare,
  `tools/check_project.py`(tkinter 없는 test_batchreport 기존 1건만 실패), `npx tsc --noEmit` · `vite build`. Windows 실기(탐색기 선택) · 실자료 대용량 zip 미검증.

## 최신 재개 — Para #15 Batch Report 조사 실패(18대) 원인 기록 · 원문 내장 메모리 절감 (2026-10-07 KST, `version_v12`)

- GitHub 이슈 #15: "진단 로그(진단로그_20261007_091634.zip) 분석해서 Batch Report 조사가 안 되는 원인 — 저장 위치나 폴더 설정이 잘못됐다고 뜸. 18대 한번에 조사."
- 진단 로그 해석: 2026-10-07 08:17~09:14 `investigate` 4회 모두 7~15분 뒤 `error`. 화면 문장은 `investigation_failed` 의 고정 문장
  ("폴더 접근과 로컬 저장 공간을 확인")이라 폴더 문제처럼 보였을 뿐, `desktop_ipc.Session.investigate` 가 예외를 삼키고 `log_failure` 도 안 불러
  원인이 오류 로그 · 상세 로그 어디에도 남지 않았다. 폴더 설정 오류(ValueError)는 시작 즉시 나므로 7~15분 뒤 실패와 맞지 않는다.
  같은 시각 엔진 메모리 사용 93%(여유 1.0GB / 15.4GB, 전날 75~79%) → 18대 수집 뒤 결과 파일 단계(v12.2.5 부터 Lot 추적 HTML 에 원문 표 전부를
  목록 → JSON 글자 → gzip → base64 로 한꺼번에 만듦)에서 메모리 부족(MemoryError)이 가장 유력. 단정은 못 함(예외가 기록되지 않았으므로).
- 수정: ① `investigate` 실패 시 `log_failure("investigate", exc)` 로 오류 로그에 traceback, `investigation_message(exc)` 로 원인별 문장을
  `message` 로 보냄(MemoryError → 메모리 부족 · 호기 나눠 조사, ValueError/RuntimeError → 엔진 안내 그대로, OSError → strerror · 코드(경로 제외), 기타 → 예외 종류).
  `record_run(False, error=…)` 에도 같은 문장. ② `report_theme.raw_blob` 를 한 장씩 JSON → `zlib.compressobj(wbits 31)` 스트리밍 압축으로 바꿔
  전체 목록 · 전체 JSON 글자를 메모리에 두지 않음(출력은 같은 표준 gzip+base64, 브라우저 쪽 그대로).
- 검증: `tests/test_investigate_failure.py`(gzip 왕복 · 순서 · 빈 목록 · 원인별 문장 · 경로 미포함) + `tools/check_project.py`(tkinter 없는 기존 1건만 실패).
  18대 실자료 · Windows 메모리 상황은 미검증 — 다시 실패하면 이제 화면 문장과 오류 로그에 실제 원인이 남는다.

## 최신 재개 — 튜토리얼(초기 설정 · 기능 둘러보기) (2026-10-06 KST, `version_v12`, v12.2.6)

- 사용자 지시(세션 대화): "초기 튜토리얼 — 초기 설정법(장비 연결 · 저장 폴더 · OneDrive: 개발자가 공유한 링크로 회사 노트북 OneDrive 에 연결한 폴더 경로)과
  간단한 기능 설명을 화살표 · 말풍선 방식으로. 튜토리얼 버튼은 설정 탭. v12.2.6 릴리즈."
- 새 `frontend/src/Tour.tsx`: `TourLayer`(앱 루트) + `startTour('setup'|'features')`('para:tour' 이벤트). 단계 = {target 선택자, 제목, 본문, go(주요 탭), sub(설정 하위 탭)}.
  화면을 어둡게 하고 대상에 강조 테두리(라임 · 맥박) + 화살표 말풍선(아래/위 자동, 화면 안으로), 이전 · 다음 · 건너뛰기, ←/→/Enter/Esc. 대상이 나타날 때까지 최대 2초 기다리고
  없으면 가운데. 튜토리얼은 안내만 — 값을 저장하거나 실행하지 않는다.
- 연결: `main.tsx` nav 버튼 `data-tour="nav:…"` · `<TourLayer/>`, `Settings.tsx` 맨 위 튜토리얼 상자([초기 설정 튜토리얼] · [기능 둘러보기]) · 'para:settings-sub' 로 하위 탭 열기 ·
  data-tour(저장 폴더 OneDrive 안내 · 경로 · 저장, AOI 폼 · 표, 하위 탭, 현재 설정), `Batch.tsx` [조사 시작] · 분석 pilltabs. 저장 폴더 탭 안내에 OneDrive 공유 링크 연결법 한 줄 추가.
- 초기 설정 12단계: 소개 → 설정 탭 → ① 저장 폴더(OneDrive 공유 링크 → [내 파일에 바로 가기 추가] → 탐색기 OneDrive - 회사 → [📁 찾기] → [저장]) → ② 장비 연결(탐색기에서 장비 폴더 확인 →
  호기 · 호기 폴더 → [추가] → 인식된 폴더 확인) → ③ 로컬 작업 폴더 → 현재 설정 → 끝. 기능 둘러보기 11단계: 주요 탭 7개 + Batch [조사 시작] · 결과 탭(레시피 비교).
- 검증: `tools/test_desktop_ui.mjs` 에 튜토리얼 단계(초기 설정 8단계 + 하위 탭 자동 전환 + 강조 위치 = 대상 + 말풍선 화면 안 + Esc 닫기, 기능 둘러보기 끝까지 → 설정 탭) 추가 · 통과,
  `docs/screenshots/rev1-tour.png`. `npx tsc --noEmit` · `vite build` · `tools/check_project.py`(tkinter 없는 기존 1건만 실패). Windows 실기(WebView2) 미검증.

## 최신 재개 — Para #14 결과 HTML 앱 디자인 · 원문 내장 + 레시피 비교 모드 (2026-10-06 KST, `version_v12`, v12.2.5)

- 이슈 #14(실자료 해석 질문) 후속 사용자 지시(세션 대화): "결과 HTML(분석 · 대시보드 · Lot 추적 · WPH)을 프로그램 화면 컨셉으로, 원문은 링크 대신
  같은 데이터로 담아서, 레시피 비교 모드(두 그룹 이름 + 레시피 드래그) 구현, 그래프가 넘치면 가로 스크롤, v12.2.5 로 릴리즈."
- 새 `param_manager/report_theme.py`: 앱(styles.css)과 같은 상단 바 · 제목(eyebrow · h1 · 배지 · stamp · 조사 범위 접기) · 큰 탭(metricnav → maintabs 모양) ·
  흰 패널 · kpib 카드 · 표 · 상태 칩 · 창 테마(`THEME_CSS`, `<body class="app-rpt">` 아래만 덮어씀) + `page_top`/`page_foot`.
  원문 창: `raw_blob(view)` = 원문 표(Batch Info · wafer 표) gzip+base64 → `RAW_JS` 가 DecompressionStream 으로 풀어 앱 원문 창과 같은 배치로 보임.
- `batchsaved.build_html` · `lotreport.build_html` · `wph_html.build_html`: 새 머리 + THEME_CSS(계산 · 그래프 스크립트는 그대로).
  Lot 추적: attempts 에 `g`(원문 번호) → [원문 보기](view 가 있을 때). view 없으면 예전 file:/// 링크. 실자료 20,465장에서 Lot HTML 42→46MB.
- `batchcharts.py`: 그래프 폭 = 컨테이너 − 36px(카드 안쪽 여백), colChart 오른쪽 36px 여유(마지막 날짜 글자 잘림) + `.chartscroll` 가로 스크롤.
- 레시피 비교: `param_manager/recipecompare.py` — 레시피 키 'Job · Recipe(s)'(최빈값), `recipes(view)`, `compare(view, spec)`:
  속도(정상 25매 · 정상 전체 · 실제 WPH, 순수 스캔, 1장 처리), 오류(레시피 탓/작업자 중단), 같은 wafer 짝(Pass · 같은 Scanned Dice · pair_hours, B 레시피별 · 부호 검정),
  기준 12 조합(WPH 3 × 테스트 Lot 2 × 호기 범위 2, ±2% 안은 '비슷함'), `build_html`(앱 디자인 · 쓴 Report 원문 내장). 테스트 Lot = Lot 이름(TEST · engineer · scan time …).
  IPC `batch_compare_recipes` · `batch_compare` · `batch_compare_export`(로컬 `배치분석/비교/`). 특징은 View 에 캐시(`_cmp_features`, 실자료 2.9초).
- 화면 `frontend/src/BatchCompare.tsx`: 분석 pilltab '레시피 비교' — 레시피 목록(검색 · 끌기 · [A]/[B]) → A/B 상자(이름 · 칩 · 기간) → 옵션(같은 호기 · 테스트 Lot 빼기 ·
  짝 시간) → [비교] → KPI 4 · 기준 12 조합 · 속도 표 · 같은 wafer 막대(+원문) · 오류 → [HTML로 저장]. 그룹 · 옵션은 localStorage(`bv.compare.v1`).
- 검증: `tests/test_recipecompare.py`(엔진 5 + IPC 1), test_batchsaved · test_wph_html · test_batchview, `tools/check_project.py`(test_batchreport 의 tkinter 없는 기존 1건만 실패),
  `npx tsc --noEmit` · `vite build`, `tools/test_desktop_ui.mjs`(레시피 비교 탭 단계 추가) 통과, 레시피 2개 fixture 로 끌기 → 비교 → HTML 저장 → 원문 창 브라우저 확인,
  실자료(조사 zip 20,465장)로 결과 HTML 4종 · 비교 HTML 생성 후 Chromium 확인. Windows 실기 · Edge(WebView2) 화면 미검증.

## 최신 재개 — Para #13 저장된 결과 HTML 을 앱과 같은 인터랙티브 그래프로 (2026-10-06 KST, `version_v12`, v12.1.5)

- GitHub 이슈 #13: "Batch Report 분석(가동률 · Lot 추적 · WPH)에서 나오는 결과 HTML 파일들도 프로그램에서 보는 것과 똑같이 인터랙티브 그래프로. v12.1.4 로 릴리즈."
  → v12.1.4 는 이미 #12 로 나간 태그라(태그 이동 · 덮어쓰기 금지) **v12.1.5** 로 릴리즈.
- 새 `param_manager/batchcharts.py`(앱 그래프의 바닐라 JS 이식 · CSS), `batchsaved.py`(`chart_data` → `bvdata` JSON, `#lotchart`/`#utilapp`/`#wphapp`,
  `JOB_JS` 삭제 — WPH 탭 전체를 `APP_JS` 가 앱처럼 그림, TAB_JS 가 탭 전환 때 `BV.rerender()`), `lotreport.py`(기간별 Lot Scan 현황 + 기간 필터 + `#lot=` 해시).
- 그래프: Lot 기간 막대(일/주/월 · 범례 켜고 끄기 · 누르면 그 기간 Lot), 가동률(호기 탭 · KPI 4 · 시간 구성 호기별/기간별 · 24시간 시간표 ◀▶ ·
  기간 상세 창: 시간 구성/손실 이유(누르면 Lot)/시간표), WPH(하위 레시피 · 호기 select · 상위 레시피 필터 · KPI 4 · 레시피 비교 · 표 · 기간별 추이(그래프 값 4종) ·
  레시피 상세 창: WPH 분해/1장 처리 시간 + 정상 25매 분포/Lot별 실제 WPH 산점도). 툴팁은 앱과 같은 표 모양(rich).
- 앱과 다른 점: 저장 HTML 에는 원문 경로가 없어 'Batch Report 원문 창'은 없음 — Lot 을 누르면 같은 폴더 Lot 추적 HTML 의 Lot History(새 탭). 대시보드는 Lot 링크 없음.
  조사 범위 = 저장 시점 조사 범위 전체(앱처럼 기간 · 호기 범위를 다시 고르는 칸은 없음).
- 검증: `test_batchsaved.test_interactive_chart_data_and_scripts` 추가, `tools/check_project.py`(test_batchreport 의 tkinter 없는 기존 1건만 실패),
  Chromium(Playwright)으로 합성 자료의 분석 HTML · 대시보드 · Lot 추적 HTML 에서 막대 hover 툴팁 · 클릭 · 범례 · 일/주/월 · 기간 상세 창 · 레시피 상세 창 ·
  시간표 · 산점도 · 상위 레시피 칩 · `#lot=` 열기 · JS 오류 없음 확인. Windows 실기 · 실자료 · 큰 자료(수천 Batch Report)에서의 파일 크기/속도 미검증.

## 최신 재개 — Para #12(#11 후속) 조사 = 이미 조사한 것은 두고 신규만 + 저장 HTML 상위 레시피 필터 (2026-10-06 KST, `version_v12`, v12.1.4)

- GitHub 이슈 #12(= #11 답변에 대한 사용자 지시): "이미 조사한 건 놔두고 신규만 있는지 빠르게 검토해서 추가할 Batch Report가 있으면 추가해서
  결과가 나오게. 병렬 읽기는 하지 마. 결과 레포트 HTML 도 똑같이 필터 기능. v12.1.4 로 릴리즈."
- `param_manager/batchreport_store.py`: `_scan`(scandir 1번 → 이름 · 수정시각 · 크기) 로 캐시 서명 비교 — 맞는 파일은 resolve/stat 없이 캐시 사용,
  진행 표시는 새로 열 파일만('새 Batch Report 없음 (캐시 n개)'). 새로 읽은 게 없으면 캐시 JSON 다시 쓰지 않음(`_save_state` 생략), 캐시 JSON 은
  `_MEMO`(파일 mtime · 크기 같을 때) 재사용 + 얕은 복사. host_gap 은 앞 호기에서 Report 를 연 경우에만, 같은 호기 추가 폴더 사이엔 없음. 병렬 없음.
  record 에 `digest` 추가(지문용).
- `param_manager/batchreport_service.py`: `fingerprint()` + `_previous()` — 가장 최근 `조사_*` 의 `조사설정.json` 지문과 같고 HTML/Lot HTML/Excel 이
  남아 있으면 결과 파일을 다시 만들지 않고 그 폴더 반환(`reused_output: True`, 대시보드도 그대로). 지문에 날짜 · 앱 버전 포함(날 바뀌면 다시 만듦).
- `param_manager/batchsaved.py`: WPH 탭(분석 HTML · 대시보드)에 `_job_filter`(앱 JobFilter 와 같은 칩 · 전체 보기 · 찾기 · 찾은 것 모두 고르기) +
  상위 레시피 묶음(`.capgrp`/`.capjob`) · '하위' 배지, 표 상위 레시피 머리 줄. `JOB_JS` 가 data-job 행을 숨기고 숫자 4개를 내장 JSON(`wphjobs`)으로
  같은 식으로 다시 계산, 막대 길이는 보이는 레시피 기준으로 다시 맞춤. `frontend/src/metricHelp.ts` 조사 설명 문구 갱신.
- 검증: 새 테스트 `test_batchreport.test_only_new_reports_fast_path`(캐시 미재기록 · parse 0 · 간격 없음 · 결과 폴더 재사용 · 새 Report 생기면 새 결과),
  `test_batchsaved`(필터 · JSON 합) 추가. `tools/check_project.py`(test_batchreport 의 tkinter 없는 기존 1건만 실패) · `npx tsc --noEmit` · `vite build` 통과,
  Chromium(Playwright)으로 저장 HTML 필터(칩 1/2개 · 전체 보기 · 찾기) 동작 확인. Windows 실기 · 장비 공유폴더 실측(속도) 미검증.

## 최신 재개 — Para #10 WPH 상위 · 하위 레시피 구분 UX + 상위 레시피 필터(여러 개) (2026-10-06 KST, `version_v12`, v12.1.3)

- GitHub 이슈 #10(예약 작업 처리): WPH · 생산능력의 레시피 비교 · 호기 × 레시피 표 둘 다 상위 레시피(Job)와 하위 레시피(Recipe(s))가
  구분되게 UX 개선 + 상위 레시피를 여러 개 고를 수 있게(필터).
- `frontend/src/BatchWph.tsx`: ①`JobFilter`(숫자 4개 위, role=group '상위 레시피 필터') — 상위 레시피 칩(aria-pressed, 하위 레시피 수) 여러 개 토글 ·
  '전체 보기' · 9개 이상이면 찾기 칸 + '찾은 것 모두 고르기'. 비면 전체. 고른 상위 레시피로 레시피 비교 · 표 · 숫자 4개(`sel`) · 기간별 추이를 거르고
  하위 레시피 select 도 그 상위 레시피 것만(고른 하위 레시피가 필터 밖이면 해제). 필터가 비었을 때는 종전처럼 하위 레시피를 고르면 같은 Job 끼리 비교.
  ②레시피 비교 = 상위 레시피마다 묶음 상자(`.capgrp`, 왼쪽 네이비 띠) + 머리 줄(`.capjob`: '상위 레시피' 배지 · Job · 하위 레시피 수 · 호기 · Batch Report)
  + 들여 쓴 하위 레시피 줄(`.caprow.sub`, '하위' 배지 · 트리 선). 상위 레시피끼리는 die 수가 달라 생산능력을 더하지 않음(머리 줄엔 막대 없음).
  ③호기 × 레시피 표 = 상위 레시피 머리 줄(`tr.grouphead.job`, 배지 + 요약) › 하위 레시피 합계 줄(`td.subr` '하위' 배지) › 호기 줄. 열 이름 '레시피 (상위 › 하위)'.
  CSS 는 `styles.css` 끝 `.bv .lv/.jobfilter/.jf-*/.capgrp/.capjob`. ? 설명 `metricHelp.ts` `wph.recipe`. 계산 · 지표 정의 변경 없음.
- 검증: `npx tsc --noEmit` · `vite build` · `tools/test_desktop_ui.mjs`(상위/하위 배지 · 칩 1개/2개 고르면 묶음 수 · 전체 보기 · 표 머리 줄 확인 추가) 통과,
  `tools/check_project.py`(test_batchreport 의 tkinter 없는 기존 1건만 실패). 실자료 · Windows 실기 미검증.

## 최신 재개 — Para #9 WPH · 생산능력 기간별 추이(일 · 주 · 월) (2026-10-06 KST, `version_v12`, v12.1.2)

- GitHub 이슈 #9(예약 작업 처리): 'Batch Report 분석 › 가동률 조사 및 분석 › WPH · 생산능력' 도 일/주/월별로 보게.
- `frontend/src/BatchWph.tsx`: 보기 탭에 **[기간별 추이]** 추가(+ 기간 단위 세그먼트 일 · 주 · 월, 기본 주 — 가동률과 같은 `batchData.bucket` ·
  `periodName` · `shortKey` · `weekRange`, 주 = ISO 주 WW). `Periods` = 위에서 고른 레시피 · 호기 · 조사 범위로 거른 U 행(숫자 4개와 같은 `sel`)을
  기간마다 다시 더해 정상 WPH · 실제 WPH · 처리량 감소 · 하루 생산능력(호기마다 24 × 그 기간 실제 WPH 의 합 = `capSum`, 레시피 미선택이면 레시피 통합) ·
  Pass 장수 · 하루 평균 Pass(Pass ÷ 범위 안 일수) · Batch Report 수. 그래프 값 세그먼트(실제/정상 WPH · 하루 생산능력 · Pass 장수) 막대 1개 + 표(최근 기간 위).
  레시피를 고르면 기간 막대/행을 눌러 **그 기간으로 범위를 좁힌 레시피 상세 창**(`win.range`). 새 식 · 새 지표 정의 없음(기존 식을 기간별로 적용).
  ? 설명 `metricHelp.ts` `wph.period`.
- 범위 밖: 저장된 결과 파일(`batchsaved` 분석 HTML/Excel)의 WPH 시트는 그대로 호기 × 레시피(기간별 WPH 없음) — 필요하면 다음 이슈로.
- 검증: `npx tsc --noEmit` · `vite build` · `tools/test_desktop_ui.mjs`(기간별 추이: 일/월/주 전환 · 그래프 값 전환 · 레시피 고른 뒤 기간 행 → 레시피 상세 창 추가) 통과,
  `tools/check_project.py`(test_batchreport 의 tkinter 없는 기존 1건만 실패). 실자료 · Windows 실기 미검증.

## 최신 재개 — Para #8 Scanresult 백업본 포함 조사 스위치 + Lot 단위 Scan List 카드 리디자인 (2026-10-06 KST, `version_v12`, v12.0.2)

- GitHub 이슈 #8(예약 작업 처리). 참고 링크(emilkowalski/skills · nextlevelbuilder/ui-ux-pro-max-skill)는 README · `emil-design-eng` 규칙만
  참고(눌림 scale(.97) · ease-out · 전환 속성 지정 · 테두리 대신 옅은 그림자). 외부 코드 · 의존성은 넣지 않음.
- ①**Scanresult 백업본 포함 조사(공통 설정)**: 설정 파일 `scanresult_backup`(기본 true = 종전 동작). 원본 = 이름이 정확히
  `Scanresult`(대소문자 · 구분자 무시), 백업본 = `Scanresult_xxx` 등 다른 Scanresult* + 설정에서 추가한 Scanresult 보관 폴더.
  끄면 원본만(원본 이름이 없으면 이름순 첫 폴더). `commonality.scanresult_roots(backup=)` · `is_backup_scanresult`,
  `desktop_config.scan_backup/scanresult_roots_info/scanresult_roots_for`, IPC `config_set_scan_backup{enabled}`, `config_state.scan_backup`.
  적용처: Commonality 조사(`cmrun_plan` · `cmsurvey_preflight` — 이제 추가 보관 폴더도 같이 봄) · Commonality 감시(`cmwatcher.run_cycle(backup=)`,
  후보 `cmwatch_candidates`) · Batch Report 찾기의 Scanresult 경로(`batch_find` → payload `scan_backup`) · tkinter(`equip_app` 3곳).
  화면: 공통 `ScanBackup.tsx`(`ScanBackupBar` = 지금 범위 표시 + [백업본 포함] 스위치, 화면끼리 이벤트로 동기화 / `ScanRoots` = 이번에 조사한
  폴더 목록과 원본 · 백업본 · 추가 폴더 표시) — 신규 Commonality 조사 1·2단계, 감시 호기 단계 · 대표 S/M 창, Batch Report 찾기, 설정 › AOI 장비 호기 루트.
- ②**Lot 추적 '지금 보는 목록' 카드**(`BatchLot.tsx` `.lotlist`, CSS 는 `styles.css` 끝 `.bv .lotlist`/`.ll-*`): 동작(필터 · 정렬 · 2,000행 · Lot 창)은
  그대로, 모양만 — 목록별 위 띠 색 · 제목 점, 오른쪽 큰 개수, 도구 줄(검색 아이콘 · 상태 세그먼트(개수 포함, 종전 select) · 재스캔/호기 이동 토글),
  고정 머리 표 · 행 hover 강조 · 키보드 Enter 로 Lot 창, Lot · S/M 한 칸, 호기 이동 → 칩, 스캔 기간 2줄, 0 은 '—', Error 원문 칩 2개 + '+n', 빈 상태 안내.
- 검증: 새 `tests/test_scan_backup.py` 6 · `tools/check_project.py`(test_batchreport 의 tkinter 없는 기존 1건만 실패) · `npx tsc --noEmit` ·
  `vite build` · `tools/test_desktop_ui.mjs`(설정 스위치 끄고 켜기 · 상태 세그먼트 · 토글 · 개수 확인 추가) 통과. 실자료 · Windows 실기 미검증.

## 최신 재개 — Para #7 호기 색 고정 + 저장된 결과 파일 v12 리뉴얼 + 레시피 비교 '없음' 행 (2026-10-05 KST, `version_v12`, v12.0.1)

- GitHub 이슈 #7(예약 작업 처리) + 처리 중 사용자 추가 요청(레시피 비교에 정상 WPH 없음 행).
- ①**호기 색 고정**: `batchData.MACH_PAL` · `machColors(ids)`(호기 이름 정렬 순서로 색) — WPH 레시피 비교 막대가 레시피마다
  다른 색을 쓰던 것(쌓는 순서 index)을 호기별 고정 색으로. 범례 '같은 호기 = 같은 색', 호기 × 레시피 표 호기 칸에 색 네모.
- ②**레시피 비교 '없음' 행(사용자 추가 요청)**: 같은 Job 의 하위 레시피끼리 바꾸면 보이는 레시피 묶음이 같아 막대가 그대로라 바뀐 건지
  헷갈림 → 고른 레시피 줄 강조(`.caprow.sel`) + 위에 '고른 레시피: … — 정상 WPH x / 정상 WPH 없음' 문장(`p.capsel`), 줄마다
  정상 WPH 값 또는 '정상 WPH 없음', 실제 WPH 자료가 없는 레시피도 '실제 WPH 자료 없음' 행으로 남김(종전엔 행 자체를 뺐다).
- ③**저장된 결과 파일 v12 리뉴얼(기준 = 프로그램)**: 새 `param_manager/batchsaved.py` — 앱과 같은 `batchview.View.payload()` 를
  `batchData.ts` 와 같은 식으로 더해 `BatchReport_분석.html`(Lot 추적 · 가동률 · WPH · 생산능력 · 지표 정의 탭) ·
  `BatchReport_분석.xlsx`(조사 정보 · 정의 / 가동률 호기별 · 일 · 주 · 월 · 날짜×호기 / 손실 이유 / WPH 호기×레시피 / 정상 25매 /
  작업자 중단 / Lot 목록 / Batch Report 목록) · `가동률_대시보드.html`(가동률 · WPH, 30분 새로고침)을 만든다. 옛 M01~M11 출력
  (`batchreport_output.build_html/write_excel`)은 더 이상 저장 파일에 쓰지 않는다(`batchreport.compute` 결과는 IPC `table_page` 용으로 유지).
  Lot 추적 HTML(`lotreport.build_html(view=)`)은 같은 View 모델(저장된 사람 선택 포함) · 앱 지표 5개 · 멈춘 이유 요약(Error Lot 단위 /
  작업자 중단 종류별) · 작업자 중단 칸 색 · 3D 표시 · '묶음/시도' → 공정 단계 · Batch Report 용어.
- 흐름: `batchreport_service.run(overrides=)` 가 View 를 한 번 만들어 파일에 쓰고 `output['view']` 로 돌려줌 → `desktop_ipc` 가
  `set_view(view=)` 로 재사용(종전처럼 두 번 계산하지 않음). `desktop_batch.run` 이 로컬 Cache 선택을 넘김.
- 범위 밖(이슈가 이름을 대지 않음): `WPH_통합.xlsx/.html` · 호기별 취합 txt 는 옛 정의 그대로.
- 검증: `tests/test_batchsaved.py` 7(앱 식과 같은 가동률 · WPH · Lot 요약, 색 표 = batchData.ts, HTML/Excel/대시보드, 정상 WPH 없음 행,
  Lot 추적 HTML view) · test_batchreport(저장 파일 기대값 갱신, tkinter 없는 기존 1건만 실패) · test_desktop_batch(취소 패치 대상 변경) ·
  test_desktop_ipc · test_batchview · `tools/check_project.py` · `npx tsc --noEmit` · `vite build` · `tools/test_desktop_ui.mjs`(범례 ·
  레시피 고르면 줄 강조 + 정상 WPH 문장 확인 추가) 통과. 합성 자료로 저장 HTML 화면 확인. 실자료 · Windows 실기 미검증.

## 최신 재개 — Batch Report 지표 개편: 시간 3칸 · 정상/실제 WPH · 작업자 중단 (2026-10-05 KST, `version_v12`)

- 사용자 지시로 `version_v11`(v11.2.0 포함) 을 복사해 `version_v12` 를 만들고 확정한 계획대로 수정. 상세 정의는 CLAUDE.md
  'Batch Report 지표 개편' 절, 화면 ? 설명 문구는 `frontend/src/metricHelp.ts` 한 곳.
- 엔진: `lotmodel` 행 판정(앞 Error 없는 Aborted. = 작업자 중단 `STOP`, 앞 Error 없는 Skipped. = 스캔 안 한 슬롯 `SKIP`, attempt
  `outcome` · `stop_faults` · `avg_scan_sec`, 행 `faults`), `batchview._metrics`(날짜 × 호기 × 레시피 `U` · `stops` · 정상 25매 `N` ·
  Lot 줄 `L` · 기준값 `X`). 종전 `B`(5칸 가동률) · `C`(WPH base/eff) 는 없앰.
- 화면: 가동률(숫자 4개 + 호기별/기간별 100% 막대 + 기간 상세 창 + 24시간 시간표), WPH · 생산능력(레시피 비교 막대 · 호기 × 레시피 표
  + 레시피 합계 · 레시피 상세 창), Lot 추적(멈춘 이유 요약 Error / 작업자 중단), Lot 창(중단 색), Defect 과다 판정 설명 창.
  용어 카드 · 로직 상자 · Lot 추적 소개 카드는 지우고 ? 버튼(`BatchHelp.tsx` `Q`)으로 옮김.
- 범위 밖(사용자 확인 대기 없이 계획대로 둠): 기존 결과 파일(분석 HTML/Excel · 가동률 대시보드 · WPH 엑셀/HTML)은 옛 정의 그대로.
- 검증: test_lotmodel 21 · test_batchview 13 · 전체 Python(tkinter 없는 기존 1건만 실패) · tsc · vite build · `tools/test_desktop_ui.mjs`
  (가동률 ? 창 · 기간 상세 창 · 레시피 상세 창 · Defect 설명 창 추가) · 실자료 420개로 브라우저 전 화면 확인(2D_WBG 정상 27.5 ·
  1장 131초 · 실제 24.0, Defect 과다 중단 5건). Windows 실기 미검증. **push · 릴리즈는 사용자가 말할 때만.**

## 최신 재개 — Para #6 Lot 추적 화면 수정 7건 + 3D 스캔 대전제 (2026-10-05 KST, `version_v11`, v11.2.0)

- GitHub 이슈 #6(예약 작업 처리). 첨부 스크린샷 2장은 이 환경에서 내려받지 못해(세션 저장소 범위 밖 경로) 글 설명만으로 반영.
- ①지표를 누르면 목록 위 제목 상자(`.listtitle`, 목록마다 색)가 바뀜 ②기간별 Lot Scan 막대 툴팁 = 색 네모 · 이름 · Lot 수(한 열 오른쪽
  정렬) · 합계(`BatchCharts` `data-tipx` → `TipLayer` 가 표처럼 그림) ③주 단위 = `WW{ISO 주}` + 둘째 줄 `(MM/DD~MM/DD)`
  (`batchData.workWeek/weekRange/periodName`, 주 key 형식은 그대로라 가동률 화면 영향 없음) ④모달이 열리면 뒤 화면 스크롤 잠금
  (`html:has(dialog:modal)` · `.wm-viewer` — 프로그램 전체) ⑤`Lot 이력 상세` → `Lot History`, 세 목차를 경계선 상자 + 제목 박스로
  ⑥**3D 스캔(대전제 추가)**: S/M 에 단독 `3D`(`ABC-3D`)면 3D 스캔(`lotmodel.scan_kind`), 2D · 3D 는 묶음을 따로(재스캔 · 중복 아님),
  `step_label` 로 ' · 3D 스캔' 표시(화면 · Excel · 가동률/WPH 레시피 이름 · Lot 추적 HTML). 같은 호기 12h 묶음에도 **Recipe(s) 일치**
  조건 추가(열이 있는 Batch Report 끼리만) ⑦Batch Report 원문 창 · Lot 창에 무엇인지 설명하는 제목.
- Lot 창 시간순 번호(#n)는 이제 공정 단계 줄이 섞여도 실제 스캔 시각 순(`flat(l, R)`). 문장 요약 · Batch Report 이력도 시각 순
  ('처음 3D 스캔 → 5분 뒤 2D 스캔'), 오류 지도 · wafer 취합은 2D/3D 표를 나눔(`byKind`).
- 검토한 다른 적용처: 가동률 레시피 점유 · WPH 레시피(3D 별도 이름), Lot 목록 '3D 스캔 포함' 배지, 찾기 · 취합 그룹 이름(grpLabel),
  Excel 공정 단계 열, `lotreport.CRITERIA`(? 판정 기준에 '3D 스캔' 항목 · Recipe(s) 일치 문구).
- 검증: test_lotmodel 20(3D · Recipe 일치 5개 추가) · test_batchview 12 · `tools/check_project.py`(test_batchreport 의 tkinter 없는 1건만
  실패 — 변경 전과 동일) · `npx tsc --noEmit` · `vite build` · `tools/test_desktop_ui.mjs`(목록 제목 · WW 라벨 · 표 툴팁 · 모달 스크롤 잠금 ·
  Lot History 3상자 확인 추가) 통과. 실자료 3D Lot 으로는 확인 못 함(실자료 없음). Windows 실기 미검증.

## 최신 재개 — Batch Report 프로토타입을 실제 앱으로 (2026-10-04 KST, `version_v11`)

- 사용자 지시로 검토 중이던 프로토타입 화면을 실제 앱 `Batch Report 분석` 탭에 옮김. 상세는 CLAUDE.md
  'Batch Report 화면 실제 앱 반영' 절. 엔진 `batchview.py` + `desktop_batch.BatchViews` + IPC `batch_*`, 화면 `Batch*.tsx`.
- 개발자 기능은 설정 › 정보로 옮김(프로토타입의 화면 위 토글 대신). 남은 화면 수정은 앱에서 이어서 한다.
- 사용자 확정: 저장된 사람 선택은 PC마다 따로(로컬 Cache), 호기가 아주 많으면 호기 격자 안에서 스크롤. 사용자 지시로 v11.1.0 릴리즈
  (`docs/release_notes/v11.1.0.md`, Actions workflow_dispatch — 이 환경은 태그 push 가 403).
- 검증: `tests/test_batchview.py` 11 · 전체 Python 테스트(tkinter 없는 기존 1건만 실패) · tsc · vite build · `tools/test_desktop_ui.mjs`
  · 실자료 420개로 브라우저 전 화면 확인(스크래치, 저장소 밖). Windows 실기 미검증.
- push · 릴리즈는 사용자가 말할 때만.

## 최신 재개 — version_v11 통합 + v11.0.0 릴리즈 (2026-10-04 KST)

- `version_v11` = `version_v10`(HEAD `b8e5a98`) + `claude/camtek-aoi-review-deploy-w796ec`(HEAD `07444ad`) merge. 충돌 없음.
- 검증: `tools/check_project.py` 63개 중 test_batchreport 의 tkinter 없는 1건만 실패(기존과 동일) · test_wafermap 21 OK ·
  `npx tsc --noEmit` · `vite build` · `tools/test_desktop_ui.mjs` 통과(메모 탭 하위 탭 이동으로 테스트 수정).
- 릴리즈 노트 `docs/release_notes/v11.0.0.md`, 태그 `v11.0.0` push → Actions `Build Windows Desktop (Tauri)` 가 빌드·Release.
  Windows 실기 미검증.
- 사용자 지시: push · 릴리즈는 사용자가 말할 때만. Batch Report 프로토타입 HTML 수정은 계속 진행 중(확정 전 커밋 금지).

## 최신 재개 — 개발자 기능 켜고 끄기 안전장치 (2026-10-04 KST, `version_v10`)

- 사용자 질문 "개발자 기능이 중간에 켜지거나 꺼지면?" → 종전 프로토타입은 토글이 결과 숫자를 바꿨다(끄면 사람 선택이 사라지고 켜면
  돌아옴, '선택 저장'은 안내만). 규칙을 바꿔 프로토타입에 반영: 결과 = 추천 + 저장된 선택(토글 무관), 저장 안 한 선택은 끄기 전 확인,
  조사 중 토글 잠금, 결과마다 '선택 기준' 표시, 저장된 선택 있으면 안내 막대, 찾기·취합 결과가 직접 선택 기반인데 꺼지면 경고·다시 취합.
  `lotreport.CRITERIA` '중복 Pass · Dice 합계' 문구에 '저장한 선택만 결과에 쓰이고 꺼도 적용' 추가.
- 검증: Chromium 시나리오 8단계(미리 보기 → 끄기 확인창 → 저장하고 끄기 후 숫자 유지 → 버리고 끄기 → 조사 중 잠금 → 찾기 직접 선택 →
  끈 뒤 경고 → 다시 취합) 통과, 기존 회귀(proto2) · test_lotmodel · test_desktop_batch 통과, test_batchreport 는 tkinter 없는 1건만 실패(기존).
- 남은 결정: 저장된 선택은 지금 PC 로컬(Cache)이라 PC마다 다를 수 있다 — 공유 여부는 사용자 확인 필요.
- 이어서 사용자 요청으로 개발자 기능 옆 ? 버튼 + 설명 창(`devHelpDlg`, 켜짐/꺼짐 비교표) 추가. 안내 막대 · 끄기 확인창에서도 연결.

## 최신 재개 — Batch Report 프로토타입 3차 피드백(Batch Report.md) 반영 (2026-10-04 KST, `version_v10`)

- 찾기·취합(최신 자동·3/3 원문 보기), 가동률(용어 `Error·중복 스캔`·`재스캔 전 대기`, 호기 탭, 기간 행 → 오른쪽 상세, 24시간 시간표,
  Error 원문별 시간 = wafer마다 자기 원문 · 대기는 Error wafer 비율 분배), WPH(용어 카드, 호기별 전체 WPH, 정상 스캔 Batch Report
  WPH 분포·목록), 조사 범위 `모든 호기`·`모든 기간` 체크박스. 상세는 CLAUDE.md '화면 프로토타입' 절.
- 정상 스캔 표본 정의 변경: 25행 모두 Pass 인 Batch Report 전부(275) → **같은 Lot 을 한 번에 끝낸 것만**(233, 재스캔 묶음 제외).
- 검증: Chromium 으로 새 상호작용 전부(호기 탭·기간 행 → 상세·시간표 클릭 → 원문·WPH 분포 클릭·취합 원문·모든 호기/기간) 확인,
  JS 오류 0, 1440px·420px 가로 넘침 0, 줄바꿈된 표 칸 0. Windows 실기·빌드·배포 미수행.

## 최신 재개 — Batch Report 프로토타입 2차 피드백(Lot.md) 반영 (2026-10-04 KST, `version_v10`)

- 사용자 Lot.md 전 항목을 `tools/batch_prototype/proto_template.html`·`gen_proto.py` 에 반영(구조는 CLAUDE.md '화면 프로토타입' 절):
  큰 탭 2개(가동률 조사 및 분석 / 찾기·취합), 30호기 고정 격자 + 설정 이동 버튼, '이미 읽은 Batch Report 다시 읽지 않기'(기본 켜짐),
  '묶음' 화면 용어 삭제, Lot 추적 설명·누르는 지표 5개·Lot 단위 Scan List·Lot Scan Error 요약(Lot 단위), Lot 클릭 = 새 창
  (Lot 이력 상세 첫 탭 — 시간순 요약 그래프), 중복 Pass 선택·저장 = 개발자 기능, 줄바꿈 금지, SVG 인터랙티브 차트.
- 엔진 문구: `lotmodel.LOT_OPEN` = `Pass하지 못한 wafer 존재`, `lotreport.CRITERIA` 에서 '묶음' → '이어서 스캔'(? 버튼 공통 문구).
  `BatchReport_Lot추적.html`(lotreport) 본문 표에는 아직 '묶음'이 남아 있다 — 프로토타입 확정 후 웹 화면 구현 때 함께 정리.
- 지표 정정: 사용자가 '340개 Batch Report'로 적은 340 은 묶음(이어서 스캔한 단위) 수. 실자료 Batch Report 는 420(Lot 417 + 점검 3).
- 검증: Chromium(playwright-core) 로 지표 5개 클릭·목록 전환·원문·차트 툴팁/클릭·Error 요약 필터·Lot 창 두 탭·개발자 기능 on/off·
  가동률/WPH 차트·설정 이동·조사(캐시 끔, 30호기)·찾기·취합 확인, JS 오류 0, 1440px·420px 가로 넘침 0, 줄바꿈된 표 칸 0.
  test_lotmodel 15(실자료 포함), test_desktop_batch, test_batchreport(tkinter 없는 1건 외) 통과. Windows 실기·빌드·배포 미수행.
- 다음: 사용자 검토 → 확정분을 웹 화면(`frontend/src/main.tsx` Batch Report 탭)·엔진(캐시 끄기 옵션, 중복 선택 저장)에 구현.

## 최신 재개 — Batch Report 명칭 통일 (2026-10-04 KST, 브랜치 `version_v10`)

- 시작 HEAD `7b7d41e`. 브랜치 `claude/version-webview-branch-compare-gnax2c` 를 사용자 지시로 `version_v10` 으로 이름 변경(같은 커밋).
- 사용자 지시: Batch Report 기능의 '배치 리포트/배치 레포트/batch report' 표기를 `Batch Report` 로 통일.
  탭·진행 문구·결과 HTML/Excel 문구·WPH 문구·사용자 문서·UI 시험 스크립트 버튼 이름. 결과 파일명
  `배치리포트분석.*` → `BatchReport_분석.*`. 로컬 폴더 `배치분석/` 은 캐시 연속성 때문에 유지.
- 검증: `py_compile`, test_batchreport(17 중 tkinter 없는 환경 1건 기존 실패 — 변경 전과 동일), test_desktop_batch,
  test_wph 9/9, test_wph_html 5/5, test_wph_status, test_wph_settings, test_desktop_aoiroot, test_desktop_ipc 통과,
  `npx tsc --noEmit` 통과. 브라우저 UI 시험·Windows 실기·빌드·배포 미수행.
- 다음: Batch Report 기능 4개 분리 재설계(CLAUDE.md '명칭 통일 + 재설계 방향' 절).

## 최신 재개 — Batch Report M09 폐지 + Lot 모델 1단계 (2026-10-04 KST, `version_v10`)

- M09(품질 이상 후보) 폐지(사용자 확정): 엔진·어댑터·웹/tkinter 입력칸·HTML 설명·테스트. 구 설정의 M09·min_baseline·
  yield_drop 은 조용히 무시. 9지표.
- 신규 `param_manager/lotmodel.py` + `tests/test_lotmodel.py`(14). 사용자 제공 실자료 424개(복사본 제외 420)로도 검증
  (저장소에는 넣지 않음 — `PARA_BATCH_SAMPLE` 로 지정). 기존 Batch Report 분석 탭은 아직 lotmodel 을 쓰지 않는다.
- 검증: test_lotmodel 14 OK, test_batchreport(tkinter 없는 1건 제외 — 기존과 동일), test_desktop_batch, test_desktop_ipc,
  test_wph, test_wph_html, `npx tsc --noEmit`, `tools/check_project.py`(test_batchreport 의 tkinter 1건 외 통과).
  브라우저 UI 시험·Windows 실기·빌드·배포 미수행.
- 호기 이동 판정 조건(48h + 미해결 + 같은 공정 단계) 사용자 확정.

## 최신 재개 — Batch Report Lot 추적 HTML + ? 판정 기준 (2026-10-04 KST, `version_v10`)

- 신규 `param_manager/lotreport.py`: lotmodel → 오프라인 단일 HTML. 조사마다 `BatchReport_Lot추적.html` 생성(서비스 결과 `lots`,
  IPC artifacts `lots`). 기준 문구 `CRITERIA` 단일 출처 → HTML [? Lot 판정 기준] · 웹 '조사 시작' 옆 ? 버튼(`lot_criteria`) · tkinter.
- lotmodel: 연쇄만 있는 웨이퍼의 원인 = 같은 Batch Report 첫 오류(`trigger`/`chain_only`). 원인별 Lot 표에 '그중 연쇄'.
- HTML 버그 수정: 검색칸 blur(change)로 표가 다시 그려져 첫 행 클릭이 사라지던 문제(같은 조건이면 다시 그리지 않음).
- 검증: test_lotmodel 15, test_batchreport(tkinter 1건 외), test_desktop_batch, test_desktop_ipc, test_wph(9), test_wph_html(5),
  `tools/check_project.py`(tkinter 1건 외), `npx tsc`·`vite build`, **브라우저 UI 시험 `tools/test_desktop_ui.mjs` 전체 통과**
  (PARA_TEST_NODE_MODULES=playwright 설치 폴더, /opt/pw-browsers Chromium). 실자료 HTML 을 Chromium 으로 열어 클릭·필터·좁은 화면 확인.
  `docs/screenshots/rev1-batch.png` 갱신(? 버튼·Lot 추적 HTML). Windows 실기·빌드·배포 미수행.
- 다음: 사용자 HTML 검토 피드백 반영 → 중복 웨이퍼 사람 선택 저장(로컬 Cache) → A(찾기·취합) · B(가동률·원인) · C(WPH).

## 최신 재개 — Batch Report 피드백 1~3 반영 + 4개 기능 화면 프로토타입 (2026-10-04 KST, `version_v10`)

- 피드백: ①'회복' 같은 해석어 금지 → `한 번에 Pass / 재스캔 Pass / 중복 Pass / Pass 없음`, Lot 상태 `한 번에 완료 / 재스캔으로 완료 /
  Pass 못 한 웨이퍼 있음` ②오류는 Batch Report 원문 그대로 ③Lot 을 고르면 Lot 취합 → 웨이퍼 취합이 맨 위 ④보고서가 아니라
  **실제 프로그램에서 4개 기능이 어떻게 동작하는지** 보고 싶다 → `tools/batch_prototype/`(생성기 + 템플릿) 신규.
- 프로토타입은 실제 앱 `frontend/src/styles.css` 를 그대로 넣은 단일 HTML. 실자료 420개로 Chromium 에서 네 탭·대화창·필터·
  좁은 화면까지 눌러 보고 콘솔 오류 없음 확인. 실자료·생성 HTML 은 저장소에 넣지 않음.
- 다음: 사용자 프로토타입 피드백 → 확정된 화면을 React(`main.tsx` Batch Report 탭) + 엔진(lotmodel 기반 ②③④ 계산·선택 저장)으로 구현.

## 최신 재개 — 공유 문서 IPC 응답성 (2026-09-22 KST)

- 시작 원격 HEAD `aec6d012915c413a7999c5a001274584da12ad46`. 변경 대상 소스/문서는 원격 blob과 로컬 hash 일치 확인 후 작업. git 메타데이터 없는 복구 디렉터리이므로 AGENTS의 API fast-forward 절차 사용.
- `document_open/edit/append`를 단일 worker로 실행. IPC 입력 처리가 Excel 읽기/저장/잠금 대기에 묶이지 않으며, document_page는 메모리 조회로 유지.
- 작업 중 다른 문서/Recipe/분석 시작 거절. shutdown/EOF는 저장을 강제 중단하지 않고 worker 완료까지 대기. 별도 문서 취소/진행률은 미지원이며 블로킹 SMB 자체의 시간 제한도 별개다.
- `tests/test_desktop_document_worker.py`에서 세 작업의 계약 응답/중복 차단/종료 대기, 오류 후 재시도와 OS 오류 상세 비노출 검증.
- 검증 결과: 신규 2개 테스트(세 작업 하위 사례 포함), 전체 독립 테스트 42개 파일, 변경 Python 구문 검사 모두 통과. 브라우저/native 실행은 이번에 수행하지 않음.
- Windows/WebView2/OneDrive 실기와 운영 배포 미수행. A4의 기능 누락 및 A5/A6 잔여는 이전 목록 그대로다. 재예약하지 않음.

## 최신 재개 — 공유 문서 행 추가 (2026-09-22 KST)

- 시작 HEAD `eed56a2619edb32869713b903db52eb9380b599c`. 첨부 `(2).html`은 저장소 계획서와 끝 빈 줄 외 내용 동일.
- A4: IP/특이사항/참고자료의 기존 문서 끝에 행 추가 UI와 `document_append` 연결. 저장 성공 후 해당 페이지 이동, 취소/실패 시 입력 보존, 빈 행/과대 입력/누락 헤더 거절.
- 기존 잠금·변경 검사·임시 저장/원자 교체 재사용. 다른 셀/구 자격증명 열 보존, 새 행으로 자격증명 복제 안 함. 문자열은 수식으로 실행하지 않음. 부모 링크/junction도 차단.
- 문서 테스트 9개 통과, TypeScript/Vite 빌드 통과. 브라우저 시험 항목은 추가했으나 Chromium 다운로드 차단으로 실행 미완료. Windows/Excel/OneDrive 실기·exe 빌드·운영 배포 미수행.
- 재개 예약: 사용자 지시로 2026-09-22 06:20 Asia/Seoul, 이 대화에서 한 번. 이미 설정됨. 새 예약을 중복 생성하지 않는다.
- 다음: A4 신규 Commonality 조사/감시, 양식/Recipe 전체 흐름, A2 폴더 등록/개별 Report/일일 갱신, A5/A6 검증. 전체 완료 아님.

## 최신 재개 — Commonality 비교 UI (2026-09-21 UTC)

- `version_rev1`의 `33ec8c1`에서 이어서 저장된 Commonality 결과 비교·Excel 출력만 새 UI에 연결했다. 전체 A/B 계획 완료가 아니다.
- 최신 상세 상태는 `docs/REV1_IMPLEMENTATION.md` 맨 위를 읽는다. 신규 조사/감시와 Windows 실기는 남아 있다.
- `desktop_commonality.py`와 4개 제한 IPC 메서드, React Commonality 화면, 5개 회귀 테스트 추가. 전체 검사 41개 파일 및 프런트엔드 빌드 통과.
- 다른 브랜치·운영 배포물 변경 없음. 다음 작업자는 원격 HEAD/로컬 변경을 다시 확인하고 같은 파일 동시 수정을 피한다.

## 현재 기준
- 저장소 `kimminkuy70-coder/Para`, 이번 작업 브랜치 `version_rev1`만 사용.
- 원본 기준: version_v7.0의 `ad895aedf298637df548b3963f30bf700ed79f14`. 다른 브랜치 수정 금지.
- 협업 구성 반영 기준 커밋: `caefbff85fd8a33543db993e965edefd8472aeb6`.
- 최신 커밋은 `git log -5 --oneline` 또는 GitHub 브랜치 HEAD로 확인한다.
- 현재 소스 기본 버전: `8.0`. 빌드할 때 입력한 버전으로 다시 기록한다.
- 현재 주요 기능: 장비 파라미터 양식/취합/비교, Commonality 조사·감시,
  WPH 조사, OneDrive 기반 exe 업데이트. 상세 구현은 CLAUDE.md와 소스 참고.

## 마지막 작업 — 새 UI 실엔진 연결 (2026-09-21, Codex)

- 시작 `4b81fe8`, version_rev1만 수정. 원본 UX 브랜치 `28c805f` 보존.
- 최신 상태/다음 작업: `docs/REV1_IMPLEMENTATION.md`의 A0~A6 표를 반드시 읽는다.
- React/Tauri 고정 sidecar, 배치 UI/설정/취소/표, Recipe 가상화·색상·비고,
  공유 문서 조회/셀 편집, 시험 패키징·무결성·의존성 도구 추가.
- Python 회귀 테스트 및 TS/Vite 빌드 통과. 브라우저는 실제 Python과 합성 자료로 시험.
- native Windows check는 windres 없음/설치 권한 오류에서 차단. 실기 성공 아님.
- 전체 계획 미완료. Commonality·양식/Recipe 전체 흐름·감시·트레이 등 A4 잔여와
  A5 실제 패키징/자동 업데이트, A6 실기·배포 gate가 남아 있다.
- exe 빌드/운영 OneDrive 게시/소스 버전 변경 없음. 기존 앱을 아직 교체하지 않는다.
- 최신 재개 예약: 2026-09-22 01:10경 KST, 사용자 요청한 5시간30분 후.
  다른 세션 변경/원격 HEAD 확인 후 이어가며 새로운 반복 예약을 만들지 않는다.

## 이전 작업 — 계획 A A1 통신 기반 (2026-09-20, Codex)

- 최신 사용자 요청은 개편 계획 A 실행이다. 아래 배치 분석 당시 '개편 보류'는 과거 기록이다.
- 기존 version_rev1 `4951f44`에서 이어서 수정. 분기 원본 UX 브랜치 `28c805f`는 변경하지 않음.
- 실행 계획 `docs/Para_version_rev1_master_plan.html` (실제 첨부 (2).html),
  상세 현황 `docs/REV1_IMPLEMENTATION.md`, 계약 `docs/REV1_IPC.md`를 먼저 읽는다.
- Python 메모리 분석 stdio IPC: 제한된 명령, 단일 작업, 취소/오류/종료, 200행 분할 조회.
  장비 읽기/출력 저장/React native 연결은 아직 없음. 기존 tkinter 실행 경로는 그대로다.
- 테스트: `python tests/test_desktop_ipc.py` 9개 통과;
  `python tools/check_project.py` 실패 파일 없음(.xlsm 필요 engine 기존 제외).
- Rust 컴파일러 없음. Tauri/프런트엔드 빌드와 Windows 실기 미검증. exe/배포/버전 변경 없음.
- 다음: Rust 환경/고정 의존성 및 라이선스 → 제한 native launcher → A2 배치 화면.
  HTTP/TCP 서버 금지, 원본 읽기 전용, localdirs/OneDrive 규칙 보존.
- 재개 예약 생성 완료. 다시 예약하지 말고 최신 HEAD/작업 중 세션을 확인하여 중복 변경 방지.

## 이전 작업 — 배치 리포트 분석 확장 (2026-09-20, Codex)

- 시작: `b235ec2402888fb3356292aafe55e895f021b5e8`. 사용자가 지정한 이 브랜치만 작업.
  `version_rev1`과 대규모 UI/기반 개편은 보류. 기존 tkinter·테마·버전·배포 방식 유지.
- 사양서 `docs/배치리포트분석_사양서.html` 기반 M01~M11, 지표 선택, 로컬 증분 수집,
  HTML/SVG/Excel, 고정 dashboard, 수동/하루 1회 갱신, 백업 폴더를 구현했다.
- 변경 파일과 지표 정의/사양서 보완: `docs/BATCH_ANALYSIS_IMPLEMENTATION.md`.
  원본 파서/WPH 함수는 재사용한다. 현재 `_wph_run`은 `BatchReportMixin`에서 제공한다.
- cache 단일 JSON 원자 교체로 batch/wafer 일관성 유지. 수정시각+크기 동일 파일은 재파싱하지
  않는다. late file, 범위 변경, 원문 unknown, 백업 중복, 파싱 실패 재시도를 처리한다.
- 품질 후보 기본 최소 과거 Pass 20개/수율 중앙−5pp는 사용자 변경 가능한 검토 기준이다.
  실제 Hold/수리 원인으로 확정하지 않는다. Aborted 직접/연쇄도 추정으로 표시한다.
- 검증: `python tests/test_batchreport.py` 16개 통과. `python tools/check_project.py`
  실패 파일 없음(원본 .xlsm 의존 engine 테스트는 기존 규칙으로 제외).
- 실제 419-report 샘플은 없어 정답 재현 미검증. Windows GUI/Excel/SMB/EDR와 대규모 실제
  자료 확인 필요. exe 빌드/버전 변경/OneDrive 배포는 미수행. 소스 push는 exe 업데이트가 아니다.
- 다음 AI는 위 구현 문서를 읽고 synthetic과 실제 샘플 검증을 구분한다.

## 이전 작업 — UI 테마 벤토+미니멀(네이비+라임) (2026-09-19, Claude)

- **별도 브랜치 `claude/ux-bento-navy-lime`**(version_new에서 분기). 이 UX 작업만 담음.
  다른 AI 협업(version_new)을 방해하지 않도록 분리. 병합 시 새 PR.
- 사용자 지정: **벤토 그리드 + 미니멀리즘**, **네이비(구조)+선명한 라임(강조)**,
  **폰트=맑은 고딕**, **상단 탭바 유지**(사이드바 전환 안 함), **hairline 플랫 카드**
  (tkinter 라 둥근 모서리·그림자 없음).
- Phase A: `theme.py PALETTE`를 네이비+라임으로 교체(accent/accent_dk/accent_lt/
  on_accent 추가, 라임 위 글자는 네이비). 맑은 고딕 위계(title16/h2 12/kpi22/…).
  Primary(네이비)·Accent(라임) ttk 버튼 스타일. Phase B: 상단바 딥 네이비·내비 버튼
  네이비 틴트·저장/활성 탭=라임. Phase C: `_bento_card`/`_kpi_cell` 헬퍼, `_step_header`
  라임 액센트 바, 주요 CTA 8개 라임, WPH .html 미리보기 벤토 카드화, 특이사항/참고자료/
  장비IP 제목 헤더. Phase D: 카드 테두리 hairline 통일.
- **보존**: 값 확인 2분할 tksheet('장비 화면', dark 회색)는 그대로. 헤드리스 로직 불변.
- 세부·재발방지: `CLAUDE.md` 의 'UI 테마 — 벤토 그리드 + 미니멀' 절.
- 검증: `tools/check_project.py` 실패 없음, `py_compile` 전체 통과. **실제 화면 색·폰트·
  레이아웃은 Windows 실기 필요**(개발환경 GUI 미지원). exe 빌드·배포 미수행.

## 이전 작업 — WPH 기간 수집 + .html 결과 (2026-09-19, Claude)

- version_new만 수정. 헤드리스 우선(테스트) 후 GUI 연결. Windows 실기·빌드 미수행.
- **기간 수집**: 호기 행마다 수집 모드(‘recipe 검색어’ / ‘기간’) 선택. 기간은
  **파일명 내장 날짜**(`_YY-Mon-DD_(HH.MM.SS)_`)로 판정한다 — 원본을 열지 않고
  이름만 본다(빠름·read-only). `wph.parse_filename_datetime`/`_in_period`/`_matches`
  (검색어 AND 기간 교집합)·`list_reports`/`count_reports(start,end)`. 파일명 날짜를
  못 읽으면 기간에서 제외. GUI `_wph_period`(YYYY-MM-DD 파싱)·`_wph_search`가 모드에
  따라 start/end를 넘김. 기간 모드는 검색어로 거르지 않고 선택 목록만 조사.
- **recipe 구분 = A안(리포트 내부 Job/Setup의 Job 이름)**: `wph.job_recipe`(`/` 앞)로
  `extract_row`가 각 행에 `recipe`를 채운다. 원본은 여전히 `read_bytes`만 —
  Job 파일/`\Job\`은 접근하지 않고 이미 파싱된 텍스트에서 이름만 뽑는다(손상 없음).
- **보기 모드(레시피별/호기통째)**: 조사 시작 옆 라디오. 기본 = ‘호기 → 레시피별’.
  여러 호기면 호기로 먼저 묶고 그 안에서 recipe로 나눈다(by_recipe=True).
- **결과 엑셀은 종전과 동일**(통합 1개). 추가로 **.html 결과**: 조사 완료 후
  **자동으로** `_wph_html_dialog`(구성 화면)가 열린다. 지표 체크박스(WPH 요약·호기·
  레시피별 WPH·Wafer scan 상태·에러 ①전체/②호기별/③호기×레시피·Report 목록·
  파싱오류)로 넣을 것만 고르고 **화면 미리보기 표**(`wph_html.preview_tables`, .html과
  같은 숫자)로 확인. **결과 리포트 제목(=배치레포트 이름) 편집 가능**(기본 템플릿,
  .html 제목·파일명에 반영). [HTML 만들기] → `WPH_통합_{시각}.html`(같은 조사 폴더,
  로컬) → 완료창 **[📄 결과 열기]/[📂 폴더 열기]**.
- **에러 3단**(사용자 재요청): ①전체 ②호기별 ③호기별→레시피별 — `wph_html.compute`가
  `wph_status.classify`를 재사용해 산출(리포트당 카테고리 1회, 이슈 Report 중복 제외).
- 라벨 변경: “Wafer 상태 요약(정상/이슈/확인불가)” → **“Wafer scan 상태 요약
  (정상/error/확인불가)”**.
- 신규 헤드리스 `param_manager/wph_html.py`(파일 접근 없음, 메모리 rows/errors만 가공,
  단일 .html·외부 의존 없음). 오류 코드 **E193**(.html 준비/저장).
- 검증: `tools/check_project.py` 실패 없음. test_wph.py 9/9(기간 필터 추가),
  신규 test_wph_html.py 5/5. `py_compile` 전체 통과. Windows GUI/Excel/브라우저
  렌더·exe 빌드·OneDrive 배포는 미수행(새 빌드에서 실기 확인 필요).

## 이전 작업 — 오류 차트 분할 제거 (2026-09-16, ChatGPT/Codex)

- 시작 커밋 1b2a261d207d5cf719f57890da65a453006dd4fd, version_new만 수정.
- wph_status.py: 12개씩 분할하던 규칙 제거. 모든 유형을 지표별 단일 차트로 표시.
  Report 수/슬롯 발생 건수는 집계 단위가 달라 각각 한 차트 유지.
- 폭 34cm, 높이 max(20, 6 + 유형 수 × 1.1)cm. 실제 높이로 다음 앵커 계산.
  원문 항목명/건수/단위를 보존하며 축 글꼴은 기존 11pt 유지.
- 수평 막대에서도 openpyxl y_axis가 숫자축임을 반영: 숫자축 역방향 제거,
  카테고리만 역순, 정수 눈금 최소 1, 0 시작 및 최대값 뒤 여유 확보.
- test_wph_status.py: 1/13/25개 유형의 저장·재열기 후 2개 차트,
  전체 데이터/원문 보존, 축/눈금, 높이 및 겹치지 않는 배치 검사.
- python tools/check_project.py 통과(실패 파일 없음), WPH 상태 테스트 7개 통과.
  원본 .xlsm 샘플 의존 engine 테스트는 기존 규칙에 따라 제외.
- Windows Excel 실제 렌더링, exe 빌드·배포 미수행. 새 빌드에서 엑셀 재생성 필요.

## 이전 작업 — WPH 상태 조사 (2026-09-15, ChatGPT/Codex)

### 마지막 조사 설정만 유지

- wph_last_investigation에 실제 조사 시작 대상(호기별 검색어)을 하나의 snapshot으로 저장.
  다음 조사는 누적 병합하지 않고 완전히 교체하며 legacy wph_prefixes도 덮어쓴다.
- 폴더 경로 지정 이력은 유지하되, 폴더가 있다는 이유로 자동 체크하지 않는다.
  검색만 하거나 대상 없음/조사 취소는 마지막 조사 설정을 갱신하지 않는다.
- 구버전 설정에는 마지막 체크 목록이 없어 추정 복원하지 않는다. 새 버전에서 첫 조사
  때 선택한 설정부터 정확히 복원된다. 저장은 로컬 config에만, 조사 시작 시 한 번.
- test_wph_settings.py에서 A→B 조사 교체, 과거 검색어 제거, 빈 검색어,
  폴더 설정 보존과 잘못된 설정 방어 확인.
- python tools/check_project.py: 독립 테스트 33개 파일 통과, 실패 없음.
  원본 .xlsm이 필요한 engine 테스트 1개 제외. Windows 실기·빌드·배포 미수행.

### 축 날짜·항목명·단위 복구 (최신)

- 기준 ae2dd559b333a172971a1ef9a61e3b127755add4. version_new만 수정.
- 차트 크기는 유지하고 축 숨김 해제(delete=false), 눈금 라벨 위치(low),
  검정 11pt 축 글꼴을 명시했다. 제목/축/데이터 라벨 영역의 여백을 확대했다.
- 축 위치도 명시(시간축 하단)하고 항목명 문자열을 차트 XML 캐시에 함께 저장한다.
- 시간 그래프는 min/max와 majorUnit=(max-min)/4로 날짜·시간 눈금 약 5개.
  yyyy-mm-dd hh:mm, 5분 미만 범위는 초까지 표시. 같은 시각뿐이면 ±2분 범위.
- WPH는 호기명+WPH 단위, Scan 분포는 시간 구간+Report 수(건),
  오류 그래프는 상태 원문+발생 건수(건)를 표시. 막대 위 수치에도 단위 표기.
  항목명은 축에서 보여 중복된 긴 데이터 라벨은 만들지 않는다.
- 시간 그래프 곡선 보간은 끄고 시간순 실측 점을 연결한다.
- 검증: 저장·재열기 후 축 표시/글꼴/단위 및 5개 날짜 눈금 간격 검사.
  Windows Excel 실제 렌더·exe 빌드 및 배포는 미수행.

### 차트 가독성·시간순 추이 (최신 후속 수정)

- 기준 fb5c8a98c1d96fb9b938cdad92232767c4146fd5. version_new만 수정.
- WPH 차트 34×17cm, 오류 차트 34×20cm. 세로 배치·고정 행높이로 간격 확보.
  라벨은 숫자만 표시(showSerName/showCatName/showLegendKey=false), 글꼴 크기 명시.
  오류 항목은 12개씩 분할하여 상세 원문·발생 건수를 빠뜨리지 않는다.
- Report 원본 순서 WPH 그래프를 Batch End 오름차순 시간 추이로 교체.
  Batch 소요시간(분) 추이도 추가한다. Excel 날짜 숫자 X축으로 실제 시간 간격을 표현한다.
  파일명/파일시스템 생성시각/OneDrive 동기화 시각을 시간 기준으로 사용하지 않는다.
- Batch End 미확인 Report는 시간 추이에서만 제외하고 제외 수를 대시보드에 표시한다.
  기존 호기별 누적 WPH·시간 구간 분포에는 유효 Lot 조건을 충족하면 포함한다.
  구간 분포·오류 종류별 빈도는 시간 추이가 아니므로 기존 집계 기준을 유지한다.
- 검증: test_wph_status.py 7개 통과. 역순 파일명/시간 정렬, 누락 시각,
  WPH/Batch 값 대응, 차트 저장·재열기 후 크기/위치/라벨 옵션/X축 참조,
  오류 25종의 12개 단위 분할과 누락 없음 확인.
- Windows Excel 실제 렌더는 미수행. 새 빌드에서 WPH 조사를 다시 해야 새 양식이 생성된다.

### 실제 차트 추가 및 상태상세 기준 빈도 (후속 수정)

- 기준 1bf92e6bc7164e0e152ffc22f91ce07535cef68f, version_new만 수정.
- 기존 WPH에는 차트 데이터/수식만 있고 차트 객체가 없었음. wph_charts.py 추가:
  05_대시보드에 호기별 누적 WPH, Report별 Actual WPH, Avg Scan 시간 분포 3개.
  파일을 열면 05_대시보드를 먼저 표시한다.
- 07_상태요약 오류 차트 2개를 오른쪽 멀리(I열)에서 요약표 아래(A열)로 이동.
  데이터는 09_상태상세에 기록한 행을 기준으로 상태별 빈도와
  호기+Report 파일명 중복 제외 수를 산출한다. 상태 확인 불가는 제외한다.
  동일 Slot에 여러 상태가 있으면 상태별로 1건씩 센다. 기타 상태도 원문별 포함.
- 차트는 Excel 기본 BarChart/LineChart이며 생성 당시 숫자 셀을 참조한다.
  Raw Data/상태상세를 나중에 수동 편집해도 차트용 집계가 자동 갱신되지 않는다.
  수동 수정 결과가 필요하면 원본 기준으로 다시 조사한다. WPH 기존 수식은 유지.
- 검증: test_wph_status.py에 WPH 숫자 집계, 09 상세와 차트 데이터 일치,
  Excel 재열기 후 WPH 3개+오류 2개 차트, 위치/참조/ZIP/XML 검사 포함.
- Windows Excel 실제 렌더 및 exe 빌드·OneDrive 운영 배포는 미수행.

- version_new, 기준 9bfa37129e7271b5917f80ccc58285d30a20fcac.
- WPH 원본 파싱 시 Wafer/Slot 상태를 함께 보관해 추가 파일 읽기 없이 집계.
- 07_상태요약 / 08_Report목록 / 09_상태상세 / 10_파싱오류 시트 추가.
  전체·이슈·정상·상태확인불가·파싱오류 수, 상태별 Report/발생 수 및 파일명 제공.
- 사용자 제공 7개 유형을 분류하고 그 외 상태는 기타 상태로 원문 유지.
  하나의 Report에 여러 유형이 있으면 각각 집계하되 전체 이슈 Report는 한 번만 센다.
  상태 없는 Report는 정상으로 간주하지 않는다. 제공된 420/71은 예시이며 코드에 고정하지 않는다.
- 기본 Excel 가로 막대 차트 2개: 유형별 Report 수 / Wafer·Slot 발생 건수.
  숫자 셀을 직접 참조하며 동적배열·매크로·외부링크를 사용하지 않는다.
  상태 통계는 조사 시점 값으로, Raw Data를 손으로 바꾸면 재계산되지 않는다.
- 신규 test_wph_status.py: 집계, HTML 추출, workbook 재열기·재저장,
  차트 참조/개수, XML·ZIP 무결성, 원문 수식 해석 방지 확인.
- 검증: 일괄 실행의 32개 테스트 파일 중 새 시트 목록 기대값만 실패.
  해당 기대값 갱신 후 test_wph.py 8/8 통과. 신규 상태 테스트 3/3 통과,
  나머지 31개 파일은 일괄 실행에서 통과. 원본 샘플 의존 engine 1개 제외.
- Windows Excel 실제 렌더·실기 및 exe 빌드/OneDrive 운영 배포는 미수행.

## 이전 작업 — 색상 선택

- 추가 요청: 실제 색상 선택창/미리보기 구현. 값 확인 색상 칸 더블클릭,
  양식 편집기 하단 ‘색상 보고 선택…’으로 단일/다중 항목 변경.
  코드 입력 미리보기·자동색·취소 지원, 코드 셀에도 실제 색 표시.
  창 미리보기는 공유 파일을 쓰지 않으며 저장 시점은 기존과 동일하다.
  기준 커밋 997ff4f5b05f86f00107e0d816330f44e5abc663. Windows 실기 미수행.

- 기준 a323f581f936aea7c22b7ac6d22397c2e20cc802, version_new만 수정.
- 변환계수 확인 창 세로 스크롤/휠, 파라미터 왼쪽 장비풍 회색 테마·분류 색상 칸,
  오른쪽 비교 구조 유지/톤 통일, 스크롤을 반영한 비고 인라인 편집 좌표 수정.
- 장비화면이름.xlsx 마지막 색상코드 열 추가. 양식 편집기는 코드 텍스트 열,
  값 확인은 색상 칸 더블클릭. 사용자 확정 시만 저장, 잠금/변경/충돌 검사 적용.
- 변경 파일: equip_app.py, namestore.py, tests/test_parameter_colors.py.
- 검증 및 구버전 쓰기 호환 한계: docs/UX_PARAMETER_COLORS.md. 전체 독립 테스트
  31개 파일 통과, 샘플 의존 engine 1개 제외. 신규 색상 테스트 최종 7개 통과.
- Windows GUI·DPI·실제 성능·exe 빌드·OneDrive 배포 미수행.

## 이전 작업 — 2026-09-13 검토

- `version_new` 분리 후 주요 기능·UX 작업 처리·성능·환경·보안·업데이트 경로 검토.
- 전체 목록 및 미완료/Windows 확인 사항: `docs/REVIEW_VERSION_NEW.md`.
- WPH 초과행 수식·중복/빈 선택, Commonality 대기 폴더 재검사, GUI 메인 스레드
  결과 전달·진행창, 계수 조회 캐시, 로컬 설정 저장, 업데이트 입력·백업·인코딩 수정.
- OneDrive 주의사항 재확인 후 공유 JSON 임시파일 추가안 철회. 로그 fallback도
  공유 폴더로 향하지 않도록 수정. 보안/접속 간격/읽기 전용/추가 의존성 금지 유지.
- 검증: `python tools/check_project.py` — 30개 독립 테스트 파일 성공, 실패 없음.
  신규 `test_review_regressions.py` 10개 포함. 원본 .xlsm 의존 test_engine.py 1개 제외.
  34개 패키지 Python 파일 AST 구문 검사 및 `git diff --check` 확인.
- Windows GUI/Excel 계산/장비망/OneDrive 다중 PC/실제 exe 빌드·배포 미수행.
- 실제 설치본 8.0에서 업데이트하려면 더 높은 입력 버전(예: 8.1)으로 빌드해야 함.
  이번 소스 기본 버전은 8.0 유지. 동일 버전 다른 바이너리 게시를 이제 거부한다.
- 테스트 로그는 게시 제외 및 원상 복원. 실제 회사 파일/OneDrive 게시물 접근 없음.

## 이전 작업 — 빌드 이름과 버전
- 빌드 이름/버전 수정: `build.bat` 진입점 추가, 입력 필수 버전을 파일명·PE 속성·
  내부 버전에 반영. 이름은 Camtek_AOI_manager, 예: Camtek_AOI_manager_v8.0.exe.
- updater 게시 이름 변경 및 구 이름 인식 유지, GUI 제목/게시 안내 변경.
- 검증: test_build_version.py 통과(8.0/8.1.2/9.0 및 구 이름 호환),
  test_updater.py 28/28 통과, git diff --check 통과.
- Windows exe 실제 빌드·배포는 미수행. 다음 단계는 Windows에서 빌드/실행 확인.

## 이전 작업 — 공통 협업 구성
- 목적: Claude와 ChatGPT가 순차 교대로 최신 소스와 결정 사항을 이어받도록 구성.
- 추가: AGENTS.md(공통 규칙), tools/ai_sync.py(시작/게시),
  tools/check_project.py(기존 테스트 일괄 실행), docs/AI_COLLABORATION.md(사용 절차).
- 수정: CLAUDE.md 첫머리의 오래된 기준 브랜치 및 공통 지침 연결, README 진입 링크.
- Claude가 2026-09-10 반영한 WPH 검색·선택·진행 표시 변경까지 포함한 최신 커밋을
  기준으로 협업 구성을 다시 적용했다.
- 프로그램 기능·실행파일 버전 변경 없음.
- 검증: `python tools/check_project.py` — 독립 테스트 파일 28개 통과,
  원본 업로드 .xlsm이 필요한 test_engine.py 1개 제외(전체 무결성 통과 의미 아님).
  동기화 ahead/behind 6개 시나리오 검증 통과, 미커밋 상태 start 거부 확인.
  `git diff --check` 통과. 테스트가 작성한 추적 로그는 원래 내용으로 복원.
- 빌드/배포: 수행하지 않음. Windows GUI·Excel·사내 장비망 실기 확인 미수행.

## 다음 세션
1. start 동기화 후 이 파일과 AGENTS.md, CLAUDE.md 및 최근 diff 확인.
2. REVIEW_VERSION_NEW.md의 Windows 실기·배포 항목과 남은 개선 과제를 확인한다.
3. 작업 결과와 미완료 항목을 이 파일에 기록하고 코드와 함께 commit/push.
4. 앱 배포 요청 시 Windows에서 빌드·실기 검증 후 기존 OneDrive 배포 경로 이용.

## 알려진 한계
- Claude 내부 대화/미게시 로컬 변경은 여기에서 접근할 수 없다. 필요한 결정은 문서에 남긴다.
- README 본문의 일부는 초기 버전 설명이다. 최신 설계는 CLAUDE.md와 코드로 확인한다.
- tests/test_engine.py는 Claude 업로드 경로의 원본 .xlsm에 의존한다.
- 현재 환경은 Windows 빌드 PC/OneDrive 게시 폴더에 연결되어 있지 않다.

## 원격 분기 후 추가 변경 확인 (2026-09-21)

게시 직전 원본 UX 브랜치는 다른 작업으로 `6bb50953a24323f33451c41383c2219c674021c0`까지
진행된 것을 확인했다(Claude 배치 Lot 집계·자정 보정·M07 통합·HTML 드릴다운 등).
이번 작업은 해당 브랜치를 수정하거나 덮어쓰지 않았다. version_rev1은 기존 분기 기준
28c805f의 분석 엔진을 유지한다. 원본의 새 계산/표 schema와 새 UI 연결을 별도 비교·통합·
재검증해야 하며 자동으로 최신 원본과 동등하다고 간주하지 않는다. 다음 세션 우선 비교 대상이다.
