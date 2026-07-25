# LiveClip agent rules

## Project goal

Build a Windows-local desktop application that turns long livestream recordings into reviewable short-video candidates while keeping media and intermediate data under user control.

## Current phase

- The project is only in technical validation and skeleton-building.
- Do not attempt to develop the complete application in one task.
- One task must handle one clear, bounded goal.

## Safety and storage constraints

- Never delete an original video.
- Do not write large files, models, caches, or virtual environments to the C drive by default.
- Never commit API keys, access tokens, credentials, or real secrets.
- Do not download large models without explicit user permission.
- Prefer temporary files plus atomic replacement when writing files that may already exist.

## Quality rules

- Run relevant tests after every modification.
- Update `docs/CURRENT_STATUS.md` when a task is completed.
- Report failures and unverified facts honestly; never fabricate success.

## GitHub task workflow

- `Start-CodexTask.ps1` must verify the canonical repository and synchronize the local base branch with `git pull --ff-only` before creating a task branch.
- `Publish-CodexTask.ps1` must verify the canonical repository, require the named result report, and run the shared source-only test entry point before staging or committing.
- `Publish-CodexAudit.ps1` may publish only `tasks/reports/*_AUDIT.md`; it may not mix source, test, configuration, or other report changes into an audit commit.
- `Get-PRHandoff.ps1` must report the PR head, required checks, result and audit reports, audit score, blockers, and Ready/manual-merge eligibility.
- A green GitHub status is not a substitute for reading the relevant test log and obtaining an independent audit.
- Automation keeps PRs as Draft and never enables auto-merge or merges them. The user always makes the final manual merge decision.
