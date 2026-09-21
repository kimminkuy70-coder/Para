@echo off
REM ============================================================
REM  Web UI (Tauri + React) DEV launcher  --  version_webview
REM  Opens the NEW web desktop app (not the old tkinter program).
REM  Requirements on this PC (install once, from official sources):
REM    - python.org Python 3.11+   (NOT Anaconda)   -> `python` on PATH
REM    - Node.js LTS               -> `npm` on PATH
REM    - Rust (MSVC toolchain)     -> `cargo` on PATH   (https://rustup.rs)
REM    - WebView2 Runtime          (usually already on Windows 10/11)
REM  This DEV mode runs the Python engine straight from this folder,
REM  so no PyInstaller build is needed. All-ASCII for cp949 safety.
REM ============================================================
cd /d "%~dp0"

where python >nul 2>nul || (echo [ERROR] Python not found. Install python.org Python 3.11+ ^& add to PATH. & pause & exit /b 1)
where npm    >nul 2>nul || (echo [ERROR] Node.js/npm not found. Install Node.js LTS. & pause & exit /b 1)
where cargo  >nul 2>nul || (echo [ERROR] Rust/cargo not found. Install from https://rustup.rs (MSVC). & pause & exit /b 1)

echo [1/4] Checking Python engine dependency (openpyxl) ...
python -c "import openpyxl" 2>nul || python -m pip install -r requirements.txt || (echo [ERROR] pip install failed. Check your PyPI mirror/proxy. & pause & exit /b 1)

echo [2/4] Installing frontend packages (first run may take a while) ...
if not exist "frontend\node_modules" (
    pushd frontend && call npm install || (echo [ERROR] npm install failed. & popd & pause & exit /b 1)
    popd
)

echo [3/4] Building the web bundle ...
pushd frontend && call npm run build || (echo [ERROR] Frontend build failed. & popd & pause & exit /b 1)
popd

echo [4/4] Launching the desktop app (first compile of Rust can take several minutes) ...
pushd frontend && call npm run tauri dev
popd
if errorlevel 1 pause
