# version_rev1 대규모 개편 구현 기록

> **브랜치 이동(2026-09-21)**: 이 개편 작업은 이제 **`version_webview`** 브랜치에서 이어진다.
> `version_rev1`을 베이스로 `claude/ux-bento-navy-lime`을 병합해 두 브랜치의 완성분을 하나로 합쳤다.
> 계획서: `docs/Para_version_rev1_master_plan.html`. 아래 A0~A6 표는 그대로 유효하다.

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
