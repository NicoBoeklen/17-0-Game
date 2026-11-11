$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "Starte NFL Build A 17-0 Team (Saison 2026/2027) auf http://127.0.0.1:8000 ..." -ForegroundColor Cyan
python start.py
