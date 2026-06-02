$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
& "f:/GitHub/MicroKISStnc/.venv/Scripts/python.exe" "MicroKISStnc.py"
