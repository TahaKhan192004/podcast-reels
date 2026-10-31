@echo off
REM Windows cmd / PowerShell wrapper:  reels prepare "<youtube-url>"
cd /d "%~dp0"
set PYTHONUTF8=1
".venv\Scripts\python.exe" -m pipeline %*
