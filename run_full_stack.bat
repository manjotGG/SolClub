@echo off
setlocal

set ROOT=%~dp0
set PY=%ROOT%venv\Scripts\python.exe

if not exist "%PY%" (
  echo [ERROR] Python virtual environment not found at %PY%
  echo Create it first: python -m venv venv
  exit /b 1
)

echo [1/2] Starting FastAPI backend on port 8000...
start "SolClub-Backend" cmd /k "cd /d %ROOT% && %PY% main.py server"

echo [2/2] Starting Flask frontend on port 5050...
start "SolClub-Frontend" cmd /k "cd /d %ROOT% && %PY% frontend\run_frontend.py"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5050
echo.
endlocal
