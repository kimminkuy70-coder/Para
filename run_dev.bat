@echo off
REM ============================================================
REM  개발/테스트용 실행 (.exe 빌드 없이 바로 띄우기)
REM  python.org 공식 Python 이 설치되어 있어야 합니다 (아나콘다 X)
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [오류] Python 을 찾을 수 없습니다. https://www.python.org 에서 설치하세요.
    pause
    exit /b 1
)

echo openpyxl 설치 확인 중...
python -c "import openpyxl" 2>nul
if errorlevel 1 (
    echo openpyxl 를 설치합니다...
    python -m pip install -r requirements.txt
)

python -m param_manager
