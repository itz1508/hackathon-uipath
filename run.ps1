#!/usr/bin/env pwsh
# NextFlow — Judge Demo Runner
# Right-click → Run with PowerShell, or: ./run.ps1
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║  NextFlow — Deterministic Pipeline Processing       ║" -ForegroundColor Cyan
Write-Host "  ║  Team: The OneShot | Minh Le                        ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Setup venv if needed
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  [!] 'uv' required: https://docs.astral.sh/uv/" -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
    Write-Host "  [setup] Creating venv + installing pydantic..." -ForegroundColor DarkGray
    & uv venv "$Root\.venv" --python 3.11
    & uv pip install pydantic --python "$Root\.venv\Scripts\python.exe"
    Write-Host ""
}

$python = "$Root\.venv\Scripts\python.exe"

# ═══════════════════════════════════════════════
# STEP 1: Run Pipeline → Show Evidence
# ═══════════════════════════════════════════════
Write-Host "  ┌─────────────────────────────────────────────────────┐" -ForegroundColor Green
Write-Host "  │  STEP 1: Run 8-phase pipeline on sample config      │" -ForegroundColor Green
Write-Host "  └─────────────────────────────────────────────────────┘" -ForegroundColor Green
Write-Host ""

& $python "$Root\pipeline\_run_e2e.py" "$Root\cases\sample-config-repair\source"

Write-Host ""
Write-Host "  Opening pipeline evidence in browser..." -ForegroundColor DarkGray
Start-Process "$Root\docs\reports\pipeline-evidence-terminal.html"
Write-Host ""
Read-Host "  Press ENTER for Step 2"

# ═══════════════════════════════════════════════
# STEP 2: Open NextFlow Slide Deck
# ═══════════════════════════════════════════════
Write-Host "  ┌─────────────────────────────────────────────────────┐" -ForegroundColor Cyan
Write-Host "  │  STEP 2: NextFlow Presentation Deck                 │" -ForegroundColor Cyan
Write-Host "  └─────────────────────────────────────────────────────┘" -ForegroundColor Cyan
Write-Host ""

Start-Process "$Root\NextFlow_Deck.pptx"
Write-Host "  Opened slide deck." -ForegroundColor DarkGray
Write-Host ""
Read-Host "  Press ENTER for Step 3"

# ═══════════════════════════════════════════════
# STEP 3: Open Test Runner (judge explores)
# ═══════════════════════════════════════════════
Write-Host "  ┌─────────────────────────────────────────────────────┐" -ForegroundColor Yellow
Write-Host "  │  STEP 3: Interactive — run tests yourself            │" -ForegroundColor Yellow
Write-Host "  └─────────────────────────────────────────────────────┘" -ForegroundColor Yellow
Write-Host ""

Start-Process "$Root\docs\index.html"
Write-Host "  Opened test runner in browser. Try the different scenarios!" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║  Demo complete. Thank you for reviewing NextFlow!   ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
