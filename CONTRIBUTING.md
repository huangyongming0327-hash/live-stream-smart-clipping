# Contributing

## Branch and Pull Request policy

- Never develop directly on `master`.
- Start each change from a clean `master` using a `task/`, `fix/`, or `chore/` branch.
- Keep one bounded task per branch.
- Use `tools/github/Start-CodexTask.ps1` to create the branch.
- Use `tools/github/Publish-CodexTask.ps1` to run the safety gate, commit, push, and open a Draft PR.
- Do not enable auto-merge. The repository owner decides whether to merge after checks and review are complete.

## Required evidence

Every PR must include or update a report under `tasks/reports/`. The report must state scope, tests, known limitations, excluded local artifacts, and whether manual accuracy review or TASK-003 was performed.

Independent audit commits may only add or update files matching `tasks/reports/*_AUDIT.md`. Use `tools/github/Publish-CodexAudit.ps1`; do not mix audit reports with source changes.

## Safety

Never commit models, media, runtime output, virtual environments, caches, logs, credentials, private keys, certificates, personal paths, machine details, private email addresses, or user data. Run `tools/github/Invoke-RepositorySafetyCheck.ps1` before publishing.

## Tests

Run the narrowest relevant unit tests locally. GitHub Actions runs the source-only test subset and never downloads models or invokes local full-model inference.
