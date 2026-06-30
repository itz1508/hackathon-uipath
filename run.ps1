#!/usr/bin/env pwsh
# NextFlow — One-click demo for judges
# Right-click → Run with PowerShell, or: ./run.ps1
$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║  NextFlow — Deterministic Pipeline Processing       ║" -ForegroundColor Cyan
Write-Host "  ║  Team: The OneShot | Minh Le | Apache 2.0           ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Setup
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  [!] 'uv' required. Install: https://docs.astral.sh/uv/" -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "  [setup] Creating venv + installing pydantic..." -ForegroundColor DarkGray
    & uv venv .venv --python 3.11
    & uv pip install pydantic --python .venv\Scripts\python.exe
    Write-Host ""
}

# Step 1
Write-Host "  ── Step 1: Clean input (fully_resolved) ──" -ForegroundColor Green
& .\.venv\Scripts\python.exe pipeline\_run_e2e.py cases\sample-config-repair\source
Write-Host ""
Read-Host "  Press ENTER to continue to Step 2"

# Step 2
Write-Host "  ── Step 2: Mixed input (partially_resolved) ──" -ForegroundColor Green
& .\.venv\Scripts\python.exe pipeline\_run_e2e.py pipeline\tests\fixtures\fixture-g-mixed
Write-Host ""
Read-Host "  Press ENTER to continue to Step 3"

# Step 3
Write-Host "  ── Step 3: Chaos input — 10 failure modes ──" -ForegroundColor Green
& .\.venv\Scripts\python.exe pipeline\_run_e2e.py pipeline\tests\fixtures\fixture-chaos-10
Write-Host ""

Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║  Done. All 3 runs complete.                         ║" -ForegroundColor Green
Write-Host "  ║  Execution traces: ./proof/                         ║" -ForegroundColor Green
Write-Host "  ║  Live reports: itz1508.github.io/hackathon-uipath   ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
