# version_rev1 대규모 개편 구현 기록

## 기준
- 분기 원본: `claude/ux-bento-navy-lime`
- 분기 SHA: `28c805f0971c47c5edac0cadbfe225a0eb27da59`
- 계획 B는 원본 브랜치에서 위 SHA로 구현/검증됨: M01~M11, 로컬 증분 cache, 오프라인 HTML/SVG/Excel, 일일 tkinter dashboard.
- 원본 브랜치는 이후 이 개편 작업에서 수정하지 않는다.

## 계획 A 상태
- A0: 완료. `version_rev1`을 검증된 B 커밋에서 생성.
- A1: 진행 중. `frontend/`에 React/TypeScript + Tauri 최소 shell을 추가한다.
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
1. A1 IPC protocol과 Python sidecar adapter를 완성하고 lifecycle/cancel/error 테스트 추가.
2. A2에서 기존 `batchreport*.py`를 변경 없이 호출하는 배치 화면 연결.
3. 이후 비교표 가상화/스크롤 동기화, 전체 UI, 패키징 순서로 진행.
