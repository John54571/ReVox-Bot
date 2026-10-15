# Script to create a Windows Desktop shortcut with custom icon
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [System.Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "ReVox Control Panel.lnk"
$targetPath = Join-Path $scriptDir "iniciar_panel.bat"
$iconPath = Join-Path $scriptDir "web\logo.ico"

# If logo.ico does not exist, generate it from logo.png with ffmpeg if available
if (-not (Test-Path $iconPath) -and (Test-Path (Join-Path $scriptDir "web\logo.png"))) {
    try {
        & ffmpeg -y -i (Join-Path $scriptDir "web\logo.png") -vf "scale=256:256" $iconPath 2>$null
    } catch {}
}

Write-Host "Creating desktop shortcut..." -ForegroundColor Cyan

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $scriptDir
$shortcut.Description = "Launch ReVox TTS Control Panel"

if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}

$shortcut.Save()

Write-Host "Shortcut created successfully at:" -ForegroundColor Green
Write-Host "  $shortcutPath" -ForegroundColor Yellow
