@echo off
REM Start the web dashboard:  dashboard.cmd   (opens http://127.0.0.1:8765)
cd /d "%~dp0"
set PYTHONUTF8=1
".venv\Scripts\python.exe" -m dashboard %*
