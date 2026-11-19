@echo off
cd /d "%~dp0"
echo Starting CineMatch (the first start builds the index and takes about a minute)...
".conda\python.exe" cinematch.py serve
echo.
echo CineMatch stopped. If this was unexpected, check the message above.
pause
