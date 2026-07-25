[CmdletBinding()]
param(
    [int] $PRNumber
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
    foreach ($property in @(
        "canonical_repository",
        "base_branch",
        "audit_score_threshold",
        "required_checks"
    )) {
        if ($policy.PSObject.Properties.Name -notcontains $property) {
            throw "Workflow policy is missing required property '$property'."
        }
    }
    if (
        $policy.canonical_repository -notmatch "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$" -or
        [string]::IsNullOrWhiteSpace($policy.base_branch) -or
        [int] $policy.audit_score_threshold -lt 0 -or
        [int] $policy.audit_score_threshold -gt 100 -or
        @($policy.required_checks).Count -eq 0
    ) {
        throw "Workflow policy contains invalid handoff settings."
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

function Get-ReportEntry {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $HeadSha
    )

    & git -C $repositoryRoot cat-file -e "$($HeadSha):$Path"
    $exists = $LASTEXITCODE -eq 0
    $commitTime = 0L
    if ($exists) {
        $commitTimeText = (& git -C $repositoryRoot log -1 --format=%ct $HeadSha -- $Path).Trim()
        if ($LASTEXITCODE -eq 0) {
            [void] [long]::TryParse($commitTimeText, [ref] $commitTime)
        }
    }
    return [pscustomobject]@{
        path = $Path
        exists = $exists
        commit_time = $commitTime
    }
}

function Get-ReportContent {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $HeadSha
    )

    $lines = @(& git -C $repositoryRoot show "$($HeadSha):$Path")
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read report '$Path' from PR head."
    }
    return $lines -join [Environment]::NewLine
}

$policy = Get-WorkflowPolicy
$canonicalRepository = [string] $policy.canonical_repository
$requiredCheckNames = @($policy.required_checks | ForEach-Object { [string] $_ })
$auditScoreThreshold = [int] $policy.audit_score_threshold
Assert-CanonicalOrigin -CanonicalRepository $canonicalRepository

$arguments = @(
    "pr", "view",
    "--repo", $canonicalRepository,
    "--json",
    "url,number,title,state,isDraft,mergeStateStatus,mergeable,mergedAt,reviewDecision,statusCheckRollup,autoMergeRequest,headRefName,headRefOid,baseRefName"
)
if ($PRNumber -gt 0) {
    $arguments += $PRNumber
}

$json = & gh @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Unable to resolve the pull request handoff."
}
$pr = $json | ConvertFrom-Json

$changedFiles = @(& gh api --paginate `
    "repos/$canonicalRepository/pulls/$($pr.number)/files" `
    --jq ".[].filename")
if ($LASTEXITCODE -ne 0) {
    throw "Unable to list pull request files."
}
$changedFiles = @(
    $changedFiles |
        Where-Object { $_ } |
        ForEach-Object { $_.Replace("\", "/") } |
        Sort-Object -Unique
)

$resultReportEntries = @(
    $changedFiles |
        Where-Object { $_ -match "^tasks/reports/.+_RESULT\.md$" } |
        ForEach-Object {
            Get-ReportEntry -Path $_ -HeadSha $pr.headRefOid
        }
)
$auditReportEntries = @(
    $changedFiles |
        Where-Object { $_ -match "^tasks/reports/.+_AUDIT\.md$" } |
        ForEach-Object {
            Get-ReportEntry -Path $_ -HeadSha $pr.headRefOid
        }
)

$latestResult = @(
    $resultReportEntries |
        Where-Object { $_.exists } |
        Sort-Object commit_time, path -Descending
) | Select-Object -First 1
$latestAudit = @(
    $auditReportEntries |
        Where-Object { $_.exists } |
        Sort-Object commit_time, path -Descending
) | Select-Object -First 1

$auditScore = $null
$auditConclusion = $null
$unresolvedBlockers = $true
$auditPassed = $false
if ($null -ne $latestAudit) {
    $auditContent = Get-ReportContent `
        -Path $latestAudit.path `
        -HeadSha $pr.headRefOid

    $scoreMatch = [regex]::Match(
        $auditContent,
        "(?im)(?:\u603B\u5206|total\s+score)[\uFF1A:]\s*\**\s*(?<score>\d+(?:\.\d+)?)\s*/\s*100"
    )
    if ($scoreMatch.Success) {
        $parsedScore = 0.0
        if ([double]::TryParse(
            $scoreMatch.Groups["score"].Value,
            [Globalization.NumberStyles]::Number,
            [Globalization.CultureInfo]::InvariantCulture,
            [ref] $parsedScore
        )) {
            $auditScore = $parsedScore
        }
    }

    $conclusionMatch = [regex]::Match(
        $auditContent,
        "(?im)^\**\s*(?:\u6700\u7EC8\u7ED3\u8BBA|\u5BA1\u6838\u7ED3\u8BBA|audit\s+conclusion)[\uFF1A:]\s*\**\s*(?<conclusion>[^\r\n*]+)"
    )
    if (-not $conclusionMatch.Success) {
        $conclusionMatch = [regex]::Match(
            $auditContent,
            "(?im)(?:\u7B49\u7EA7|\u7ED3\u8BBA)[\uFF1A:]\s*\**\s*(?<conclusion>\u901A\u8FC7|\u6709\u6761\u4EF6\u901A\u8FC7|\u4E0D\u901A\u8FC7|\u9700\u8981[^\r\n*]+)"
        )
    }
    if ($conclusionMatch.Success) {
        $auditConclusion = $conclusionMatch.Groups["conclusion"].Value.Trim().TrimEnd(
            [char] 0x3002
        )
    }
    if ($null -ne $auditConclusion) {
        $auditPassed = $auditConclusion -match "^(\u901A\u8FC7|\u6709\u6761\u4EF6\u901A\u8FC7)(?:$|[\uFF0C,\uFF1B;\u3002\s])"
    }

    $blockerSection = [regex]::Match(
        $auditContent,
        "(?ms)^##\s+[^\r\n]*\u963B\u65AD\u95EE\u9898[^\r\n]*\r?\n(?<body>.*?)(?=^##\s+|\z)"
    )
    if ($blockerSection.Success) {
        $blockerBody = $blockerSection.Groups["body"].Value
        if ($blockerBody -match "(?im)(\u672A\u53D1\u73B0|\u6CA1\u6709|\u65E0)\s*[^\r\n]{0,16}\u963B\u65AD") {
            $unresolvedBlockers = $false
        }
        elseif ($blockerBody -match "(?im)^###\s+|B-\d+") {
            $unresolvedBlockers = $true
        }
        else {
            $unresolvedBlockers = -not $auditPassed
        }
    }
    else {
        $unresolvedBlockers = -not $auditPassed
    }
}

$requiredChecks = @(
    foreach ($requiredName in $requiredCheckNames) {
        $matches = @($pr.statusCheckRollup | Where-Object { $_.name -eq $requiredName })
        $latestMatch = @(
            $matches | Sort-Object completedAt -Descending
        ) | Select-Object -First 1
        [ordered]@{
            name = $requiredName
            present = ($matches.Count -gt 0)
            status = if ($null -ne $latestMatch) { $latestMatch.status } else { $null }
            conclusion = if ($null -ne $latestMatch) { $latestMatch.conclusion } else { $null }
            url = if ($null -ne $latestMatch) { $latestMatch.detailsUrl } else { $null }
        }
    }
)
$checksAllSuccess = @(
    $requiredChecks | Where-Object {
        -not $_.present -or
        [string] $_.status -ne "COMPLETED" -or
        [string] $_.conclusion -ne "SUCCESS"
    }
).Count -eq 0

$merged = $null -ne $pr.mergedAt
$autoMerge = $null -ne $pr.autoMergeRequest
$resultReportExists = $null -ne $latestResult
$auditReportExists = $null -ne $latestAudit
$auditScoreMeetsThreshold = (
    $null -ne $auditScore -and
    [double] $auditScore -ge $auditScoreThreshold
)
$commonEligibility = (
    $pr.state -eq "OPEN" -and
    -not $merged -and
    $pr.mergeable -eq "MERGEABLE" -and
    $checksAllSuccess -and
    $resultReportExists -and
    $auditReportExists -and
    $auditPassed -and
    $auditScoreMeetsThreshold -and
    -not $unresolvedBlockers -and
    -not $autoMerge
)
$eligibleToMarkReady = $commonEligibility -and [bool] $pr.isDraft
$eligibleForManualMerge = $commonEligibility -and -not [bool] $pr.isDraft

$chatGptHandoff = if ($eligibleForManualMerge) {
    "PR #$($pr.number) has successful required checks and a passing audit; it is eligible for the user's manual merge decision."
}
elseif ($eligibleToMarkReady) {
    "PR #$($pr.number) is still Draft but has met the automated and audit gates; the user may decide whether to mark it Ready."
}
else {
    "PR #$($pr.number) is not eligible for Ready or manual merge; keep it unmerged and resolve the reported gates first."
}

$handoff = [ordered]@{
    repository = $canonicalRepository
    pr_url = $pr.url
    pr_number = $pr.number
    title = $pr.title
    state = $pr.state
    draft = [bool] $pr.isDraft
    base_branch = $pr.baseRefName
    head_branch = $pr.headRefName
    head_sha = $pr.headRefOid
    merged = $merged
    merge_state = $pr.mergeStateStatus
    mergeable = $pr.mergeable
    review_decision = $pr.reviewDecision
    auto_merge = $autoMerge
    required_checks = $requiredChecks
    required_checks_all_success = $checksAllSuccess
    result_reports = @($resultReportEntries)
    result_report_path = if ($null -ne $latestResult) { $latestResult.path } else { $null }
    result_report_exists = $resultReportExists
    audit_reports = @($auditReportEntries)
    audit_report_path = if ($null -ne $latestAudit) { $latestAudit.path } else { $null }
    audit_report_exists = $auditReportExists
    audit_score = $auditScore
    audit_score_threshold = $auditScoreThreshold
    audit_conclusion = $auditConclusion
    unresolved_blockers = $unresolvedBlockers
    eligible_to_mark_ready = $eligibleToMarkReady
    eligible_for_manual_merge = $eligibleForManualMerge
    chatgpt_handoff = $chatGptHandoff
}

Write-Output ("PR_HANDOFF=" + ($handoff | ConvertTo-Json -Depth 7 -Compress))
