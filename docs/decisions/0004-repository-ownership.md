# ADR-0004: Repository ownership and packaged application resources

- Status: Accepted for local implementation at the owner's request
- Date: 2026-10-11

## Context

The owner requested a refined folder architecture before source publication. Docker assets were
split between root/config/scripts, operational scripts shared one flat directory, the review
harness occupied the root and unrelated transactional services shared one 719-line module.
Portal templates depended on the execution directory despite belonging to the application.

## Decision

Use the responsibility-based [repository layout](../repository-layout.md). Keep root entry points
and tool-discovered configuration where expected; group Docker assets under `infra/docker`, scripts
by purpose and the review harness under documentation. Split portal services into domain modules
with stable public exports. Package templates with the application and derive their default path
from the package, while retaining the explicit settings override.

Preserve route/CLI behavior, database schema, transaction ordering, domain failures, scenario
isolation, secret exclusions and all canonical assessment/evidence bytes. Do not revise locked
dependencies or create new application frameworks for this change. The PRD's original proposed
tree remains historical design context; this ADR records the implemented ownership refinement.

## Consequences and validation

Script paths and direct Docker build paths change; current documentation, CI and Compose consumers
must change together. Installed wheels and final Docker images must contain HTML templates.
Existing `bank_lab.services` callers retain their imports. Tests that patch the change-management
clock target its owning implementation module.

Compare extracted service definitions structurally, run the existing suite on Windows/Linux,
verify package contents and rendered pages, parse PowerShell, validate Compose overlays, verify
frozen snapshots and rerun publication/secret checks. This refactor does not close incomplete
assessment procedures, owner review or known residual container advisories.
