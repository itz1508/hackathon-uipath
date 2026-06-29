[CmdletBinding()]
param([string]$PackagePath)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
if (-not $PackagePath) {
    $PackagePath = Get-ChildItem (Join-Path $Root 'dist') -Filter '*.nupkg' | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $PackagePath -or -not (Test-Path -LiteralPath $PackagePath)) { throw 'No .nupkg package found.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Archive = [IO.Compression.ZipFile]::OpenRead($PackagePath)
try {
    $Names = $Archive.Entries.FullName
    foreach ($Required in @('NextFlow-Demo.bpmn','NextFlow-RealCase.bpmn','entry-points.json','package-descriptor.json')) {
        if ($Required -notin $Names) { throw "Package is missing $Required" }
    }
    [pscustomobject]@{package=$PackagePath;sha256=(Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash;entries=$Names.Count} | ConvertTo-Json -Compress
} finally {
    $Archive.Dispose()
}
exit 0
