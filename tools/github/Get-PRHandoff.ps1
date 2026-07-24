[CmdletBinding()]
param(
    [int] $PRNumber
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$arguments = @(
    "pr", "view",
    "--json",
    "url,number,title,state,isDraft,mergeStateStatus,reviewDecision,statusCheckRollup,autoMergeRequest,headRefName,baseRefName"
)
if ($PRNumber -gt 0) {
    $arguments += $PRNumber
}

$json = & gh @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Unable to resolve the pull request handoff."
}

$pr = $json | ConvertFrom-Json
$handoff = [ordered]@{
    number = $pr.number
    url = $pr.url
    title = $pr.title
    state = $pr.state
    draft = $pr.isDraft
    base = $pr.baseRefName
    head = $pr.headRefName
    merge_state = $pr.mergeStateStatus
    review_decision = $pr.reviewDecision
    auto_merge = ($null -ne $pr.autoMergeRequest)
    checks = @(
        $pr.statusCheckRollup | ForEach-Object {
            [ordered]@{
                name = $_.name
                status = $_.status
                conclusion = $_.conclusion
            }
        }
    )
}

Write-Output ("PR_HANDOFF=" + ($handoff | ConvertTo-Json -Depth 5 -Compress))
& gh pr checks $pr.number
if ($LASTEXITCODE -notin @(0, 8)) {
    throw "Unable to read pull request checks."
}
