# Script para crear acceso directo en el Escritorio de Windows con icono personalizado
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [System.Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "ReVox Control Panel.lnk"
$targetPath = Join-Path $scriptDir "iniciar_panel.bat"
$iconPath = Join-Path $scriptDir "web\logo.ico"

# Si no existe logo.ico, generarlo desde logo.png con ffmpeg si está disponible
if (-not (Test-Path $iconPath) -and (Test-Path (Join-Path $scriptDir "web\logo.png"))) {
    try {
        & ffmpeg -y -i (Join-Path $scriptDir "web\logo.png") -vf "scale=256:256" $iconPath 2>$null
    } catch {}
}

Write-Host "Creando acceso directo en el Escritorio..." -ForegroundColor Cyan

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $scriptDir
$shortcut.Description = "Iniciar ReVox TTS Control Panel"

if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}

$shortcut.Save()

Write-Host "Acceso directo creado con exito en:" -ForegroundColor Green
Write-Host "  $shortcutPath" -ForegroundColor Yellow
