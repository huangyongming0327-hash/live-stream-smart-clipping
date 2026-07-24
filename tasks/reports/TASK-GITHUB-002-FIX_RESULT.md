# TASK-GITHUB-002-FIX result

- Execution date: 2026-07-24 (Asia/Shanghai)
- Public working-copy path: `<PROJECT_ROOT>`
- Repository: https://github.com/huangyongming0327-hash/live-stream-smart-clipping
- License: Apache License 2.0
- Merge policy: automated upload, never automated merge

## 1. Why a new public history was used

The original private Git history contains machine-specific identity and path material. Editing only the current files would not remove those values from historical Git objects. The task therefore preserved the original repository as a read-only private archive and created a new public repository from the accepted TASK-002 snapshot.

No history rewrite, `git filter-repo`, force push, `git reset --hard`, or `git clean` was used. The original `.git`, commits, tags, reflogs, and objects were not copied.

## 2. Original repository unchanged evidence

Read-only evidence collected before and after publication is identical:

- HEAD: `24b2496a23aa5fcf26f334fc18e5757c31bbba1f`
- HEAD tree: `153d601e0cb5817063af97e6bc678d31f00e03b3`
- refs manifest SHA-256: `7EFA7BD0173B43037ED5154251311290D9EC1C1B952984898ECD3BEBB6379833`
- remotes: 0
- branch: `master`
- only non-ignored worktree item: the previously created `TASK-GIT-002-R` audit report

The private archive received no commit, tag, branch, remote, push, history rewrite, or tracked-file modification from this task.

## 3. License

- Selected by the user: Apache License 2.0
- `LICENSE`: exact match to the Apache-2.0 text returned by the GitHub license API
- `NOTICE`: `Copyright 2026 live-stream-smart-clipping contributors`
- No private email address is used.
- The repository license covers repository code and repository-owned documentation. External FFmpeg components, ASR runtimes, and model weights remain subject to their own licenses and are not distributed here.

## 4. Sanitized copy and scan result

The initial public candidate contained 117 UTF-8 text files after public infrastructure was added. The pre-Git and staged scans found:

- NUL files: 0
- files over 5 MiB: 0
- media/model/binary/archive files: 0
- forbidden directories in the publication set: 0
- private path, local identity, full PATH snapshot, private email, private IP, Codex-private-path, token, or private-key findings after remediation: 0
- largest public file: 32,192 bytes
- final status: passed

Full rules and counts are recorded in `docs/PUBLIC_REPOSITORY_SANITIZATION_REPORT.md` without reproducing any redacted value.

## 5. Excluded and sanitized files

Excluded tracked placeholders:

- `docs/ENVIRONMENT_REPORT.md`
- `runtime/cache/.gitkeep`
- `runtime/logs/.gitkeep`
- `runtime/temp/.gitkeep`
- `模型/.gitkeep`
- `项目/.gitkeep`
- `设置/.gitkeep`

The original environment snapshot was replaced by `docs/ENVIRONMENT_REPORT_PUBLIC.md`.

Generated with public placeholders:

- `README.md`
- `config.example.json`
- `docs/ASR_DEPENDENCY_PLAN.md`
- `docs/ASR_MODEL_COMPARISON_REPORT.md`
- `docs/DECISIONS.md`
- `tasks/reports/TASK-001-FIX-R_AUDIT.md`
- `tasks/reports/TASK-001-FIX2-R_AUDIT.md`
- `tasks/reports/TASK-001-FIX2_RESULT.md`
- `tasks/reports/TASK-001-FIX3-R_AUDIT.md`
- `tasks/reports/TASK-001-FIX3_RESULT.md`
- `tasks/reports/TASK-001-FIX_RESULT.md`
- `tasks/reports/TASK-002-FIX-R_AUDIT.md`
- `tasks/reports/TASK-002-FIX2-R_AUDIT.md`
- `tasks/reports/TASK-002-R_AUDIT.md`
- `tasks/reports/TASK-GIT-001_RESULT.md`
- `tasks/reports/TASK-GIT-002_RESULT.md`
- `tasks/reports/TASK-GIT-002-R_AUDIT.md`
- `tests/conftest.py`

The related timeline round-trip assertion was updated to test the synthetic Chinese file name after the private root prefix was replaced. Normal source path handling and unrelated synthetic test paths were preserved.

Never copied or uploaded:

- the original `.git` and historical objects;
- `.venv`, ASR environments, runtime, caches, logs, or test caches;
- local FFmpeg/ASR binaries or archives;
- model directories or weights;
- real video, audio, subtitles, recognition output, human-review runtime copies, or user projects;
- `.env`, tokens, API keys, private keys, certificates, credentials, or private configuration.

## 6. Validation

Local source-only validation:

- base/schema/media unit subset: 110 passed, 1 FFmpeg-binary-dependent case deselected;
- ASR experiment unit subset: 35 passed, 2 runtime-result-dependent regression cases deselected;
- `pip check`: passed;
- five GitHub PowerShell scripts: syntax parse passed;
- `git diff --cached --check`: passed;
- staged repository safety scan: 117 files, 0 findings.

Excluded tests require FFmpeg binaries or the intentionally unshipped 399-segment runtime result. No model was downloaded or run.

## 7. New Git baseline

- branch: `master`
- root commit: `001fee64bf48549592a6a533b8a249f27b56e564`
- commit message: `chore: publish sanitized project baseline`
- parent commits: 0
- initial history length: 1 commit
- annotated tag: `public-baseline-task-002-tech`
- tag message: `Sanitized public baseline after TASK-002 technical validation`
- remote tag peel: `001fee64bf48549592a6a533b8a249f27b56e564`
- safe repository-local identity: `LiveClip Public <local@liveclip.invalid>`

The tag and branch were pushed normally. No old commit or tag was pushed.

## 8. GitHub repository and Actions

- repository visibility: public
- default branch: `master`
- baseline workflow run: https://github.com/huangyongming0327-hash/live-stream-smart-clipping/actions/runs/30107297389
- `repository-safety`: success
- `lightweight-tests`: success
- `task-report-gate`: success
- `pull_request_target`: not used
- external Actions: official `actions/checkout` and `actions/setup-python`, both pinned to full commit SHAs
- models downloaded or executed in Actions: none

## 9. Master ruleset and merge safety

- ruleset: `Protect master`
- ruleset ID: `19696285`
- enforcement: active
- bypass actors: 0
- required pull request: enabled
- required checks: `repository-safety`, `lightweight-tests`, `task-report-gate`
- strict up-to-date checks: enabled
- conversation resolution: required
- branch deletion: prohibited
- non-fast-forward/force push: prohibited
- repository auto-merge: disabled
- final merge decision: user only

## 10. Smoke PR

- PR: https://github.com/huangyongming0327-hash/live-stream-smart-clipping/pull/1
- branch: `chore/TASK-GITHUB-002-workflow-smoke`
- change: one sanitized smoke result report only
- automated safety scan: passed
- automated commit: `f5baa7b`
- normal push: passed
- Draft PR creation: passed
- three Actions checks: passed
- handoff: passed; reported Draft, clean merge state, three successful checks, and auto-merge false
- final PR state: closed
- merged: no
- remote smoke branch: deleted
- local smoke branch: deleted

GitHub returned a transient GraphQL 504 during the first post-create verification. The PR had been created successfully. The publisher was subsequently hardened to recover an already-created PR and verify it through the REST API, avoiding duplicate PR creation.

## 11. Remote content verification

The GitHub tree for `master` is complete and not truncated:

- public blobs: 117
- forbidden path or extension matches: 0
- remote `master`: the new root commit
- public tag: the new annotated tag only

No model, media, environment, runtime, cache, log, secret, user data, original private commit, or original private tag is reachable from the public baseline.

## 12. Final workspace and result delivery

- local repository: `<PROJECT_ROOT>`
- final task branch: `chore/TASK-GITHUB-002-result`
- publication method: safety scan, automatic commit, normal push, and Draft PR
- result PR: recorded in the final handoff after creation
- result PR merge: intentionally not performed
- Git worktree/index after publication: clean
- ignored source-test runtime output: local only and not uploaded

## 13. Daily workflow

1. Start from a clean `master` with `tools/github/Start-CodexTask.ps1`.
2. Use one `task/`, `fix/`, or `chore/` branch for one bounded task.
3. Add or update the task result report.
4. Run relevant source-only tests and the repository safety check.
5. Use `tools/github/Publish-CodexTask.ps1 -ConfirmScope` to stage, commit, push, and open a Draft PR.
6. Let GitHub run the three required checks.
7. An independent auditor may only add or update `tasks/reports/*_AUDIT.md` using `Publish-CodexAudit.ps1`.
8. Use `Get-PRHandoff.ps1` to report checks, review, Draft, merge, and auto-merge state.
9. The user resolves conversations and manually decides whether to merge.

## 14. Rollback

- Before merge: close the exact PR and delete only its exact task branch.
- After merge: create a bounded `fix/` branch and use `git revert` through another PR.
- Restore the public baseline from `public-baseline-task-002-tech` only through an auditable branch and PR.
- Do not use force push, `git reset --hard`, `git clean`, history rewriting, or broad deletion.
- The original private archive remains the independent local rollback source and must not be modified or deleted.

## 15. Explicitly not performed

- Manual ASR accuracy review: not performed
- CER/WER calculation: not performed
- Accuracy-winner or final-model declaration: not performed
- TASK-003: not performed
- PR merge or automatic merge: not performed
