[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$ffmpegPath = Join-Path $projectRoot "tools\ffmpeg\bin\ffmpeg.exe"
$ffprobePath = Join-Path $projectRoot "tools\ffmpeg\bin\ffprobe.exe"
$pipCachePath = Join-Path $projectRoot "runtime\cache\pip"
$tempPath = Join-Path $projectRoot "runtime\temp"
$logPath = Join-Path $projectRoot "runtime\logs"
$runId = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$capabilityLog = Join-Path $logPath "ffmpeg-capabilities-$runId.txt"

foreach ($required in @($pythonPath, $ffmpegPath, $ffprobePath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required project-local executable is missing: $required"
    }
}

New-Item -ItemType Directory -Force -Path $pipCachePath, $tempPath, $logPath | Out-Null
$env:PIP_CACHE_DIR = $pipCachePath
$env:TEMP = $tempPath
$env:TMP = $tempPath
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Assert-Capability {
    param(
        [Parameter(Mandatory = $true)][string] $Name,
        [Parameter(Mandatory = $true)][string] $Text,
        [Parameter(Mandatory = $true)][string] $Pattern
    )

    if ($Text -notmatch $Pattern) {
        throw "Required FFmpeg capability is missing: $Name"
    }
    Write-Output "[PASS] $Name"
}

$ffmpegVersion = (& $ffmpegPath -version 2>&1) -join "`n"
$ffprobeVersion = (& $ffprobePath -version 2>&1) -join "`n"
$encoders = (& $ffmpegPath -hide_banner -encoders 2>&1) -join "`n"
$decoders = (& $ffmpegPath -hide_banner -decoders 2>&1) -join "`n"
$filters = (& $ffmpegPath -hide_banner -filters 2>&1) -join "`n"
$formats = (& $ffmpegPath -hide_banner -formats 2>&1) -join "`n"

@(
    "===== ffmpeg -version =====", $ffmpegVersion,
    "===== ffprobe -version =====", $ffprobeVersion,
    "===== encoders =====", $encoders,
    "===== decoders =====", $decoders,
    "===== filters =====", $filters,
    "===== formats =====", $formats
) | Set-Content -LiteralPath $capabilityLog -Encoding UTF8

Assert-Capability -Name "libx264 encoder" -Text $encoders -Pattern "(?m)^\s*V\S*\s+libx264\s"
Assert-Capability -Name "H.264 decoder" -Text $decoders -Pattern "(?m)^\s*V\S*\s+h264\s"
Assert-Capability -Name "AAC encoder" -Text $encoders -Pattern "(?m)^\s*A\S*\s+aac\s"
Assert-Capability -Name "AAC decoder" -Text $decoders -Pattern "(?m)^\s*A\S*\s+aac\s"
Assert-Capability -Name "subtitles/libass filter" -Text $filters -Pattern "(?m)^\s*\.\S*\s+subtitles\s"
Assert-Capability -Name "ass/libass filter" -Text $filters -Pattern "(?m)^\s*\.\S*\s+ass\s"
Assert-Capability -Name "SRT demux/mux format" -Text $formats -Pattern "(?m)^\s*DE\s+srt\s"
Assert-Capability -Name "WAV demux/mux format" -Text $formats -Pattern "(?m)^\s*DE\s+wav\s"
Assert-Capability -Name "PCM s16le WAV encoder" -Text $encoders -Pattern "(?m)^\s*A\S*\s+pcm_s16le\s"

$h264Amf = $encoders -match "(?m)^\s*V\S*\s+h264_amf\s"
$hevcAmf = $encoders -match "(?m)^\s*V\S*\s+hevc_amf\s"
Write-Output "[INFO] h264_amf advertised: $h264Amf (non-blocking probe only)"
Write-Output "[INFO] hevc_amf advertised: $hevcAmf (non-blocking probe only)"

Write-Output "Running synthetic end-to-end media validation..."
& $pythonPath (Join-Path $PSScriptRoot "media_validation.py")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Output "Running mandatory A/V sync unit and FFmpeg integration tests..."
& $pythonPath -m pytest `
    (Join-Path $projectRoot "tests\test_media_sync.py") `
    (Join-Path $projectRoot "tests\test_media_integration.py") `
    -q
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Output "Media validation completed successfully."
Write-Output "Capability log: $capabilityLog"
Write-Output "System PATH was not modified."
