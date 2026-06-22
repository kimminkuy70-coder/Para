@echo off
REM ============================================================
REM  Run WITHOUT a console window (uses pythonw.exe).
REM  - Note: errors are NOT shown in this mode.
REM  - For debugging / first-time setup use run_dev.bat instead.
REM  - The packaged .exe (build_exe.bat, --windowed) also has no console.
REM ============================================================
cd /d "%~dp0"
start "" pythonw -m param_manager
