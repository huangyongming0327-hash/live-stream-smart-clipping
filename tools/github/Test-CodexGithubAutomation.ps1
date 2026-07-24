[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runtimeTemp = Join-Path $repositoryRoot "runtime\temp"
$testRoot = Join-Path $runtimeTemp ("github-automation-" + [guid]::NewGuid().ToString("N"))
$realGit = (Get-Command git.exe -ErrorAction Stop).Source
$windowsPowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
$canonicalRepository = "huangyongming0327-hash/live-stream-smart-clipping"
$canonicalUrl = "https://github.com/$canonicalRepository.git"
$passed = 0
$failed = 0
$failures = [System.Collections.Generic.List[string]]::new()

function Assert-True {
    param(
        [Parameter(Mandatory = $true)][bool] $Condition,
        [Parameter(Mandatory = $true)][string] $Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)][string] $Text,
        [Parameter(Mandatory = $true)][string] $Expected,
        [Parameter(Mandatory = $true)][string] $Message
    )

    if ($Text.IndexOf($Expected, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "$Message Expected text: $Expected"
    }
}

function Invoke-TestCase {
    param(
        [Parameter(Mandatory = $true)][string] $Name,
        [Parameter(Mandatory = $true)][scriptblock] $Body
    )

    try {
        & $Body
        $script:passed++
        Write-Output "[PASS] $Name"
    }
    catch {
        $script:failed++
        $script:failures.Add("$Name`: $($_.Exception.Message)")
        Write-Output "[FAIL] $Name`: $($_.Exception.Message)"
    }
}

function Set-Utf8Text {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Content
    )

    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        [void] (New-Item -ItemType Directory -Path $parent -Force)
    }
    [IO.File]::WriteAllText(
        $Path,
        $Content,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Invoke-RealGit {
    param(
        [Parameter(Mandatory = $true)][string] $WorkingDirectory,
        [Parameter(ValueFromRemainingArguments = $true)][string[]] $GitArguments
    )

    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $gitOutput = @(& $realGit -C $WorkingDirectory @GitArguments 2>&1)
        $gitExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    if ($gitExitCode -ne 0) {
        throw "git failed in fixture: $($GitArguments -join ' ') $($gitOutput -join ' ')"
    }
}

function New-RepositoryFixture {
    param(
        [Parameter(Mandatory = $true)][string] $Name,
        [ValidateSet("None", "Canonical", "Wrong", "Local")]
        [string] $OriginMode = "Canonical"
    )

    $root = Join-Path $testRoot "repositories\$Name"
    [void] (New-Item -ItemType Directory -Path $root -Force)
    & $realGit init --initial-branch=master $root | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to initialize fixture repository."
    }
    Invoke-RealGit -WorkingDirectory $root config user.name "LiveClip Test"
    Invoke-RealGit -WorkingDirectory $root config user.email "test@liveclip.invalid"
    Invoke-RealGit -WorkingDirectory $root config core.autocrlf false

    foreach ($relative in @(
        ".github\liveclip-workflow.json",
        "tools\github\Start-CodexTask.ps1",
        "tools\github\Invoke-RepositorySafetyCheck.ps1",
        "tools\github\Invoke-SourceOnlyTests.ps1",
        "tools\github\Publish-CodexTask.ps1",
        "tools\github\Publish-CodexAudit.ps1",
        "tools\github\Get-PRHandoff.ps1"
    )) {
        $destination = Join-Path $root $relative
        $destinationParent = Split-Path -Parent $destination
        [void] (New-Item -ItemType Directory -Path $destinationParent -Force)
        Copy-Item -LiteralPath (Join-Path $repositoryRoot $relative) -Destination $destination
    }
    Set-Utf8Text -Path (Join-Path $root "README.md") -Content "# fixture`n"
    Invoke-RealGit -WorkingDirectory $root add --all
    Invoke-RealGit -WorkingDirectory $root commit -m "test: initialize fixture"

    $remote = $null
    if ($OriginMode -eq "Canonical") {
        Invoke-RealGit -WorkingDirectory $root remote add origin $canonicalUrl
    }
    elseif ($OriginMode -eq "Wrong") {
        Invoke-RealGit -WorkingDirectory $root remote add origin "https://github.com/example/wrong.git"
    }
    elseif ($OriginMode -eq "Local") {
        $remote = Join-Path $testRoot "remotes\$Name.git"
        $remoteParent = Split-Path -Parent $remote
        [void] (New-Item -ItemType Directory -Path $remoteParent -Force)
        & $realGit init --bare $remote | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to initialize fixture bare remote."
        }
        Invoke-RealGit -WorkingDirectory $root remote add origin $remote
        Invoke-RealGit -WorkingDirectory $root push -u origin master
    }

    return [pscustomobject]@{
        Root = $root
        Remote = $remote
    }
}

function New-CommandShims {
    param([Parameter(Mandatory = $true)][string] $Name)

    $shimRoot = Join-Path $testRoot "shims\$Name"
    [void] (New-Item -ItemType Directory -Path $shimRoot -Force)

    Set-Utf8Text -Path (Join-Path $shimRoot "git.cmd") -Content @'
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0git-shim.ps1" %*
exit /b %ERRORLEVEL%
'@
    Set-Utf8Text -Path (Join-Path $shimRoot "git-shim.ps1") -Content @'
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$allArguments = @($args)

if (
    $env:LIVECLIP_SHIM_CANONICAL_REMOTE -eq "1" -and
    $allArguments -contains "remote" -and
    $allArguments -contains "get-url"
) {
    Write-Output "https://github.com/huangyongming0327-hash/live-stream-smart-clipping.git"
    exit 0
}

if ($allArguments -contains "push" -and $env:LIVECLIP_SHIM_PUSH -eq "1") {
    $count = 0
    if (Test-Path -LiteralPath $env:LIVECLIP_PUSH_COUNTER) {
        [void] [int]::TryParse(
            (Get-Content -LiteralPath $env:LIVECLIP_PUSH_COUNTER -Raw).Trim(),
            [ref] $count
        )
    }
    $count++
    Set-Content -LiteralPath $env:LIVECLIP_PUSH_COUNTER -Value $count -Encoding ASCII
    $failCount = 0
    [void] [int]::TryParse($env:LIVECLIP_PUSH_FAIL_COUNT, [ref] $failCount)
    if ($count -le $failCount) {
        [Console]::Error.WriteLine("synthetic push failure $count")
        exit 1
    }
    Write-Output "synthetic normal push success"
    exit 0
}

& $env:LIVECLIP_REAL_GIT @allArguments
exit $LASTEXITCODE
'@

    Set-Utf8Text -Path (Join-Path $shimRoot "gh.cmd") -Content @'
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0gh-shim.ps1" %*
exit /b %ERRORLEVEL%
'@
    Set-Utf8Text -Path (Join-Path $shimRoot "gh-shim.ps1") -Content @'
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$allArguments = @($args)
$joined = $allArguments -join " "
$branch = $env:LIVECLIP_EXPECTED_BRANCH
$prObject = @{
    number = 2
    html_url = "https://github.com/huangyongming0327-hash/live-stream-smart-clipping/pull/2"
    draft = $true
    auto_merge = $null
    state = "open"
    head = @{ ref = $branch }
    base = @{ ref = "master" }
}

if ($env:LIVECLIP_GH_MODE -eq "handoff") {
    if ($allArguments.Count -ge 2 -and $allArguments[0] -eq "pr" -and $allArguments[1] -eq "view") {
        Write-Output $env:LIVECLIP_HANDOFF_JSON
        exit 0
    }
    if ($allArguments.Count -ge 1 -and $allArguments[0] -eq "api") {
        Write-Output "tasks/reports/TASK-TEST_RESULT.md"
        Write-Output "tasks/reports/TASK-TEST-R_AUDIT.md"
        exit 0
    }
}

if ($allArguments.Count -ge 1 -and $allArguments[0] -eq "api") {
    if ($joined -match "/pulls/2(?:\s|$)") {
        Write-Output ($prObject | ConvertTo-Json -Depth 5 -Compress)
        exit 0
    }
    if ($joined -match "/pulls(?:\s|$)") {
        if (
            $env:LIVECLIP_GH_MODE -eq "existing" -or
            (
                $env:LIVECLIP_GH_MODE -eq "create-recover" -and
                (Test-Path -LiteralPath $env:LIVECLIP_CREATE_STATE)
            )
        ) {
            Write-Output (@($prObject) | ConvertTo-Json -Depth 5 -Compress)
        }
        else {
            Write-Output "[]"
        }
        exit 0
    }
}

if ($allArguments.Count -ge 2 -and $allArguments[0] -eq "pr" -and $allArguments[1] -eq "create") {
    Set-Content -LiteralPath $env:LIVECLIP_CREATE_CALLED -Value "called" -Encoding ASCII
    if ($env:LIVECLIP_GH_MODE -eq "create-recover") {
        Set-Content -LiteralPath $env:LIVECLIP_CREATE_STATE -Value "created" -Encoding ASCII
        [Console]::Error.WriteLine("synthetic API response loss")
        exit 1
    }
    Write-Output "https://github.com/huangyongming0327-hash/live-stream-smart-clipping/pull/2"
    exit 0
}

[Console]::Error.WriteLine("Unexpected gh invocation: $joined")
exit 97
'@

    Set-Utf8Text -Path (Join-Path $shimRoot "python.cmd") -Content @'
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0python-shim.ps1" %*
exit /b %ERRORLEVEL%
'@
    Set-Utf8Text -Path (Join-Path $shimRoot "python-shim.ps1") -Content @'
Set-StrictMode -Version Latest
$joined = @($args) -join " "
$stage = if ($joined -match "experiments") {
    "asr"
}
elseif ($joined -match "pip check") {
    "pip"
}
else {
    "base"
}
Add-Content -LiteralPath $env:LIVECLIP_PYTHON_MARKER -Value $stage -Encoding ASCII
$variableName = "LIVECLIP_" + $stage.ToUpperInvariant() + "_EXIT"
$exitCodeText = [Environment]::GetEnvironmentVariable($variableName)
$exitCode = 0
[void] [int]::TryParse($exitCodeText, [ref] $exitCode)
Write-Output "synthetic python stage=$stage exit=$exitCode"
exit $exitCode
'@

    return $shimRoot
}

function Invoke-ChildPowerShell {
    param(
        [Parameter(Mandatory = $true)][string] $ScriptPath,
        [string[]] $Arguments = @(),
        [hashtable] $Environment = @{}
    )

    $saved = @{}
    foreach ($key in $Environment.Keys) {
        $saved[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
        [Environment]::SetEnvironmentVariable(
            $key,
            [string] $Environment[$key],
            "Process"
        )
    }
    try {
        $savedErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $output = @(
            & $windowsPowerShell `
                -NoProfile `
                -ExecutionPolicy Bypass `
                -File $ScriptPath `
                @Arguments 2>&1 |
                ForEach-Object { $_.ToString() }
        )
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $savedErrorActionPreference
    }
    finally {
        $ErrorActionPreference = "Stop"
        foreach ($key in $Environment.Keys) {
            [Environment]::SetEnvironmentVariable(
                $key,
                $saved[$key],
                "Process"
            )
        }
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $output -join [Environment]::NewLine
    }
}

function Get-ShimEnvironment {
    param(
        [Parameter(Mandatory = $true)][string] $ShimRoot,
        [hashtable] $Additional = @{}
    )

    $environment = @{
        PATH = "$ShimRoot;$env:PATH"
        LIVECLIP_REAL_GIT = $realGit
    }
    foreach ($key in $Additional.Keys) {
        $environment[$key] = $Additional[$key]
    }
    return $environment
}

function Add-ResultReportChange {
    param([Parameter(Mandatory = $true)][string] $Root)

    Set-Utf8Text `
        -Path (Join-Path $Root "tasks\reports\TASK-TEST_RESULT.md") `
        -Content "# TASK-TEST result`n"
}

function Use-PassingSourceTestStub {
    param([Parameter(Mandatory = $true)][string] $Root)

    Set-Utf8Text `
        -Path (Join-Path $Root "tools\github\Invoke-SourceOnlyTests.ps1") `
        -Content "Write-Output 'SOURCE_ONLY_RESULT={""status"":""passed""}'`n"
    Invoke-RealGit -WorkingDirectory $Root add tools/github/Invoke-SourceOnlyTests.ps1
    Invoke-RealGit -WorkingDirectory $Root commit -m "test: install passing source stub"
}

function Use-FailingSourceTestStub {
    param([Parameter(Mandatory = $true)][string] $Root)

    Set-Utf8Text `
        -Path (Join-Path $Root "tools\github\Invoke-SourceOnlyTests.ps1") `
        -Content "Write-Error 'synthetic source failure'`nexit 9`n"
    Invoke-RealGit -WorkingDirectory $Root add tools/github/Invoke-SourceOnlyTests.ps1
    Invoke-RealGit -WorkingDirectory $Root commit -m "test: install failing source stub"
}

function New-PublishFixture {
    param(
        [Parameter(Mandatory = $true)][string] $Name,
        [ValidateSet("Canonical", "Wrong")]
        [string] $OriginMode = "Canonical",
        [switch] $FailSourceTests,
        [switch] $StayOnMaster
    )

    $fixture = New-RepositoryFixture -Name $Name -OriginMode $OriginMode
    if ($FailSourceTests) {
        Use-FailingSourceTestStub -Root $fixture.Root
    }
    else {
        Use-PassingSourceTestStub -Root $fixture.Root
    }
    if (-not $StayOnMaster) {
        Invoke-RealGit -WorkingDirectory $fixture.Root switch -c "chore/publish-test"
    }
    Add-ResultReportChange -Root $fixture.Root
    return $fixture
}

function Invoke-PublishFixture {
    param(
        [Parameter(Mandatory = $true)] $Fixture,
        [Parameter(Mandatory = $true)][string] $ShimRoot,
        [Parameter(Mandatory = $true)][hashtable] $Environment
    )

    $arguments = @(
        "-ConfirmScope",
        "-CommitMessage", "test: publish fixture",
        "-PRTitle", "TASK-TEST: fixture",
        "-PRBody", "Synthetic fixture validation.",
        "-ResultReportPath", "tasks/reports/TASK-TEST_RESULT.md"
    )
    $combined = Get-ShimEnvironment -ShimRoot $ShimRoot -Additional $Environment
    return Invoke-ChildPowerShell `
        -ScriptPath (Join-Path $Fixture.Root "tools\github\Publish-CodexTask.ps1") `
        -Arguments $arguments `
        -Environment $combined
}

try {
    [void] (New-Item -ItemType Directory -Path $testRoot -Force)

    Invoke-TestCase -Name "Windows PowerShell 5.1 parses every GitHub script" -Body {
        $files = Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.ps1" -File
        foreach ($file in $files) {
            $parseOutput = & $windowsPowerShell -NoProfile -Command @"
`$errors = `$null
[void] [System.Management.Automation.Language.Parser]::ParseFile(
    '$($file.FullName.Replace("'", "''"))',
    [ref] `$null,
    [ref] `$errors
)
if (@(`$errors).Count -ne 0) {
    `$errors | ForEach-Object { Write-Error `$_.Message }
    exit 1
}
"@ 2>&1
            Assert-True -Condition ($LASTEXITCODE -eq 0) `
                -Message "AST parsing failed for $($file.Name): $parseOutput"
        }
    }

    Invoke-TestCase -Name "source-only first-stage failure is nonzero and stops later stages" -Body {
        $shim = New-CommandShims -Name "source-failure"
        $marker = Join-Path $testRoot "source-failure-stages.txt"
        $environment = Get-ShimEnvironment -ShimRoot $shim -Additional @{
            LIVECLIP_PYTHON_MARKER = $marker
            LIVECLIP_BASE_EXIT = "9"
            LIVECLIP_ASR_EXIT = "0"
            LIVECLIP_PIP_EXIT = "0"
        }
        $result = Invoke-ChildPowerShell `
            -ScriptPath (Join-Path $repositoryRoot "tools\github\Invoke-SourceOnlyTests.ps1") `
            -Environment $environment
        Assert-True -Condition ($result.ExitCode -ne 0) `
            -Message "Synthetic first-stage failure returned zero."
        $stages = @(Get-Content -LiteralPath $marker)
        Assert-True -Condition ($stages.Count -eq 1 -and $stages[0] -eq "base") `
            -Message "Later source-only stages ran after the first failure."
    }

    Invoke-TestCase -Name "source-only success runs all three stages and returns zero" -Body {
        $shim = New-CommandShims -Name "source-success"
        $marker = Join-Path $testRoot "source-success-stages.txt"
        $environment = Get-ShimEnvironment -ShimRoot $shim -Additional @{
            LIVECLIP_PYTHON_MARKER = $marker
            LIVECLIP_BASE_EXIT = "0"
            LIVECLIP_ASR_EXIT = "0"
            LIVECLIP_PIP_EXIT = "0"
        }
        $result = Invoke-ChildPowerShell `
            -ScriptPath (Join-Path $repositoryRoot "tools\github\Invoke-SourceOnlyTests.ps1") `
            -Environment $environment
        Assert-True -Condition ($result.ExitCode -eq 0) `
            -Message "Synthetic all-stage success returned nonzero: $($result.Output)"
        $stages = @(Get-Content -LiteralPath $marker)
        Assert-True -Condition (($stages -join ",") -eq "base,asr,pip") `
            -Message "Source-only stage order was not base, asr, pip."
        Assert-Contains -Text $result.Output -Expected '"status":"passed"' `
            -Message "Source-only success summary is missing."
    }

    Invoke-TestCase -Name "workflow contains cancellation and checked native commands" -Body {
        $workflow = Get-Content `
            -LiteralPath (Join-Path $repositoryRoot ".github\workflows\pr-checks.yml") `
            -Raw
        Assert-Contains -Text $workflow -Expected "cancel-in-progress: true" `
            -Message "Concurrency cancellation is missing."
        Assert-Contains -Text $workflow -Expected "Invoke-SourceOnlyTests.ps1" `
            -Message "Workflow does not call the unified source-only entry point."
        Assert-True -Condition ($workflow -notmatch "continue-on-error") `
            -Message "Workflow must not use continue-on-error."
        Assert-True -Condition (
            ([regex]::Matches($workflow, "\`$LASTEXITCODE -ne 0")).Count -ge 2
        ) -Message "Dependency installation commands do not both propagate failures."
    }

    foreach ($case in @(
        @{ Name = "audit-zero"; Kind = "zero"; Success = $false },
        @{ Name = "audit-one-valid"; Kind = "one-valid"; Success = $true },
        @{ Name = "audit-one-invalid"; Kind = "one-invalid"; Success = $false },
        @{ Name = "audit-two-valid"; Kind = "two-valid"; Success = $true },
        @{ Name = "audit-mixed"; Kind = "mixed"; Success = $false }
    )) {
        $caseCopy = $case
        Invoke-TestCase -Name "Publish-CodexAudit $($caseCopy.Kind)" -Body {
            $fixture = New-RepositoryFixture -Name $caseCopy.Name -OriginMode Local
            Invoke-RealGit -WorkingDirectory $fixture.Root switch -c "chore/audit-test"
            if ($caseCopy.Kind -in @("one-valid", "two-valid", "mixed")) {
                Set-Utf8Text `
                    -Path (Join-Path $fixture.Root "tasks\reports\TASK-A_AUDIT.md") `
                    -Content "# audit A`n"
            }
            if ($caseCopy.Kind -eq "two-valid") {
                Set-Utf8Text `
                    -Path (Join-Path $fixture.Root "tasks\reports\TASK-B_AUDIT.md") `
                    -Content "# audit B`n"
            }
            if ($caseCopy.Kind -in @("one-invalid", "mixed")) {
                Set-Utf8Text `
                    -Path (Join-Path $fixture.Root "src\outside.py") `
                    -Content "value = 1`n"
            }
            $shim = New-CommandShims -Name ($caseCopy.Name + "-shim")
            $environment = Get-ShimEnvironment -ShimRoot $shim -Additional @{
                LIVECLIP_SHIM_CANONICAL_REMOTE = "1"
            }
            $result = Invoke-ChildPowerShell `
                -ScriptPath (Join-Path $fixture.Root "tools\github\Publish-CodexAudit.ps1") `
                -Arguments @(
                    "-ConfirmScope",
                    "-CommitMessage", "audit: fixture"
                ) `
                -Environment $environment
            Assert-True -Condition ($result.ExitCode -eq $(if ($caseCopy.Success) { 0 } else { 1 })) `
                -Message "Unexpected audit publisher exit $($result.ExitCode): $($result.Output)"
            Assert-True -Condition ($result.Output -notmatch "property 'Count'") `
                -Message "Audit publisher still hit scalar Count failure."
            if (-not $caseCopy.Success -and $caseCopy.Kind -ne "zero") {
                Assert-Contains -Text $result.Output -Expected "may only change" `
                    -Message "Invalid audit scope did not receive the explicit path rejection."
            }
        }
    }

    Invoke-TestCase -Name "Start-CodexTask clean synchronized master" -Body {
        $fixture = New-RepositoryFixture -Name "start-synchronized" -OriginMode Local
        $shim = New-CommandShims -Name "start-synchronized-shim"
        $result = Invoke-ChildPowerShell `
            -ScriptPath (Join-Path $fixture.Root "tools\github\Start-CodexTask.ps1") `
            -Arguments @("-BranchName", "task/synchronized") `
            -Environment (Get-ShimEnvironment -ShimRoot $shim -Additional @{
                LIVECLIP_SHIM_CANONICAL_REMOTE = "1"
            })
        Assert-True -Condition ($result.ExitCode -eq 0) `
            -Message "Synchronized start failed: $($result.Output)"
        Assert-Contains -Text $result.Output -Expected '"repository":"' `
            -Message "Start output omitted repository."
        Assert-True -Condition (
            (& $realGit -C $fixture.Root branch --show-current).Trim() -eq "task/synchronized"
        ) -Message "Start did not create the requested branch."
    }

    Invoke-TestCase -Name "Start-CodexTask fast-forwards a behind master" -Body {
        $fixture = New-RepositoryFixture -Name "start-behind" -OriginMode Local
        $updater = Join-Path $testRoot "updaters\start-behind"
        & $realGit clone $fixture.Remote $updater | Out-Null
        Invoke-RealGit -WorkingDirectory $updater config user.name "LiveClip Test"
        Invoke-RealGit -WorkingDirectory $updater config user.email "test@liveclip.invalid"
        Set-Utf8Text -Path (Join-Path $updater "remote-change.txt") -Content "remote`n"
        Invoke-RealGit -WorkingDirectory $updater add remote-change.txt
        Invoke-RealGit -WorkingDirectory $updater commit -m "test: remote advance"
        Invoke-RealGit -WorkingDirectory $updater push origin master
        $remoteHead = (& $realGit -C $updater rev-parse HEAD).Trim()

        $shim = New-CommandShims -Name "start-behind-shim"
        $result = Invoke-ChildPowerShell `
            -ScriptPath (Join-Path $fixture.Root "tools\github\Start-CodexTask.ps1") `
            -Arguments @("-BranchName", "task/behind") `
            -Environment (Get-ShimEnvironment -ShimRoot $shim -Additional @{
                LIVECLIP_SHIM_CANONICAL_REMOTE = "1"
            })
        Assert-True -Condition ($result.ExitCode -eq 0) `
            -Message "Behind master did not fast-forward: $($result.Output)"
        $branchHead = (& $realGit -C $fixture.Root rev-parse HEAD).Trim()
        Assert-True -Condition ($branchHead -eq $remoteHead) `
            -Message "New task branch was not based on the updated remote master."
    }

    Invoke-TestCase -Name "Start-CodexTask rejects a diverged master" -Body {
        $fixture = New-RepositoryFixture -Name "start-diverged" -OriginMode Local
        Set-Utf8Text -Path (Join-Path $fixture.Root "local-change.txt") -Content "local`n"
        Invoke-RealGit -WorkingDirectory $fixture.Root add local-change.txt
        Invoke-RealGit -WorkingDirectory $fixture.Root commit -m "test: local advance"

        $updater = Join-Path $testRoot "updaters\start-diverged"
        & $realGit clone $fixture.Remote $updater | Out-Null
        Invoke-RealGit -WorkingDirectory $updater config user.name "LiveClip Test"
        Invoke-RealGit -WorkingDirectory $updater config user.email "test@liveclip.invalid"
        Set-Utf8Text -Path (Join-Path $updater "remote-change.txt") -Content "remote`n"
        Invoke-RealGit -WorkingDirectory $updater add remote-change.txt
        Invoke-RealGit -WorkingDirectory $updater commit -m "test: remote advance"
        Invoke-RealGit -WorkingDirectory $updater push origin master

        $shim = New-CommandShims -Name "start-diverged-shim"
        $result = Invoke-ChildPowerShell `
            -ScriptPath (Join-Path $fixture.Root "tools\github\Start-CodexTask.ps1") `
            -Arguments @("-BranchName", "task/diverged") `
            -Environment (Get-ShimEnvironment -ShimRoot $shim -Additional @{
                LIVECLIP_SHIM_CANONICAL_REMOTE = "1"
            })
        Assert-True -Condition ($result.ExitCode -ne 0) `
            -Message "Diverged master was accepted."
        $branches = @(& $realGit -C $fixture.Root branch --format="%(refname:short)")
        Assert-True -Condition ($branches -notcontains "task/diverged") `
            -Message "A branch was created after divergence."
    }

    foreach ($startCase in @(
        @{ Name = "start-no-origin"; Origin = "None"; Expected = "origin" },
        @{ Name = "start-wrong-origin"; Origin = "Wrong"; Expected = "canonical repository" }
    )) {
        $startCaseCopy = $startCase
        Invoke-TestCase -Name "Start-CodexTask rejects $($startCaseCopy.Origin) origin" -Body {
            $fixture = New-RepositoryFixture `
                -Name $startCaseCopy.Name `
                -OriginMode $startCaseCopy.Origin
            $result = Invoke-ChildPowerShell `
                -ScriptPath (Join-Path $fixture.Root "tools\github\Start-CodexTask.ps1") `
                -Arguments @("-BranchName", "task/remote-check")
            Assert-True -Condition ($result.ExitCode -ne 0) `
                -Message "Invalid Start origin was accepted."
            Assert-Contains -Text $result.Output -Expected $startCaseCopy.Expected `
                -Message "Start origin rejection was not explicit."
        }
    }

    Invoke-TestCase -Name "Publish-CodexTask test failure leaves HEAD and index unchanged" -Body {
        $fixture = New-PublishFixture -Name "publish-test-failure" -FailSourceTests
        $headBefore = (& $realGit -C $fixture.Root rev-parse HEAD).Trim()
        $shim = New-CommandShims -Name "publish-test-failure-shim"
        $result = Invoke-PublishFixture -Fixture $fixture -ShimRoot $shim -Environment @{
            LIVECLIP_GH_MODE = "existing"
            LIVECLIP_EXPECTED_BRANCH = "chore/publish-test"
            LIVECLIP_SHIM_PUSH = "1"
            LIVECLIP_PUSH_COUNTER = (Join-Path $testRoot "publish-test-failure-push.txt")
            LIVECLIP_PUSH_FAIL_COUNT = "0"
        }
        Assert-True -Condition ($result.ExitCode -ne 0) `
            -Message "Publish continued after a source-test failure."
        $headAfter = (& $realGit -C $fixture.Root rev-parse HEAD).Trim()
        $cached = @(& $realGit -C $fixture.Root diff --cached --name-only)
        Assert-True -Condition ($headAfter -eq $headBefore -and $cached.Count -eq 0) `
            -Message "Publish staged or committed after a source-test failure."
    }

    Invoke-TestCase -Name "Publish-CodexTask rejects wrong remote" -Body {
        $fixture = New-PublishFixture -Name "publish-wrong-remote" -OriginMode Wrong
        $shim = New-CommandShims -Name "publish-wrong-remote-shim"
        $result = Invoke-PublishFixture -Fixture $fixture -ShimRoot $shim -Environment @{}
        Assert-True -Condition ($result.ExitCode -ne 0) `
            -Message "Publish accepted a wrong GitHub repository."
        Assert-Contains -Text $result.Output -Expected "canonical repository" `
            -Message "Publish wrong-remote rejection was not explicit."
    }

    Invoke-TestCase -Name "Publish-CodexTask rejects master" -Body {
        $fixture = New-PublishFixture -Name "publish-master" -StayOnMaster
        $shim = New-CommandShims -Name "publish-master-shim"
        $result = Invoke-PublishFixture -Fixture $fixture -ShimRoot $shim -Environment @{}
        Assert-True -Condition ($result.ExitCode -ne 0) `
            -Message "Publish accepted master."
        Assert-Contains -Text $result.Output -Expected "Publishing is allowed only" `
            -Message "Publish master rejection was not explicit."
    }

    Invoke-TestCase -Name "Publish-CodexTask reuses one existing PR without create" -Body {
        $fixture = New-PublishFixture -Name "publish-existing"
        $shim = New-CommandShims -Name "publish-existing-shim"
        $createCalled = Join-Path $testRoot "publish-existing-create.txt"
        $secretMarker = "SYNTHETIC_AUTH_VALUE"
        $result = Invoke-PublishFixture -Fixture $fixture -ShimRoot $shim -Environment @{
            LIVECLIP_GH_MODE = "existing"
            LIVECLIP_EXPECTED_BRANCH = "chore/publish-test"
            LIVECLIP_CREATE_CALLED = $createCalled
            LIVECLIP_CREATE_STATE = (Join-Path $testRoot "publish-existing-state.txt")
            LIVECLIP_SHIM_PUSH = "1"
            LIVECLIP_PUSH_COUNTER = (Join-Path $testRoot "publish-existing-push.txt")
            LIVECLIP_PUSH_FAIL_COUNT = "0"
            LIVECLIP_SYNTHETIC_AUTH = $secretMarker
        }
        Assert-True -Condition ($result.ExitCode -eq 0) `
            -Message "Existing PR recovery failed: $($result.Output)"
        Assert-True -Condition (-not (Test-Path -LiteralPath $createCalled)) `
            -Message "Publisher called PR create despite a unique existing PR."
        Assert-True -Condition ($result.Output -notmatch [regex]::Escape($secretMarker)) `
            -Message "Publisher output exposed the synthetic auth marker."
    }

    Invoke-TestCase -Name "Publish-CodexTask recovers unique PR after create API failure" -Body {
        $fixture = New-PublishFixture -Name "publish-create-recover"
        $shim = New-CommandShims -Name "publish-create-recover-shim"
        $createCalled = Join-Path $testRoot "publish-create-recover-called.txt"
        $result = Invoke-PublishFixture -Fixture $fixture -ShimRoot $shim -Environment @{
            LIVECLIP_GH_MODE = "create-recover"
            LIVECLIP_EXPECTED_BRANCH = "chore/publish-test"
            LIVECLIP_CREATE_CALLED = $createCalled
            LIVECLIP_CREATE_STATE = (Join-Path $testRoot "publish-create-recover-state.txt")
            LIVECLIP_SHIM_PUSH = "1"
            LIVECLIP_PUSH_COUNTER = (Join-Path $testRoot "publish-create-recover-push.txt")
            LIVECLIP_PUSH_FAIL_COUNT = "0"
        }
        Assert-True -Condition ($result.ExitCode -eq 0) `
            -Message "Unique PR recovery after create failure failed: $($result.Output)"
        Assert-True -Condition (Test-Path -LiteralPath $createCalled) `
            -Message "Create-failure recovery case never attempted PR creation."
        Assert-Contains -Text $result.Output -Expected '"pr_number":2' `
            -Message "Recovered PR was not verified."
    }

    Invoke-TestCase -Name "Publish-CodexTask caps normal push retries at three" -Body {
        $fixture = New-PublishFixture -Name "publish-push-cap"
        $shim = New-CommandShims -Name "publish-push-cap-shim"
        $counter = Join-Path $testRoot "publish-push-cap.txt"
        $result = Invoke-PublishFixture -Fixture $fixture -ShimRoot $shim -Environment @{
            LIVECLIP_GH_MODE = "existing"
            LIVECLIP_EXPECTED_BRANCH = "chore/publish-test"
            LIVECLIP_CREATE_CALLED = (Join-Path $testRoot "publish-push-cap-create.txt")
            LIVECLIP_CREATE_STATE = (Join-Path $testRoot "publish-push-cap-state.txt")
            LIVECLIP_SHIM_PUSH = "1"
            LIVECLIP_PUSH_COUNTER = $counter
            LIVECLIP_PUSH_FAIL_COUNT = "99"
        }
        Assert-True -Condition ($result.ExitCode -ne 0) `
            -Message "Publisher reported success after all synthetic pushes failed."
        $attempts = [int] (Get-Content -LiteralPath $counter -Raw)
        Assert-True -Condition ($attempts -eq 3) `
            -Message "Publisher used $attempts push attempts instead of three."
    }

    Invoke-TestCase -Name "Get-PRHandoff reports audit score, SHA, reports, and eligibility" -Body {
        $fixture = New-RepositoryFixture -Name "handoff-fields" -OriginMode Canonical
        Set-Utf8Text `
            -Path (Join-Path $fixture.Root "tasks\reports\TASK-TEST_RESULT.md") `
            -Content "# TASK-TEST result`n"
        Copy-Item `
            -LiteralPath (Join-Path $repositoryRoot "tasks\reports\TASK-GITHUB-002-FIX-R_AUDIT.md") `
            -Destination (Join-Path $fixture.Root "tasks\reports\TASK-TEST-R_AUDIT.md")
        Invoke-RealGit -WorkingDirectory $fixture.Root add --all
        Invoke-RealGit -WorkingDirectory $fixture.Root commit -m "test: add handoff reports"
        $headSha = (& $realGit -C $fixture.Root rev-parse HEAD).Trim()
        $handoffJson = [ordered]@{
            url = "https://github.com/$canonicalRepository/pull/2"
            number = 2
            title = "TASK-TEST"
            state = "OPEN"
            isDraft = $true
            mergeStateStatus = "CLEAN"
            mergeable = "MERGEABLE"
            mergedAt = $null
            reviewDecision = ""
            autoMergeRequest = $null
            headRefName = "chore/test"
            headRefOid = $headSha
            baseRefName = "master"
            statusCheckRollup = @(
                @{ name = "repository-safety"; status = "COMPLETED"; conclusion = "SUCCESS"; completedAt = "2026-01-01T00:00:03Z"; detailsUrl = "https://example.invalid/1" },
                @{ name = "lightweight-tests"; status = "COMPLETED"; conclusion = "SUCCESS"; completedAt = "2026-01-01T00:00:02Z"; detailsUrl = "https://example.invalid/2" },
                @{ name = "task-report-gate"; status = "COMPLETED"; conclusion = "SUCCESS"; completedAt = "2026-01-01T00:00:01Z"; detailsUrl = "https://example.invalid/3" }
            )
        } | ConvertTo-Json -Depth 6 -Compress
        $shim = New-CommandShims -Name "handoff-fields-shim"
        $result = Invoke-ChildPowerShell `
            -ScriptPath (Join-Path $fixture.Root "tools\github\Get-PRHandoff.ps1") `
            -Arguments @("-PRNumber", "2") `
            -Environment (Get-ShimEnvironment -ShimRoot $shim -Additional @{
                LIVECLIP_GH_MODE = "handoff"
                LIVECLIP_HANDOFF_JSON = $handoffJson
            })
        Assert-True -Condition ($result.ExitCode -eq 0) `
            -Message "Handoff failed: $($result.Output)"
        $handoffLine = @(
            $result.Output -split "\r?\n" |
                Where-Object { $_ -like "PR_HANDOFF=*" }
        ) | Select-Object -Last 1
        $handoff = $handoffLine.Substring("PR_HANDOFF=".Length) | ConvertFrom-Json
        Assert-True -Condition (
            $handoff.repository -eq $canonicalRepository -and
            $handoff.head_sha -eq $headSha -and
            $handoff.result_report_exists -and
            $handoff.audit_report_exists -and
            [double] $handoff.audit_score -eq 65 -and
            -not [string]::IsNullOrWhiteSpace($handoff.audit_conclusion) -and
            $handoff.required_checks_all_success -and
            $handoff.unresolved_blockers -and
            -not $handoff.eligible_for_manual_merge
        ) -Message "Handoff omitted or miscomputed required fields."
    }

    Invoke-TestCase -Name "Get-PRHandoff rejects wrong remote before gh" -Body {
        $fixture = New-RepositoryFixture -Name "handoff-wrong-remote" -OriginMode Wrong
        $result = Invoke-ChildPowerShell `
            -ScriptPath (Join-Path $fixture.Root "tools\github\Get-PRHandoff.ps1") `
            -Arguments @("-PRNumber", "2")
        Assert-True -Condition ($result.ExitCode -ne 0) `
            -Message "Handoff accepted a wrong repository."
        Assert-Contains -Text $result.Output -Expected "canonical repository" `
            -Message "Handoff wrong-remote rejection was not explicit."
    }

    Invoke-TestCase -Name "repository safety accepts safe text and rejects unsafe samples" -Body {
        $fixture = New-RepositoryFixture -Name "safety-samples" -OriginMode None
        Set-Utf8Text -Path (Join-Path $fixture.Root "safe.txt") -Content "safe fixture`n"
        $safe = Invoke-ChildPowerShell `
            -ScriptPath (Join-Path $fixture.Root "tools\github\Invoke-RepositorySafetyCheck.ps1") `
            -Arguments @("-RepositoryRoot", $fixture.Root, "-Scope", "All")
        Assert-True -Condition ($safe.ExitCode -eq 0) `
            -Message "Safe repository sample was rejected: $($safe.Output)"

        $syntheticSecret = "gh" + "p_" + ("A" * 30)
        Set-Utf8Text -Path (Join-Path $fixture.Root "unsafe.txt") -Content $syntheticSecret
        Set-Utf8Text -Path (Join-Path $fixture.Root "sample.mp4") -Content "not media"
        $unsafe = Invoke-ChildPowerShell `
            -ScriptPath (Join-Path $fixture.Root "tools\github\Invoke-RepositorySafetyCheck.ps1") `
            -Arguments @("-RepositoryRoot", $fixture.Root, "-Scope", "All")
        Assert-True -Condition ($unsafe.ExitCode -ne 0) `
            -Message "Unsafe repository samples were accepted."
        Assert-Contains -Text $unsafe.Output -Expected "high-confidence-secret" `
            -Message "Synthetic secret was not rejected."
        Assert-Contains -Text $unsafe.Output -Expected "forbidden-extension" `
            -Message "Synthetic media extension was not rejected."
    }
}
finally {
    $resolvedRuntimeTemp = [IO.Path]::GetFullPath($runtimeTemp).TrimEnd("\") + "\"
    $resolvedTestRoot = [IO.Path]::GetFullPath($testRoot)
    if (
        $resolvedTestRoot.StartsWith(
            $resolvedRuntimeTemp,
            [StringComparison]::OrdinalIgnoreCase
        ) -and
        (Test-Path -LiteralPath $resolvedTestRoot)
    ) {
        Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
    }
}

$summary = [ordered]@{
    status = if ($failed -eq 0) { "passed" } else { "failed" }
    passed = $passed
    failed = $failed
    failures = @($failures)
}
Write-Output ("GITHUB_AUTOMATION_TEST_RESULT=" + ($summary | ConvertTo-Json -Depth 5 -Compress))
if ($failed -ne 0) {
    exit 1
}
