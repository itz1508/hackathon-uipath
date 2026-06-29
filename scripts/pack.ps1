[CmdletBinding()]
param([string]$Version = '1.0.0')
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Project = Join-Path $Root 'maestro\NextFlow-RealCase-Template'
$Dist = Join-Path $Root 'dist'
New-Item -ItemType Directory -Path $Dist -Force | Out-Null
uip maestro bpmn pack $Project $Dist -v $Version
exit $LASTEXITCODE
