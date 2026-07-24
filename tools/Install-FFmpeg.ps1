[CmdletBinding()]
param(
    [string] $ProjectRoot = "",
    [switch] $TestMode,
    [string] $TestIsolationRoot = "",
    [string] $TestArchivePath = "",
    [string] $TestPublisherChecksumPath = "",
    [string] $TestExpectedSha256 = "",
    [string] $TestExpectedVersion = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# Production provenance is deliberately frozen in audited constants. Upgrading
# FFmpeg requires editing these values and completing a new independent audit;
# callers cannot replace them with command-line arguments.
$productionSourcePage = "https://ffmpeg.org/download.html"
$productionOfficialWindowsProviders = @("gyan.dev", "BtbN")
$productionProvider = "gyan.dev"
$productionProviderPage = "https://www.gyan.dev/ffmpeg/builds/"
$productionVersion = "8.1.2"
$productionBuild = "full_build"
$productionArchiveFileName = "ffmpeg-8.1.2-full_build.7z"
$productionDownloadUri = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z"
$productionPublisherChecksumUri = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z.sha256"
$productionExpectedSha256 = "0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059"

$scriptProjectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
$projectRootWasProvided = -not [string]::IsNullOrWhiteSpace($ProjectRoot)

if (-not $TestMode -and (
    -not [string]::IsNullOrWhiteSpace($TestIsolationRoot) -or
    -not [string]::IsNullOrWhiteSpace($TestArchivePath) -or
    -not [string]::IsNullOrWhiteSpace($TestPublisherChecksumPath) -or
    -not [string]::IsNullOrWhiteSpace($TestExpectedSha256) -or
    -not [string]::IsNullOrWhiteSpace($TestExpectedVersion)
)) {
    throw "Test-only parameters require explicit -TestMode."
}

if (-not $projectRootWasProvided) {
    if ($TestMode) {
        throw "TestMode requires an explicit isolated ProjectRoot."
    }
    $ProjectRoot = $scriptProjectRoot
}

$realInstallRoot = Join-Path $scriptProjectRoot "tools\ffmpeg"
$testIsolationFull = $null

function Test-PathEqualOrWithin {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Parent
    )

    $pathFull = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\')
    if ($pathFull.Equals($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    return $pathFull.StartsWith($parentFull + '\', [System.StringComparison]::OrdinalIgnoreCase)
}

function Resolve-LocalFixedDiskPath {
    param(
        [Parameter(Mandatory = $true)][string] $Value,
        [Parameter(Mandatory = $true)][string] $Label
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Label is required in TestMode."
    }

    $candidate = $Value.Trim()
    if ($candidate.StartsWith('\\') -or $candidate.StartsWith('//')) {
        throw "$Label failed validation: TestMode only allows local fixed-disk paths; UNC, network, device, and named-pipe paths are forbidden. Path: $Value"
    }

    $uri = $null
    if ([System.Uri]::TryCreate($candidate, [System.UriKind]::Absolute, [ref] $uri) -and $uri.IsAbsoluteUri) {
        if (-not $uri.IsFile) {
            throw "$Label failed validation: TestMode only allows local fixed-disk paths or local file URIs; remote URLs are forbidden. Path: $Value"
        }
        if (-not [string]::IsNullOrEmpty($uri.Host)) {
            throw "$Label failed validation: remote file URI hosts are forbidden; TestMode only allows local fixed-disk paths. Path: $Value"
        }
        $candidate = $uri.LocalPath
    }

    if (
        $candidate.StartsWith('\\') -or
        $candidate.StartsWith('//') -or
        $candidate -notmatch '^[A-Za-z]:[\\/]'
    ) {
        throw "$Label failed validation: TestMode only allows absolute paths on a local fixed disk; UNC, network, device, and named-pipe paths are forbidden. Path: $Value"
    }

    try {
        $fullPath = [System.IO.Path]::GetFullPath($candidate)
        $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
        if ([string]::IsNullOrWhiteSpace($pathRoot)) {
            throw "The path has no drive root."
        }
        $drive = New-Object System.IO.DriveInfo -ArgumentList $pathRoot
        $driveType = $drive.DriveType
    }
    catch {
        throw "$Label failed validation: unable to determine a local fixed-disk volume. Path: $Value. $($_.Exception.Message)"
    }

    if ($driveType -ne [System.IO.DriveType]::Fixed) {
        throw "$Label failed validation: TestMode only allows local fixed disks; drive type '$driveType' is forbidden. Path: $fullPath"
    }

    if ($fullPath.Length -gt $pathRoot.Length) {
        return $fullPath.TrimEnd('\')
    }
    return $fullPath
}

function Assert-NoReparsePointPath {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Label
    )

    $fullPath = Resolve-LocalFixedDiskPath -Value $Path -Label $Label
    $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
    $pathsToCheck = New-Object System.Collections.Generic.List[string]
    $pathsToCheck.Add($pathRoot)
    $relativePath = $fullPath.Substring($pathRoot.Length)
    $currentPath = $pathRoot
    foreach ($component in ($relativePath -split '[\\/]' | Where-Object { -not [string]::IsNullOrEmpty($_) })) {
        $currentPath = Join-Path $currentPath $component
        $pathsToCheck.Add($currentPath)
    }

    foreach ($candidatePath in $pathsToCheck) {
        try {
            $item = Get-Item -LiteralPath $candidatePath -Force -ErrorAction Stop
        }
        catch [System.Management.Automation.ItemNotFoundException] {
            break
        }
        catch {
            throw "$Label failed validation: unable to verify path component '$candidatePath'. $($_.Exception.Message)"
        }
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "$Label failed validation: test isolation paths must not contain a junction, symlink, mount point, or other reparse point. Reparse point: $candidatePath"
        }
    }
}

function Assert-SafeTestPath {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Label,
        [string] $RequiredParent = ""
    )

    $fullPath = Resolve-LocalFixedDiskPath -Value $Path -Label $Label
    if (-not [string]::IsNullOrWhiteSpace($RequiredParent) -and -not (Test-PathEqualOrWithin -Path $fullPath -Parent $RequiredParent)) {
        throw "$Label failed validation: path must remain inside '$RequiredParent'. Path: $fullPath"
    }
    Assert-NoReparsePointPath -Path $fullPath -Label $Label
    return $fullPath
}

function Resolve-LocalTestFile {
    param(
        [Parameter(Mandatory = $true)][string] $Value,
        [Parameter(Mandatory = $true)][string] $Label
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Label is required in TestMode."
    }

    $resolved = Assert-SafeTestPath -Path $Value -Label $Label -RequiredParent $testIsolationFull
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "$Label does not exist as a local file: $resolved"
    }
    return $resolved
}

if ($TestMode) {
    $testIsolationFull = Assert-SafeTestPath -Path $TestIsolationRoot -Label "TestIsolationRoot"
    if (-not (Test-Path -LiteralPath $testIsolationFull -PathType Container)) {
        throw "TestIsolationRoot does not exist as a local directory: $testIsolationFull"
    }
    $testSentinel = Assert-SafeTestPath -Path (Join-Path $testIsolationFull ".liveclip-ffmpeg-test-root") -Label "TestIsolationRoot sentinel" -RequiredParent $testIsolationFull
    if (-not (Test-Path -LiteralPath $testSentinel -PathType Leaf)) {
        throw "TestIsolationRoot is missing the required .liveclip-ffmpeg-test-root sentinel."
    }
    $projectRoot = Assert-SafeTestPath -Path $ProjectRoot -Label "ProjectRoot" -RequiredParent $testIsolationFull
}
else {
    $projectRoot = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\')
}

$mode = "production"
$sourceType = "remote_https"
$sourcePage = $productionSourcePage
$officialWindowsProviders = $productionOfficialWindowsProviders
$selectedProvider = $productionProvider
$providerPage = $productionProviderPage
$expectedVersion = $productionVersion
$buildName = $productionBuild
$archiveFileName = $productionArchiveFileName
$downloadResource = $productionDownloadUri
$publisherChecksumResource = $productionPublisherChecksumUri
$expectedSha256 = $productionExpectedSha256
$fixedAuditedSha256 = $productionExpectedSha256

if ($TestMode) {
    if ([string]::IsNullOrWhiteSpace($TestExpectedVersion)) {
        throw "TestExpectedVersion is required in TestMode."
    }
    if ($TestExpectedSha256 -notmatch "^[0-9a-fA-F]{64}$") {
        throw "TestExpectedSha256 must contain exactly 64 hexadecimal characters."
    }

    $mode = "test"
    $sourceType = "local_test_resource"
    $sourcePage = $null
    $officialWindowsProviders = @()
    $selectedProvider = "test_fixture"
    $providerPage = $null
    $expectedVersion = $TestExpectedVersion
    $buildName = "test_fixture"
    $downloadResource = Resolve-LocalTestFile -Value $TestArchivePath -Label "TestArchivePath"
    $publisherChecksumResource = Resolve-LocalTestFile -Value $TestPublisherChecksumPath -Label "TestPublisherChecksumPath"
    $archiveFileName = [System.IO.Path]::GetFileName($downloadResource)
    $expectedSha256 = $TestExpectedSha256.ToLowerInvariant()
    $fixedAuditedSha256 = $null
}

$installRoot = Join-Path $projectRoot "tools\ffmpeg"
$ffmpegPath = Join-Path $installRoot "bin\ffmpeg.exe"
$ffprobePath = Join-Path $installRoot "bin\ffprobe.exe"
$markerPath = Join-Path $installRoot ".liveclip-ffmpeg-install.json"
$downloadRoot = Join-Path $projectRoot "runtime\temp\ffmpeg-download"
$archivePath = Join-Path $downloadRoot $archiveFileName
$partialPath = Join-Path $downloadRoot ("{0}.{1}.partial" -f $archiveFileName, [guid]::NewGuid().ToString("N"))
$extractRoot = Join-Path $downloadRoot ("extract-{0}" -f [guid]::NewGuid().ToString("N"))

if ($TestMode -and [System.IO.Path]::GetFullPath($installRoot).TrimEnd('\').Equals(
    [System.IO.Path]::GetFullPath($realInstallRoot).TrimEnd('\'),
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "TestMode cannot target the real project tools\ffmpeg installation."
}

$archiveAcquiredThisRun = $false
$archiveDownloadedThisRun = $false
$archiveHashRecomputedThisRun = $false
$publisherHashCheckedThisRun = $false
$publisherHashMatchThisRun = $null
$downloadTime = $null
$publisherHash = $null
$actualHash = $null
$archiveSize = $null

function Assert-TestModeSafetyBoundary {
    if (-not $TestMode) {
        return
    }

    [void](Assert-SafeTestPath -Path $testIsolationFull -Label "TestIsolationRoot")
    [void](Assert-SafeTestPath -Path $testSentinel -Label "TestIsolationRoot sentinel" -RequiredParent $testIsolationFull)
    [void](Assert-SafeTestPath -Path $projectRoot -Label "ProjectRoot" -RequiredParent $testIsolationFull)
    [void](Resolve-LocalTestFile -Value $downloadResource -Label "TestArchivePath")
    [void](Resolve-LocalTestFile -Value $publisherChecksumResource -Label "TestPublisherChecksumPath")

    foreach ($entry in @(
        @{ Path = $installRoot; Label = "test install target" },
        @{ Path = $ffmpegPath; Label = "test ffmpeg executable" },
        @{ Path = $ffprobePath; Label = "test ffprobe executable" },
        @{ Path = $markerPath; Label = "test install marker" },
        @{ Path = $downloadRoot; Label = "test temporary download directory" },
        @{ Path = $archivePath; Label = "test temporary archive" },
        @{ Path = $partialPath; Label = "test partial archive" },
        @{ Path = $extractRoot; Label = "test extraction directory" }
    )) {
        [void](Assert-SafeTestPath -Path $entry.Path -Label $entry.Label -RequiredParent $projectRoot)
    }
}

function Assert-NoReparsePointTree {
    param(
        [Parameter(Mandatory = $true)][string] $Root,
        [Parameter(Mandatory = $true)][string] $Label
    )

    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        return
    }
    Assert-NoReparsePointPath -Path $Root -Label $Label
    $reparseItem = Get-ChildItem -LiteralPath $Root -Force -Recurse -ErrorAction Stop |
        Where-Object { ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 } |
        Select-Object -First 1
    if ($null -ne $reparseItem) {
        throw "$Label failed validation: extracted or temporary content must not contain a junction, symlink, mount point, or other reparse point. Reparse point: $($reparseItem.FullName)"
    }
}

function Remove-OwnedFile {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }
    if ($TestMode) {
        try {
            [void](Assert-SafeTestPath -Path $Path -Label $Label -RequiredParent $projectRoot)
        }
        catch {
            Write-Warning "Refusing unsafe test-artifact cleanup for '$Path': $($_.Exception.Message)"
            return
        }
    }
    Remove-Item -LiteralPath $Path -Force
}

function Remove-OwnedDirectoryTree {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return
    }
    if ($TestMode) {
        try {
            [void](Assert-SafeTestPath -Path $Path -Label $Label -RequiredParent $projectRoot)
            Assert-NoReparsePointTree -Root $Path -Label $Label
        }
        catch {
            Write-Warning "Refusing unsafe recursive test-artifact cleanup for '$Path': $($_.Exception.Message)"
            return
        }
    }
    Remove-Item -LiteralPath $Path -Recurse -Force
}

function Assert-PathWithinProject {
    param([Parameter(Mandatory = $true)][string] $Path)

    if (-not (Test-PathEqualOrWithin -Path $Path -Parent $projectRoot)) {
        throw "Refusing to operate outside the project directory: $Path"
    }
}

function Get-TextResource {
    param([Parameter(Mandatory = $true)][string] $Value)

    if ($TestMode) {
        return Get-Content -LiteralPath $Value -Raw -Encoding UTF8
    }
    return (Invoke-WebRequest -UseBasicParsing -Uri $Value).Content
}

function Copy-ResourceToFile {
    param(
        [Parameter(Mandatory = $true)][string] $Source,
        [Parameter(Mandatory = $true)][string] $Destination
    )

    if ($TestMode) {
        Copy-Item -LiteralPath $Source -Destination $Destination
        return
    }
    Invoke-WebRequest -UseBasicParsing -Uri $Source -OutFile $Destination
}

function Get-MarkerValue {
    param(
        [Parameter(Mandatory = $true)][object] $Marker,
        [Parameter(Mandatory = $true)][string[]] $Names
    )

    foreach ($name in $Names) {
        $property = $Marker.PSObject.Properties[$name]
        if ($null -ne $property) {
            return $property.Value
        }
    }
    return $null
}

function Get-InstalledVersionLine {
    if (-not (Test-Path -LiteralPath $ffmpegPath -PathType Leaf)) {
        return $null
    }
    $versionOutput = & $ffmpegPath -version 2>&1
    if ($LASTEXITCODE -ne 0 -or -not $versionOutput) {
        return $null
    }
    return [string]$versionOutput[0]
}

function Get-KnownInstallation {
    if (
        -not (Test-Path -LiteralPath $markerPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $ffmpegPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $ffprobePath -PathType Leaf)
    ) {
        return $null
    }
    if ((Get-Item -LiteralPath $ffmpegPath).Length -le 0 -or (Get-Item -LiteralPath $ffprobePath).Length -le 0) {
        return $null
    }
    try {
        $marker = Get-Content -LiteralPath $markerPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        return $null
    }

    $markerProvider = [string](Get-MarkerValue -Marker $marker -Names @("provider"))
    $markerSource = [string](Get-MarkerValue -Marker $marker -Names @("installed_from_url", "actual_url"))
    $markerChecksumSource = [string](Get-MarkerValue -Marker $marker -Names @("published_checksum_url"))
    $markerArchiveName = [string](Get-MarkerValue -Marker $marker -Names @("archive_file_name"))
    $markerArchiveSize = Get-MarkerValue -Marker $marker -Names @("installed_archive_size", "archive_size_bytes")
    $markerArchiveHash = [string](Get-MarkerValue -Marker $marker -Names @("installed_archive_sha256", "sha256"))
    $markerPublisherHash = [string](Get-MarkerValue -Marker $marker -Names @("publisher_sha256"))
    $markerVerified = Get-MarkerValue -Marker $marker -Names @("publisher_hash_verified_at_install", "sha256_verified_against_publisher")
    $markerVersion = [string](Get-MarkerValue -Marker $marker -Names @("version", "expected_version"))
    $markerInstalledAt = [string](Get-MarkerValue -Marker $marker -Names @("installed_at", "installed_time"))
    $markerVersionLine = [string](Get-MarkerValue -Marker $marker -Names @("version_line"))
    $markerPathModified = Get-MarkerValue -Marker $marker -Names @("system_path_modified")

    if (
        [string]::IsNullOrWhiteSpace($markerProvider) -or
        [string]::IsNullOrWhiteSpace($markerSource) -or
        [string]::IsNullOrWhiteSpace($markerChecksumSource) -or
        [string]::IsNullOrWhiteSpace($markerArchiveName) -or
        $null -eq $markerArchiveSize -or [long]$markerArchiveSize -le 0 -or
        [string]::IsNullOrWhiteSpace($markerArchiveHash) -or
        $null -eq $markerVerified -or
        [string]::IsNullOrWhiteSpace($markerVersion) -or
        [string]::IsNullOrWhiteSpace($markerInstalledAt) -or
        [string]::IsNullOrWhiteSpace($markerVersionLine) -or
        $null -eq $markerPathModified
    ) {
        return $null
    }
    if (
        $markerProvider -ne $selectedProvider -or
        $markerSource -ne $downloadResource -or
        $markerChecksumSource -ne $publisherChecksumResource -or
        $markerArchiveName -ne $archiveFileName -or
        $markerArchiveHash -ne $expectedSha256 -or
        $markerVersion -ne $expectedVersion -or
        -not [bool]$markerVerified -or
        [bool]$markerPathModified
    ) {
        return $null
    }
    if (-not [string]::IsNullOrWhiteSpace($markerPublisherHash) -and $markerPublisherHash -ne $expectedSha256) {
        return $null
    }

    $installedVersionLine = Get-InstalledVersionLine
    if (-not $installedVersionLine -or $installedVersionLine -notmatch [regex]::Escape($expectedVersion)) {
        return $null
    }
    return $marker
}

function Write-StructuredSummary {
    param(
        [Parameter(Mandatory = $true)][string] $Status,
        [string] $Message = "",
        [object] $Marker = $null
    )

    $size = $archiveSize
    $installedArchiveHash = $actualHash
    $recordedPublisherHash = $publisherHash
    $publisherVerifiedAtInstall = $false
    $recordedDownloadTime = $downloadTime
    $recordedInstallTime = $null
    $installedFrom = $downloadResource
    $versionLine = $null

    if ($null -ne $Marker) {
        $size = Get-MarkerValue -Marker $Marker -Names @("installed_archive_size", "archive_size_bytes")
        $installedArchiveHash = [string](Get-MarkerValue -Marker $Marker -Names @("installed_archive_sha256", "sha256"))
        $markerPublisherHash = Get-MarkerValue -Marker $Marker -Names @("publisher_sha256")
        if ($null -ne $markerPublisherHash -and -not [string]::IsNullOrWhiteSpace([string]$markerPublisherHash)) {
            $recordedPublisherHash = [string]$markerPublisherHash
        }
        $publisherVerifiedAtInstall = [bool](Get-MarkerValue -Marker $Marker -Names @("publisher_hash_verified_at_install", "sha256_verified_against_publisher"))
        $recordedDownloadTime = Get-MarkerValue -Marker $Marker -Names @("download_time")
        $recordedInstallTime = Get-MarkerValue -Marker $Marker -Names @("installed_at", "installed_time")
        $installedFrom = [string](Get-MarkerValue -Marker $Marker -Names @("installed_from_url", "actual_url"))
        $versionLine = [string](Get-MarkerValue -Marker $Marker -Names @("version_line"))
    }

    $summary = [ordered]@{
        status = $Status
        message = $Message
        mode = $mode
        source_type = $sourceType
        official_download_page = $sourcePage
        official_windows_build_providers = $officialWindowsProviders
        selected_provider = $selectedProvider
        provider_download_page = $providerPage
        direct_download_url = $downloadResource
        publisher_checksum_url = $publisherChecksumResource
        archive_file_name = $archiveFileName
        archive_size_bytes = $size
        download_time = $recordedDownloadTime
        installed_archive_sha256 = $installedArchiveHash
        publisher_sha256 = $recordedPublisherHash
        fixed_audited_sha256 = $fixedAuditedSha256
        publisher_hash_verified_at_install = $publisherVerifiedAtInstall
        publisher_hash_checked_this_run = $publisherHashCheckedThisRun
        publisher_hash_match_this_run = $publisherHashMatchThisRun
        archive_hash_recomputed_this_run = $archiveHashRecomputedThisRun
        archive_downloaded_this_run = $archiveDownloadedThisRun
        installed_from_url = $installedFrom
        version = $expectedVersion
        build = $buildName
        version_line = $versionLine
        installed_at = $recordedInstallTime
        ffmpeg_path = $ffmpegPath
        ffprobe_path = $ffprobePath
        system_path_modified = $false
    }
    Write-Output ("LIVECLIP_FFMPEG_SUMMARY=" + ($summary | ConvertTo-Json -Depth 4 -Compress))
}

if ([System.IO.Path]::GetFileName($archiveFileName) -ne $archiveFileName) {
    throw "Archive file name must not contain directory components."
}
if ($expectedSha256 -notmatch "^[0-9a-f]{64}$") {
    throw "Expected SHA-256 must contain exactly 64 lowercase hexadecimal characters."
}
Assert-PathWithinProject -Path $installRoot
Assert-PathWithinProject -Path $downloadRoot
Assert-PathWithinProject -Path $archivePath
Assert-PathWithinProject -Path $partialPath
Assert-PathWithinProject -Path $extractRoot
Assert-TestModeSafetyBoundary

$knownInstallation = Get-KnownInstallation
if ($null -ne $knownInstallation) {
    Write-Output "FFmpeg $expectedVersion is already installed; the offline skip path did not access the publisher or archive."
    Write-StructuredSummary -Status "already_installed" -Message "Known matching installation was safely skipped offline." -Marker $knownInstallation
    exit 0
}

if (Test-Path -LiteralPath $installRoot) {
    Write-StructuredSummary -Status "failed" -Message "Unknown or incomplete installation directory was not overwritten."
    throw "Refusing to overwrite an unknown or incomplete FFmpeg directory: $installRoot"
}

if (Test-Path -LiteralPath $archivePath) {
    Write-StructuredSummary -Status "failed" -Message "A pre-existing local archive was not used or removed."
    throw "Refusing to use a pre-existing local archive; provenance must come from the active mode resource: $archivePath"
}

try {
    New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null
    $env:TEMP = $downloadRoot
    $env:TMP = $downloadRoot
    Assert-TestModeSafetyBoundary

    $publisherChecksumText = [string](Get-TextResource -Value $publisherChecksumResource)
    $publisherHashCheckedThisRun = $true
    $publisherMatch = [regex]::Match($publisherChecksumText, "(?i)\b[0-9a-f]{64}\b")
    if (-not $publisherMatch.Success) {
        throw "Publisher checksum resource does not contain a SHA-256 value."
    }
    $publisherHash = $publisherMatch.Value.ToLowerInvariant()
    $publisherHashMatchThisRun = ($publisherHash -eq $expectedSha256)
    if (-not $publisherHashMatchThisRun) {
        throw "Pinned SHA-256 does not match the publisher checksum. Expected $expectedSha256, publisher reported $publisherHash."
    }

    if ($TestMode) {
        Write-Output "Copying an isolated local FFmpeg test fixture: $downloadResource"
    }
    else {
        Write-Output "Downloading the audited FFmpeg portable build: $downloadResource"
    }
    Assert-TestModeSafetyBoundary
    Copy-ResourceToFile -Source $downloadResource -Destination $partialPath
    $downloadTime = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss.fffK")
    Move-Item -LiteralPath $partialPath -Destination $archivePath
    $archiveAcquiredThisRun = $true
    $archiveDownloadedThisRun = -not $TestMode
    Assert-TestModeSafetyBoundary

    $archiveInfo = Get-Item -LiteralPath $archivePath
    $archiveSize = $archiveInfo.Length
    if ($archiveSize -le 0) {
        throw "FFmpeg archive is empty."
    }
    $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $archiveHashRecomputedThisRun = $true
    if ($actualHash -ne $publisherHash) {
        throw "FFmpeg archive SHA-256 mismatch. Publisher expected $publisherHash, got $actualHash."
    }

    $tarCommand = Get-Command tar.exe -ErrorAction Stop
    New-Item -ItemType Directory -Path $extractRoot | Out-Null
    Assert-TestModeSafetyBoundary
    & $tarCommand.Source -xf $archivePath -C $extractRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Archive extraction failed with exit code $LASTEXITCODE."
    }
    Assert-TestModeSafetyBoundary
    if ($TestMode) {
        Assert-NoReparsePointTree -Root $extractRoot -Label "test extraction directory"
    }

    $extractedFfmpeg = Get-ChildItem -LiteralPath $extractRoot -Recurse -File -Filter ffmpeg.exe | Select-Object -First 1
    if (-not $extractedFfmpeg) {
        throw "The verified archive did not contain ffmpeg.exe."
    }
    $extractedBin = Split-Path -Parent $extractedFfmpeg.FullName
    $extractedFfprobe = Join-Path $extractedBin "ffprobe.exe"
    if (-not (Test-Path -LiteralPath $extractedFfprobe -PathType Leaf)) {
        throw "The verified archive did not contain ffprobe.exe next to ffmpeg.exe."
    }
    if ($TestMode) {
        [void](Assert-SafeTestPath -Path $extractedFfmpeg.FullName -Label "extracted ffmpeg executable" -RequiredParent $extractRoot)
        [void](Assert-SafeTestPath -Path $extractedFfprobe -Label "extracted ffprobe executable" -RequiredParent $extractRoot)
    }

    $versionOutput = & $extractedFfmpeg.FullName -version 2>&1
    if ($LASTEXITCODE -ne 0 -or [string]$versionOutput[0] -notmatch [regex]::Escape($expectedVersion)) {
        throw "Extracted FFmpeg does not report the expected version $expectedVersion."
    }
    $encoderOutput = (& $extractedFfmpeg.FullName -hide_banner -encoders 2>&1) -join "`n"
    $filterOutput = (& $extractedFfmpeg.FullName -hide_banner -filters 2>&1) -join "`n"
    if ($encoderOutput -notmatch "\blibx264\b") {
        throw "Extracted FFmpeg lacks the required libx264 encoder."
    }
    if ($filterOutput -notmatch "\bsubtitles\b" -or $filterOutput -notmatch "\bass\b") {
        throw "Extracted FFmpeg lacks the required subtitles/ass filters (libass)."
    }

    $sourceRoot = Split-Path -Parent $extractedBin
    if ([System.IO.Path]::GetFullPath($sourceRoot) -eq [System.IO.Path]::GetFullPath($extractRoot)) {
        throw "Unexpected archive layout; refusing to publish an ambiguous install root."
    }

    $installedAt = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss.fffK")
    $marker = [ordered]@{
        mode = $mode
        source_type = $sourceType
        source_page = $sourcePage
        official_windows_build_providers = $officialWindowsProviders
        provider = $selectedProvider
        provider_page = $providerPage
        installed_from_url = $downloadResource
        actual_url = $downloadResource
        published_checksum_url = $publisherChecksumResource
        archive_file_name = $archiveFileName
        installed_archive_size = $archiveSize
        archive_size_bytes = $archiveSize
        installed_archive_sha256 = $actualHash
        sha256 = $actualHash
        publisher_sha256 = $publisherHash
        publisher_hash_verified_at_install = $true
        sha256_verified_against_publisher = $true
        sha256_verification_status = "publisher_match"
        version = $expectedVersion
        expected_version = $expectedVersion
        download_time = $downloadTime
        installed_at = $installedAt
        installed_time = $installedAt
        version_line = [string]$versionOutput[0]
        system_path_modified = $false
    }
    $sourceMarker = Join-Path $sourceRoot ".liveclip-ffmpeg-install.json"
    if ($TestMode) {
        [void](Assert-SafeTestPath -Path $sourceRoot -Label "test publication source" -RequiredParent $extractRoot)
        Assert-NoReparsePointTree -Root $sourceRoot -Label "test publication source"
        Assert-TestModeSafetyBoundary
    }
    $marker | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $sourceMarker -Encoding UTF8
    if ($TestMode) {
        [void](Assert-SafeTestPath -Path $sourceMarker -Label "test source install marker" -RequiredParent $extractRoot)
        Assert-TestModeSafetyBoundary
    }
    Move-Item -LiteralPath $sourceRoot -Destination $installRoot
    Assert-TestModeSafetyBoundary
    if (-not (Test-Path -LiteralPath $ffmpegPath -PathType Leaf) -or -not (Test-Path -LiteralPath $ffprobePath -PathType Leaf)) {
        throw "FFmpeg publication failed; stable executables are missing."
    }

    if ($archiveAcquiredThisRun) {
        Remove-OwnedFile -Path $archivePath -Label "test temporary archive cleanup"
    }
    Write-Output "FFmpeg portable install completed."
    Write-StructuredSummary -Status "installed" -Message "Checksum verification passed; temporary extraction was atomically published." -Marker ([pscustomobject]$marker)
}
catch {
    if ($archiveAcquiredThisRun) {
        Remove-OwnedFile -Path $archivePath -Label "test temporary archive cleanup"
    }
    Write-StructuredSummary -Status "failed" -Message $_.Exception.Message
    throw
}
finally {
    Remove-OwnedFile -Path $partialPath -Label "test partial archive cleanup"
    Remove-OwnedDirectoryTree -Path $extractRoot -Label "test extraction directory cleanup"
}
