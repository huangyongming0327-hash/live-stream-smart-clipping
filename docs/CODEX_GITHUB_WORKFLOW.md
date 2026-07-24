# Codex GitHub workflow

## Principles

- The original local repository is a private archive and is never used as a push source.
- Public development starts from the sanitized repository with a new Git history.
- Direct development on `master`, force push, branch deletion through history rewriting, and automatic merging are prohibited.
- One task uses one `task/`, `fix/`, or `chore/` branch.
- Models, media, runtime data, environments, caches, logs, secrets, and user data never enter Git.

## Start a task

Begin from a clean local `master`:

```powershell
.\tools\github\Start-CodexTask.ps1 -BranchName 'task/TASK-ID-short-name'
```

The script refuses a dirty worktree, a non-`master` starting point, an invalid prefix, or an existing branch.

## Publish a task

Review `git status` and the task report, then explicitly confirm that all non-ignored changes belong to the task:

```powershell
.\tools\github\Publish-CodexTask.ps1 `
  -ConfirmScope `
  -CommitMessage 'task: concise description' `
  -PRTitle 'TASK-ID: concise description' `
  -PRBody 'Summary, impact, validation, and known limitations.'
```

The script scans publish candidates, stages the confirmed scope, scans the Git index again, runs `git diff --cached --check`, commits, performs a normal push, and opens a Draft PR. It verifies that GitHub auto-merge is not enabled for the PR. It never calls a merge API.

## Independent audit

An auditor may only add or update `tasks/reports/*_AUDIT.md` on the task branch:

```powershell
.\tools\github\Publish-CodexAudit.ps1 `
  -ConfirmScope `
  -CommitMessage 'audit: TASK-ID independent review'
```

The audit publisher rejects any source, test, configuration, or non-audit-report change. A report may identify problems and recommend a follow-up fix, but it must not silently repair implementation files.

## Handoff

```powershell
.\tools\github\Get-PRHandoff.ps1
```

The command reports the PR URL, Draft state, checks, review state, merge state, and auto-merge state. The user resolves conversations and manually decides whether to merge.

## Rollback

- Before merge, close the PR and delete only its exact task branch.
- After merge, prefer a new `revert/`-equivalent `fix/` task and `git revert` through a PR.
- Never use `git reset --hard`, `git clean`, force push, or history rewriting as routine rollback.
- Never delete or modify the original private archive, original media, models, or user data.
