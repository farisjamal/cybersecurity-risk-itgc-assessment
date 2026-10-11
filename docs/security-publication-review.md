# Source publication security review

Reviewed locally on 11 October 2026, starting from `6f4afb9` on `complete-assessment`.
This review covers source publication and the local container baseline. It does not approve
internet-facing deployment or close the outstanding assessment procedures and owner review in
[the review packet](assessment-review.md).

## Findings and remediation

| Severity | Finding | Result |
| --- | --- | --- |
| High | The old Python 3.12.11/Bookworm app image had 9 Critical and 94 High package/advisory records. | Replaced with digest-pinned Python 3.12.14/Trixie, refreshed OS packages and patched pip. Residual advisories are recorded below. |
| High | PostgreSQL 17.6 and its bundled Go privilege-drop helper were outdated. Updating Alpine alone did not patch that binary. | Updated to digest-pinned PostgreSQL 17.11/Alpine 3.24 and refreshed packages. Alpine's C `su-exec` replaces the helper at the official entrypoint's expected path. Only the maintained filesystem is copied into the final image, excluding obsolete base-layer binaries. |
| High | Twenty generated portfolio files were tracked despite ignore rules, including PDF, XLSX and evidence ZIP. | Removed them from the Git index while preserving local copies. They remain in historical commits; reachable historical content was scanned. No history rewrite was performed. |
| Medium | The former path regex missed some root `.env` and portfolio paths. | Added `publication-check` for staged bytes and tracked working files, forbidden credential/data/archive paths and placeholder-only `.env.example` credentials. `.gitignore` must be included. |
| Medium | Mutable CI references and no container OS advisory gate. | Pinned action revisions and scanner digests, restricted token permissions and added full-history secret, payload and fixable High/Critical image checks. CI integration builds the maintained database image. |

Severity describes priority and potential impact. Image counts are package/advisory records, not
confirmed exploitable application vulnerabilities. No blanket CVE suppression or secret allowlist
was introduced.

## Secrets and publication payload

- Gitleaks 8.30.1 scanned all five pre-review reachable commits with complete value redaction:
  zero findings. Scanner image digest is pinned in CI.
- All 305 pre-review reachable Git blobs were also materialized locally for a directory scan,
  including ZIP/XLSX archive traversal to depth five and extracted PDF text: zero findings.
- Both actual credential values from local `.env`, including URL-encoded variants, were compared
  against reachable Git blob contents without printing their values: zero matches.
- `.env` was never tracked in reachable history. It remains ignored and excluded from the Docker
  build context. `.gitignore` is included as explicitly requested by the owner.
- Generated passwords, TOTP secrets, database backups, runtime evidence, reports, image exports
  and scanner caches remain local in ignored directories.
- Test/CI credentials are synthetic, ephemeral fixture values, distinct from the local lab
  credentials. They must never be reused for deployment.
- The payload gate rejects credential-shaped tokens/private keys, nested JSON credential fields,
  credential stores, dumps, captures and generated document/archive bundles. It does not detect
  every secret format; full-history Gitleaks remains a separate gate.

Raw, redacted reports and image exports remain under ignored `runtime/security-audit/`.
Do not publish that directory or original evidence bundles as a shortcut to sharing results.

## Container results and verification

Trivy 0.75.0 used the advisory database updated at `2026-10-11T07:05:14Z`.
CI rescans rebuilt images against the then-current database, so future results can differ.

| Final image | Critical | High | Medium | Low | Unknown | Advisories with an available fix |
| --- | --- | --- | --- | --- | --- | --- |
| Application, Python 3.12.14/Trixie | 0 | 44 | 58 | 61 | 1 | 0 |
| PostgreSQL 17.11/Alpine 3.24, maintained filesystem | 0 | 0 | 0 | 0 | 0 | 0 |

Local immutable image configuration IDs:

- Application: `sha256:9f2ea4fb8400b1717871385695ca69fa33bda92a75fb6e6c6d1ecd96acff1478`.
- Database: `sha256:84aaca73551206b33a77ef67d712a6154da025b627608ab606e23dd64bc4812e`.

The application runtime excludes pip and ensurepip; installation tools remain in build/test
stages. Updating pip alone still shipped vulnerable vendored tooling, so unused installers were
removed from the runtime. The 44 remaining High records have no fix listed in this scan and are
not treated as resolved or accepted for public runtime deployment.

Windows Python 3.12.14 passed 137 tests with 85.43% branch-aware coverage. Isolated Linux
Python 3.12.14/PostgreSQL passed 137 tests with 85.22% coverage. Ruff, formatting, strict mypy,
assessment/finding validation, local links and the 40-package locked Python advisory audit pass.
Hosted CI for this revision and fresh-machine Windows reproduction remain outstanding.

The PostgreSQL entrypoint, data directory, volume, stop signal and port configuration are preserved
explicitly. Build assertions verify privilege dropping and rejection of an unknown user.
Tests cover both fresh isolated initialization and an existing major-17 test volume.
The application remains non-root, read-only, capability-restricted and loopback-published.
The Compose database has no published host port and uses an internal network.

## Application review and practical limits

A targeted source review found parameterized SQLAlchemy queries, generated seed credentials,
hashed passwords/sessions, CSRF checks on authenticated mutations, privileged MFA and explicit
role/object access checks. Regression tests exercise these boundaries. This is a bounded review,
not exhaustive adversarial testing. Health/readiness, landing/login pages and development API
documentation are intentionally unauthenticated; business data routes require identity.

HTTP and non-Secure cookies belong to the documented local development workflow. Production mode
requires Secure cookies, but that setting alone does not make this lab production-ready.
Do not expose it publicly or introduce real banking/client data. Residual advisories require
continued review, maintained base updates and a new deployment assessment before wider use.

Source publication requires the exact reviewed payload, a fresh secret scan, intended repository
visibility and successful hosted CI. Final PRD v1 release remains blocked by sixteen incomplete
control conclusions/procedures, owner review and remaining acceptance requirements. This security
review does not change those conclusions or the frozen assessment snapshot.

## Repeatable checks

```powershell
uv run python -m cyber_assess publication-check --json
./scripts/check-repository.ps1
docker compose build --pull --no-cache
```

Run full-history Gitleaks and the container Trivy jobs in [CI](../.github/workflows/ci.yml).
The image gate distinguishes fixable High/Critical advisories from unresolved vendor advisories;
passing is not a zero-vulnerability statement. Review unfiltered local reports too.

If a real credential ever enters a commit or shared artifact, revoke/rotate it first, then assess
history, forks and artifacts and remove the exposure. Ignore rules and current-file deletion
cannot revoke credentials or erase their history.

References: [GitHub ignore-file behavior](https://docs.github.com/en/get-started/git-basics/ignoring-files),
[Gitleaks](https://github.com/gitleaks/gitleaks),
[official PostgreSQL entrypoint](https://github.com/docker-library/postgres/blob/master/docker-entrypoint.sh),
[su-exec interface](https://github.com/ncopa/su-exec),
[Debian SQLite advisory](https://security-tracker.debian.org/tracker/CVE-2025-7458).
