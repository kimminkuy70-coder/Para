# Para — Claude / ChatGPT 공통 작업 규칙

## 기준과 읽는 순서
- 저장소: https://github.com/kimminkuy70-coder/Para
- 사용자 지정 작업 브랜치: `claude/ux-bento-navy-lime`. 이 브랜치에만 commit/push한다.
- 현재 요청은 배치 리포트 분석 확장만이다. 대규모 UI/기반 개편과 `version_rev1` 분기는 보류한다.
- 원본 `version_v7.0` 및 다른 브랜치 수정·push·merge 금지(이번 사용자 지시).
- 매 세션 `python tools/ai_sync.py start`로 최신 코드를 받은 다음 이 파일,
  `docs/AI_HANDOFF.md`, `CLAUDE.md`, 작업 관련 설계 문서와 소스/테스트를 읽는다.
- 두 AI의 대화 기록은 자동 공유되지 않는다. GitHub에 반영된 코드·결정·인수인계가 공통 기억이다.
- `CLAUDE.md`는 ChatGPT도 읽는 상세 설계 문서다. 과거 설명과 코드가 다르면
  최신 확정 결정과 테스트를 확인한다. 문서만 보고 이미 구현된 기능을 다시 만들지 않는다.

## 변경과 인수인계
1. 시작 커밋과 작업 범위를 확인한다. 변경 전 관련 소스와 테스트를 읽는다.
2. 작업 완료 후 관련 테스트를 실행한다. `python tools/check_project.py`는 전체
   독립 테스트 파일을 실행하며 샘플 의존 engine 테스트는 사유를 표시하고 제외한다.
3. `docs/AI_HANDOFF.md`에 변경 이유/파일, 검증 명령과 결과, 미완료/다음 작업,
   Windows 실기·빌드·배포 여부를 갱신한다. 설계 변경은 `CLAUDE.md`에도 반영한다.
4. `git diff --check`와 diff를 검토하고 이번 작업 파일만 명시적으로 stage/commit한다.
5. `python tools/ai_sync.py publish`로 공통 브랜치에 push한다. 성공 후 커밋과 결과를 알린다.
   push 전까지는 상대 AI가 변경을 볼 수 없다. 로컬 저장만 하고 연동 완료라고 하지 않는다.
- 두 AI가 동시에 같은 브랜치를 수정하지 않는 순차 교대를 기본으로 한다.
- 변경 중인 파일, 다른 브랜치, 원격의 새 커밋 때문에 동기화가 중단되면 기존 작업을 보존한다.
  원격 diff를 읽고 통합·재검증한 뒤 다시 push한다. 강제 push/reset --hard/자동 stash 금지.
- 다른 브랜치 push 및 요청하지 않은 PR 생성 금지. 원격 접근이 없으면 미반영 상태를 명시한다.
- Git 도구가 없는 연결형 환경에서는 API로 브랜치 HEAD를 읽고 해당 SHA의 파일을 읽는다.
  같은 부모 SHA의 커밋을 만들고 비강제 fast-forward 갱신한다. 경쟁 갱신 거절 시 최신본과 다시 통합한다.

## 유지해야 할 프로젝트 제약
- Python/tkinter Windows 데스크톱 앱. 런타임 의존성은 openpyxl + tksheet만.
  Anaconda/conda 및 추가 런타임 패키지 금지.
- 장비 원본은 읽기 전용. net use/자격증명 취급을 재도입하지 않는다.
- 런타임 인터넷 접속 금지. 개발용 Git 동기화는 프로그램 실행 경로에 넣지 않는다.
- 임시 수집물·로그 등은 기존 localdirs 규칙을 지킨다. OneDrive 쓰기를 늘리지 않는다.
- 실제 앱 업데이트는 기존 Windows `build_exe.bat <버전>` → 실기 검증 →
  앱의 `새 버전 배포…(개발자용)` → OneDrive 게시 절차를 유지한다.
- 브랜치 이름 v7.0과 실행파일 버전은 다르다. 실제 버전은
  `param_manager/__init__.py`의 `__version__`를 확인한다.
- 소스 push만으로 기존 exe가 바뀌지는 않는다. 빌드/게시하지 않았으면 분명히 알린다.
