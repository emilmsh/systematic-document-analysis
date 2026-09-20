@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bin\launch.ps1" -Script setup_ocr.py
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
