[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [switch] $ConfirmScope,

    [Parameter(Mandatory = $true)]
    [string] $CommitMessage
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$safetyScript = Join-Path $PSScriptRoot "Invoke-RepositorySafetyCheck.ps1"
$policyPath = Join-Path $repositoryRoot ".github\liveclip-workflow.json"

function Get-WorkflowPolicy {
    if (-not (Test-Path -LiteralPath $policyPath -PathType Leaf)) {
        throw "Workflow policy is missing: .github/liveclip-workflow.json"
    }
    $policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    if (
        $policy.PSObject.Properties.Name -notcontains "canonical_repository" -or
        $policy.PSObject.Properties.Name -notcontains "base_branch" -or
        $policy.canonical_repository -notmatch "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$" -or
        [string]::IsNullOrWhiteSpace($policy.base_branch)
    ) {
        throw "Workflow policy is missing a valid canonical_repository or base_branch."
    }
    return $policy
}

function ConvertTo-GitHubRepositoryName {
    param([Parameter(Mandatory = $true)][string] $Url)

    $clean = $Url.Trim().TrimEnd("/")
    if ($clean.EndsWith(".git", [StringComparison]::OrdinalIgnoreCase)) {
        $clean = $clean.Substring(0, $clean.Length - 4)
    }
    if (
        $clean -match "^https://github\.com/(?<name>[^/\s]+/[^/\s]+)$" -or
        $clean -match "^git@github\.com:(?<name>[^/\s]+/[^/\s]+)$" -or
        $clean -match "^ssh://git@github\.com/(?<name>[^/\s]+/[^/\s]+)$"
    ) {
        return $Matches.name
    }
    throw "origin must use an HTTPS or SSH URL for GitHub."
}

function Assert-CanonicalOrigin {
    param([Parameter(Mandatory = $true)][string] $CanonicalRepository)

    $fetchUrls = @(& git -C $repositoryRoot remote get-url --all origin)
    $fetchExitCode = $LASTEXITCODE
    $pushUrls = @(& git -C $repositoryRoot remote get-url --push --all origin)
    $pushExitCode = $LASTEXITCODE
    if (
        $fetchExitCode -ne 0 -or
        $pushExitCode -ne 0 -or
        $fetchUrls.Count -ne 1 -or
        $pushUrls.Count -ne 1
    ) {
        throw "A single unambiguous origin fetch URL and push URL are required."
    }
    foreach ($url in @($fetchUrls[0], $pushUrls[0])) {
        $repository = ConvertTo-GitHubRepositoryName -Url $url
        if (-not $repository.Equals(
            $CanonicalRepository,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            throw "origin does not match canonical repository '$CanonicalRepository'."
        }
    }
}

if (-not $ConfirmScope) {
    throw "Pass -ConfirmScope only after reviewing the audit report changes."
}

$policy = Get-WorkflowPolicy
$canonicalRepository = [string] $policy.canonical_repository
$baseBranch = [string] $policy.base_branch

$branch = (& git -C $repositoryRoot branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $branch -eq $baseBranch) {
    throw "Audit reports may not be published directly from $baseBranch."
}

Assert-CanonicalOrigin -CanonicalRepository $canonicalRepository

$changed = @(
    @(
        & git -C $repositoryRoot diff --name-only
        & git -C $repositoryRoot diff --cached --name-only
        & git -C $repositoryRoot ls-files --others --exclude-standard
    ) |
        Where-Object { $_ } |
        Sort-Object -Unique
)

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
& git -C $repositoryRoot push origin $branch
if ($LASTEXITCODE -ne 0) {
    throw "Normal audit push failed."
}

Write-Output "AUDIT_BRANCH=$branch"
Write-Output "AUDIT_COMMIT=$((& git -C $repositoryRoot rev-parse HEAD).Trim())"
Write-Output "AUDIT_REPOSITORY=$canonicalRepository"
