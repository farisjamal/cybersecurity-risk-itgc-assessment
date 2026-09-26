# Cybersecurity Risk & IT General Controls Assessment

Independent portfolio project for a **simulated Malaysian financial institution**.

**Status:** MVP implementation candidate. The secure lab, assessment engine, all six bounded scenario
paths, and one complete S01 leaver-access evidence-to-retest chain are implemented. This is **not**
the final PRD v1 release: nineteen control workpapers, the remaining canonical scenario evidence,
manual acceptance records, and final presentation/report artifacts are still pending.

## Start here

Read the [Product Requirements Document](PRD.md) before changing the system. It remains the
implementation baseline for scope, architecture, assessment methodology, evidence handling,
deliverables, and acceptance criteria.

The current implementation combines:

- A local service portal with testable identity, access, change, logging, and recovery controls.
- A 20-control catalogue aligned to NIST CSF 2.0 and selected, explicitly limited BNM RMiT
  references; only IAM-02/S01 currently has a completed canonical workpaper.
- Six reproducible exception paths in the lab and a frozen S01 remediation/retest record.
- Hash-verified snapshots and allowlisted sanitized exports for the completed S01 material.

## Verified implementation baseline

As of 26 September 2026:

- 69 automated tests pass with 81.29% branch-aware coverage.
- Ruff, format, strict mypy, 23 local Markdown links, canonical assessment validation, and the
  hash-locked production dependency audit pass.
- The effective Compose model publishes only `127.0.0.1:8000`, exposes no PostgreSQL host port,
  and uses an internal network.
- Snapshot `SNAP-20260926T012311-1F44808C` verifies 14 source artifacts and produces an ignored,
  sanitized local export.
- A live Docker image build and local PostgreSQL health check remain unverified because the Docker
  Desktop engine was unavailable during this run. Linux CI is also pending the first push.

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

## Build sequence

1. Foundation: environment checks, scope, schemas, source register, and versioned policies.
2. Secure lab: portal, roles, change workflows, and audit events.
3. Evidence and scenarios: collection, backup/restore, and isolated exceptions.
4. Assessment: workpapers, findings, mappings, and review.
5. Remediation: implement fixes and collect fresh retest evidence.
6. Portfolio: generate, reconcile, review, and reproduce final deliverables.

The implemented baseline begins with the leaver-access scenario as the complete vertical slice.
Expansion to the remaining workpapers and release artifacts must continue to follow PRD Sections
19, 21, and 24.

## Important context

This is a local educational simulation. It does not represent a real client engagement, independent audit opinion, regulatory certification, or a guaranteed employment outcome. Synthetic records and observed lab results must remain clearly distinguished.

Passing the current automated suite is evidence for the implemented baseline, not evidence that all
AT-01 through AT-20 requirements or all PRD deliverables are complete.
