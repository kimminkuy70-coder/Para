# AI 공통 인수인계

## 현재 기준
- 저장소 `kimminkuy70-coder/Para`, 공통 브랜치 `version_v7.0`.
- 협업 구성 반영 기준 커밋: `caefbff85fd8a33543db993e965edefd8472aeb6`.
- 최신 커밋은 `git log -5 --oneline` 또는 GitHub 브랜치 HEAD로 확인한다.
- 확인한 실행파일 내부 버전: `4.0.3`. 브랜치 v7.0을 앱 버전으로 간주하지 않는다.
- 현재 주요 기능: 장비 파라미터 양식/취합/비교, Commonality 조사·감시,
  WPH 조사, OneDrive 기반 exe 업데이트. 상세 구현은 CLAUDE.md와 소스 참고.

## 마지막 작업 — 2026-09-13, ChatGPT/Codex
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
2. 사용자가 요청하는 기능/수정 작업 수행. 현재 별도의 기능 수정 요청은 없음.
3. 작업 결과와 미완료 항목을 이 파일에 기록하고 코드와 함께 commit/push.
4. 앱 배포 요청 시 Windows에서 빌드·실기 검증 후 기존 OneDrive 배포 경로 이용.

## 알려진 한계
- Claude 내부 대화/미게시 로컬 변경은 여기에서 접근할 수 없다. 필요한 결정은 문서에 남긴다.
- README 본문의 일부는 초기 버전 설명이다. 최신 설계는 CLAUDE.md와 코드로 확인한다.
- tests/test_engine.py는 Claude 업로드 경로의 원본 .xlsm에 의존한다.
- 현재 환경은 Windows 빌드 PC/OneDrive 게시 폴더에 연결되어 있지 않다.
