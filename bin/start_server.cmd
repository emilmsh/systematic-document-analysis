@echo off
rem Starter MCP-serveren for OE Kildeanalyse. Kalles fra .mcp.json via cmd /c.
rem stdout er reservert for MCP-protokollen; alt annet skrives til stderr.
setlocal
set "ROOT=%~dp0.."
rem Bruk etiketter: %%variabler%% i en parentesblokk ekspanderes for tidlig.
if defined OE_KILDEANALYSE_PYTHON goto :valgt_python
if exist "%ROOT%\.venv\Scripts\python.exe" goto :lokal_python
where py >nul 2>nul
if not errorlevel 1 goto :py_launcher
where python >nul 2>nul
if not errorlevel 1 goto :python_path
echo [kildeanalyse] Fant ikke Python. Installer Python 3.12+ eller sett OE_KILDEANALYSE_PYTHON til python.exe. 1>&2
exit /b 1
:valgt_python
"%OE_KILDEANALYSE_PYTHON%" "%~dp0start_server.py"
exit /b %errorlevel%
:lokal_python
"%ROOT%\.venv\Scripts\python.exe" "%~dp0start_server.py"
exit /b %errorlevel%
:py_launcher
py -3 "%~dp0start_server.py"
exit /b %errorlevel%
:python_path
python "%~dp0start_server.py"
exit /b %errorlevel%
