# AI 공통 인수인계

## 현재 기준
- 저장소 `kimminkuy70-coder/Para`, 이번 작업 브랜치 `version_new`만 사용.
- 원본 기준: version_v7.0의 `ad895aedf298637df548b3963f30bf700ed79f14`. 다른 브랜치 수정 금지.
- 협업 구성 반영 기준 커밋: `caefbff85fd8a33543db993e965edefd8472aeb6`.
- 최신 커밋은 `git log -5 --oneline` 또는 GitHub 브랜치 HEAD로 확인한다.
- 현재 소스 기본 버전: `8.0`. 빌드할 때 입력한 버전으로 다시 기록한다.
- 현재 주요 기능: 장비 파라미터 양식/취합/비교, Commonality 조사·감시,
  WPH 조사, OneDrive 기반 exe 업데이트. 상세 구현은 CLAUDE.md와 소스 참고.

## 마지막 작업 — 2026-09-13, ChatGPT/Codex

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
