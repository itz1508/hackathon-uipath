[CmdletBinding()]
param(
    [ValidateSet('apply','cancel','preserve_for_later')][string]$Decision = 'apply',
    [ValidateSet('happy_path','readiness_rejected','simulation_failure')][string]$Scenario = 'happy_path'
)
$Root = Split-Path -Parent $PSScriptRoot
python "$PSScriptRoot\nextflow_demo.py" --repo-root $Root --decision $Decision --scenario $Scenario
exit $LASTEXITCODE
