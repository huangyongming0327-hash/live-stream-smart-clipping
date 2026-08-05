[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Get-LiveClipCommandSource {
    param([Parameter(Mandatory = $true)][object] $Candidate)

    if ($Candidate -is [string]) {
        return [string] $Candidate
    }
    foreach ($propertyName in @("Source", "Path", "Definition")) {
        $property = $Candidate.PSObject.Properties[$propertyName]
        if ($null -ne $property -and -not [string]::IsNullOrWhiteSpace([string] $property.Value)) {
            return [string] $property.Value
        }
    }
    return $null
}

function Resolve-LiveClipPython {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string] $RepositoryRoot,
        [AllowEmptyString()][string] $AssetsRoot = "",
        [object[]] $CommandCandidates
    )

    $projectPython = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $projectPython -PathType Leaf) {
        return (Resolve-Path -LiteralPath $projectPython).Path
    }

    if (-not [string]::IsNullOrWhiteSpace($AssetsRoot)) {
        $assetsPython = Join-Path $AssetsRoot ".venv\Scripts\python.exe"
        if (Test-Path -LiteralPath $assetsPython -PathType Leaf) {
            return (Resolve-Path -LiteralPath $assetsPython).Path
        }
    }

    if (-not $PSBoundParameters.ContainsKey("CommandCandidates")) {
        $CommandCandidates = @(
            Get-Command python -All -CommandType Application -ErrorAction SilentlyContinue
        )
    }
    foreach ($candidate in @($CommandCandidates)) {
        if ($null -eq $candidate) {
            continue
        }
        $candidatePath = Get-LiveClipCommandSource -Candidate $candidate
        if (
            [string]::IsNullOrWhiteSpace($candidatePath) -or
            $candidatePath -match "(?i)[\\/]WindowsApps[\\/]" -or
            -not (Test-Path -LiteralPath $candidatePath -PathType Leaf)
        ) {
            continue
        }
        return (Resolve-Path -LiteralPath $candidatePath).Path
    }

    throw (
        "Python was not found. LiveClip checked the repository .venv, the " +
        "LIVECLIP_ASSETS_ROOT .venv, and real python applications; WindowsApps " +
        "aliases are ignored automatically."
    )
}

function Resolve-LiveClipAssetsRoot {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string] $RepositoryRoot,
        [Parameter(Mandatory = $true)][ValidateSet("paraformer", "sensevoice")]
        [string] $AsrModel,
        [AllowEmptyString()][string] $ConfiguredRoot = ""
    )

    if (-not [string]::IsNullOrWhiteSpace($ConfiguredRoot)) {
        return [IO.Path]::GetFullPath($ConfiguredRoot)
    }

    $missing = [System.Collections.Generic.List[string]]::new()
    $ffmpeg = Join-Path $RepositoryRoot "tools\ffmpeg\bin\ffmpeg.exe"
    $ffprobe = Join-Path $RepositoryRoot "tools\ffmpeg\bin\ffprobe.exe"
    if (
        -not (Test-Path -LiteralPath $ffmpeg -PathType Leaf) -or
        -not (Test-Path -LiteralPath $ffprobe -PathType Leaf)
    ) {
        $missing.Add("FFmpeg/ffprobe")
    }

    if ($AsrModel -eq "sensevoice") {
        $requiredModelFiles = @(
            "模型\asr\sensevoice-small\model.int8.onnx",
            "模型\asr\sensevoice-small\tokens.txt",
            "模型\asr\sensevoice-small\silero_vad.onnx"
        )
        $modelLabel = "SenseVoice model"
    }
    else {
        $requiredModelFiles = @(
            "模型\asr\paraformer-zh\model.pt",
            "模型\asr\paraformer-zh\config.yaml",
            "模型\asr\fsmn-vad\model.pt",
            "模型\asr\fsmn-vad\config.yaml",
            "模型\asr\ct-punc\model.pt",
            "模型\asr\ct-punc\config.yaml"
        )
        $modelLabel = "Paraformer model"
    }
    if (@($requiredModelFiles | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $RepositoryRoot $_) -PathType Leaf)
    }).Count -gt 0) {
        $missing.Add($modelLabel)
    }

    if ($missing.Count -gt 0) {
        $example = '[Environment]::SetEnvironmentVariable("LIVECLIP_ASSETS_ROOT", "<包含模型、FFmpeg和ASR环境的目录>", "User")'
        throw (
            "LIVECLIP_ASSETS_ROOT is not configured, and repository-local assets are " +
            "missing: $($missing -join ', '). Set it in PowerShell with: $example"
        )
    }
    return [IO.Path]::GetFullPath($RepositoryRoot)
}

function Invoke-LiveClipLauncher {
    $repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

    try {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = [System.Windows.Forms.OpenFileDialog]::new()
        try {
            $dialog.Title = "Select one MP4 for LiveClip"
            $dialog.Filter = "MP4 video (*.mp4)|*.mp4"
            $dialog.Multiselect = $false
            $dialog.CheckFileExists = $true
            $selection = $dialog.ShowDialog()
            if ($selection -ne [System.Windows.Forms.DialogResult]::OK) {
                Write-Output "No video selected. LiveClip exited normally."
                exit 0
            }
            $videoPath = $dialog.FileName
        }
        finally {
            $dialog.Dispose()
        }

        $choices = @(
            [System.Management.Automation.Host.ChoiceDescription]::new(
                "&Paraformer (recommended)",
                "Default local model with Chinese quality priority."
            ),
            [System.Management.Automation.Host.ChoiceDescription]::new(
                "&SenseVoice (low resource)",
                "Local fallback model with lower memory usage."
            )
        )
        $choice = $Host.UI.PromptForChoice(
            "Select ASR model",
            "Choose the local speech recognition model:",
            $choices,
            0
        )
        $asrModel = if ($choice -eq 1) { "sensevoice" } else { "paraformer" }
        $configuredAssetsRoot = if (
            [string]::IsNullOrWhiteSpace($env:LIVECLIP_ASSETS_ROOT)
        ) { "" } else { $env:LIVECLIP_ASSETS_ROOT }
        $assetsRoot = Resolve-LiveClipAssetsRoot `
            -RepositoryRoot $repositoryRoot `
            -AsrModel $asrModel `
            -ConfiguredRoot $configuredAssetsRoot
        $python = Resolve-LiveClipPython `
            -RepositoryRoot $repositoryRoot `
            -AssetsRoot $assetsRoot

        $originalPythonPath = $env:PYTHONPATH
        $sourceRoot = Join-Path $repositoryRoot "src"
        $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($originalPythonPath)) {
            $sourceRoot
        }
        else {
            $sourceRoot + [IO.Path]::PathSeparator + $originalPythonPath
        }
        try {
            Push-Location -LiteralPath $repositoryRoot
            try {
                & $python -m liveclip run --video $videoPath --asr-model $asrModel
                $exitCode = $LASTEXITCODE
            }
            finally {
                Pop-Location
            }
        }
        finally {
            $env:PYTHONPATH = $originalPythonPath
        }

        if ($exitCode -ne 0) {
            Write-Output "LiveClip failed with exit code $exitCode."
        }
        exit $exitCode
    }
    catch {
        $message = ($_.Exception.Message -split "\r?\n") -join " "
        Write-Output "LiveClip launcher failed: $message"
        exit 1
    }
}

if ($MyInvocation.InvocationName -ne ".") {
    Invoke-LiveClipLauncher
}
