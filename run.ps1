# run.ps1
# Mode A: pause/resume between steps. No auto-advance.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# ---------- Setup ----------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv required: https://docs.astral.sh/uv/"
}
if (-not (Test-Path (Join-Path $root ".venv\Scripts\python.exe"))) {
    & uv venv (Join-Path $root ".venv") --python 3.11
    if ($LASTEXITCODE -ne 0) { throw "uv venv failed (exit $LASTEXITCODE)" }
    & uv pip install pydantic --python (Join-Path $root ".venv\Scripts\python.exe")
    if ($LASTEXITCODE -ne 0) { throw "uv pip install failed (exit $LASTEXITCODE)" }
}
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Python interpreter not found after setup: $python" }

# ---------- STEP 1: Video ----------
Write-Host "`n=== STEP 1: Audisor Execution Flow (video) ===" -ForegroundColor Cyan
$video = Join-Path $root "step-1\Audisor_Execution_Flow.mp4"
if (-not (Test-Path $video)) { throw "Missing: $video" }
Start-Process $video
Read-Host "Press ENTER to continue to Step 2"

# ---------- STEP 2: Slideshow + Pipeline + Evidence ----------
Write-Host "`n=== STEP 2: Slides + Pipeline run + Evidence ===" -ForegroundColor Cyan
$slideDir = Join-Path $root "step-2\NextFlow_Slide_Images"
$slideshowPath = Join-Path $root "step-2\slideshow.html"

if (-not (Test-Path $slideDir)) { throw "Missing slide directory: $slideDir" }

# Build slideshow.html (auto-cycle 12 PNGs, 3s each)
$imgTags = (1..12 | ForEach-Object { "Slide_{0:D2}.png" -f $_ }) -join "','"
$slideshowHtml = @"
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>NextFlow Slides</title>
<style>
  body{margin:0;background:#000;display:flex;align-items:center;justify-content:center;height:100vh;}
  img{max-width:100%;max-height:100%;}
</style></head>
<body>
<img id="slide" src="NextFlow_Slide_Images/Slide_01.png">
<script>
  const imgs = ['$imgTags'];
  let i = 0;
  setInterval(() => {
    i = (i + 1) % imgs.length;
    document.getElementById('slide').src = 'NextFlow_Slide_Images/' + imgs[i];
  }, 3000);
</script>
</body></html>
"@
Set-Content -Path $slideshowPath -Value $slideshowHtml -Encoding UTF8

Start-Process $slideshowPath

# Run pipeline (positional arg: target_path)
$pipelineScript = Join-Path $root "system\pipeline\_run_e2e.py"
$caseSource = Join-Path $root "system\cases\sample-config-repair\source"
if (-not (Test-Path $pipelineScript)) { throw "Missing pipeline script: $pipelineScript" }
if (-not (Test-Path $caseSource)) { throw "Missing case source: $caseSource" }

Write-Host "Running pipeline..." -ForegroundColor Green
& $python $pipelineScript $caseSource
if ($LASTEXITCODE -ne 0) {
    Write-Host "Pipeline exited non-zero ($LASTEXITCODE)." -ForegroundColor Red
}

$evidence = Join-Path $root "step-3\pipeline-evidence-terminal.html"
if (-not (Test-Path $evidence)) { throw "Missing: $evidence" }
Start-Process $evidence

Read-Host "Press ENTER to continue to Step 3"

# ---------- STEP 3: Test menu ----------
Write-Host "`n=== STEP 3: Try It Yourself ===" -ForegroundColor Cyan
$index = Join-Path $root "step-3\index.html"
if (-not (Test-Path $index)) { throw "Missing: $index" }
Start-Process $index
Write-Host "Done." -ForegroundColor Green
