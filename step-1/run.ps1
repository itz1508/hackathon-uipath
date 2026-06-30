#!/usr/bin/env pwsh
# Step 1: Setup environment and run pipeline on CLEAN input (fully resolved)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "`n  STEP 1: Pipeline on clean config (expect: fully_resolved)" -ForegroundColor Cyan
Write-Host "  ─────────────────────────────────────────────────────────`n"

# Setup venv if needed
if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
    Write-Host "  [setup] Creating venv..." -ForegroundColor DarkGray
    & uv venv "$Root\.venv" --python 3.11
    & uv pip install pydantic --python "$Root\.venv\Scripts\python.exe"
}

$python = "$Root\.venv\Scripts\python.exe"
& $python "$Root\pipeline\_run_e2e.py" "$Root\cases\sample-config-repair\source"

Write-Host "`n  ✓ Step 1 complete" -ForegroundColor Green
