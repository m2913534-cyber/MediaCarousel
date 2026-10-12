@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Install Python 3.11 or 3.12 from python.org first.
  pause
  exit /b 1
)
set "MEDIA_PY=py -3.12"
%MEDIA_PY% -c "import sys" >nul 2>&1
if errorlevel 1 set "MEDIA_PY=py -3.11"
%MEDIA_PY% -c "import sys" >nul 2>&1
if errorlevel 1 (
  echo Please install Python 3.11 or 3.12 from python.org.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe %MEDIA_PY% -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -c "import PySide6" >nul 2>&1
if errorlevel 1 .venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe app.py
if errorlevel 1 goto fail
exit /b 0
:fail
echo Startup failed. Check Python version, internet access and the message above.
pause
exit /b 1
