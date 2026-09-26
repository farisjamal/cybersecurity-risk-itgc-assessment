# Cybersecurity Risk & IT General Controls Assessment

Independent portfolio project for a **simulated Malaysian financial institution**.

**Status:** Gate 2 implementation candidate. The secure lab, assessment engine, all six bounded
scenario paths, twenty workpapers, governance registers, and four required remediation/retest chains
are implemented. This is **not** the final PRD v1 release: sixteen workpapers remain limitation-only,
external framework locators remain unverified, local Docker reproduction is outstanding, and the
acceptance register records one passed, seventeen partial, and two missing tests.

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

## Verified implementation baseline

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
- A live Docker image build and local PostgreSQL health check remain unverified because the Docker
  Desktop engine was unavailable during this run. The prior PR revision passed Linux/PostgreSQL,
  Windows, containment, and secret-scanning CI; the current revision requires a fresh CI run.

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

This is a local educational simulation. It does not represent a real client engagement, independent audit opinion, regulatory certification, or a guaranteed employment outcome. Synthetic records and observed lab results must remain clearly distinguished.

Passing the current automated suite is evidence for the implemented baseline, not evidence that all
AT-01 through AT-20 requirements or all PRD deliverables are complete.
