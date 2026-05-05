@echo off
REM ============================================================================
REM MicroKISStnc public v1 - Startup Script (Windows)
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================================
echo MicroKISStnc public v1 - APRS TNC Desktop Application
echo ============================================================================
echo.

cd /d "%~dp0"

REM Check if python exists
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.8+ or add it to PATH
    pause
    exit /b 1
)

REM Check if .venv exists
if not exist ".venv" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [SETUP] Setup complete - venv created
)

REM Activate environment
call .venv\Scripts\activate.bat

echo [SETUP] Installing dependencies from requirements.txt...
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo WARNING: Some dependencies may have failed to install
    echo Continuing anyway...
    timeout /t 2
)

echo.
echo [RUN] Starting MicroKISStnc public v1...
echo.
echo Web UI will be available at:
echo   Local:  http://127.0.0.1:8765
echo   Remote: http://^<your-pc-ip^>:8765
echo.
echo KISS Server listening on port 8001
echo.

REM Run the app with full venv python path
.venv\Scripts\python.exe MicroKISStnc_dev.py

echo.
echo [EXIT] Application closed
pause
