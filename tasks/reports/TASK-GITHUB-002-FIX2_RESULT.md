# TASK-GITHUB-002-FIX2 result

- Execution date: 2026-07-25 (Asia/Shanghai)
- Public working copy: `<PROJECT_ROOT>`
- Repository: `huangyongming0327-hash/live-stream-smart-clipping`
- Existing branch: `chore/TASK-GITHUB-002-result`
- Existing PR: https://github.com/huangyongming0327-hash/live-stream-smart-clipping/pull/2
- Status: implementation and implementation-head online validation passed; waiting for final latest-head verification and independent FIX2-R
- Merge policy: keep Draft; user-only manual decision after independent FIX2-R

## 1. B-01 CI false-green fix

The old workflow placed two pytest commands and `pip check` in one Windows PowerShell block without checking each native exit code. The first pytest returned nonzero, but the later successful `pip check` became the final block result and GitHub marked `lightweight-tests` successful.

`tools/github/Invoke-SourceOnlyTests.ps1` is now the common local/CI entry point. It records `$LASTEXITCODE` immediately after each stage, reports the stage and code, and throws on the first nonzero result. The dependency-install step also checks both pip commands individually. Synthetic regression evidence confirms a first-stage exit 9 makes the script nonzero and prevents both ASR tests and `pip check` from running.

## 2. B-02 single audit report fix

`Publish-CodexAudit.ps1` now wraps the filtered/sorted changed-file pipeline in an outer array expression. The value remains an array for zero, one, or multiple paths under Windows PowerShell 5.1.

Temporary-repository tests confirm:

- zero changes: explicit rejection;
- one legal AUDIT report: commit and normal local-remote push succeed;
- one out-of-scope file: explicit path rejection, not a `.Count` crash;
- two legal AUDIT reports: commit and normal local-remote push succeed;
- one AUDIT plus one source file: explicit rejection.

The real failed audit `tasks/reports/TASK-GITHUB-002-FIX-R_AUDIT.md` remains unchanged and is included in this task's publication scope.

## 3. GitHub Windows Chinese subprocess root cause

The failing tests used Python text streams (`print`) and therefore also depended on the GitHub Windows runner's redirected console encoding/error behavior. One probe exited 1 while encoding stdout; the nonzero probe emitted literal backslash Unicode escapes rather than the intended Chinese stderr text. These symptoms occurred before `run_process()` decoded its captured bytes.

The tests now make the child write explicit UTF-8 through `sys.stdout.buffer` and `sys.stderr.buffer`. They still require exact complete Chinese text, exit code 7 for the failure case, UTF-8 decoding, nonzero raw byte length, and `replacement_occurred=false`. UTF-8, BOM, CP936, replacement fallback, and unknown-codec unit tests remain. Production `run_process()` was not broadened because deterministic byte-level evidence shows its existing decoding contract is correct.

## 4. Workflow exit propagation and concurrency

- `lightweight-tests` calls the shared source-only script.
- Both dependency-install pip commands throw immediately on nonzero.
- No `continue-on-error` or exit-code-swallowing pipeline is used.
- Required job names remain `repository-safety`, `lightweight-tests`, and `task-report-gate`.
- Concurrency group is scoped to workflow plus PR number/ref and uses `cancel-in-progress: true`.
- No `pull_request_target`, secret use, model/media download, or user-data artifact was added.

## 5. Shared source-only scope

The entry point runs exactly:

1. base/schema/media tests excluding media integration, FFmpeg install-source, and the FFmpeg-binary-dependent corrupt probe;
2. ASR experiment tests excluding the intentionally unshipped 399-sentence byte-for-byte result;
3. `python -m pip check`.

It sets Python UTF-8 environment values only for its process and restores prior values in `finally`. It installs nothing and runs no model, real media, FFmpeg integration, or local 399-result regression.

## 6. Start synchronization

`Start-CodexTask.ps1` now validates the canonical origin, requires a clean configured base branch, rejects an existing task branch, runs `git pull --ff-only origin master`, and verifies local `master` equals `origin/master` before creating the branch. Output includes repository, base commit, and branch.

Temporary Git repositories prove synchronized and behind/fast-forward cases succeed, while divergence, missing origin, and wrong repository stop without creating the requested branch.

## 7. Canonical repository policy

`.github/liveclip-workflow.json` defines:

- canonical repository: `huangyongming0327-hash/live-stream-smart-clipping`;
- base branch: `master`;
- audit threshold: 85/100;
- the three required check contexts.

Start, task publishing, audit publishing, and handoff accept normal HTTPS/SSH GitHub origin formats only when owner/repository exactly matches. Missing, ambiguous, non-GitHub, other-owner, and other-repository origins are rejected.

## 8. Task publishing before commit

`Publish-CodexTask.ps1` now requires the exact task RESULT path and requires that report to be added or updated. It validates repository/base/branch and runs the shared source-only entry point before safety scanning or staging.

Tests prove a source-test failure leaves HEAD and the index unchanged, `master` and a wrong remote are rejected, one existing head/base PR is reused without a create call, a lost create response recovers only one matching PR, normal push stops after three attempts, and a synthetic authentication marker is not printed.

## 9. Audit publishing

Audit publication validates the canonical repository, accepts only `tasks/reports/*_AUDIT.md`, runs repository safety, checks the staged diff, commits, and performs `git push origin <current-branch>`. It does not create a PR, force, merge, enable auto-merge, or touch implementation files.

## 10. Handoff fields and eligibility

`Get-PRHandoff.ps1` now reports repository, URL/number/title/state, Draft, base/head, head SHA, merged/merge state, review decision, auto-merge, the three required checks, RESULT/AUDIT paths and existence, audit score/threshold/conclusion, unresolved blockers, `eligible_to_mark_ready`, `eligible_for_manual_merge`, and a short ChatGPT handoff.

Manual-merge eligibility requires an open Ready PR, all required checks present and `SUCCESS`, RESULT and AUDIT reports, a passing or conditional audit at or above 85, no unresolved blocker, no merge, and auto-merge disabled. Draft can only become eligible to mark Ready; no script performs that transition.

## 11. Local validation

- Windows PowerShell: 5.1.26100.8875.
- GitHub PowerShell AST: 7/7 scripts parsed with 0 errors.
- Automation behavior matrix: 23 passed, 0 failed.
- Base/schema/media source-only: 110 passed, 1 deselected, 0 failed.
- ASR experiment source-only: 35 passed, 2 deselected, 1 deprecation warning, 0 failed.
- `pip check`: `No broken requirements found.`
- Deterministic Chinese process tests: 2 passed, 0 failed.
- Synthetic false-green regression: nonzero first stage stopped later stages; all-zero case ran base, ASR, and pip in order.
- Repository safety synthetic positive/negative samples: safe text accepted; synthetic high-confidence secret and media extension rejected.

## 12. PR head and online Actions

- Pre-publication PR head: `2d02d3947daf26eaea92ec6baa0c933bf88cb00e`.
- Implementation commit/head: `465cab37bece9d4ee8c679d792f6c472bd9825b4`.
- Implementation run: https://github.com/huangyongming0327-hash/live-stream-smart-clipping/actions/runs/30116190668
- `repository-safety`: executed, success; https://github.com/huangyongming0327-hash/live-stream-smart-clipping/actions/runs/30116190668/job/89557334088
- `lightweight-tests`: executed, success; https://github.com/huangyongming0327-hash/live-stream-smart-clipping/actions/runs/30116190668/job/89557334114
- `task-report-gate`: executed, success; https://github.com/huangyongming0327-hash/live-stream-smart-clipping/actions/runs/30116190668/job/89557334077
- Run event/head: `pull_request` / `465cab37bece9d4ee8c679d792f6c472bd9825b4`.
- Complete `lightweight-tests` log: all 259 lines read in three contiguous sections.
- Base/schema/media: `110 passed, 1 deselected`, 0 failed; stage exit 0.
- ASR experiments: `35 passed, 2 deselected, 1 warning`, 0 failed; stage exit 0.
- `pip check`: `No broken requirements found.`; stage exit 0.
- Final source-only summary: status `passed`, all three recorded exit codes 0.
- Exact failure-result markers `FAILED`, `ERROR`, and `2 failed`: 0 occurrences. Two lowercase phrases `failed with exit code` are the displayed workflow guard source, not runtime failures.

Recording an Actions run URL changes this report and therefore creates one final evidence-only commit/run. Its own SHA cannot be embedded in its own contents. The completion handoff must verify that final PR head and read that final run's complete log before declaring this task finished.

## 13. Changed files

- workflow/policy: `.github/workflows/pr-checks.yml`, `.github/liveclip-workflow.json`;
- process regression: `tests/test_media_unit.py`;
- shared tests/automation: `tools/github/Invoke-SourceOnlyTests.ps1`, `tools/github/Test-CodexGithubAutomation.ps1`;
- GitHub scripts: `Start-CodexTask.ps1`, `Publish-CodexTask.ps1`, `Publish-CodexAudit.ps1`, `Get-PRHandoff.ps1`;
- workflow documentation: `AGENTS.md`, `docs/CODEX_GITHUB_WORKFLOW.md`, `docs/CURRENT_STATUS.md`, `docs/DECISIONS.md`;
- task evidence: this task file/result and the unchanged FIX-R failed audit.

## 14. Security and task boundaries

- No new PR or long-lived branch was created.
- No direct `master` push, force push, rebase, amend, history rewrite, Ready transition, auto-merge, or merge was performed.
- The master ruleset was not modified.
- No dependency was installed or updated.
- No model, media, environment, runtime, cache, log, credential, secret, or user data is included.
- No FFmpeg integration, model execution, real-media test, manual accuracy review, or TASK-003 was performed.
- The original private archive was not modified.

## 15. Known limitations

- The excluded tests still require intentionally unshipped FFmpeg/runtime evidence and remain documented rather than weakened.
- Python 3.12 reports the existing `audioop` deprecation warning in ASR review code; it is non-failing and outside this bounded task.
- GitHub check conclusions alone remain insufficient; the latest `lightweight-tests` log must be read after push.

## 16. Rollback

- Before merge, close PR #2 and delete only its exact task branch if the user decides to abandon it.
- After a future merge, use `git revert` from a bounded fix branch through another PR.
- Do not use force push, `git reset --hard`, `git clean`, rebase, amend, or history rewriting.
- Do not modify or delete the original private archive.

## 17. Next step

After the latest-head Actions logs are verified, stop and request only the independent `TASK-GITHUB-002-FIX2-R` audit. Do not mark Ready, merge, run manual accuracy review, or start TASK-003.
