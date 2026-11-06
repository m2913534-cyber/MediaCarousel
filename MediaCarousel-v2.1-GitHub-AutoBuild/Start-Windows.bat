@echo off
rem MediaCarousel 2.11 - Windows one-click launcher (source edition)
rem Double-click to start. Run "Start-Windows.bat --repair" to rebuild the environment.
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\launch-windows.ps1" %*
set "code=%errorlevel%"
if not "%code%"=="0" pause
exit /b %code%
