# version_rev1 대규모 개편 구현 기록

## 기준
- 분기 원본: `claude/ux-bento-navy-lime`
- 분기 SHA: `28c805f0971c47c5edac0cadbfe225a0eb27da59`
- 계획 B는 원본 브랜치에서 위 SHA로 구현/검증됨: M01~M11, 로컬 증분 cache, 오프라인 HTML/SVG/Excel, 일일 tkinter dashboard.
- 원본 브랜치는 이후 이 개편 작업에서 수정하지 않는다.

## 계획 A 상태
- A0: 완료. `version_rev1`을 검증된 B 커밋에서 생성.
- A1: 진행 중. 기존 React/TypeScript + Tauri shell에 Python stdio 기반을 추가했다.
  native launcher/React 연결 및 Windows 실행 gate는 아직 통과하지 않았다.
- A2~A6: 미완료.

## 불변 경계
- 장비 SMB는 기존 Python 계층만 접근하고 원본 수정/삭제/이동 금지.
- React UI가 UNC/임의 파일을 직접 읽지 않는다.
- 외부 CDN, telemetry, 로컬 HTTP/TCP 서버를 사용하지 않는다.
- Tauri command는 allowlist된 제한 명령만 제공한다. 임의 shell/Python 코드 실행 API 금지.
- 배치 분석 산출물/cache/log는 기존 `localdirs` 로컬 경계를 유지한다.
- 운영 배포/OneDrive 배포/자동 PR/강제 push는 별도 승인 전 수행하지 않는다.

## 검증 상태
- 계획 B 원본 커밋 기록: synthetic 16 tests + 기존 standalone suite 통과.
- Windows GUI/Excel, 실제 419-report sample, SMB/EDR, executable deployment는 미검증.
- Tauri shell은 저장소 구조 검토 단계이며 Windows 실기/패키징 검증 전이다.

## 다음 작업
1. Rust 가능한 개발 환경에서 기존 shell을 빌드하고 의존성 버전/lockfile/라이선스를 검증한다.
2. `docs/REV1_IPC.md` 기준으로 고정 sidecar 실행파일 launcher, stdout 이벤트 전달,
   종료 감시와 제한 command를 연결한다. 개발용 HTTP 서버는 실행하지 않는다.
3. A2에서 기존 `batchreport*.py`를 호출하는 배치 화면 연결. 입력 설정 전달 및 기존
   수집 서비스 경계 연결은 별도 구현하고 계산 결과/파일 출력 동등성을 검증한다.
4. 이후 비교표 가상화/스크롤 동기화, 전체 UI, 패키징 순서로 진행.

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
