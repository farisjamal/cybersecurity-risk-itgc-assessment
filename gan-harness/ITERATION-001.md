# Iteration 001 — S01 vertical-slice baseline

## Contract

- **Requirements:** FR-01–FR-14 and FR-18 foundations; full S01 chain for AT-01, AT-02,
  AT-05, AT-11–AT-14, and AT-18; repository foundations for AT-19 and AT-20.
- **Snapshot:** `SNAP-20260926T012311-1F44808C`.
- **Environment:** Windows host, Python 3.12.14, uv 0.11.26; Docker Desktop installed but its
  Linux engine unavailable during the evaluation.
- **Interfaces exercised:** assessment CLI, FastAPI ASGI interface, SQLite workflow and recovery
  boundary, Compose effective configuration, snapshot verification, and sanitized export.
- **Out of scope for this iteration:** completion of the remaining nineteen workpapers, final
  workbook/report/presentation, manual visual/accessibility review, and final AT-01–AT-20 sign-off.

## Evaluation evidence

| Dimension | Score | Evidence and limitation |
| --- | ---: | --- |
| Security and containment | 8 | Direct HTTP authorization, CSRF, MFA, session-revocation, throttling, deduplicated-alert, and scenario-scope tests pass. Effective Compose config is loopback-only, has no database host port, and uses an internal network. Live container inspection is pending. |
| Evidence integrity and assessment quality | 8 | S01 population, policy, failed baseline, finding, action, fresh retest, and workpaper reconcile. Snapshot verification covers 14 source artifacts; tamper and corrupt-backup tests fail safely. Only one of twenty workpapers is complete. |
| Functional correctness | 7 | All 69 automated tests pass; all six in-process scenario baseline/remediation/retest paths pass. Complete AT behavior and final deliverables have not been exercised. |
| Reproducibility and operations | 6 | Python dependencies are locked, deterministic seed counts pass, PowerShell gates work, and sanitized export is reproducible. Docker image build, PostgreSQL runtime, Linux CI, and measured startup/capacity remain unverified. |
| Documentation and claim honesty | 8 | Local links resolve, limitations and claims remain explicit, and README status matches the partial baseline. A fresh external reviewer has not reproduced the full chain. |

**Weighted score:** 7.5 / 10.

**Verdict:** ITERATE. No credential, real-client data, authorization bypass, unsafe scenario target,
database host exposure, or snapshot-integrity blocker was found. This iteration is suitable for an
MVP review commit, not a final PRD release.

## Major findings

1. Start Docker Desktop and run the image build, migrations, PostgreSQL-backed tests, health check,
   and scoped teardown.
2. Complete and self-review the remaining nineteen control workpapers with evidence or explicit
   limitations and separate design/operation conclusions.
3. Generate and reconcile DEL-01–DEL-10, then record AT-01–AT-20 against one final frozen snapshot.

## Regression checks

- `./scripts/check-repository.ps1 -SkipCompose` — passed.
- `python -m pip_audit --requirement requirements.lock --disable-pip` — no known vulnerabilities.
- `docker compose config --quiet` plus loopback/database/internal-network assertions — passed.
- `cyber_assess verify --snapshot SNAP-20260926T012311-1F44808C` — 14 files verified.
- Sanitized export manifest — 14 allowlisted artifacts; no runtime or backup material.
