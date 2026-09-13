# Claude · ChatGPT 번갈아 작업하기

공통 소스는 GitHub의 `version_new` 브랜치다. 각 AI는 같은 브랜치의
최신 코드와 AGENTS.md / AI_HANDOFF.md / CLAUDE.md를 읽고 작업한다.
채팅 내용 자체는 서로 전송되지 않으므로 결정과 남은 일을 인수인계에 적는다.

## 최초 준비 (개발 PC)
Git과 Python 3.11 이상을 준비하고 GitHub 쓰기 인증을 설정한다.
이미 복제한 저장소는 새로 만들지 않고 변경 사항을 보존한 뒤 해당 브랜치로 이동한다.

```sh
git clone --branch version_new --single-branch https://github.com/kimminkuy70-coder/Para.git
cd Para
python -m venv .venv
```

Windows: `.venv\Scripts\activate` / macOS·Linux: `source .venv/bin/activate`.
이후 `python -m pip install -r requirements.txt`를 실행한다.
GitHub 연결형 AI는 저장소 읽기·쓰기 권한과 브랜치 선택이 필요하다.
인증 토큰을 코드나 인수인계에 적지 않는다.

## 매번 교대할 때

시작: `python tools/ai_sync.py start` → 공통 문서와 관련 코드 읽기 → 수정.
검증: `python tools/check_project.py` 및 변경 기능의 실기 확인.
완료: AI_HANDOFF.md 갱신 → diff 확인 → 이번 작업 파일만 commit → 게시.

```sh
git diff --check
git diff
# 아래 경로는 이번에 수정한 파일 목록으로 바꾼다.
git add AGENTS.md docs/AI_HANDOFF.md
git commit -m "Describe the change"
python tools/ai_sync.py publish
```

명령이 STOP으로 끝나면 내용을 읽고 기존 변경을 보존한다. 수정 중인 파일을
자동 삭제하거나 덮어쓰지 않는다. 원격 변경이 있으면 비교·통합·재검증한다.
한 AI가 push를 마친 다음 다른 AI가 start를 실행해야 교대가 완성된다.
이 도구는 상주 자동 동기화가 아니라 작업 시작/완료 시 실행하는 개발 도구다.

## 두 AI에 똑같이 전달할 시작 문구

> kimminkuy70-coder/Para의 version_new 최신본을 확인하고 AGENTS.md,
> docs/AI_HANDOFF.md, CLAUDE.md를 읽어 이어서 작업해.
> 수정 후 테스트 결과와 남은 일을 인수인계에 기록하고 같은 브랜치에 반영해.

## 실제 프로그램 업데이트
GitHub push는 소스 공유 단계다. 기존 exe를 업데이트하려면 Windows에서
`build_exe.bat <새 버전>`으로 빌드하고 실행·핵심 기능을 확인한다.
프로그램의 ⋯파일 → 새 버전 배포…(개발자용)에서 생성된 exe와 변경 내용을
선택해 기존 OneDrive 프로그램 폴더에 게시한다. 사용자는 기존 업데이트 기능으로 받는다.
개발용 Git 코드를 앱 런타임에 포함하거나 GitHub 직접 업데이트를 추가하지 않는다.
