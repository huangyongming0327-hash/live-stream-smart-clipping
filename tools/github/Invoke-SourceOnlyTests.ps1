[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$stageResults = [System.Collections.Generic.List[object]]::new()
$originalPythonIoEncoding = $env:PYTHONIOENCODING
$originalPythonUtf8 = $env:PYTHONUTF8
$failureRecord = $null

function Invoke-CheckedNativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Stage,

        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    Write-Output "SOURCE_ONLY_STAGE_START=$Stage"
    & python @Arguments
    $exitCode = $LASTEXITCODE
    $stageResults.Add([pscustomobject]@{
        stage = $Stage
        exit_code = $exitCode
    })
    Write-Output "SOURCE_ONLY_STAGE_EXIT=${Stage}:$exitCode"

    if ($exitCode -ne 0) {
        throw "Source-only stage '$Stage' failed with exit code $exitCode."
    }
}

try {
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"
    Push-Location -LiteralPath $repositoryRoot
    try {
        Invoke-CheckedNativeCommand -Stage "base-schema-media" -Arguments @(
            "-m", "pytest", ".\tests",
            "--ignore", ".\tests\test_media_integration.py",
            "--ignore", ".\tests\test_ffmpeg_install_source.py",
            "-k", "not probe_corrupt_file_returns_clear_error"
        )
        Invoke-CheckedNativeCommand -Stage "asr-experiments" -Arguments @(
            "-m", "pytest", ".\experiments\asr\tests",
            "-k", "not existing_399_sentence_info_result_is_byte_for_byte_reproducible"
        )
        Invoke-CheckedNativeCommand -Stage "pip-check" -Arguments @(
            "-m", "pip", "check"
        )
    }
    finally {
        Pop-Location
    }
}
catch {
    $failureRecord = $_
}
finally {
    $env:PYTHONIOENCODING = $originalPythonIoEncoding
    $env:PYTHONUTF8 = $originalPythonUtf8
}

$summary = [ordered]@{
    status = if ($null -eq $failureRecord) { "passed" } else { "failed" }
    stages = @($stageResults)
}
Write-Output ("SOURCE_ONLY_RESULT=" + ($summary | ConvertTo-Json -Depth 4 -Compress))
if ($null -ne $failureRecord) {
    throw $failureRecord
}
