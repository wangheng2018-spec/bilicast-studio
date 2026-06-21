@echo off
setlocal
cd /d "%~dp0"
echo Starting BiliCast Studio...
echo Open http://127.0.0.1:8000 in your browser
echo Press Ctrl+C to stop.
echo.
python server.py --host 127.0.0.1 --port 8000
pause
