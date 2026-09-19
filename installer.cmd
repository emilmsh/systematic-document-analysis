@echo off
setlocal
where py >nul 2>nul
if errorlevel 1 goto python_path
py -3 "%~dp0bin\installer.py" %*
goto done
:python_path
python "%~dp0bin\installer.py" %*
:done
set "RESULT=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %RESULT%
