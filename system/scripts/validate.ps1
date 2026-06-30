[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    python -m pytest tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    foreach ($File in @(
        '.\maestro\NextFlow-RealCase-Template\NextFlow-Demo.bpmn',
        '.\maestro\NextFlow-RealCase-Template\NextFlow-RealCase.bpmn'
    )) {
        uip maestro bpmn validate $File
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
} finally {
    Pop-Location
}
