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

& git -C $repositoryRoot push -u origin $branch
if ($LASTEXITCODE -ne 0) {
    throw "Normal branch push failed."
}

$prUrl = (& gh pr create `
    --repo ((& gh repo view --json nameWithOwner --jq .nameWithOwner).Trim()) `
    --draft `
    --base $BaseBranch `
    --head $branch `
    --title $PRTitle `
    --body $PRBody).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($prUrl)) {
    throw "Draft pull request creation failed."
}

$pr = & gh pr view $prUrl --json url,number,state,isDraft,autoMergeRequest,headRefName,baseRefName |
    ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "Unable to verify the created pull request."
}
if (-not $pr.isDraft -or $null -ne $pr.autoMergeRequest) {
    throw "The pull request is not a Draft or auto-merge is unexpectedly enabled."
}

$result = [ordered]@{
    branch = $branch
    commit = $commit
    pr_number = $pr.number
    pr_url = $pr.url
    draft = $pr.isDraft
    auto_merge = $false
    staged_files = $staged.Count
}
Write-Output ("PUBLISH_RESULT=" + ($result | ConvertTo-Json -Compress))
