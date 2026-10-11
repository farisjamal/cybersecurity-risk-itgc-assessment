# Cybersecurity Risk & IT General Controls Assessment

Independent portfolio project for a **simulated Malaysian financial institution**.

**Status, 11 October 2026:** This is the main twenty-control project selected by the owner.
The local Docker/PostgreSQL lab, isolated recovery and all six scenario retests have now been
executed. Selected framework references are verified. This is **not** the final PRD v1 release:
sixteen control conclusions remain incomplete, substantive owner review is open and the acceptance
register records four passed and sixteen partial criteria. Start with the
[control-by-control review packet](docs/assessment-review.md).

## Start here

Read the [Product Requirements Document](PRD.md) before changing the system. It remains the
implementation baseline for scope, architecture, assessment methodology, evidence handling,
deliverables, and acceptance criteria.

The current implementation combines:

- A local service portal with testable identity, access, change, logging, and recovery controls.
- A 20-control catalogue and one frozen workpaper per control. IAM-02/S01, IAM-04/S03,
  OPS-01/S05, and OPS-03/S06 have executed conclusions; the other sixteen retain explicit
  `not_assessed`/`not_tested` limitations.
- Six reproducible exception paths and preserved baseline/action/retest chains for S01, S03, S05,
  and S06.
- Structured assets, risks, mappings, evidence requests, blockers, milestones, review decisions,
  and AT-01 through AT-20 records.
- Snapshot-driven sanitized exports, a 14-sheet XLSX workbook, engagement brief, executive report,
  remediation roadmap, and seven-slide presentation with English speaker notes.

## Current verification

On 11 October 2026, Windows tests passed 120 cases with 85.67% branch-aware coverage. Ruff lint,
formatting and strict mypy passed. A separate Linux/PostgreSQL verification target is available:

```powershell
docker compose -p cyber-assess-verification -f compose.yaml -f config/compose.verification.yaml build app
docker compose -p cyber-assess-verification -f compose.yaml -f config/compose.verification.yaml run --rm app
```

Sanitized current observations are registered under `fixtures/evidence/completion`:

- An isolated PostgreSQL restore reconciled seven business tables and 51 requests through read-only
  application acceptance; the source was preserved.
- S01 through S06 passed fresh retests in separate Compose projects; the main lab population stayed
  unchanged. Scenario containers and networks were stopped; their volumes were retained.
- The advisory audit checked 40 locked Python packages and returned zero known vulnerabilities at
  the recorded collection time. Failed feeds cannot produce a clean result.

The suite also checks 10,000 audit events and a 200-evidence export. Capacity-only synthetic records
do not become assessment evidence. Local Linux execution does not replace hosted CI or fresh-machine
Windows reproduction. Measured logical recovery does not establish full disaster recovery.

```powershell
uv run python -m cyber_assess dependencies audit --json
uv run python -m cyber_assess release-check --engagement ENG-001 --json
```

Structural validation and release readiness are separate. `release-check` currently exits 4 because
required assessment, review and delivery work remains.

## Historical implementation baseline

As of 26 September 2026:

- 99 automated tests pass with 85.61% branch-aware coverage.
- Ruff, format, strict mypy, local Markdown links, canonical assessment/finding validation, and the
  hash-locked production dependency audit pass.
- The effective Compose model publishes only `127.0.0.1:8000`, exposes no PostgreSQL host port,
  and uses an internal network.
- Snapshot `SNAP-20260926T024908-88653414` verifies 99 source artifacts and reconciles 20 controls,
  20 workpapers, 19 evidence records, four findings, four actions, and four retests without unmatched
  references.
- The ignored local artifact bundle includes visually inspected A4 engagement/report PDFs and a
  seven-page 16:9 presentation PDF rendered with Microsoft Edge; their hashes and renderer version
  are recorded separately from the deterministic source-artifact manifest.
- Docker was unavailable during that historical run. Current local observations above supersede
  that runtime limitation; the current revision still requires a fresh hosted CI run.

## Local verification

Install the locked environment and run the source/integration gate:

```powershell
uv sync --frozen --all-groups
./scripts/check-repository.ps1 -SkipCompose
```

For the full local container gate, copy `.env.example` to ignored `.env`, replace every
`CHANGE_ME` value, start Docker Desktop, and run:

```powershell
./scripts/check-repository.ps1
```

See [setup](docs/setup.md), [testing and release gates](docs/testing.md), and the
[honest-use limitations](docs/limitations.md).

Freeze and render one validated snapshot with:

```powershell
uv run python -m cyber_assess snapshot create --engagement ENG-001 --json
uv run python -m cyber_assess verify --snapshot SNAPSHOT_ID --json
uv run python -m cyber_assess export --snapshot SNAPSHOT_ID --json
uv run python -m cyber_assess report-inputs --snapshot SNAPSHOT_ID --json
uv run python -m cyber_assess artifacts --snapshot SNAPSHOT_ID --json
./scripts/render-pdfs.ps1 -SnapshotId SNAPSHOT_ID
```

## Build sequence

1. Foundation: environment checks, scope, schemas, source register, and versioned policies.
2. Secure lab: portal, roles, change workflows, and audit events.
3. Evidence and scenarios: collection, backup/restore, and isolated exceptions.
4. Assessment: workpapers, findings, mappings, and review.
5. Remediation: implement fixes and collect fresh retest evidence.
6. Portfolio: generate, reconcile, review, and reproduce final deliverables.

The implemented baseline began with the leaver-access scenario and now includes the remaining three
mandatory remediation chains plus the full reporting pipeline. Completion still follows the evidence
and release blockers in PRD Sections 19, 21, and 24; file presence is not treated as a passed control.

## Important context

Before publishing source, read the [security publication review](docs/security-publication-review.md)
and run `uv run python -m cyber_assess publication-check --json`. Include `.gitignore`; keep `.env`,
credentials, backups and generated evidence/document bundles local. CI scans history, dependencies
and rebuilt images. Residual advisories are documented; passing CI is not a security certification.

This is a local educational simulation. It does not represent a real client engagement, independent audit opinion, regulatory certification, or a guaranteed employment outcome. Synthetic records and observed lab results must remain clearly distinguished.

Passing the current automated suite is evidence for the implemented baseline, not evidence that all
AT-01 through AT-20 requirements or all PRD deliverables are complete.
