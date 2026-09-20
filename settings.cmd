@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bin\launch.ps1" -Script configure_keys.py
exit /b %ERRORLEVEL%
