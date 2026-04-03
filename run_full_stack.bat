@echo off
setlocal

set ROOT=%~dp0
set PY=%ROOT%venv\Scripts\python.exe

if not exist "%PY%" (
  echo [ERROR] Python virtual environment not found at %PY%
  echo Create it first: python -m venv venv
  exit /b 1
)

echo [1/1] Starting SolClub FastAPI server on port 8000...
start "SolClub-Server" cmd /k "cd /d %ROOT% && %PY% main.py server"

echo.
echo API:      http://localhost:8000
echo UI:       http://localhost:8000/ui/client
echo.
endlocal
