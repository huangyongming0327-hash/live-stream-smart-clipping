# TASK-GITHUB-002-FIX2

## Goal

Harden the existing Draft PR #2 so a real source-only failure cannot appear green, and make the local Codex GitHub scripts safe and reproducible on Windows PowerShell 5.1.

## Scope

- Keep using branch `chore/TASK-GITHUB-002-result` and PR #2.
- Add one shared source-only test entry point.
- Make GitHub Windows Chinese subprocess tests deterministic without weakening their Unicode assertions.
- Propagate native command failures and add workflow concurrency cancellation.
- Bind Start, task publishing, audit publishing, and handoff to the canonical repository policy.
- Add temporary-repository behavior tests for Start, Publish, Audit, Handoff, source-only failure propagation, and repository safety.
- Include the existing failed FIX-R audit as formal PR evidence.
- Produce `tasks/reports/TASK-GITHUB-002-FIX2_RESULT.md`.

## Boundaries

- No new PR or long-lived branch.
- No direct `master` push, force push, history rewrite, Ready transition, auto-merge, or merge.
- No ruleset modification.
- No dependency installation or update.
- No model, FFmpeg integration, real media, 399-result regression, manual accuracy review, or TASK-003.
- No modification to the original private archive.

## Acceptance

- Both Chinese subprocess tests pass locally and on GitHub Windows with complete text and no replacement.
- Any source-only native-command failure makes the shared entry point and workflow nonzero.
- All four GitHub workflow scripts validate the canonical origin.
- Audit publishing handles 0, 1, and multiple changed paths without scalar `.Count` failure.
- Start synchronizes or stops; task publishing tests before staging; handoff reports score, SHA, reports, blockers, and eligibility.
- Local source-only, PowerShell AST, behavior, safety, and diff checks pass.
- The latest PR #2 run has all three required jobs executed successfully and the complete `lightweight-tests` log contains real `0 failed`.
- PR #2 remains Draft, unmerged, and without auto-merge pending TASK-GITHUB-002-FIX2-R.
