[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PytestArgs = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pipCachePath = Join-Path $projectRoot "runtime\cache\pip"
$tempPath = Join-Path $projectRoot "runtime\temp"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Project Python was not found: $pythonPath"
}

New-Item -ItemType Directory -Force -Path $pipCachePath, $tempPath | Out-Null

$env:PIP_CACHE_DIR = $pipCachePath
$env:TEMP = $tempPath
$env:TMP = $tempPath
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

Write-Output "Project Python: $pythonPath"
Write-Output "PIP_CACHE_DIR: $env:PIP_CACHE_DIR"
Write-Output "TEMP/TMP: $env:TEMP"

& $pythonPath -m pytest @PytestArgs
$testExitCode = $LASTEXITCODE
if ($testExitCode -ne 0) {
    exit $testExitCode
}

& $pythonPath -m pip check
$pipCheckExitCode = $LASTEXITCODE
if ($pipCheckExitCode -ne 0) {
    exit $pipCheckExitCode
}
