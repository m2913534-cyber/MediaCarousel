@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 or 3.12 is needed ON THE BUILD COMPUTER.
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
if not exist .build-venv\Scripts\python.exe %MEDIA_PY% -m venv .build-venv
if errorlevel 1 goto fail
.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 goto fail
.build-venv\Scripts\python.exe build.py
if errorlevel 1 goto fail
echo Finished. Copy the ENTIRE dist\MediaCarousel folder to the playback computer.
echo Open MediaCarousel.exe there. The playback computer does not need Python.
explorer dist\MediaCarousel
pause
exit /b 0
:fail
echo Build failed. Read the error above.
pause
exit /b 1
