[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $BranchName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
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

$policy = Get-WorkflowPolicy
$canonicalRepository = [string] $policy.canonical_repository
$baseBranch = [string] $policy.base_branch

if ($BranchName -notmatch "^(task|fix|chore)/[A-Za-z0-9][A-Za-z0-9._/-]*$") {
    throw "BranchName must start with task/, fix/, or chore/ and use safe Git characters."
}

$status = @(& git -C $repositoryRoot status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read Git status."
}
if ($status.Count -ne 0) {
    throw "The worktree must be clean before starting a task."
}

$currentBranch = (& git -C $repositoryRoot branch --show-current).Trim()
$currentBranchExitCode = $LASTEXITCODE
if ($currentBranchExitCode -ne 0 -or $currentBranch -ne $baseBranch) {
    throw "Tasks must start from the local $baseBranch branch."
}

Assert-CanonicalOrigin -CanonicalRepository $canonicalRepository

& git -C $repositoryRoot show-ref --verify --quiet "refs/heads/$BranchName"
if ($LASTEXITCODE -eq 0) {
    throw "The local branch already exists: $BranchName"
}

& git -C $repositoryRoot pull --ff-only origin $baseBranch
$pullExitCode = $LASTEXITCODE
if ($pullExitCode -ne 0) {
    throw "Unable to fast-forward local $baseBranch from origin/$baseBranch."
}

$baseCommit = (& git -C $repositoryRoot rev-parse $baseBranch).Trim()
$baseCommitExitCode = $LASTEXITCODE
$remoteBaseCommit = (& git -C $repositoryRoot rev-parse "refs/remotes/origin/$baseBranch").Trim()
$remoteBaseCommitExitCode = $LASTEXITCODE
if (
    $baseCommitExitCode -ne 0 -or
    $remoteBaseCommitExitCode -ne 0 -or
    $baseCommit -ne $remoteBaseCommit
) {
    throw "Local $baseBranch is ahead of or differs from origin/$baseBranch; task creation stopped."
}

& git -C $repositoryRoot switch -c $BranchName
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create task branch: $BranchName"
}

$result = [ordered]@{
    repository = $canonicalRepository
    base_commit = $baseCommit
    branch = $BranchName
}
Write-Output ("TASK_START_RESULT=" + ($result | ConvertTo-Json -Compress))
Write-Output "TASK_BRANCH=$BranchName"
