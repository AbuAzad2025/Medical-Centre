@echo off
REM Medical System - Single Startup Script
REM Usage: run.bat [--dev]

cd /d "%~dp0"

if /I "%1"=="--dev" (
    title Medical System - DEV MODE
    set FLASK_DEBUG=1
    set FLASK_ENV=development
    echo ==========================================
    echo   Medical System - DEVELOPMENT MODE
    echo ==========================================
    echo Debug: ON ^| Auto-reload: ON
) else (
    title Medical System - Starting...
    echo ==========================================
    echo   Medical System - Starting Application
    echo ==========================================
)

chcp 65001 >nul
set PYTHONIOENCODING=utf-8

echo.
echo Access at: http://127.0.0.1:8080
echo Press Ctrl+C to stop
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    pause
    exit /b 1
)

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

.venv\Scripts\python run_server.py

echo.
echo Application stopped.
pause
