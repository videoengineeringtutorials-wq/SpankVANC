@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0python\python.exe" (
  echo Extract the entire ZIP before running this launcher.
  pause
  exit /b 1
)
"%~dp0python\python.exe" -X utf8 "%~dp0app\windows_launcher.py"
set "SPANKVANC_EXIT=%ERRORLEVEL%"
if not "%SPANKVANC_EXIT%"=="0" pause
exit /b %SPANKVANC_EXIT%
