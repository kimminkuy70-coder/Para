# version_rev1 대규모 개편 구현 기록

> **브랜치 이동(2026-09-21)**: 이 개편 작업은 이제 **`version_webview`** 브랜치에서 이어진다.
> `version_rev1`을 베이스로 `claude/ux-bento-navy-lime`을 병합해 두 브랜치의 완성분을 하나로 합쳤다.
> 계획서: `docs/Para_version_rev1_master_plan.html`. 아래 A0~A6 표는 그대로 유효하다.

## 재개 체크포인트 — 웹 UI 스텝바이스텝 + 토스트 알림 (2026-09-22)

- **요청**: 화면이 "보고서처럼 주르륵" 나열돼 보기 힘듦 → 각 기능을 **단계(스텝)**로,
  오류·알림은 **새 메시지창(팝업)**으로.
- **공용 UI**(`frontend/src/ui.tsx`): `Toaster`+`notify(msg,kind)`+`fail(e)`(우측 상단
  토스트, error 6.5s/그외 3.4s, ×닫기, 접근성 role), `Stepper`(단계 표시·완료 단계 클릭
  이동)+`StepNav`(이전/다음·N/M·마지막 CTA). styles.css 에 토스트/스텝퍼 CSS 추가.
- **Settings 는 스텝이 아니라 하위 탭**(사용자 지정): 설정창 안에서 `저장폴더 / 배치 Report
  폴더 / Scanresult 루트` **서브탭**(`.subtabs`)으로 전환. 스텝바이스텝은 **나머지 기능만**.
- **스텝 전환**: Form(원본 선택→항목 편집→확정), History(파일 선택→결과),
  Commonality(신규조사 계획→결과 / 결과비교 파일선택→비교표), 배치(조사 대상→분석 설정→
  실행·결과). 각 화면 한 번에 한 단계만 표시.
- **오류 팝업 통일**: 전 화면 인라인 `.alert`/`.dialog-error` 제거. main/Recipe/Documents 는
  기존 `setError`→토스트 브리지(`useEffect(error→notify)`), 나머지는 `fail(e)`/`notify` 직접.
- **부수 수정**: 배치 '전체 선택/해제' 판정이 `metrics.length===11`(구 11지표)로 굳어 있던 것을
  `===metrics.length`(현 10)로 교정.
- **검증**: `tsc` 0건 · `npm run build` 통과 · 렌더 스크린샷으로 스텝퍼/토스트 동작 확인.
  (Python 무변경 — 이번은 프런트 UX 전환.)

## 재개 체크포인트 — 저장폴더/폴더 등록 설정(웹 자립) (2026-09-22)

- **문제**: 웹 UI 가 config 의 save_dir 을 **읽기만** 하고 지정하는 UI 가 없어, 기존 tkinter
  로 저장폴더를 안 잡아두면 전 화면이 빈다(=사용자의 "파일 불러오기부터 안 됨"). 또한
  참고: 패키지 엔진(desktop_engine_entry)은 SingleInstance 를 써서 **tkinter 가 켜져 있으면
  엔진이 안 뜬다**(기존 프로그램을 끄면 정상 — 사용자 확인).
- **추가(네이티브 폴더 선택)**: Rust `pick_folder` 커맨드(rfd) — OS 폴더 선택창을 열어
  사용자가 고른 절대경로만 반환(탐색기로 고르는 것과 같은 신뢰 모델, 임의 경로 주입 불가).
  `lib.rs` invoke_handler 에 등록. `cargo check` 통과.
- **추가(설정 저장)**: `param_manager/desktop_config.py`(`DesktopConfig`) + IPC 동기
  `config_state`/`config_set_save_dir`(+ 초기 파일 `장비 IP/참고자료/특이사항.xlsx` 자동 생성,
  tkinter 첫 실행과 동일)/`config_set_report_path`/`config_set_scanresult_root`/`config_remove`.
  경로 검증(절대·존재·symlink 거부), `atomicfile.write_json` 로 공유 config 원자 기록,
  무관 키 보존.
- **프런트엔드**: `frontend/src/Settings.tsx` + **'설정' 탭(맨 앞·기본 진입)**. 저장폴더 지정
  (찾기/직접입력/저장), 호기별 Report 폴더·Scanresult 루트 등록/삭제. `desktop.ts pickFolder`.
- **검증**: `tests/test_desktop_config.py`(5)·IPC·`config_state` 왕복 통과. `tsc`/`build` 통과.
  렌더 스크린샷으로 설정 탭 확인. Windows 실기(폴더창 실제 표시)는 사용자 확인 필요.

## 재개 체크포인트 — GitHub Actions 윈도우 빌드(개인 PC 툴체인 불필요) (2026-09-22)

- **배경**: 사용자 PC에 Python 만 있고 Rust·Node 는 회사 승인이 필요. pywebview 로 host 를
  바꾸면 Tauri 의 Rust 보안 경계·무서버 원칙이 깨져 **계획 이탈**이므로 채택 안 함. 대신
  **빌드만 GitHub 윈도우 러너에서** 하고 완성 폴더를 배포(=REV1_PACKAGING 의 포터블 폴더).
- **추가**: `.github/workflows/build-desktop.yml` — windows-latest 에서 Python/Node/Rust(MSVC)
  준비 → `set_version.py` → PyInstaller onedir 사이드카(`Camtek_AOI_engine`) → `sidecar/` 로
  스테이징 → `npm ci` → `npm run tauri -- build --no-bundle` → **exe + sidecar 폴더**를
  artifact 로 업로드. 트리거는 `workflow_dispatch`(버전 입력) + 태그 `v*.*.*` push.
- **사용자 절차**: Actions 탭 → Run workflow(브랜치 version_webview, 버전) 또는 `git tag
  v8.1.0 && git push origin v8.1.0` → Artifacts 다운로드 → 폴더 통째로 실행(sidecar 옆에 유지).
  개인 PC 설치 0(WebView2만). `docs/WEB_UI_사용법.md` 2절에 정리.
- **검증**: 워크플로 YAML 파싱 OK(15 steps). 각 단계는 `tools/build_desktop.py`(검증된 로컬
  빌드)와 동일한 명령·경로를 온라인(캐시 없는 CI)용으로 옮긴 것. 실제 러너 빌드는 사용자가
  실행해 확인(윈도우 러너 필요). native `cargo check`·프런트 build 는 이미 통과.

## 재개 체크포인트 — 웹 UI 실행 가능화 + native 배선 버그 수정 (2026-09-21)

- **치명 버그 수정(재발 방지)**: `frontend/src-tauri/src/desktop.rs`의 `desktop_send`
  METHODS 배열이 **19개로 고정**돼 있어, 이후 추가한 `batch_reports`/`form_*`/`cmsurvey_*`/
  `history_*` 가 **native 층에서 전부 차단**됐다(=웹에서 새 기능이 안 됨). 이 이중 목록이
  드리프트의 원인이라, native 는 **봉투 형태 + method 토큰(소문자/밑줄) 검사만** 하고 정확한
  허용 집합은 **신뢰 엔진(Python `desktop_ipc.METHODS`)**이 강제하도록 위임했다.
- **개발 실행 가능화**: native 는 원래 **패키징된 고정 sidecar exe만** 실행해 `tauri dev`
  에서 백엔드가 없었다(=데이터 안 뜸). `engine_command`에 **디버그 전용 폴백**을 추가 —
  sidecar 가 없으면 저장소에서 `python -m param_manager.desktop_ipc` 를 실행한다
  (`#[cfg(debug_assertions)]`, 릴리스에는 컴파일되지 않음). 이제 **Python+Node+Rust 만으로
  `npm run tauri dev`** 가 실동작(PyInstaller 불필요).
- **아이콘 누락 수정**: `tauri::generate_context!` 가 `icons/icon.png` 를 요구해 빌드가
  실패했다. stdlib 생성기(`tools/make_icon.py`)로 `frontend/src-tauri/icons/`(32/128/256/512
  png + multi-size ico) 생성, `tauri.conf.json bundle.icon` 을 그 세트로 교체.
- **실행 도우미/문서**: 루트 `run_web_dev.bat`(준비물 점검→npm install→build→`tauri dev`,
  전부 ASCII/cp949 안전), 사용법 `docs/WEB_UI_사용법.md`.
- **검증(이 환경)**: GTK/webkit 개발 라이브러리 설치 후 **`cargo check` 통과(exit 0)** —
  native Rust 가 실제로 컴파일됨. `python -m param_manager.desktop_ipc` 프로토콜 왕복 정상
  (tkinter 없이 동작). 프런트 `tsc`/`build` 통과. **실제 창 실행·실장비는 Windows 필요**.

## 재개 체크포인트 — 웹 테마 M8 슬레이트/에메랄드 (2026-09-21)

- **범위**: 사용자 확정 디자인 컨셉(para_demo.html M8)을 웹 UI(`frontend/src/styles.css`)에
  이식. 팔레트를 **슬레이트 `#37474f` + 에메랄드 `#10b981`** 로 교체하고, Apple 계열 요소를
  더했다: 스프링/ease 트랜지션, 부드러운 2단 그림자, 다이얼로그 sheet 슬라이드업 +
  backdrop blur, `prefers-reduced-motion` 존중.
- **방식**: :root 토큰(--navy/--lime 등 **이름 유지**)만 M8 값으로 바꿔 전 화면 자동 리컬러 +
  강조 스팟(브랜드 마크·활성 탭·선택 타일·primary 버튼·진행바)을 에메랄드로. 값 확인 2분할
  장비뷰(어두운 회색)는 CLAUDE.md 지침대로 **그대로 보존**.
- **검증**: `tsc` 0건·`npm run build` 통과. 빌드본을 로컬 서버+Chromium 으로 렌더 스크린샷
  확인(슬레이트 상단바·에메랄드 강조·lot KPI·10지표·양식 만들기/이력 확인 탭 정상).

## 재개 체크포인트 — A2 배치 개별 Report 선택(웹) (2026-09-21)

- **범위**: 배치 화면에서 조사에 넣을 **개별 batch report 를 고른다**([더보기] = tkinter 와 동일).
  호기별 [📋 리포트 선택…] → 파일 이름 목록(read-only)에서 체크 → 그 목록만 조사.
- **백엔드**: `desktop_batch.reports`(그 호기 폴더 이름 목록, `wph.list_reports`), `prepare`가
  타깃별 `names` 를 받는다(collect 가 이름을 재검증). IPC 동기 `batch_reports`.
- **프런트엔드**: `main.tsx` 호기 카드에 리포트 선택 dialog + '선택 N개/전체' 표시. 선택분만
  investigate `targets[].names` 로 전달(없으면 전체).
- **검증**: `test_desktop_batch.py`(리스트+선택 왕복) 통과 · `tsc`/`build` 통과.
- **남음(A2)**: 새 호기 Report 폴더 등록·자동 일일 갱신 UI 는 네이티브 경로 선택/스케줄러가
  필요해 별개(Windows native) — 지금은 config 에 이미 등록된 호기만 대상.

## 재개 체크포인트 — A4 이력 확인(웹) (2026-09-21)

- **범위**: 계획 A A4 'Recipe 값 업데이트·이력' 중 **이력 확인**을 웹에 붙였다. 저장폴더의
  '파라미터 값 취합' 파일 2개를 골라 `history.diff_files` 로 **값이 달라진 셀만** 비교
  (값변경/추가/삭제·종류·검색 필터·페이지). 전 과정 로컬·읽기 전용.
- **백엔드**: `param_manager/desktop_history.py`(`DesktopHistory.files/diff/page`).
  opaque id·file_stamp 변경 검사·save_dir 경로 경계. IPC 동기 `history_files/diff/page`.
- **프런트엔드**: `frontend/src/History.tsx` + 네비 '이력 확인'.
- **검증**: `tests/test_desktop_history.py`(5) 통과. `tsc` 0건·`npm run build` 통과.
- **남음**: 값 업데이트(장비 SMB 수집→재취합)는 장비 접속이 필요해 별개 증분. 변경내역
  Excel 저장(`history.write_diff_excel`) 웹 연결은 후속.

## 재개 체크포인트 — A4 신규 Commonality 조사 계획 프리플라이트(웹) (2026-09-21)

- **범위**: 지금까지 웹은 저장된 결과 비교/내보내기만 있었다. 여기서 **신규 조사의 첫
  단계 = 계획 프리플라이트**를 붙였다. 조사 계획을 **데이터 행**(디바이스/공정/S·M/호기/
  fail)으로 올리면, 그 호기의 **설정된 Scanresult 루트**(config `commonality_roots`)에서
  실제 Lot 폴더 실재/변형/슬롯/Scan일자/사유를 해석해 발견·없음을 보고한다(원본 read-only).
- **백엔드**: `param_manager/desktop_cmsurvey.py`(`DesktopCmSurvey.config/preflight`).
  `commonality.filter_plan_for_machine`+`scanresult_roots`+`resolve_plan` 재사용. UI 는
  경로를 넘기지 않는다(루트는 설정에서). IPC 동기 `cmsurvey_config`·`cmsurvey_preflight`.
- **프런트엔드**: `Commonality.tsx` 최상단에 '신규 조사 계획 확인' 패널(호기 선택 +
  편집 가능한 계획 표 + 발견/없음 결과표). `SurveyPreflight` 하위 컴포넌트.
- **검증**: `tests/test_desktop_cmsurvey.py`(6) 통과. `tsc` 0건·`npm run build` 통과.
- **남음(다음 증분)**: 안전복사→값 조사→결과 누적(로컬 commonality 레이아웃에 `조사_*.xlsx`
  → 기존 비교 뷰어가 자동 인식), 디바이스/다중레시피 분리, 자동 감시(cmwatcher) 웹 연결.

## 재개 체크포인트 — A4 양식 만들기(웹) 1차 (2026-09-21)

- **범위**: 저장폴더에 이미 있는 원본(초안)을 웹에서 열어 **항목 사용(Y/N)·표시이름·
  변환(RAW/LINEAR/AREA)** 을 편집하고 **확정 양식 + 편집용 원본**을 새 회차로 저장한다.
  장비/SMB 신규 수집은 별개 후속 — 여기서는 원본이 이미 있는 경우라 전 과정 오프라인·테스트 가능.
- **백엔드**: `param_manager/desktop_form.py`(`DesktopForm`: catalog/open/page/edit/confirm).
  `formbuilder.initial_to_pivot` → `editor_model.build_entries` 로 grid, 확정은 tested
  `editor_model.build_records` → `extract_io.write_snapshot` 재사용. 계수는 coefstore
  읽기전용 → 원본 라벨의 계수 → `ini_parser.DEFAULT_SCALE` 순 폴백(파일 미수정).
  경로 경계는 save_dir 하위로 제한, snapshot 스테일 검사, 확정은 전역 잠금 `양식_{레시피}`.
- **IPC**: `form_catalog/open/page/edit` 동기, `form_confirm` 은 worker(파일 쓰기+잠금).
  `desktop_ipc.METHODS`/allowed/dispatch/`form_work` 추가.
- **프런트엔드**: `frontend/src/Form.tsx` + 네비게이션 '양식 만들기'. 원본 선택 → grid 편집
  (체크·이름 dialog·변환 select) → 호기 입력 후 확정 → 산출 경로 표시. styles.css 보강.
- **검증**: `tests/test_desktop_form.py`(5) + `test_desktop_ipc.py` form 왕복 통과.
  `tools/check_project.py` 실패=`test_batchreport.py`(tkinter)뿐. 프런트 `tsc` 0건·
  `npm run build`(36 모듈) 통과. Windows native/실기 미검증.
- **남음**: 장비/로컬 신규 수집(양식 새로 만들기), 계수 입력 UI, 다중 레시피, 레시피 삭제.

## 재개 체크포인트 — webview 통합 (계획 B 최신 배치엔진 반영, 2026-09-21)

- **목적**: 계획서대로 `version_rev1`(계획 A 골격)과 `claude/ux-bento-navy-lime`(계획 B
  완성분 + 최신 배치엔진·theme·wph_html·HTML 뷰·net use 제거)을 `version_webview`로 합쳐
  계획 A를 최종 완성하기 위한 통합 기준선을 만들었다.
- **병합**: 분기점 `28c805f`. rev1은 분기 후 배치 파일을 손대지 않아 lot 기준 재정의(10지표,
  M07 폐지, summary 키 재명명)가 깨끗이 들어왔다. 충돌은 `CLAUDE.md` 하나뿐 — 양쪽 최신
  섹션을 모두 보존해 해결.
- **정합 작업(핵심)**: 새 엔진의 `compute`/`build_html`/`write_excel` 시그니처는 rev1의
  `batchreport_service.py`가 부르던 것과 일치해 어댑터는 그대로 동작. 바뀐 것은 **summary 키**
  뿐 → `desktop_batch` 테스트 2곳·`batchreport_ui` 목 데이터를 `Batch(리포트) 수`/`Lot 수`로,
  프런트엔드(`desktop.ts`·`main.tsx`)의 **지표 목록에서 M07 제거(11→10)**·라벨을 lot 기준으로,
  **KPI를 lot 기준**(전체 Report·분석 Lot·이슈 Lot)으로 교체.
- **검증**: `python tools/check_project.py` 실패 파일은 `test_batchreport.py`(tkinter 미설치
  GUI 테스트)뿐 — 나머지 전부 통과. `desktop_*` 테스트 통과. 프런트엔드 `tsc --noEmit` 0건,
  `npm run build`(tsc && vite build) 통과(35 모듈). Windows native/실기·배포는 미검증.
- **남은 계획 A**: A2 새 호기 폴더 등록·개별 Report 선택·일일 갱신 UI, A4 양식 만들기·신규
  Commonality 조사/감시·트레이·Recipe 값 업데이트/이력, A5 실제 빌드·서명·SBOM, A6 실기·배포.

## 재개 체크포인트 — 문서 작업 응답성 (2026-09-22 KST)

- 시작 `aec6d01`. A 구조/성능 요구사항에 맞춰 문서 열기·셀 저장·행 추가의 파일 I/O를 IPC 입력 스레드에서 분리했다. React 기존 accepted/completed 처리와 호환되며 계약 필드 변경 없음.
- 단일 worker와 중복 작업 차단, 종료 시 완료 대기를 재사용. 문서 저장 중 강제 취소/종료 없음. 저장 실패 후 busy 해제 및 재시도 가능.
- 신규 worker 시험은 open/edit/append 세 경로에서 계약 응답, 다른 편집·분석 차단, 종료 대기와 오류 경로를 검증한다. Windows/OneDrive 실기나 성능 실측의 대체가 아니다.
- 검증: `python tests/test_desktop_document_worker.py` 2개(3작업 하위 사례 포함) 통과, `python tools/check_project.py` 42개 파일 실패 없음, 변경 Python 구문 검사 통과. 이번 변경은 프런트엔드 소스 불변; 브라우저/native 실기 재실행 없음.
- 기능 개편 전체 완료 아님. 신규 Commonality 조사/감시, 양식/Recipe 전체 흐름, A2 잔여, A5/A6 검증 계속 필요. 운영 배포 없음.

## 재개 체크포인트 — 공유 문서 행 추가 (2026-09-22 KST)

- 시작 `eed56a2`. 사용자 재첨부 계획서는 기존 문서와 끝 빈 줄 외 동일; version_rev1만 이어서 변경.
- A4 기존 IP/특이사항/참고자료 행 추가 폼, 입력 검증, 성공 후 마지막 페이지 이동. 문서가 없을 때 신규 파일 생성과 열 추가/삭제는 아직 미지원.
- `desktop_documents`의 기존 셀 편집 저장 경로를 공통화하여 행 추가도 잠금·수정 감지·임시 파일 교체를 적용. 누락 헤더/빈 행/과대 입력/다른 사용자 잠금/파일 변경/저장 실패를 검사.
- 문서 테스트 9개 통과, 프런트엔드 빌드 통과. 브라우저 자동화에 행 추가 검사를 작성했지만 현재 Chromium 다운로드 차단으로 미실행. Windows/SMB/OneDrive 실기·빌드·배포 없음.
- 전체 `python tools/check_project.py` 41개 파일 실패 없음. 마지막 추가한 저장 실패/참고자료 경계 테스트 포함 문서 9개를 별도로 재실행해 통과했다.
- 문서 작업은 기존처럼 동기 IPC 처리이며 대형 공유 문서 저장 시간 실측/worker 전환은 남음. 전체 A4~A6 완료가 아니다.

## 재개 체크포인트 — Commonality 저장 결과 비교 (2026-09-21 UTC)

- 시작 원격 HEAD `33ec8c18b498b408e672c70aa9a2a6a158cd4c3c`. 이전 임시 작업 공간은 없어 원격 소스 기준으로 복구·재구현했다. 사용자에게 소스 복구 작업을 요구하지 않는다.
- 기존 수동/감시 결과 목록, 최대 100개 결과 비교, 100행·12파라미터 페이지, 값 차이 필터/검색, Fail/낮은 매칭/최빈값 이탈 표시, 로컬 Excel 내보내기 연결.
- UI 임의 경로 금지, opaque ID와 파일 변경 검사, 경로 순회 전 symlink/junction 검사, 고정 로컬 출력+임시 파일 교체. 문자열을 Excel 수식으로 해석하지 않도록 저장.
- 비교/내보내기는 worker 실행, 다른 조사와 동시 실행 차단 및 종료 대기. 이 두 작업의 별도 취소/진행률은 아직 미구현이다.
- `python tools/check_project.py`: 41개 테스트 파일 실패 없음. Commonality 신규 5개 테스트 통과. `npm ci` 및 `npm --prefix frontend run build` 통과.
- 브라우저 통합 테스트는 Commonality fixture/선택/페이지/출력 검사를 추가했지만 이번 환경에서는 실행 미완료: Chromium 실행 파일 없음, 설치 CDN 응답 HTTP 502. 기존 환경의 과거 성공과 이번 실행을 구분한다. Windows/WebView2 실기를 대체하지 않는다.
- A4 전체 완료가 아니다: 신규 Commonality 조사·감시, 양식 생성/편집, Recipe 업데이트/이력, 문서 행 추가 등 남음. A5/A6 Windows 네이티브 빌드·실기·배포 미수행. 전체 개편 완료나 운영 배포로 해석하지 않는다.
- 원본 UX 브랜치의 후속 변경은 자동 병합하지 않았다. 최신 원본과 지표/기능 차이는 별도 검토해야 한다.

## 기준
- 분기 원본: `claude/ux-bento-navy-lime`
- 분기 SHA: `28c805f0971c47c5edac0cadbfe225a0eb27da59`
- 계획 B는 원본 브랜치에서 위 SHA로 구현/검증됨: M01~M11, 로컬 증분 cache, 오프라인 HTML/SVG/Excel, 일일 tkinter dashboard.
- 원본 브랜치는 이후 이 개편 작업에서 수정하지 않는다.

## 계획 A 현재 상태 (2026-09-21)

| 단계 | 구현 상태 | 남은 gate |
|---|---|---|
| A0 분기 | 완료, version_rev1만 변경 | 원본 브랜치 유지 |
| A1 통신 | 고정 native sidecar·채널·종료 대기·제한 IPC 연결 | Windows 컴파일/실행/종료 실기 |
| A2 배치 화면 | 11지표·호기/검색/기간·진행/취소·200행 표·5날짜 눈금·기존 출력 엔진 | 새 호기 폴더 등록, 개별 Report 선택, 자동 일일 갱신 UI, 실제 자료/SMB |
| A3 비교표 | 100행·12비교열 가상화, 장비 톤 왼쪽·다중호기 오른쪽, 색상/비고/복사 | 대량 실자료·DPI/IME/클립보드 실기, 전체 Recipe 작업 동등성 |
| A4 전체 UI | 장비 IP·특이사항·참고자료 기존 문서 조회/셀 수정/행 추가, Commonality 저장 결과 비교/내보내기 | Commonality 신규 조사·감시, 양식 생성/편집, Recipe 업데이트/이력, 감시·트레이, 문서 생성/열 편집 등 |
| A5 패키징 | Windows 시험 빌드 스크립트·전체 폴더 manifest/무결성 시험·의존성 목록 도구 | 실제 빌드, 라이선스 누락 해소·최종 SBOM·서명·전체 구성 자동 업데이트/복구 |
| A6 운영 | 미완료 | 회사 Windows/419 Report/SMB/OneDrive/Excel 검증 및 별도 배포 판단 |

**전체 계획 완료가 아니다. 새 UI가 기존 앱을 완전히 대체하는 배포본이 아니다.**
기존 tkinter 엔진/GUI/배포 코드는 보존했고 소스 버전 8.0을 올리지 않았다.

## 이번 구현과 검증

- 시작 HEAD: `4b81fe841b09c63db425444d404f7123598dc00c`.
- React 정적 번들, Tauri 제한 stdio launcher, Python 도메인 어댑터 3개.
- 배치 조건: 기존 설정 최초 읽기 + 새 UI의 마지막 실행 조건 한 벌만 로컬 Cache에 저장.
  구 앱으로의 조건 역동기화는 미구현이다. 소스 폴더·공유 파일 일괄 변환 없음.
- `python tools/check_project.py`: 실패 파일 없음. 원본 .xlsm 의존 engine 기존 제외.
- Python 신규: batch 6, recipe 5, documents 4, bundle 4; 기존 IPC 9 통과.
- `npm run build`: TypeScript·Vite 정적 빌드 통과. npm audit 당시 0건.
- 브라우저↔실제 Python: 합성 Report 205개, 페이지200/5행, 날짜5눈금,
  원문 script 이스케이프, 4 viewport, Recipe 2,000행/20호기에서 DOM100행/12비교열,
  색상 저장/스크롤 시험. native IPC를 대체한 시험이며 실제 Tauri 실행 증거가 아니다.
- 화면 캡처: `screenshots/rev1-batch.png`, `screenshots/rev1-recipe.png` (합성 데이터).
- Rust 1.98.1 설치 후 Windows GNU check 시도: 의존성 컴파일 후 windres 부재로 중단.
  apt 설치도 환경 권한 오류. 정책 변경/권한 우회하지 않음. native 빌드 성공 아님.
- 패키징/라이선스/미검증 상세: `REV1_PACKAGING.md`; IPC: `REV1_IPC.md`.

## 다음 작업 순서

1. Windows 개발 환경에서 native 빌드·sidecar 리소스·종료/중복 실행을 먼저 검증.
2. A4 기존 기능 목록을 일대일로 대조하면서 Commonality·양식/Recipe·감시/트레이 연결.
3. A2 폴더 등록/Report 선택/일일 갱신, A3 실자료 성능·DPI 및 문서 편집 동등성.
4. A5 의존성·라이선스·전체 구성 업데이트/복구 시험 후 A6 결과 제출. 운영 배포 별도.
5. 사용자 새 요청에 따라 5시간30분 후 재개 예약 생성: 한국시간 2026-09-22 01:10경.
   최신 원격/작업 중 세션을 확인하고 중복 작업·재예약하지 않는다.

## 불변 경계

version_rev1만 publish. 원본 장비 읽기 전용, 기존 SMB 인증, 런타임 인터넷 및
HTTP/TCP 서버 금지, 로컬 결과/공유 명시 편집 경계 유지. 강제 push·운영 배포 없음.

## 이번 체크포인트 (2026-09-20)

- 시작 HEAD: `4951f44a97f0d16c9e995e7156bc609198a304eb`. 이미 존재한 version_rev1 작업을
  보존했다. 원본과의 merge-base가 `28c805f`임을 확인했다. 재분기/덮어쓰기하지 않았다.
- 첨부 실제 이름: `Para_version_rev1_master_plan(2).html` (사용자 메시지에는 (1)).
  본문을 `docs/Para_version_rev1_master_plan.html`에 보존했다. 계획의 과거 '미착수' 표시는
  이 구현 기록 및 코드/테스트와 함께 해석한다.
- 추가: `param_manager/desktop_ipc.py`, `tests/test_desktop_ipc.py`, `docs/REV1_IPC.md`.
  allowlist, protocol v1, 증가하는 요청 ID, 입력 제한, 단일 작업, 협력 취소,
  구조화 오류, 결과 200행 분할 조회, EOF/shutdown 종료 대기를 구현했다.
- 변경: AGENTS/CLAUDE/HANDOFF/ai_sync 대상은 이 브랜치로 제한.
  Vite dev script/server 설정 제거. node_modules/dist/Rust target은 git 제외.
- 검증: 신규 IPC 9개 통과. `python tools/check_project.py` 실패 파일 없음.
  원본 .xlsm 의존 engine 테스트는 기존 규칙대로 제외.
- 미검증: Rust 미설치로 Tauri 빌드/실행, frontend 의존성 설치·lockfile,
  Windows/WebView2/SMB/EDR/Excel, 실제 419 Report, 대용량 성능 및 배포.
- A1 전체 완료/A2 완료/화면 연결 완료로 보고하지 않는다. 기존 tkinter 엔진/설정/배포 동작은
  변경하지 않았다. exe 빌드·버전 변경·OneDrive 운영 게시 없음.
- 5시간 30분 뒤 재개 예약은 이미 생성했다. 다음 실행에서 중복 예약하지 말고 최신 원격
  HEAD와 작업 중 변경부터 확인한다. 다른 세션이 작업 중이면 충돌을 피한다.

## 원격 분기 후 추가 변경 확인 (2026-09-21)

게시 직전 원본 UX 브랜치는 다른 작업으로 `6bb50953a24323f33451c41383c2219c674021c0`까지
진행된 것을 확인했다(Claude 배치 Lot 집계·자정 보정·M07 통합·HTML 드릴다운 등).
이번 작업은 해당 브랜치를 수정하거나 덮어쓰지 않았다. version_rev1은 기존 분기 기준
28c805f의 분석 엔진을 유지한다. 원본의 새 계산/표 schema와 새 UI 연결을 별도 비교·통합·
재검증해야 하며 자동으로 최신 원본과 동등하다고 간주하지 않는다. 다음 세션 우선 비교 대상이다.
