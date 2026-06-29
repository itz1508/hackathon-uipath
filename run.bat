@echo off
echo ============================================
echo  NextFlow - Deterministic Pipeline Processing
echo  Team: The OneShot / Minh Le
echo ============================================
echo.

:: Check for uv
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 'uv' not found. Installing via pip...
    pip install uv 2>nul || (
        echo [X] Please install uv: https://docs.astral.sh/uv/getting-started/installation/
        pause
        exit /b 1
    )
)

:: Create venv if not exists
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating virtual environment...
    uv venv .venv --python 3.11
    echo [*] Installing dependencies...
    uv pip install pydantic --python .venv\Scripts\python.exe
)

echo.
echo [*] Running 8-phase pipeline on sample case...
echo.
.venv\Scripts\python.exe pipeline\_run_e2e.py cases\sample-config-repair\source

echo.
echo ============================================
echo  Done. Check proof\ for execution trace.
echo ============================================
pause
