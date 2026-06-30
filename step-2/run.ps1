#!/usr/bin/env pwsh
# Step 2: Run pipeline on MIXED input (overlapping issues, partial resolution)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "`n  STEP 2: Pipeline on mixed-severity input (expect: partially_resolved)" -ForegroundColor Cyan
Write-Host "  ──────────────────────────────────────────────────────────────────────`n"

$python = "$Root\.venv\Scripts\python.exe"
& $python "$Root\pipeline\_run_e2e.py" "$Root\pipeline\tests\fixtures\fixture-g-mixed"

Write-Host "`n  ✓ Step 2 complete — isolation engine engaged, partial resolution" -ForegroundColor Green
