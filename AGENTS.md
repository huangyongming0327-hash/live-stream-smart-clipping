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
