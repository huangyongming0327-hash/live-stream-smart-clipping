[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [switch] $ConfirmScope,

    [Parameter(Mandatory = $true)]
    [string] $CommitMessage,

    [Parameter(Mandatory = $true)]
    [string] $PRTitle,

    [Parameter(Mandatory = $true)]
    [string] $PRBody,

    [Parameter(Mandatory = $true)]
    [string] $ResultReportPath,

    [string] $BaseBranch = "master"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$safetyScript = Join-Path $PSScriptRoot "Invoke-RepositorySafetyCheck.ps1"
$sourceTestsScript = Join-Path $PSScriptRoot "Invoke-SourceOnlyTests.ps1"
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

function Get-MatchingOpenPullRequests {
    param(
        [Parameter(Mandatory = $true)][string] $Repository,
        [Parameter(Mandatory = $true)][string] $Owner,
        [Parameter(Mandatory = $true)][string] $HeadBranch,
        [Parameter(Mandatory = $true)][string] $TargetBranch
    )

    $pullsOutput = @(& gh api --method GET "repos/$Repository/pulls" `
        -f state=open `
        -f "head=${Owner}:$HeadBranch" `
        -f "base=$TargetBranch")
    $queryExitCode = $LASTEXITCODE
    if ($queryExitCode -ne 0) {
        throw "Unable to query existing pull requests."
    }

    $pullsParsed = ($pullsOutput -join [Environment]::NewLine) |
        ConvertFrom-Json
    return @(
        @($pullsParsed | Where-Object { $null -ne $_ }) |
            Where-Object {
                $_.head.ref -eq $HeadBranch -and
                $_.base.ref -eq $TargetBranch -and
                $_.state -eq "open"
            }
    )
}

function Find-MatchingOpenPullRequestsWithRetry {
    param(
        [Parameter(Mandatory = $true)][string] $Repository,
        [Parameter(Mandatory = $true)][string] $Owner,
        [Parameter(Mandatory = $true)][string] $HeadBranch,
        [Parameter(Mandatory = $true)][string] $TargetBranch
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        if ($attempt -gt 1) {
            Start-Sleep -Seconds 2
        }
        try {
            return @(
                Get-MatchingOpenPullRequests `
                    -Repository $Repository `
                    -Owner $Owner `
                    -HeadBranch $HeadBranch `
                    -TargetBranch $TargetBranch
            )
        }
        catch {
            $lastError = $_
        }
    }
    throw "Unable to query existing pull requests after 3 attempts: $lastError"
}

if (-not $ConfirmScope) {
    throw "Pass -ConfirmScope only after reviewing that every non-ignored change belongs to this task."
}

$policy = Get-WorkflowPolicy
$canonicalRepository = [string] $policy.canonical_repository
$configuredBaseBranch = [string] $policy.base_branch
if ($BaseBranch -ne $configuredBaseBranch) {
    throw "BaseBranch must match workflow policy base branch '$configuredBaseBranch'."
}

$branch = (& git -C $repositoryRoot branch --show-current).Trim()
$branchExitCode = $LASTEXITCODE
if ($branchExitCode -ne 0) {
    throw "Unable to determine the current branch."
}
if ($branch -eq $BaseBranch -or $branch -notmatch "^(task|fix|chore)/") {
    throw "Publishing is allowed only from a task/, fix/, or chore/ branch."
}

Assert-CanonicalOrigin -CanonicalRepository $canonicalRepository

$normalizedReportPath = $ResultReportPath.Replace("\", "/")
if (
    [IO.Path]::IsPathRooted($ResultReportPath) -or
    $normalizedReportPath -notmatch "^tasks/reports/[A-Za-z0-9][A-Za-z0-9._-]*_RESULT\.md$"
) {
    throw "ResultReportPath must name one repository report under tasks/reports/*_RESULT.md."
}
$fullReportPath = Join-Path $repositoryRoot $normalizedReportPath
if (-not (Test-Path -LiteralPath $fullReportPath -PathType Leaf)) {
    throw "The required result report does not exist: $normalizedReportPath"
}
$reportChanges = @(& git -C $repositoryRoot status --porcelain=v1 --untracked-files=all -- $normalizedReportPath)
if ($LASTEXITCODE -ne 0 -or $reportChanges.Count -eq 0) {
    throw "The specified result report must be added or updated by this task."
}

$changes = @(& git -C $repositoryRoot status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $changes.Count -eq 0) {
    throw "No publishable worktree changes were found."
}

if (-not (Test-Path -LiteralPath $sourceTestsScript -PathType Leaf)) {
    throw "The source-only test entry point is missing."
}
& $sourceTestsScript

& $safetyScript -RepositoryRoot $repositoryRoot -Scope PublishCandidates
if ($LASTEXITCODE -ne 0) {
    throw "Repository safety check failed before staging."
}

& git -C $repositoryRoot add --all
if ($LASTEXITCODE -ne 0) {
    throw "git add failed."
}

& $safetyScript -RepositoryRoot $repositoryRoot -Scope Tracked
if ($LASTEXITCODE -ne 0) {
    throw "Repository safety check failed after staging."
}

& git -C $repositoryRoot diff --cached --check
if ($LASTEXITCODE -ne 0) {
    throw "git diff --cached --check failed."
}

$staged = @(& git -C $repositoryRoot diff --cached --name-only)
if ($staged.Count -eq 0) {
    throw "No staged changes remain after validation."
}

& git -C $repositoryRoot commit -m $CommitMessage
if ($LASTEXITCODE -ne 0) {
    throw "git commit failed."
}
$commit = (& git -C $repositoryRoot rev-parse HEAD).Trim()

$pushSucceeded = $false
for ($attempt = 1; $attempt -le 3; $attempt++) {
    if ($attempt -gt 1) {
        Start-Sleep -Seconds 2
    }
    & git -C $repositoryRoot push -u origin $branch
    if ($LASTEXITCODE -eq 0) {
        $pushSucceeded = $true
        break
    }
}
if (-not $pushSucceeded) {
    throw "Normal branch push failed."
}

$repositoryName = $canonicalRepository
$owner = $repositoryName.Split("/")[0]
$matching = @(
    Find-MatchingOpenPullRequestsWithRetry `
        -Repository $repositoryName `
        -Owner $owner `
        -HeadBranch $branch `
        -TargetBranch $BaseBranch
)
if ($matching.Count -gt 1) {
    throw "More than one matching open pull request exists; publication is ambiguous."
}

$prUrl = $null
if ($matching.Count -eq 1) {
    $prUrl = [string] $matching[0].html_url
}
else {
    $createOutput = @(& gh pr create `
        --repo $repositoryName `
        --draft `
        --base $BaseBranch `
        --head $branch `
        --title $PRTitle `
        --body $PRBody)
    $createExitCode = $LASTEXITCODE
    $prUrl = @(
        $createOutput |
            Where-Object { $_ -match "^https://github\.com/.+/pull/\d+$" }
    ) | Select-Object -Last 1

    if ($createExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($prUrl)) {
        $matching = @(
            Find-MatchingOpenPullRequestsWithRetry `
                -Repository $repositoryName `
                -Owner $owner `
                -HeadBranch $branch `
                -TargetBranch $BaseBranch
        )
        if ($matching.Count -ne 1) {
            throw "Draft pull request creation failed and no unique matching open PR was found."
        }
        $prUrl = [string] $matching[0].html_url
    }
}

$prNumberText = $prUrl.TrimEnd("/").Split("/")[-1]
$prNumber = 0
if (-not [int]::TryParse($prNumberText, [ref] $prNumber)) {
    throw "Unable to parse the pull request number from its URL."
}

$pr = $null
for ($attempt = 1; $attempt -le 3; $attempt++) {
    if ($attempt -gt 1) {
        Start-Sleep -Seconds 2
    }
    $prJson = & gh api "repos/$repositoryName/pulls/$prNumber"
    if ($LASTEXITCODE -eq 0) {
        $pr = $prJson | ConvertFrom-Json
        break
    }
}
if ($null -eq $pr) {
    throw "Unable to verify the created pull request through the REST API."
}
if (
    $pr.state -ne "open" -or
    $pr.head.ref -ne $branch -or
    $pr.base.ref -ne $BaseBranch -or
    -not $pr.draft -or
    $null -ne $pr.auto_merge
) {
    throw "The pull request is not a Draft or auto-merge is unexpectedly enabled."
}

$result = [ordered]@{
    branch = $branch
    commit = $commit
    repository = $repositoryName
    result_report = $normalizedReportPath
    pr_number = $pr.number
    pr_url = $pr.html_url
    draft = $pr.draft
    auto_merge = $false
    staged_files = $staged.Count
}
Write-Output ("PUBLISH_RESULT=" + ($result | ConvertTo-Json -Compress))
