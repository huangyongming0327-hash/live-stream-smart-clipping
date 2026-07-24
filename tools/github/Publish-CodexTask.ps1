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

    [string] $BaseBranch = "master"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$safetyScript = Join-Path $PSScriptRoot "Invoke-RepositorySafetyCheck.ps1"

if (-not $ConfirmScope) {
    throw "Pass -ConfirmScope only after reviewing that every non-ignored change belongs to this task."
}

$branch = (& git -C $repositoryRoot branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Unable to determine the current branch."
}
if ($branch -eq $BaseBranch -or $branch -notmatch "^(task|fix|chore)/") {
    throw "Publishing is allowed only from a task/, fix/, or chore/ branch."
}

$changes = @(& git -C $repositoryRoot status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $changes.Count -eq 0) {
    throw "No publishable worktree changes were found."
}

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

$remoteUrl = (& git -C $repositoryRoot remote get-url origin).Trim().TrimEnd("/")
if ($remoteUrl.EndsWith(".git", [StringComparison]::OrdinalIgnoreCase)) {
    $remoteUrl = $remoteUrl.Substring(0, $remoteUrl.Length - 4)
}
if ($remoteUrl -notmatch "github\.com[/:](?<owner>[^/]+)/(?<repository>[^/]+)$") {
    throw "Unable to derive the GitHub repository from origin."
}
$owner = $Matches.owner
$repositoryName = "$owner/$($Matches.repository)"

$createOutput = @(& gh pr create `
    --repo $repositoryName `
    --draft `
    --base $BaseBranch `
    --head $branch `
    --title $PRTitle `
    --body $PRBody)
$createExitCode = $LASTEXITCODE
$prUrl = (
    $createOutput |
        Where-Object { $_ -match "^https://github\.com/.+/pull/\d+$" } |
        Select-Object -Last 1
)

if ($createExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($prUrl)) {
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        if ($attempt -gt 1) {
            Start-Sleep -Seconds 2
        }
        $pullsJson = & gh api --method GET "repos/$repositoryName/pulls" `
            -f state=open `
            -f "head=${owner}:$branch" `
            -f "base=$BaseBranch"
        if ($LASTEXITCODE -eq 0) {
            $pullsParsed = $pullsJson | ConvertFrom-Json
            $pulls = @($pullsParsed | Where-Object { $null -ne $_ })
            $matching = @($pulls | Where-Object {
                $_.head.ref -eq $branch -and $_.base.ref -eq $BaseBranch
            })
            if ($matching.Count -eq 1) {
                $prUrl = $matching[0].html_url
                break
            }
        }
    }
    if ([string]::IsNullOrWhiteSpace($prUrl)) {
        throw "Draft pull request creation failed and no matching open PR was found."
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
if (-not $pr.draft -or $null -ne $pr.auto_merge) {
    throw "The pull request is not a Draft or auto-merge is unexpectedly enabled."
}

$result = [ordered]@{
    branch = $branch
    commit = $commit
    pr_number = $pr.number
    pr_url = $pr.html_url
    draft = $pr.draft
    auto_merge = $false
    staged_files = $staged.Count
}
Write-Output ("PUBLISH_RESULT=" + ($result | ConvertTo-Json -Compress))
