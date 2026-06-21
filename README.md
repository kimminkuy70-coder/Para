# PI_ALL 장비 파라미터 관리 프로그램

Camtek AOI 장비의 **PI 코어 파라미터를 호기별로 관리·이력추적**하던 엑셀(.xlsm) + VBA 도구를,
**오프라인 데스크톱 프로그램(tkinter)** 으로 옮긴 것입니다.

기존 엑셀+VBA의 한계(동시편집 충돌, 매크로 보안경고, 깨지기 쉬운 수식)를 벗어나,
**OneDrive 동기화 폴더의 공용 .xlsx 파일 하나**를 여러 사람이 각자 PC에서 안전하게 편집합니다.

## 핵심 특징

- 🖥️ **각 PC에서 더블클릭 실행** — 서버 불필요, 설치 흔적은 .exe 하나
- 🔌 **완전 오프라인** — 실행 중 네트워크/프록시/소켓 접속 0. OneDrive 폴더의 파일만 사용
- 🔒 **동시편집 안전장치** — 편집 잠금 표시 + **저장 시 Row_ID 기준 행 단위 병합**(서로 다른 행 수정이 안 부딪힘) + OneDrive 충돌본 감지
- 📝 **변경 이력 자동 기록** — 값 바꾸면 누가/언제/Old→New 자동 누적, 검색·필터
- 📊 **호기 비교/누락 뷰** — 파라미터별 호기 간 값 차이·빈 호기 강조
- 🔁 **엑셀 가져오기/내보내기** — 기존 .xlsm 변환, .xlsx 내보내기

## 라이선스/보안 (아나콘다 이슈 회피)

- **아나콘다/conda 미사용** → python.org 공식 Python(무료, PSF)만 사용
- 외부 패키지는 **openpyxl(MIT) 1개뿐**, 나머지는 파이썬 표준 내장(tkinter 등)
- PyInstaller(GPL+상업예외) → 사내 .exe 배포 합법, 과금 없음
- 자세한 검토는 [`docs/보안_라이선스_검토.md`](docs/보안_라이선스_검토.md)

## 빠른 시작

### A. 개발/테스트 (Python 설치 PC)
```bat
run_dev.bat            REM openpyxl 자동 설치 후 프로그램 실행
```
또는:
```bash
pip install -r requirements.txt
python -m param_manager
```

### B. 배포용 .exe 만들기 (Windows, 빌드 PC 1대)
```bat
build_exe.bat          REM dist\PI파라미터관리.exe 생성
```
생성된 `dist\PI파라미터관리.exe` **하나만** 각 PC나 OneDrive 폴더에 두면 됩니다.
(배포된 .exe는 Python·패키지·네트워크 모두 불필요)

### 처음 한 번: 기존 엑셀 가져오기
프로그램 실행 → **파일 > 기존 엑셀(.xlsm) 가져오기** → 기존 파일 선택 →
OneDrive 폴더에 저장할 `.xlsx` 경로 지정. 이후로는 그 `.xlsx`를 공용 파일로 사용합니다.

## 구조

```
param_manager/
  engine.py     # 핵심 로직 (엑셀 입출력·Row_ID·이력·요약·비교·병합·잠금) — GUI 비의존
  app.py        # tkinter 화면 (3개 탭)
  __main__.py   # python -m param_manager
run.py          # .exe 엔트리포인트
tests/test_engine.py   # 헤드리스 엔진 테스트
docs/           # 사용설명 / 보안·라이선스 검토
```

## 테스트

```bash
python tests/test_engine.py
```
실제 업로드 파일 기준 132개 파라미터, 1948건 이력, 동시편집 병합, 요약 집계를 검증합니다.

## 사용 안내

[`docs/사용설명.md`](docs/사용설명.md) 참고.
