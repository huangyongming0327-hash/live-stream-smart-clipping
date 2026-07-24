# Security Policy

## Reporting a vulnerability

Do not open a public issue containing credentials, private paths, user data, or an exploitable proof of concept. Use the repository's private GitHub security advisory reporting flow when available.

Include the affected revision, a minimal sanitized reproduction, impact, and suggested mitigation. Do not attach real livestream media, model files, runtime output, tokens, keys, certificates, or machine-specific environment dumps.

## Repository data boundary

This repository contains source, tests, lock files, and sanitized documentation only. Models, FFmpeg binaries, user media, subtitles, recognition output, runtime directories, virtual environments, caches, logs, secrets, and private configuration must remain local.

## Supported status

The project is in technical validation and has no stable production release. Security fixes should target the current `master` branch through a `fix/` branch and Draft PR.
