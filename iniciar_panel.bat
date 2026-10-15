@echo off
title ReVox Control Panel
cd /d "%~dp0"

echo ========================================================
echo   ReVox TTS - Host Control Panel
echo ========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Checking Python installation...
    where python >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Python was not found on your system.
        echo Please install Python 3.11 by running in PowerShell:
        echo   winget install Python.Python.3.11
        echo.
        pause
        exit /b 1
    )
    echo [INFO] Creating virtual environment and installing dependencies...
    python -m venv .venv
    call .venv\Scripts\pip install -r requirements.txt
)

echo [INFO] Starting panel at http://127.0.0.1:5050 ...
.venv\Scripts\python panel.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] The panel exited with an error code.
    pause
)
