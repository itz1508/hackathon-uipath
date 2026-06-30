#!/usr/bin/env pwsh
$ErrorActionPreference = 'Stop'

Write-Host "`n  NextFlow — Deterministic Pipeline Processing" -ForegroundColor Cyan
Write-Host "  Team: The OneShot | Minh Le`n" -ForegroundColor DarkGray

# Setup
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Write-Host "  [!] uv required: https://docs.astral.sh/uv/" -ForegroundColor Yellow; exit 1 }
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & uv venv .venv --python 3.11
    & uv pip install pydantic --python .venv\Scripts\python.exe
}

# STEP 1: Play video
Write-Host "  STEP 1: Audisor Execution Flow" -ForegroundColor Green
Start-Process "step-1\Audisor_Execution_Flow.mp4"
Read-Host "`n  Press ENTER when video is done"

# STEP 2: Slide show + pipeline run + evidence
Write-Host "`n  STEP 2: NextFlow Slides + Live Pipeline" -ForegroundColor Cyan

$slides = Get-ChildItem "step-2\NextFlow_Slide_Images" -Filter "*.png" | Sort-Object Name
foreach ($slide in $slides) {
    Start-Process $slide.FullName
    Start-Sleep 3
}

Write-Host "`n  Running pipeline..." -ForegroundColor Green
& .\.venv\Scripts\python.exe pipeline\_run_e2e.py cases\sample-config-repair\source

Write-Host "`n  Opening pipeline evidence..." -ForegroundColor Green
Start-Process (Resolve-Path "docs\reports\pipeline-evidence-terminal.html")
Read-Host "`n  Press ENTER for Step 3"

# STEP 3: Interactive test menu
Write-Host "`n  STEP 3: Try It Yourself" -ForegroundColor Magenta
Start-Process (Resolve-Path "docs\index.html")
Write-Host "  Done. Run any test from the menu.`n" -ForegroundColor Green
