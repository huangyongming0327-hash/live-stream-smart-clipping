# Codex GitHub workflow

## Principles

- The original local repository is a private archive and is never used as a push source.
- Public development starts from the sanitized repository with a new Git history.
- Direct development on `master`, force push, branch deletion through history rewriting, and automatic merging are prohibited.
- One task uses one `task/`, `fix/`, or `chore/` branch.
- Models, media, runtime data, environments, caches, logs, secrets, and user data never enter Git.
- Local Codex automation is bound to the canonical repository declared in `.github/liveclip-workflow.json`; another owner, repository, host, missing origin, or ambiguous origin is rejected.

## Start a task

Begin from a clean local `master`:

```powershell
.\tools\github\Start-CodexTask.ps1 -BranchName 'task/TASK-ID-short-name'
```

The script refuses a dirty worktree, a non-`master` starting point, an invalid prefix, an existing branch, or a non-canonical origin. Before it creates the branch, it runs `git pull --ff-only origin master` and verifies that local `master` exactly matches `origin/master`. Network failure, a local-ahead branch, or a divergence stops task creation.

## Publish a task

Review `git status` and the task report, then explicitly confirm that all non-ignored changes belong to the task:

```powershell
.\tools\github\Publish-CodexTask.ps1 `
  -ConfirmScope `
  -CommitMessage 'task: concise description' `
  -PRTitle 'TASK-ID: concise description' `
  -PRBody 'Summary, impact, validation, and known limitations.' `
  -ResultReportPath 'tasks/reports/TASK-ID_RESULT.md'
```

The publisher first verifies the canonical repository and the exact result report named by `-ResultReportPath`. It then runs `Invoke-SourceOnlyTests.ps1`. If any base test, ASR experiment test, or `pip check` command fails, the script stops before staging, committing, pushing, or creating a PR.

After tests pass, the publisher scans publish candidates, stages the confirmed scope, scans the Git index again, runs `git diff --cached --check`, commits, and performs at most three normal push attempts. It reuses one existing open PR with the same head/base instead of creating a duplicate. A new PR is always Draft. It verifies that auto-merge is disabled and never calls a merge API.

## Why the CI once looked green while tests failed

The earlier workflow ran two pytest commands and `pip check` inside one PowerShell block. PowerShell 5.1 did not automatically make the whole block fail when the first pytest command returned nonzero. The later successful `pip check` became the block's final exit result, so GitHub displayed a green check even though the log contained `2 failed`.

The workflow and local publisher now share `Invoke-SourceOnlyTests.ps1`. It reads `$LASTEXITCODE` immediately after each native command and stops on the first nonzero value. Dependency installation commands have the same explicit checks. A real test failure therefore makes `lightweight-tests` red; a later command cannot overwrite it. The workflow also cancels an older run when a newer commit for the same PR or ref starts.

## Independent audit

An auditor may only add or update `tasks/reports/*_AUDIT.md` on the task branch:

```powershell
.\tools\github\Publish-CodexAudit.ps1 `
  -ConfirmScope `
  -CommitMessage 'audit: TASK-ID independent review'
```

The audit publisher treats zero, one, or many changed paths as an array. It accepts one or more `tasks/reports/*_AUDIT.md` files only, and rejects every source, test, configuration, result-report, or mixed change. It verifies the canonical origin, runs the repository safety gate, commits the reports, and performs a normal push to the current branch. A report may identify problems and recommend a follow-up fix, but it must not silently repair implementation files.

## Handoff

```powershell
.\tools\github\Get-PRHandoff.ps1
```

The command reports repository, PR URL/number, Draft state, base/head branches, head SHA, merge/review/auto-merge state, all three required checks, RESULT/AUDIT reports, audit score and conclusion, unresolved blockers, and two separate eligibility fields:

- `eligible_to_mark_ready` means a Draft has met the automated and independent-audit gates. The user may decide whether to move it out of Draft.
- `eligible_for_manual_merge` additionally requires the PR already to be Ready. It never means automation may merge.

GitHub's green icon alone is not enough. The required checks must exist and report `SUCCESS`, the relevant test log must show real `0 failed`, and an independent audit must pass the configured score/blocker gate. The user resolves conversations and makes the final manual merge decision.

## Rollback

- Before merge, close the PR and delete only its exact task branch.
- After merge, prefer a new `revert/`-equivalent `fix/` task and `git revert` through a PR.
- Never use `git reset --hard`, `git clean`, force push, or history rewriting as routine rollback.
- Never delete or modify the original private archive, original media, models, or user data.
