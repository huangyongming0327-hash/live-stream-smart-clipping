[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

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

    $projectPython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $projectPython -PathType Leaf) {
        $python = $projectPython
    }
    elseif (-not [string]::IsNullOrWhiteSpace($env:LIVECLIP_ASSETS_ROOT)) {
        $assetsPython = Join-Path $env:LIVECLIP_ASSETS_ROOT ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $assetsPython -PathType Leaf)) {
            throw "LIVECLIP_ASSETS_ROOT does not contain .venv\\Scripts\\python.exe."
        }
        $python = $assetsPython
    }
    else {
        $pythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue
        if ($null -eq $pythonCommand) {
            throw "Python was not found. Configure the project Python environment first."
        }
        $python = $pythonCommand.Source
    }

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
