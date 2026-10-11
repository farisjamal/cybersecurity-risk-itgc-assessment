# Repository layout and ownership

Run all documented commands from the repository root. `compose.yaml`, Python metadata, lockfiles
and the owner-facing entry documents stay at the root. Deployment assets, operational scripts,
application resources and review tooling have explicit homes.

```text
CybersecurityProject/
├── README.md, PRD.md, SECURITY.md, CONTRIBUTING.md, CHANGELOG.md
├── compose.yaml                    # Root-relative Compose entry point
├── pyproject.toml, uv.lock, requirements.lock, alembic.ini, mkdocs.yml
├── .github/                        # CI, issue/PR templates and ownership
├── src/
│   ├── bank_lab/                    # Portal application
│   │   ├── app.py                   # HTTP inputs, routes and dependency wiring
│   │   ├── services/                # Transactional domain workflows
│   │   │   ├── authentication.py    # Login, sessions and privileged MFA policy
│   │   │   ├── access.py            # Access requests, activation and reviews
│   │   │   ├── requests.py          # Request visibility and lifecycle
│   │   │   ├── changes.py           # Change approval, deployment and rollback
│   │   │   ├── events.py            # Ordered event reads and correlation IDs
│   │   │   ├── errors.py            # Shared safe domain failures
│   │   │   └── __init__.py          # Stable public service exports
│   │   ├── templates/              # Packaged portal HTML
│   │   └── models.py, security.py, database.py, seed.py, ...
│   └── cyber_assess/                # Assessment CLI and evidence/report pipeline
├── infra/docker/                   # App/DB Dockerfiles, entrypoint and scoped overlays
├── config/scenarios.yaml           # Versioned scenario definitions
├── migrations/                     # Alembic environment and immutable DB revisions
├── scripts/
│   ├── lab/                        # Doctor, demonstration and observed lab verifiers
│   ├── quality/                    # Repository gate and local link checker
│   └── reporting/                  # Reviewed local PDF rendering
├── tests/{unit,integration,acceptance}/
├── assessment/                     # Canonical versioned assessment records/snapshots
├── fixtures/                       # Synthetic evidence and frozen baseline inputs
├── docs/                           # Setup, methodology, architecture and review guides
│   ├── decisions/                  # Architecture decision records
│   └── quality/harness/            # Review contract and historical iteration record
└── runtime/, outputs/, portfolio/  # Ignored local execution and generated artifacts
```

The environment file, virtual environment and tool caches remain local and ignored. Their presence
on the owner's computer does not mean they enter the source publication payload.

## Dependency boundaries

- HTTP routes call domain services; services own transactions and business authorization.
- Domain modules share models, security primitives and safe exceptions. They do not import the
  HTTP application or assessment package.
- `bank_lab.services` re-exports the established classes/functions, so callers do not need to
  know where an implementation lives. New domain code belongs in its owning module.
- `cyber_assess` owns evidence collection, validation, frozen snapshots and reporting. Existing
  cohesive modules stay direct children; new layers are unnecessary until responsibilities grow.
- Runtime templates are package resources. Their default location is relative to `bank_lab`,
  independent of the caller's current directory. `templates_dir` remains overridable.
- Docker builds use the repository root as context even though Dockerfiles live in `infra/docker`.
  The root `.dockerignore` continues to exclude credentials and private generated artifacts.
- `assessment/`, frozen baselines and evidence paths retain their existing layout and bytes.
  Moving them would invalidate lineage/hash references and is outside this structural refactor.

## Common entry points

| Task | Entry point |
| --- | --- |
| Prepare/check local prerequisites | `./scripts/lab/doctor.ps1` |
| Run quality, schema, links and publication checks | `./scripts/quality/check-repository.ps1` |
| Run a contained demonstration | `./scripts/lab/demo.ps1 -Scenario S01 -KeepRunning` |
| Rebuild runtime images | `docker compose build` |
| Build the app directly | `docker build -f infra/docker/Dockerfile .` |
| Build/run Linux tests | Root Compose plus `infra/docker/compose.verification.yaml` |
| Run observed scenario verification | `uv run python scripts/lab/verify-scenarios.py` |
| Render reviewed PDF artifacts | `./scripts/reporting/render-pdfs.ps1 -SnapshotId SNAPSHOT_ID` |

The runtime recovery verifier is copied to `/app/scripts/lab/verify-runtime.py` in the container.
It deliberately adds a synthetic checkpoint and retains a restore database; follow the
[recovery runbook](recovery-runbook.md) before running it. Historical iteration records retain
the commands used at their original execution date; use the current entry points above.

## Adding or moving files

Choose the owner by responsibility, update consumers and CI together, then run the same verification
before and after a move. Check package resources in the built wheel and runtime image, not only
the editable source checkout. Verify frozen snapshots and the publication payload after changes.
Do not create catch-all `utils`, duplicate implementations or move secret/generated material into
tracked source folders to make the tree look cleaner.

See [ADR-0004](decisions/0004-repository-ownership.md) for the rationale and compatibility boundary.
