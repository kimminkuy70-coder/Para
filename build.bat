@echo off
REM Compatibility entry point; keep all build logic in build_exe.bat.
call "%~dp0build_exe.bat" %*
exit /b %errorlevel%
