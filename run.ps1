#!/usr/bin/env pwsh
# NextFlow — Judge Demo Runner
# Right-click → Run with PowerShell, or: ./run.ps1
$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "  NextFlow — Deterministic Pipeline Processing" -ForegroundColor Cyan
Write-Host "  Team: The OneShot | Minh Le" -ForegroundColor DarkGray
Write-Host ""

# Setup
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  [!] 'uv' required: https://docs.astral.sh/uv/" -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "  [setup] Creating venv + installing pydantic..." -ForegroundColor DarkGray
    & uv venv .venv --python 3.11
    & uv pip install pydantic --python .venv\Scripts\python.exe
    Write-Host ""
}

# ═══════════════════════════════════════════════════════
# STEP 1: Run pipeline → open evidence
# ═══════════════════════════════════════════════════════
Write-Host "  ┌─────────────────────────────────────────┐" -ForegroundColor Green
Write-Host "  │  STEP 1: Run Pipeline (clean input)     │" -ForegroundColor Green
Write-Host "  └─────────────────────────────────────────┘" -ForegroundColor Green
Write-Host ""

& .\.venv\Scripts\python.exe pipeline\_run_e2e.py cases\sample-config-repair\source

Write-Host ""
Write-Host "  Opening pipeline evidence..." -ForegroundColor DarkGray
Start-Process (Resolve-Path "docs\reports\pipeline-evidence-terminal.html")

Write-Host ""
Read-Host "  Press ENTER for Step 2"

# ═══════════════════════════════════════════════════════
# STEP 2: Show the slide
# ═══════════════════════════════════════════════════════
Write-Host "  ┌─────────────────────────────────────────┐" -ForegroundColor Cyan
Write-Host "  │  STEP 2: NextFlow Architecture          │" -ForegroundColor Cyan
Write-Host "  └─────────────────────────────────────────┘" -ForegroundColor Cyan
Write-Host ""

Start-Process (Resolve-Path "NextFlow-Slide.png")
Write-Host "  Slide opened. Review the 8-phase architecture." -ForegroundColor DarkGray

Write-Host ""
Read-Host "  Press ENTER for Step 3"

# ═══════════════════════════════════════════════════════
# STEP 3: Open test menu → judge runs tests themselves
# ═══════════════════════════════════════════════════════
Write-Host "  ┌─────────────────────────────────────────┐" -ForegroundColor Magenta
Write-Host "  │  STEP 3: Try It Yourself                │" -ForegroundColor Magenta
Write-Host "  └─────────────────────────────────────────┘" -ForegroundColor Magenta
Write-Host ""
Write-Host "  Opening test menu — pick any test and run it." -ForegroundColor DarkGray

Start-Process (Resolve-Path "docs\index.html")

Write-Host ""
Write-Host "  Done. Copy commands from the page and run in this terminal." -ForegroundColor Green
Write-Host ""
