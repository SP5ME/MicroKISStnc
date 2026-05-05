#!/usr/bin/env pwsh
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = "f:/GitHub/MicroKISStnc/.venv/Scripts/python.exe"
$icon = Join-Path $root "Ikona-MicroKISStnc.ico"

if (-not (Test-Path $python)) {
    Write-Error "Python interpreter not found: $python"
}

if (-not (Test-Path $icon)) {
    Write-Error "Icon file not found: $icon"
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name MicroKISStnc_public_v1 `
    --icon "$icon" `
    --add-data "$icon;." `
    --distpath "release/win" `
    --workpath "build/pyinstaller" `
    --specpath "build/pyinstaller-spec" `
    --hidden-import serial.tools.list_ports `
    --exclude-module matplotlib `
    MicroKISStnc_dev.py

Write-Host "Build complete: release/win/MicroKISStnc_public_v1.exe" -ForegroundColor Green
