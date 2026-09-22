# 웹 UI(version_webview) 실행·사용법

새 웹 UI는 **기존 tkinter 프로그램과 별개의 앱**입니다. `run.py`/`run_dev.bat`로는
기존 프로그램만 뜹니다. 새 웹 UI는 아래 방법으로 실행합니다.

> **Rust·Node를 이 PC에 설치할 수 없다면(회사 승인 등) → 바로 [2. GitHub Actions로
> 빌드받기](#2-github-actions로-빌드받기-개인-pc에-rustnode-설치-불가일-때-)로 가세요.**
> 완성된 폴더만 받아 실행하며, 사용자 PC엔 아무 설치도 필요 없습니다(WebView2만).
> 아래 1번(개발 모드)은 그 PC에 Rust·Node가 이미 있을 때의 방법입니다.

## 0. 준비물 (이 PC에 한 번만 설치 — 모두 공식 배포본)

| 도구 | 확인 | 설치처 |
|---|---|---|
| Python 3.11+ (python.org, **Anaconda 금지**) | `python --version` | https://www.python.org |
| Node.js LTS | `npm --version` | https://nodejs.org |
| Rust (MSVC 툴체인) | `cargo --version` | https://rustup.rs |
| WebView2 런타임 | 보통 Windows 10/11에 기본 탑재 | Microsoft |

> `python`·`npm`·`cargo`가 명령창(cmd)에서 바로 실행돼야 합니다(PATH 등록).

## 1. 실행 (개발 모드 — 가장 쉬움, 권장)

저장소 루트의 **`run_web_dev.bat`를 더블클릭**하면 됩니다. 내부적으로:

1. Python 엔진 의존성(openpyxl) 확인·설치
2. `frontend`의 npm 패키지 설치(첫 실행만, 몇 분 소요)
3. 웹 번들 빌드(`npm run build`)
4. 데스크톱 앱 실행(`npm run tauri dev`) — **첫 Rust 컴파일은 수 분 걸립니다**

창이 뜨면 새 웹 UI입니다. 이 개발 모드는 **Python 엔진을 이 폴더에서 직접 실행**하므로
별도 exe 빌드(PyInstaller)가 필요 없습니다. (개발 모드는 디버그 빌드에서만 이 방식을 쓰고,
배포용 빌드는 반드시 패키징된 고정 엔진 exe만 실행합니다 — 보안 경계 유지.)

**동작 조건**: 앱은 기존 프로그램과 **같은 설정 파일**(`%USERPROFILE%\.pi_param_manager.json`)을
읽습니다. 그래서 화면에 데이터가 나오려면 먼저 **기존 프로그램에서 저장폴더를 지정**하고,
배치/WPH의 Report 폴더·Commonality의 Scanresult 루트를 한 번 설정해 두어야 합니다.
설정이 없으면 각 화면은 "먼저 저장폴더를 지정하세요" 같은 안내만 표시합니다(정상).

## 2. GitHub Actions로 빌드받기 (개인 PC에 Rust/Node 설치 불가일 때) ⭐

회사 승인 때문에 각자 PC에 Rust·Node를 못 깔아도, **빌드는 GitHub 윈도우 러너에서**
하고 완성본만 받으면 됩니다. 사용자 PC엔 아무것도 설치하지 않습니다(WebView2만).

1. GitHub 저장소 → **Actions** 탭 → **Build Windows Desktop (Tauri)** 워크플로.
2. **Run workflow** → 브랜치 `version_webview` 선택 → 버전(예: `8.1.0`) 입력 → 실행.
   · Run workflow 버튼이 안 보이면(기본 브랜치에만 표시되는 GitHub 제약) 대신 태그를
     밀어 실행합니다: `git tag v8.1.0 && git push origin v8.1.0`.
3. 빌드 완료(약 10~20분) 후 그 실행 페이지 하단 **Artifacts** 에서
   `Camtek_AOI_manager_v8.1.0` zip 다운로드.
4. 압축을 풀면 **`Camtek_AOI_manager.exe` + `sidecar\` 폴더**가 있습니다. **폴더 통째로**
   원하는 위치(또는 OneDrive 배포 폴더)에 두고 exe 를 실행합니다.
   · exe 만 따로 옮기면 안 됩니다 — `sidecar\`(파이썬 엔진)가 옆에 있어야 동작합니다.
   · 미서명 exe라 처음 실행 시 SmartScreen 경고가 날 수 있습니다(추가 정보 → 실행).

> 이 방식이 계획서(REV1_PACKAGING)의 "완전한 포터블 폴더 배포"와 동일합니다.
> Tauri 구조·보안 경계를 그대로 유지하며, 빌드 도구는 러너에만 있으면 됩니다.

## 3. 배포용 exe 빌드 — 승인받은 PC 1대에서 직접 (대안)

개발 도구가 없는 PC에도 나눠 주려면 패키지 폴더를 만듭니다:

```
python tools\build_desktop.py 8.1.0
```

`dist\Camtek_AOI_manager_v8.1.0\` 폴더 전체(앱 exe + `sidecar\` + licenses)를 통째로 복사해
사용합니다. 이 과정은 npm/cargo 캐시가 준비된 환경을 전제로 하며(오프라인 락파일 빌드),
**실기 검증 전에는 운영 배포하지 않습니다**(상세: `docs/REV1_PACKAGING.md`).

## 4. 화면별 사용법

상단 탭으로 이동합니다.

- **Recipe 관리**: 최신 취합본을 호기별로 비교(읽기 전용). 셀 색상·비고만 편집.
- **양식 만들기**: 저장폴더에 이미 있는 **원본(초안)**을 골라 항목의 사용(Y/N)·표시 이름·
  변환(RAW/LINEAR/AREA)을 편집 → 호기 입력 후 **양식 확정**(새 회차로 확정본+원본 저장).
  *장비에서 새로 수집해 처음부터 만드는 흐름은 아직 기존 tkinter 프로그램에서 하세요.*
- **이력 확인**: '파라미터 값 취합' 파일 2개를 골라 값이 달라진 셀만 비교(종류·검색 필터).
- **Commonality 조사**:
  · *신규 조사 계획 확인* — 조사 계획(디바이스/공정/S·M)을 입력해 그 호기 Scanresult에서
    실제 Lot 폴더 실재를 확인(발견/없음). *안전복사·값 조사는 아직 기존 프로그램에서.*
  · *저장 결과 비교* — 기존 조사/감시가 저장한 결과 파일들을 골라 비교·Excel 내보내기.
- **배치 리포트 분석**: 호기·검색어/기간 선택 → **📋 리포트 선택…**으로 개별 Report만 고르기 →
  지표 선택 → 조사 시작 → 결과 표·저장된 Excel/HTML 위치.
- **특이사항 / 참고자료 / 장비 IP**: 공유 문서 조회·셀 편집·행 추가.

## 5. 현재 웹 UI로 "되는 것 / 아직 기존 프로그램에서 하는 것"

| 되는 것(웹) | 아직 기존 tkinter에서 |
|---|---|
| 취합 비교·색상/비고, 이력 diff | 장비 SMB 신규 수집(양식 새로 만들기·값 업데이트) |
| 양식 원본 편집·확정 | Commonality 안전복사→값 조사, 자동 감시·트레이 |
| 배치 분석(개별 Report 선택 포함) | 자동 업데이트·배포 |
| Commonality 계획 프리플라이트·저장결과 비교·내보내기 | 새 호기 Report 폴더 등록(네이티브 파일 선택) |

즉 웹 UI는 **읽기·비교·편집·배치 분석**은 실사용 가능하고, **장비에 직접 접속해 수집하는
작업**은 당분간 기존 프로그램을 병행합니다.

## 6. 문제가 생기면

- 창은 뜨는데 데이터가 없음 → 기존 프로그램에서 저장폴더/Report 폴더/Scanresult 루트를
  먼저 설정했는지 확인(같은 설정 파일 공유).
- `cargo`/`npm`/`python`을 못 찾음 → 설치 후 PATH 등록, cmd 새로 열기.
- 첫 실행이 느림 → Rust 최초 컴파일은 정상적으로 수 분 걸립니다(두 번째부터 빠름).
- 개발 모드에서 엔진 연결 오류 → cmd에서 `python -m param_manager.desktop_ipc`가 실행되는지
  (openpyxl 설치 여부) 확인.
