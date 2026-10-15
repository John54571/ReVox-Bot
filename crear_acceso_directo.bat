@echo off
title Create Desktop Shortcut - ReVox
cd /d "%~dp0"

echo [INFO] Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0crear_acceso_directo.ps1"

echo.
pause
