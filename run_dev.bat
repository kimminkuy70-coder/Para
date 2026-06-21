@echo off
REM ============================================================
REM  Dev / test launcher (run WITHOUT building the .exe)
REM  Requires the official python.org Python (NOT Anaconda).
REM  All-ASCII so it works on Korean Windows (cp949) too.
REM ============================================================
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Install it from https://www.python.org
    pause
    exit /b 1
)

echo Checking openpyxl ...
python -c "import openpyxl" 2>nul
if errorlevel 1 (
    echo Installing openpyxl ...
    python -m pip install openpyxl
    if errorlevel 1 (
        echo [ERROR] Failed to install openpyxl. Check your PyPI mirror/proxy.
        pause
        exit /b 1
    )
)

echo Starting PI_ALL Parameter Manager ...
python -m param_manager
if errorlevel 1 pause
