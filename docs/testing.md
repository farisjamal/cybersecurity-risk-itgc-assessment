# Testing and release gates

## Local gate

With `.env` populated and Docker running:

```powershell
./scripts/check-repository.ps1
```

For a fast source-only pass:

```powershell
./scripts/check-repository.ps1 -SkipIntegration -SkipCompose
```

The full gate synchronizes the locked environment, runs Ruff lint/format checks, enforces test
coverage, validates assessment/finding schemas, checks local Markdown links, runs integration and
acceptance tests, validates Compose, and rejects tracked runtime/secret paths.

## Focused commands

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -m "not slow"
uv run pytest -m "integration or acceptance"
uv run python -m cyber_assess assess validate --engagement ENG-001
uv run python -m cyber_assess findings validate --engagement ENG-001
./scripts/check-links.ps1
docker compose --env-file .env config --quiet
```

For snapshot and artifact reconciliation:

```powershell
uv run python -m cyber_assess snapshot create --engagement ENG-001 --json
uv run python -m cyber_assess verify --snapshot SNAPSHOT_ID --json
uv run python -m cyber_assess export --snapshot SNAPSHOT_ID --json
uv run python -m cyber_assess report-inputs --snapshot SNAPSHOT_ID --json
uv run python -m cyber_assess artifacts --snapshot SNAPSHOT_ID --json
./scripts/render-pdfs.ps1 -SnapshotId SNAPSHOT_ID
```

The deterministic artifact manifest covers the XLSX, Markdown, HTML, CSV, JSON, and reconciliation
outputs. Locally rendered PDFs use a separate manifest containing source HTML names, hashes, sizes,
and the Microsoft Edge version. Inspect every rendered PDF before distribution.

Tests are successful only when their asserted behavior is correct. Detecting an intentionally failing
scenario is a successful test while the associated control conclusion remains failed.

## Recorded local run, 11 October 2026

- Windows Python 3.12.14: 120 tests passed, 85.67% branch-aware coverage.
- Isolated Docker Linux Python 3.12.11/PostgreSQL: 120 tests passed, 85.45% coverage.
- Ruff lint/format, strict mypy, assessment/finding validation and local Markdown links pass.
- The live advisory audit returned zero known vulnerabilities for 40 locked Python packages.
- Local Docker reproduction and logical recovery are observed; fresh-machine Windows setup and
  hosted CI for the final revision are still outstanding.
- Snapshot `SNAP-20261011T105042-6CFB8FC2` verifies 105 files and reconciles 20 controls,
  20 workpapers, 22 evidence records and four finding/action/retest chains with zero unmatched
  references. Four conclusions are recorded; sixteen remain incomplete.
- Current brief/report PDFs each contain two A4 pages; the presentation contains seven landscape
  pages. Every rendered page was visually inspected with no clipped content. These remain review
  artifacts and do not close the outstanding substantive assessment or owner review.

The [review packet](assessment-review.md) identifies the procedure and judgment gaps per control.
Raw JUnit output remains under ignored `runtime`; sanitized operational observations are registered
under `fixtures/evidence/completion` with hashes. Historical snapshots remain intact.

## CI gates

| Job | Purpose |
| --- | --- |
| Lint, unit, schema, links | Locked install, Ruff, coverage, assessment validation, local-link integrity |
| PostgreSQL integration | Database-backed integration and scenario acceptance with ephemeral CI credentials |
| Compose containment | Effective model is valid, app is loopback-published, database has no host port |
| Windows PowerShell path | PowerShell parsing, link validation, locked unit tests on Windows |
| Secret scanning | Gitleaks scan of repository history and current content |

GitHub-hosted Windows validation does not prove Docker Desktop behavior on the owner's laptop. AT-19
requires a recorded fresh local Windows run plus Linux CI evidence before final release.

## Acceptance record

AT-01 through AT-20 are release requirements. Record for each test: revision, environment and tool
versions, UTC start/end, command/procedure, expected result, actual result, evidence IDs, status,
limitations, and reviewer state. A green CI run alone does not complete manual visual review,
regulatory-source verification, recovery timing, or distribution review.

## Release blockers

Do not release with broken secure-default authorization, exposed credentials, unsafe scenario scope,
untraceable material findings, false evidence, unsupported regulatory conclusions, integrity
failures, missing mandatory artifacts, or failed required acceptance tests. Accurately reported
residual findings may remain open except where the PRD requires verified remediation.
