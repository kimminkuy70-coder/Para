@echo off
REM ============================================================
REM  Build a single-file .exe (Windows only).
REM  All-ASCII so it works on Korean Windows (cp949) too.
REM
REM  Prerequisite (internet needed ONCE, on the build PC only):
REM    1) Install Python from https://www.python.org  (NOT Anaconda)
REM    2) If the corporate network blocks PyPI, use the approved mirror
REM
REM  Output: dist\PI_Param_Manager.exe
REM    - Distribute that single .exe to each PC (or the OneDrive folder).
REM    - The built .exe needs NO Python, NO packages, NO network.
REM    - You may rename the .exe afterwards (Korean name is fine).
REM ============================================================
cd /d "%~dp0"

echo [1/3] Installing build tools (openpyxl + pyinstaller) ...
python -m pip install openpyxl pyinstaller
if errorlevel 1 (
    echo [ERROR] Package install failed. Check your PyPI mirror/proxy policy.
    pause
    exit /b 1
)

echo [2/3] Building with PyInstaller ...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "PI_Param_Manager" --collect-submodules openpyxl run.py
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo [3/3] Done.
echo   Output: dist\PI_Param_Manager.exe
echo   Put this single .exe on each PC or in the OneDrive folder.
pause
