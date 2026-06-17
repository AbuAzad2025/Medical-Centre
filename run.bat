@echo off
REM Medical System - Startup Script
REM Runs the Flask-SocketIO application

cd /d "%~dp0"

title Medical System - Starting...

REM Enable UTF-8 for emoji/arabic support in console
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

echo.
echo ==========================================
echo   Medical System - Starting Application
echo ==========================================
echo.

REM Use python from PATH, check if available
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python and add to PATH
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv" (
    echo Virtual environment not found. Creating...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Installing dependencies...
    .venv\Scripts\pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install requirements
        pause
        exit /b 1
    )
)

echo.
echo Starting Flask-SocketIO server on port 8080...
echo Access at: http://127.0.0.1:8080
echo Press Ctrl+C to stop
echo.

.venv\Scripts\python run_server.py

echo.
echo Application stopped.
pause
