#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Run pip-audit with --fix to auto-upgrade vulnerable dependencies, then regenerate the report.

.DESCRIPTION
  1. Runs pip-audit --fix to upgrade any packages with known vulnerabilities
  2. Regenerates pip-audit-report.json with current state
  3. Shows summary of findings

.EXAMPLE
  .\scripts\audit-fix.ps1
#>

$ErrorActionPreference = "Continue"
$Python = Join-Path $PSScriptRoot ".." ".venv" "Scripts" "python.exe"
if (-not (Test-Path $Python)) {
    # Fallback: try Edge venv via environment variable
    $EdgeRoot = $env:EDGE_ROOT
    if ($EdgeRoot) { $Python = Join-Path $EdgeRoot ".venv" "Scripts" "python.exe" }
    else { $Python = "python" }
}
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== Pip Audit: Fix Vulnerabilities ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Run pip-audit --fix
Write-Host "[1/3] Running pip-audit --fix..." -ForegroundColor Yellow
& $Python -m pip_audit --fix
$fixExitCode = $LASTEXITCODE

if ($fixExitCode -eq 0) {
    Write-Host "  No vulnerabilities found or all fixed." -ForegroundColor Green
} else {
    Write-Host "  Some issues may remain (exit code: $fixExitCode)" -ForegroundColor Red
}

Write-Host ""

# Step 2: Regenerate report
Write-Host "[2/3] Regenerating pip-audit-report.json..." -ForegroundColor Yellow
& $Python -m pip_audit --format json --output "$ProjectRoot\pip-audit-report.json"
Write-Host "  Report saved to pip-audit-report.json" -ForegroundColor Green

Write-Host ""

# Step 3: Show summary
Write-Host "[3/3] Current vulnerability status:" -ForegroundColor Yellow
& $Python -m pip_audit
$finalExitCode = $LASTEXITCODE

Write-Host ""
if ($finalExitCode -eq 0) {
    Write-Host "=== ALL CLEAR: No known vulnerabilities ===" -ForegroundColor Green
} else {
    Write-Host "=== WARNING: Vulnerabilities remain — review pip-audit-report.json ===" -ForegroundColor Red
}

exit $finalExitCode
