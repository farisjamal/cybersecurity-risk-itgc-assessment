# Source publication security review

Reviewed locally on 11 October 2026 and refreshed on 12 October 2026 on `complete-assessment`.
This review covers source publication and the local container baseline. It does not approve
internet-facing deployment or close the outstanding assessment procedures and owner review in
[the review packet](assessment-review.md).

## Publication refresh, 12 October 2026

The owner explicitly authorized **public GitHub source publication**. This remains an educational
work in progress; it is not a final PRD v1 release or authorization to expose the running lab.

| Check | Observed result |
| --- | --- |
| Candidate payload before the final documentation edit | 294 tracked/untracked source files; no forbidden-path or credential-pattern errors. |
| Actual private local values | All 32 values from ignored local configuration and generated lab credentials, plus URL-encoded variants, compared against candidate and reachable blob content, nested ZIP/XLSX members and PDF text: zero matches. Values were never logged. |
| Reachable Git commit history before the publication commit | Gitleaks 8.30.1 scanned all eight commits: zero findings. |
| Additional blob/archive inspection | 400 reachable blobs, including local app capture trees, and 124 archive members/PDF extractions inspected. Five generic-key matches were verified as source SHA-256 integrity metadata, not secrets. Local capture refs are not published. |
| Final candidate Gitleaks directory scan | Zero findings after representing source hashes as explicit path/sha256 pairs and clarifying one prose phrase. Hash values and observations preserved; evidence byte hashes refreshed. No detector rules disabled and no secret allowlists added. |
| Locked Python dependency audit | 40 packages, zero known advisories at 12 October 2026 collection time. |
| Current application image | 0 Critical, 44 High, 58 Medium, 61 Low, 1 Unknown; zero advisories with an available fix. |
| Current maintained PostgreSQL image | Zero reported advisories. |

The refreshed Trivy database was updated at `2026-10-12T09:47:21.509023105Z`.
The unfiltered image counts remain unresolved vendor advisory records, not a zero-vulnerability
claim or proof that all listed vulnerabilities are exploitable. Raw reports stay ignored under
`runtime/publication-20261012/`. The final publication commit `a033caa` passed Gitleaks across all nine reachable commits and
the independent candidate scan. Its 294 published files match the reviewed local tree; no forbidden
publication paths were present. All six [hosted CI jobs](https://github.com/farisjamal/cybersecurity-risk-itgc-assessment/actions/runs/38251894350) passed on 12 October 2026, including Windows, PostgreSQL, full-history secrets and fixable
High/Critical image gates. Later revisions must repeat those gates.

### Current application findings

| Severity | Finding | Disposition |
| --- | --- | --- |
| Medium | Read-only accounts previously had global service-request visibility, conflicting with the owner's selected own/assigned scope. | Corrected list/detail authorization; twenty HTTP matrix cases and a separate PostgreSQL deployment smoke verify selected boundaries. Baseline and retest evidence preserved. |
| Medium | Access-review validation accepted duplicate/conflicting IDs and missing/blank/non-string decisions. | Requires exactly one non-empty decision per account. Five negative cases now reject without persistence; the complete-population positive case still succeeds. |
| Medium | Six privileged approvals require PAM, but implementation and acceptance evidence are absent. | Open **PAM-001** in the [owner decision packet](iam05-access-review.md). RBAC, TOTP MFA and audit events are not presented as complete PAM. Existing local accounts remain active under those observed controls. |
| Low | Browser sign-in is disabled and Swagger assets are blocked by the current CSP. | Documented API-first workflow in [setup](setup.md). Interactive browser usability/accessibility acceptance remains open. |

Targeted source inspection confirms SQLAlchemy-bound queries, identity dependencies on business
routes, CSRF dependencies on authenticated mutations, role checks and generated seed credentials.
The unauthenticated health/readiness, landing/login, OpenAPI and development documentation routes
are intentional. The only raw SQL in the HTTP adapter is fixed `SELECT 1` readiness SQL; no
user-supplied SQL concatenation was found in the reviewed paths. This bounded inspection and
regression suite do not establish absence of every application vulnerability.

Owner account dispositions are current policy evidence, not an independent assessment: 15 scoped
approvals, six conditional RBAC/PAM approvals and three access denials preserving disabled records.
No breach by the three terminated accounts is alleged. Historical effectiveness, full role-matrix
reconciliation and sixteen overall incomplete control conclusions remain open.

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

- Application after the folder refactor: `sha256:1249dcc50b1092f8fd1dad885da97c66606d00800a5ede5564807292c8fdb8fc`.
- Database: `sha256:84aaca73551206b33a77ef67d712a6154da025b627608ab606e23dd64bc4812e`.

The application runtime excludes pip and ensurepip; installation tools remain in build/test
stages. Updating pip alone still shipped vulnerable vendored tooling, so unused installers were
removed from the runtime. The 44 remaining High records have no fix listed in this scan and are
not treated as resolved or accepted for public runtime deployment.

After the folder refactor, Windows Python 3.12.14 passed 138 tests with 85.65% branch-aware
coverage. Isolated Linux Python 3.12.14/PostgreSQL passed 138 tests with 85.57% coverage.
The rebuilt app image was rescanned against the same advisory database with unchanged counts
and no fixable advisories. Ruff, formatting, strict mypy,
assessment/finding validation, local links and the 40-package locked Python advisory audit pass.
Hosted CI for the published baseline is linked in the current refresh above. A separate manual
fresh-machine Windows reproduction remains outstanding.

The PostgreSQL entrypoint, data directory, volume, stop signal and port configuration are preserved
explicitly. Build assertions verify privilege dropping and rejection of an unknown user.
Tests cover both fresh isolated initialization and an existing major-17 test volume.
The application remains non-root, read-only, capability-restricted and loopback-published.
The Compose database has no published host port and uses an internal network.
Host smoke testing also found that Docker Engine 29.2.0 retained the requested loopback binding
but did not publish it for an internal-only app. A separate UI bridge restores host access.
Only the default app joins it; database, scenario and verification services remain internal.
The UI bridge permits app egress and must not be described as an outbound-denial control.
See [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/).

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

Source publication requires the exact reviewed payload, a fresh secret scan and intended repository
visibility; hosted CI checks the published revision and must pass before treating it as a verified baseline. Final PRD v1 release remains blocked by sixteen incomplete
control conclusions/procedures, owner review and remaining acceptance requirements. This security
review does not change those conclusions or the frozen assessment snapshot.

## GitHub protections and disclosure

The public repository enables provider secret scanning and push protection, vulnerability alerts
and private vulnerability reporting. These add safeguards and do not cover every possible secret
or replace the local payload/history checks. Review current settings before changing visibility
or publishing new material. Only the owner's `main` branch was pushed; local app capture refs and
old local branch names were not published. Commit author metadata uses the owner's GitHub noreply
address and contains no co-author trailers.

## Repeatable checks

```powershell
uv run python -m cyber_assess publication-check --json
./scripts/quality/check-repository.ps1
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
