[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $BranchName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

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
if ($LASTEXITCODE -ne 0 -or $currentBranch -ne "master") {
    throw "Tasks must start from the local master branch."
}

& git -C $repositoryRoot show-ref --verify --quiet "refs/heads/$BranchName"
if ($LASTEXITCODE -eq 0) {
    throw "The local branch already exists: $BranchName"
}

& git -C $repositoryRoot switch -c $BranchName
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create task branch: $BranchName"
}

Write-Output "TASK_BRANCH=$BranchName"
