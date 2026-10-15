@echo off
title Crear Acceso Directo - ReVox
cd /d "%~dp0"

echo [INFO] Creando acceso directo en el Escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0crear_acceso_directo.ps1"

echo.
pause
