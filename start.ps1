#!/usr/bin/env pwsh
# ============================================================================
# MicroKISStnc public v1 - PowerShell Startup Script
# ============================================================================

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "MicroKISStnc public v1 - APRS TNC Desktop Application" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Check if .venv exists
if (-not (Test-Path ".venv")) {
    Write-Host "[SETUP] Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    Write-Host "[SETUP] Activating and installing dependencies..." -ForegroundColor Yellow
    & ".\.venv\Scripts\Activate.ps1"
    pip install -q -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    Write-Host "[SETUP] Setup complete!" -ForegroundColor Green
}

# Activate environment
& ".\.venv\Scripts\Activate.ps1"

Write-Host "[RUN] Starting MicroKISStnc public v1..." -ForegroundColor Green
Write-Host ""
Write-Host ""

# Run the app
python MicroKISStnc_dev.py

Read-Host "Press Enter to exit"
