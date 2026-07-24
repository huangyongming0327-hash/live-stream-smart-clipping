[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [switch] $ConfirmScope,

    [Parameter(Mandatory = $true)]
    [string] $CommitMessage
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$safetyScript = Join-Path $PSScriptRoot "Invoke-RepositorySafetyCheck.ps1"

if (-not $ConfirmScope) {
    throw "Pass -ConfirmScope only after reviewing the audit report changes."
}

$branch = (& git -C $repositoryRoot branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $branch -eq "master") {
    throw "Audit reports may not be published directly from master."
}

$changed = @(
    & git -C $repositoryRoot diff --name-only
    & git -C $repositoryRoot diff --cached --name-only
    & git -C $repositoryRoot ls-files --others --exclude-standard
) | Where-Object { $_ } | Sort-Object -Unique

if ($changed.Count -eq 0) {
    throw "No audit report changes were found."
}

$invalid = @($changed | Where-Object {
    $_.Replace("\", "/") -notmatch "^tasks/reports/.+_AUDIT\.md$"
})
if ($invalid.Count -ne 0) {
    throw "Independent audit commits may only change tasks/reports/*_AUDIT.md."
}

& $safetyScript -RepositoryRoot $repositoryRoot -Scope PublishCandidates
if ($LASTEXITCODE -ne 0) {
    throw "Repository safety check failed."
}

& git -C $repositoryRoot add -- $changed
if ($LASTEXITCODE -ne 0) {
    throw "Unable to stage audit reports."
}
& git -C $repositoryRoot diff --cached --check
if ($LASTEXITCODE -ne 0) {
    throw "git diff --cached --check failed."
}

& git -C $repositoryRoot commit -m $CommitMessage
if ($LASTEXITCODE -ne 0) {
    throw "Audit commit failed."
}
& git -C $repositoryRoot push
if ($LASTEXITCODE -ne 0) {
    throw "Normal audit push failed."
}

Write-Output "AUDIT_BRANCH=$branch"
Write-Output "AUDIT_COMMIT=$((& git -C $repositoryRoot rev-parse HEAD).Trim())"
