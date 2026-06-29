#!/usr/bin/env pwsh
<#
.SYNOPSIS
    NextFlow — One-click pipeline demo runner
.DESCRIPTION
    Sets up a Python venv, installs pydantic, and runs the full 8-phase
    deterministic pipeline against the sample configuration repair case.
.NOTES
    Team: The OneShot | Author: Minh Le | Apache 2.0
#>
$ErrorActionPreference = 'Stop'
Write-Host ""
Write-Host "  NextFlow — Deterministic Pipeline Processing" -ForegroundColor Cyan
Write-Host "  Team: The OneShot / Minh Le" -ForegroundColor DarkGray
Write-Host ""

# Find uv
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "[!] 'uv' not found. Install: https://docs.astral.sh/uv/" -ForegroundColor Yellow
    Write-Host "    Or run: pip install uv" -ForegroundColor Yellow
    exit 1
}

# Create venv
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[*] Creating venv..." -ForegroundColor DarkGray
    & uv venv .venv --python 3.11
    Write-Host "[*] Installing pydantic..." -ForegroundColor DarkGray
    & uv pip install pydantic --python .venv\Scripts\python.exe
}

$python = ".venv\Scripts\python.exe"

Write-Host ""
Write-Host "=== Running full 8-phase pipeline ===" -ForegroundColor Green
Write-Host ""

& $python pipeline\_run_e2e.py cases\sample-config-repair\source

Write-Host ""
Write-Host "Done. Execution trace saved in proof/" -ForegroundColor Green
Write-Host ""
