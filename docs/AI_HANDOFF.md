# AI 공통 인수인계

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
