# Security policy

## Scope

This repository is an educational, local-only simulation using synthetic data. It is not a
production banking service, an audit opinion, or a regulatory certification. Do not submit real
personal, financial, authentication, or client data.

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, evidence archives, or personal
data. Use [GitHub private vulnerability reporting](https://github.com/farisjamal/cybersecurity-risk-itgc-assessment/security/advisories/new)
to contact the repository owner. Include the affected revision, reproduction conditions, impact, and a minimal
proof of concept that does not target third-party systems.

The owner will acknowledge a valid report, assess its scope, and document remediation and retest
evidence. No response-time commitment is implied for this independently maintained portfolio.

## Supported version

Only the current default branch is maintained. Local exception scenarios are intentionally bounded
test fixtures; running them outside their project-scoped lab is unsupported.

## Before source publication

Include `.gitignore`; exclude `.env`, real credentials, local backups, captures and generated
document/evidence bundles. Only placeholder `.env.example` settings belong in source control.
Run `uv run python -m cyber_assess publication-check --json`, full-history Gitleaks, dependency
audit and image checks. A tracked file is not protected by a later ignore rule.

Read the [local publication review](docs/security-publication-review.md) for scope, remediation
and residual advisories. Rebuild with `docker compose build --pull --no-cache` to refresh
distribution patches. Scan new images before replacing services and preserve database volumes.

If a real credential reaches Git history or a shared artifact, revoke/rotate it before removing
files or rewriting history. Never post the credential in a public issue or scan log.
