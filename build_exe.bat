@echo off
setlocal
REM ============================================================
REM  Build the .exe (Windows only).
REM  All-ASCII so it works on Korean Windows (cp949) too.
REM
REM  Usage:
REM    build_exe.bat 4.0.2          -> stamp version 4.0.2, then ONE-FILE build
REM    build_exe.bat 4.0.2 onedir   -> same, but ONE-FOLDER build (fallback)
REM    build_exe.bat                -> build with the version already in the source
REM
REM  ALWAYS pass the version you are going to publish. The version the running
REM  program reports comes from param_manager\__init__.py (__version__), NOT from
REM  the file name. If you publish 4.0.2 but build with 3.0.1 inside, every user
REM  keeps being told "a new version is available" forever (this happened).
REM  Passing the version here stamps it into the source AND into the exe file
REM  properties, and the publish dialog checks that they match.
REM
REM  Prerequisite (internet needed ONCE, on the build PC only):
REM    1) Install Python 3.11+ from https://www.python.org  (NOT Anaconda)
REM    2) If the corporate network blocks PyPI, use the approved mirror
REM
REM  ---------------------------------------------------------------
REM  Why --runtime-tmpdir is used (fixes "Failed to load Python DLL")
REM  ---------------------------------------------------------------
REM  A one-file exe unpacks itself into a temp folder (_MEIxxxxxx) and
REM  loads python3xx.dll from there. On some PCs %TEMP% is
REM    - cleaned by policy / disk cleanup while the app starts,
REM    - redirected per session (C:\...\AppData\Local\Temp\1\...),
REM    - or watched by antivirus, which quarantines the unpacked DLL.
REM  Then the unpacked python3xx.dll disappears between unpack and load
REM  and the app dies with:
REM    Failed to load Python DLL '...\_MEIxxxxxx\python311.dll'
REM    LoadLibrary: The specified module could not be found.
REM  So we unpack into a stable per-user folder instead of %TEMP%.
REM  (Needs PyInstaller 6.x - it expands %VARS% in --runtime-tmpdir.)
REM
REM  If a PC still fails, build with "onedir" and run it from that
REM  folder: a one-folder build unpacks nothing at all, so this error
REM  cannot happen. Do NOT publish a one-folder build to OneDrive as a
REM  single .exe - it only runs together with its _internal folder.
REM ============================================================
cd /d "%~dp0"

set "APPNAME=PI_Param_Manager"
set "VERARG=%~1"
set "MODEARG=%~1"
if /i not "%~1"=="onedir" set "MODEARG=%~2"
if /i "%VERARG%"=="onedir" set "VERARG="

if not "%VERARG%"=="" (
    echo [0/3] Stamping version %VERARG% ...
    python tools\set_version.py %VERARG%
    if errorlevel 1 (
        echo [ERROR] Version stamping failed.
        pause
        exit /b 1
    )
)
for /f "delims=" %%V in ('python tools\set_version.py --show') do set "APPVER=%%V"
if "%APPVER%"=="" (
    echo [ERROR] Could not read the version. Is Python on PATH?
    pause
    exit /b 1
)
echo     Building version %APPVER%
REM  The version resource lives in tools\ on purpose: PyInstaller --clean wipes
REM  everything inside the work path (build\), so a file there would vanish
REM  before it is read and the whole build would fail.
set "VERFILE="
if exist "tools\version_info.txt" set "VERFILE=--version-file tools\version_info.txt"

REM  Remove the previous output first. If a build fails halfway, a stale or
REM  half-written exe must not be left behind for someone to publish by mistake.
if exist "dist\%APPNAME%.exe" del /q "dist\%APPNAME%.exe"
REM  %%VAR%% keeps the literal %VAR% - PyInstaller expands it at run time.
set "RTTMPDIR=%%LOCALAPPDATA%%\CamtekAOI\runtime"
set "MODE=--onefile --runtime-tmpdir %RTTMPDIR%"
set "OUTDESC=dist\%APPNAME%.exe   (single file)"
if /i "%MODEARG%"=="onedir" (
    set "MODE=--onedir"
    set "OUTDESC=dist\%APPNAME%\%APPNAME%.exe   (keep the whole folder together)"
)

echo [1/3] Installing build tools (openpyxl + tksheet + pyinstaller) ...
python -m pip install openpyxl tksheet "pyinstaller>=6.0"
if errorlevel 1 (
    echo [ERROR] Package install failed. Check your PyPI mirror/proxy policy.
    pause
    exit /b 1
)

echo [2/3] Building with PyInstaller ...
REM  --add-data : data files are loaded relative to the package folder
REM               (rtp_template.json, para_icon.ico) and are NOT bundled
REM               automatically - without this they are missing at run time.
python -m PyInstaller --noconfirm --clean %MODE% --windowed ^
    --name "%APPNAME%" ^
    --icon "param_manager\data\para_icon.ico" ^
    %VERFILE% ^
    --add-data "param_manager\data;param_manager\data" ^
    --collect-submodules openpyxl --collect-submodules tksheet run.py
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

set "OUTFILE=dist\%APPNAME%.exe"
if /i "%MODEARG%"=="onedir" set "OUTFILE=dist\%APPNAME%\%APPNAME%.exe"
if not exist "%OUTFILE%" (
    echo [ERROR] Build reported success but %OUTFILE% is missing.
    pause
    exit /b 1
)

echo [3/3] Done.
echo   Version: %APPVER%   (publish this exact number)
echo   Output: %OUTDESC%
echo.
echo   Publish it from the app:  ... file menu ^> New version publish
echo   (the app copies it to the shared folder as
echo    Camtek_AOI_Parameter_manage_v^<version^>.exe)
pause
