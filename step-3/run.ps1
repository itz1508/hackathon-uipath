#!/usr/bin/env pwsh
# Step 3: Run pipeline on CHAOS input (10 different failure modes)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "`n  STEP 3: Pipeline on chaos input — 10 failure modes (expect: partially_resolved)" -ForegroundColor Cyan
Write-Host "  ─────────────────────────────────────────────────────────────────────────────────`n"

$python = "$Root\.venv\Scripts\python.exe"
& $python "$Root\pipeline\_run_e2e.py" "$Root\pipeline\tests\fixtures\fixture-chaos-10"

Write-Host "`n  ✓ Step 3 complete — deterministic handling of 10 failure types" -ForegroundColor Green
Write-Host "  Execution traces saved in proof/" -ForegroundColor DarkGray
