@echo off
set ROOT=%~dp0

echo ========================================
echo     AI Interview - Quick Start
echo ========================================
echo.

echo [1/2] Starting backend on port 8000...
start "Backend" cmd /k "cd /d %ROOT%backend && uvicorn app.main:app --reload --port 8000"








timeout /t 2 >/dev/null

echo [2/2] Starting frontend on port 5173...
start "Frontend" cmd /k "cd /d %ROOT%frontend && npm run dev"

echo.
echo Done! Open http://localhost:5173
echo Close the CMD windows to stop.
pause
