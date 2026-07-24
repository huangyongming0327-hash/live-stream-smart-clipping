# Public repository sanitization report

## Scope

The public working copy was built from the accepted TASK-002 source snapshot without copying the original `.git` directory or commit objects. Only source, tests, lock files, scripts, and necessary documentation were considered.

## Scan rules

- Enumerate every public file and record type and size.
- Reject files over 5 MiB, NUL bytes, non-UTF-8 text, media, model formats, executables, archives, certificates, private keys, and secret-like files.
- Reject `.venv/`, `runtime/`, `tools/ffmpeg/`, `tools/asr/`, model, user-project, settings, cache, and test-cache paths.
- Detect Windows and POSIX user homes, local identity values, private project paths, Codex temporary paths, Machine/User/Process PATH snapshots, private IP addresses, non-placeholder email addresses, common token formats, and private-key markers.
- Preserve synthetic paths used by source and tests when they do not contain real personal information.

## Findings and handling

The private input snapshot contained:

- 37 plain or JSON-escaped references to the private project root across the tracked snapshot and required final baseline audit;
- 15 user-home path references;
- 18 local-user references;
- 3 full Machine/User/Process PATH snapshot lines;
- 0 private email matches;
- 0 private IP matches;
- 0 high-confidence token or private-key matches.

Eighteen public files were generated with placeholders instead of private values:

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

The original machine environment snapshot was not copied. It was replaced by `docs/ENVIRONMENT_REPORT_PUBLIC.md`, which retains only portable technical requirements.

The timeline round-trip assertion in `tests/test_timeline_schema.py` was updated to verify the synthetic Chinese file name after the real project-root prefix was replaced.

Excluded tracked placeholders:

- `runtime/cache/.gitkeep`
- `runtime/logs/.gitkeep`
- `runtime/temp/.gitkeep`
- `模型/.gitkeep`
- `项目/.gitkeep`
- `设置/.gitkeep`

Also excluded in full: the original `.git`, `.venv`, local FFmpeg/ASR binary directories, model weights, media, runtime output, recognition output, caches, logs, secrets, certificates, archives, and user data.

## Final pre-Git result

- Files scanned before this report: 116
- Largest file: 32,192 bytes
- Files over 5 MiB: 0
- Files containing NUL: 0
- Forbidden media/model/binary/archive files: 0
- Forbidden directories present: 0
- Personal-path, local-identity, PATH-snapshot, private-email, private-IP, and high-confidence-secret findings after sanitization: 0
- Status: **passed**

The report records counts and public file names only; it does not reproduce any redacted source value.
