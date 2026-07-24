[CmdletBinding()]
param(
    [string] $RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),

    [ValidateSet("All", "Tracked", "PublishCandidates")]
    [string] $Scope = "All"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$root = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$gitDirectory = Join-Path $root ".git"
$rootPrefix = $root.TrimEnd("\") + "\"
$issues = [System.Collections.Generic.List[object]]::new()
$scanned = 0
$textFiles = 0
$maxBytes = 5MB

$forbiddenExtensions = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)
@(
    ".mp4", ".mkv", ".mov", ".flv", ".avi", ".wav", ".mp3", ".aac",
    ".m4a", ".m4v", ".wmv", ".mpeg", ".mpg", ".ts", ".m2ts", ".webm",
    ".ogg", ".flac", ".wma", ".bin", ".safetensors", ".onnx", ".pt",
    ".pth", ".ckpt", ".gguf", ".ggml", ".tflite", ".exe", ".dll",
    ".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".pfx", ".p12",
    ".ppk", ".pem", ".key", ".jks", ".keystore", ".kdbx"
) | ForEach-Object { [void] $forbiddenExtensions.Add($_) }

function Add-Issue {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Rule
    )

    $issues.Add([pscustomobject]@{
        path = $Path
        rule = $Rule
    })
}

function Get-RepositoryFiles {
    if ($Scope -eq "All") {
        return @(
            Get-ChildItem -LiteralPath $root -File -Recurse -Force |
                Where-Object {
                    -not $_.FullName.StartsWith(
                        $gitDirectory + [IO.Path]::DirectorySeparatorChar,
                        [StringComparison]::OrdinalIgnoreCase
                    )
                } |
                ForEach-Object {
                    [pscustomobject]@{
                        Relative = $_.FullName.Substring($rootPrefix.Length).Replace("\", "/")
                        FullName = $_.FullName
                    }
                }
        )
    }

    if (-not (Test-Path -LiteralPath $gitDirectory)) {
        throw "Scope '$Scope' requires an initialized Git repository."
    }

    $arguments = @("-c", "core.quotepath=false", "-C", $root, "ls-files")
    if ($Scope -eq "PublishCandidates") {
        $arguments += @("--cached", "--others", "--exclude-standard")
    }
    $relativeFiles = @(& git @arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "git ls-files failed."
    }

    return @(
        $relativeFiles |
            Where-Object { $_ } |
            Sort-Object -Unique |
            ForEach-Object {
                [pscustomobject]@{
                    Relative = $_.Replace("\", "/")
                    FullName = Join-Path $root $_
                }
            } |
            Where-Object { Test-Path -LiteralPath $_.FullName -PathType Leaf }
    )
}

$files = @(Get-RepositoryFiles)
$utf8Strict = [System.Text.UTF8Encoding]::new($false, $true)
$privateKeyPrefix = ("-" * 5) + "BEGIN "
$posixHomePattern = "(?i)(" + "/" + "Users/[^/\s]+|" + "/" + "home/[^/\s]+)"

foreach ($file in $files) {
    $relative = $file.Relative
    $fullName = $file.FullName
    $scanned++

    if ($relative -match "(?i)(^|/)(\.venv|runtime|tools/ffmpeg|tools/asr|模型|项目|设置|__pycache__|\.pytest_cache)(/|$)") {
        Add-Issue -Path $relative -Rule "forbidden-path"
    }

    $leafName = [IO.Path]::GetFileName($relative)
    if (
        $leafName -match "(?i)^\.env($|\.)" -or
        $leafName -match "(?i)(secret|credential|token|private[-_]?key)" -and
        $leafName -notmatch "(?i)\.(md|ps1|py)$"
    ) {
        Add-Issue -Path $relative -Rule "secret-like-filename"
    }

    $extension = [IO.Path]::GetExtension($relative)
    if ($forbiddenExtensions.Contains($extension)) {
        Add-Issue -Path $relative -Rule "forbidden-extension"
    }

    $item = Get-Item -LiteralPath $fullName
    if ($item.Length -gt $maxBytes) {
        Add-Issue -Path $relative -Rule "file-over-5-mib"
        continue
    }

    $bytes = [IO.File]::ReadAllBytes($fullName)
    if ([Array]::IndexOf($bytes, [byte] 0) -ge 0) {
        Add-Issue -Path $relative -Rule "nul-byte"
        continue
    }

    try {
        $content = $utf8Strict.GetString($bytes)
        $textFiles++
    }
    catch {
        Add-Issue -Path $relative -Rule "non-utf8-text"
        continue
    }

    if ($content -match "(?i)C:\\Users\\") {
        Add-Issue -Path $relative -Rule "windows-user-home"
    }
    if ($content -match $posixHomePattern) {
        Add-Issue -Path $relative -Rule "posix-user-home"
    }
    if ($content -match "(?i)(\\|/)\.codex(\\|/)") {
        Add-Issue -Path $relative -Rule "codex-private-path"
    }
    if ($content -match "(?i)[A-Z]:\\AI project\\") {
        Add-Issue -Path $relative -Rule "private-project-path"
    }
    if ($content -match "(?m)^(Machine|User|Process)\s*=\s*(?!<REDACTED_PATH>\s*$).+$") {
        Add-Issue -Path $relative -Rule "full-path-snapshot"
    }
    if (
        $content -match "(?i)(^|[^0-9])(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})([^0-9]|$)"
    ) {
        Add-Issue -Path $relative -Rule "private-ip"
    }

    $emailMatches = [regex]::Matches(
        $content,
        "(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
    )
    foreach ($match in $emailMatches) {
        $email = $match.Value
        if (
            $email -notmatch "(?i)@[^@]+\.invalid$" -and
            $email -notmatch "(?i)@example\.(com|org|net)$" -and
            $email -notmatch "(?i)@users\.noreply\.github\.com$"
        ) {
            Add-Issue -Path $relative -Rule "public-email"
            break
        }
    }

    if (
        $content -match "AKIA[A-Z0-9]{16}" -or
        $content -match "gh[pousr]_[A-Za-z0-9]{20,}" -or
        $content -match "sk-[A-Za-z0-9]{20,}" -or
        $content -match "xox[baprs]-[A-Za-z0-9-]{20,}" -or
        ($content.Contains($privateKeyPrefix) -and $content.Contains("PRIVATE KEY"))
    ) {
        Add-Issue -Path $relative -Rule "high-confidence-secret"
    }

    foreach ($dynamicValue in @($env:USERPROFILE, $env:USERNAME, $env:COMPUTERNAME)) {
        if (
            -not [string]::IsNullOrWhiteSpace($dynamicValue) -and
            $dynamicValue.Length -ge 4 -and
            $content.IndexOf($dynamicValue, [StringComparison]::OrdinalIgnoreCase) -ge 0
        ) {
            Add-Issue -Path $relative -Rule "current-machine-identity"
            break
        }
    }
}

$uniqueIssues = @($issues | Sort-Object path, rule -Unique)
$summary = [ordered]@{
    status = if ($uniqueIssues.Count -eq 0) { "passed" } else { "failed" }
    scope = $Scope
    files_scanned = $scanned
    text_files = $textFiles
    issue_count = $uniqueIssues.Count
}

Write-Output ("SAFETY_RESULT=" + ($summary | ConvertTo-Json -Compress))
foreach ($issue in $uniqueIssues) {
    Write-Output ("[FAIL] {0}: {1}" -f $issue.rule, $issue.path)
}

if ($uniqueIssues.Count -ne 0) {
    exit 1
}
