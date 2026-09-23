# version_rev1 시험 패키징·복구 경계

**현재 운영 배포 승인 없음. Windows 빌드·실기 통과 전 사용 중인 exe를 교체하지 않는다.**

## 빌드 준비와 실행

- 회사가 허용한 Windows 개발 PC에서 python.org Python 3.11+, Node, Rust MSVC,
  Windows SDK/Build Tools를 사용한다. conda는 사용하지 않는다.
- 의존성 설치는 개발 준비 단계다. npm은 `frontend/package-lock.json`, Rust는
  `frontend/src-tauri/Cargo.lock`을 사용한다. Python은 기존 requirements를 유지한다.
- 개발 네트워크에서 승인된 경로로 의존성을 준비한 뒤, `python tools/build_desktop.py 8.1.0`.
  8.1.0은 예시이며 실제 버전은 명시적으로 지정한다. 이 명령을 이번 환경에서는 실행하지 않았다.
- 스크립트는 `build/desktop-*`에 소스를 복사하고 해당 복사본에만 버전을 찍는다.
  Python sidecar는 console/onedir로 패키징한다. stdio를 유지하고 native에서 콘솔 창을 숨긴다
  (CREATE_NO_WINDOW). 앱 exe 자체는 `#![windows_subsystem = "windows"]`(debug 빌드 포함)라
  검은 콘솔 창이 뜨지 않는다 — 예전 시험본에서 그 창을 닫으면 프로그램 전체가 꺼졌다.
- npm ci / Cargo build는 offline/lockfile 조건으로 실행한다. 캐시가 없으면 실패하며
  자동 다운로드·정책 우회·방화벽 변경을 하지 않는다. 실패 staging은 조사용으로 남긴다.
- 출력은 `dist/Camtek_AOI_manager_v<버전>/` 전체 폴더다. UI exe, sidecar exe와
  `_internal`을 함께 보존한다. `tools/desktop_bundle.py verify <폴더>`로 무결성을 확인한다.
- 기존 `build_exe.bat`는 기존 tkinter 프로그램 빌드용이며 그대로 보존한다.

## 의존성과 승인

`python tools/desktop_inventory.py <검토폴더>`는 npm/Cargo lockfile 및 설치된 라이선스
자료를 모은다. 전체 배포 binary SBOM은 아니다. Python·WebView2·OS 런타임, 빌드 도구,
실제 포함 파일과의 대조가 추가로 필요하다. 미확인 라이선스는 null/목록으로 남긴다.
2026-09-21 개발 환경 조회: 561개 lockfile 항목, 라이선스 메타데이터 미확인 102개.
다른 플랫폼용 미설치 패키지도 포함하며 이 결과를 '전부 라이선스 검토 완료'로 해석하지 않는다.
프런트엔드 npm audit는 당시 0건. 이는 회사 사용 승인이나 미래 취약점 없음의 보장이 아니다.

## 최초 전환·복구

1. 새 폴더를 기존 exe와 별개인 로컬 시험 위치에 배치한다. 기존 설정·공유 문서를 일괄 변환하지 않는다.
2. 기존 앱을 종료한 뒤 새 앱을 실행한다. 기존 SingleInstance mutex를 공유해 중복 엔진을 막는다.
3. 기존 설정은 읽고 새 배치 최신 조건만 로컬 Cache/rev1_batch_last.json(schema 1)에 저장한다.
   구 앱의 batch_last를 덮어쓰지 않으며 새 조건의 구 앱 역동기화는 아직 없다.
4. 실패 시 새 앱을 정상 종료한 후 보존한 기존 exe로 돌아간다. 공유 문서의 명시적 사용자
   편집까지 자동으로 되돌리는 기능은 없다. 파일별 백업/OneDrive 이력과 별개다.
5. 새 구성은 기존 '단일 exe 교체' 게시 기능에 넣지 않는다. 전체 폴더 원자 전환·서명 검증·
   실패 복구를 구현하고 실제 구버전 전환 테스트한 뒤 운영 배포 여부를 결정한다.

해시는 손상 확인이며 게시자 인증이 아니다. 개인키는 소스/OneDrive에 넣지 않는다.
현재 manifest의 deployment_approved=false는 참고 상태이며 보안 승인 장치가 아니다.

## 남은 Windows gate

- Rust/MSVC native 컴파일, WebView2 실행 및 전체 리소스 발견, 한글·공백 경로.
- 앱 종료 중 작업 완료/취소, 강제 종료 복구, 중복 실행 및 트레이 통합.
- DPI 100/125/150/200%, 키보드/IME/색상 다이얼로그, Excel 실제 차트 렌더링.
- 실장비 SMB 지연·접근 실패·재연결·EDR, OneDrive 동시 편집, 실제 Report 샘플.
- 버전별 전체 폴더 전환/rollback, 서명·배포권한·라이선스·최종 SBOM.

Linux 개발 환경의 Windows GNU cargo check는 windres 부재에서 중단되었다.
표준 apt 설치도 실행 환경 권한 오류로 실패했다. 권한 상승이나 정책 변경으로 우회하지 않았다.
