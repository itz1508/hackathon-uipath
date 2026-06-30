[CmdletBinding(SupportsShouldProcess, ConfirmImpact='High')]
param([string]$RunRoot = (Join-Path $env:TEMP 'nextflow-demo-runs'))
$Temp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
$Target = [IO.Path]::GetFullPath($RunRoot).TrimEnd('\')
if (-not $Target.StartsWith($Temp + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to reset outside the user temp directory: $Target"
}
if ((Test-Path -LiteralPath $Target) -and $PSCmdlet.ShouldProcess($Target, 'Remove NextFlow demo runs')) {
    Remove-Item -LiteralPath $Target -Recurse -Force
}
