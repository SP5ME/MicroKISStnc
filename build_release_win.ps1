#!/usr/bin/env pwsh
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = "f:/GitHub/MicroKISStnc/.venv/Scripts/python.exe"
$icon = Join-Path $root "Ikona-MicroKISStnc.ico"
$outputDir = Join-Path $root "build"
$outputExe = Join-Path $outputDir "MicroKISStnc_v1.exe"
$tempRoot = Join-Path $outputDir "_pyinstaller_tmp"
$workDir = Join-Path $tempRoot "work"
$specDir = Join-Path $tempRoot "spec"
$cacheDir = Join-Path $tempRoot "cache"

if (-not (Test-Path $python)) { throw "Python interpreter not found: $python" }
if (-not (Test-Path $icon)) { throw "Icon file not found: $icon" }

if (Test-Path $tempRoot) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
}
if (Test-Path $outputDir) {
    Get-ChildItem -LiteralPath $outputDir -Force | Remove-Item -Recurse -Force
} else {
New-Item -ItemType Directory -Path $outputDir | Out-Null
}
New-Item -ItemType Directory -Path $workDir -Force | Out-Null
New-Item -ItemType Directory -Path $specDir -Force | Out-Null
New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null

$previousPyInstallerConfigDir = $env:PYINSTALLER_CONFIG_DIR
$env:PYINSTALLER_CONFIG_DIR = $cacheDir

try {
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name MicroKISStnc_v1 `
    --icon "$icon" `
    --add-data "$icon;." `
    --distpath "$outputDir" `
    --workpath "$workDir" `
    --specpath "$specDir" `
    --hidden-import serial.tools.list_ports `
    --exclude-module matplotlib `
    MicroKISStnc.py

    if (-not (Test-Path $outputExe)) {
        throw "Build finished, but exe was not created: $outputExe"
    }
} finally {
    if ($null -eq $previousPyInstallerConfigDir) {
        Remove-Item Env:PYINSTALLER_CONFIG_DIR -ErrorAction SilentlyContinue
    } else {
        $env:PYINSTALLER_CONFIG_DIR = $previousPyInstallerConfigDir
    }
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host "Build complete: build/MicroKISStnc_v1.exe" -ForegroundColor Green
