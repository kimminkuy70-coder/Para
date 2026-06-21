@echo off
REM ============================================================
REM  단일 실행파일(.exe) 빌드 스크립트 (Windows 전용)
REM
REM  사전 준비 (인터넷이 필요한 유일한 단계 - 빌드 PC 1대에서만):
REM    1) https://www.python.org 에서 Python 설치 (아나콘다 사용 금지)
REM    2) (사내망이 PyPI 를 막으면 회사 승인 미러 사용)
REM
REM  결과물: dist\PI파라미터관리.exe  (이 파일만 각 PC에 배포)
REM    - 배포된 .exe 는 Python/패키지 설치 불필요, 네트워크 불필요
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] 빌드 도구 설치 (openpyxl + pyinstaller)
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt
if errorlevel 1 (
    echo [오류] 패키지 설치 실패. 사내 PyPI 미러/프록시 정책을 확인하세요.
    pause
    exit /b 1
)

echo [2/3] PyInstaller 빌드
python -m PyInstaller --noconfirm --clean ^
    --onefile --windowed ^
    --name "PI파라미터관리" ^
    --collect-submodules openpyxl ^
    run.py
if errorlevel 1 (
    echo [오류] 빌드 실패
    pause
    exit /b 1
)

echo [3/3] 완료
echo   생성된 파일: dist\PI파라미터관리.exe
echo   이 .exe 하나만 각 PC(또는 OneDrive 폴더)에 두면 됩니다.
pause
