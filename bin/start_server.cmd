@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1" -Script start_server.py
exit /b %ERRORLEVEL%
