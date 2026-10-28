@echo off
setlocal
cd /d "%~dp0"
if exist "python\python.exe" (
  "python\python.exe" -X utf8 "app\windows_build_capture.py"
) else (
  py -3 "%~dp0build_capture.py"
)
set "build_result=%errorlevel%"
pause
exit /b %build_result%
