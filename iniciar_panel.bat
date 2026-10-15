@echo off
title ReVox Control Panel
cd /d "%~dp0"

echo ========================================================
echo   ReVox TTS - Panel de Control Host
echo ========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Verificando instalacion de Python...
    where python >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] No se encontro Python instalado en el sistema.
        echo Por favor instala Python 3.11 ejecutando en PowerShell:
        echo   winget install Python.Python.3.11
        echo.
        pause
        exit /b 1
    )
    echo [INFO] Creando entorno virtual e instalando dependencias...
    python -m venv .venv
    call .venv\Scripts\pip install -r requirements.txt
)

echo [INFO] Iniciando panel en http://127.0.0.1:5050 ...
.venv\Scripts\python panel.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] El panel se cerro con un codigo de error.
    pause
)
