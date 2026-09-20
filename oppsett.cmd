@echo off
rem Oppsett av Systematic Document Analysis på Windows: lager .venv, installerer pakken og viser motorstatus.
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto :installer
if defined SDA_PYTHON goto :valgt_python
set "PYCMD=python"
where py >nul 2>nul && set "PYCMD=py -3"
echo Lager virtuelt Python-miljo i .venv ...
%PYCMD% -m venv .venv || goto :feil
goto :installer
:valgt_python
"%SDA_PYTHON%" -m venv .venv || goto :feil
:installer
".venv\Scripts\python.exe" -m pip install -e ".[dev]" || goto :feil
echo.
".venv\Scripts\python.exe" -m kildeanalyse oppsett || goto :feil
echo.
echo Ferdig. Start Claude Code i prosjektmappen din med pluginen:
echo   claude --plugin-dir "%~dp0."
echo Kjør testene med:  .venv\Scripts\python.exe -m pytest
exit /b 0
:feil
echo Oppsettet feilet. Kontroller at Python 3.12 er installert (python.org) og at du har nettilgang til PyPI.
exit /b 1
