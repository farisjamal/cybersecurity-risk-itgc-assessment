# ADR-0001: Architecture baseline

- Status: Accepted
- Date: 25 September 2026
- Requirements: DEC-01–DEC-06, NFR-03, NFR-11

## Context

The project needs a small control-testable service and a larger evidence-based assessment without
turning into a general GRC platform. One developer must be able to reproduce the environment on
Windows and verify it in Linux CI.

## Decision

Use Python 3.12 for the FastAPI/Jinja portal and `cyber_assess` CLI, PostgreSQL 17 for lab data,
SQLAlchemy/Alembic for persistence, YAML/JSON as canonical assessment records, Docker Compose for the
contained local stack, and one-way generation for workbook/report/presentation artifacts. Dependencies
are resolved in and installed from committed `uv.lock`.

## Alternatives considered

- Separate JavaScript frontend: rejected because it adds build/auth surface without improving the
  assessment objective.
- SQLite-only lab: rejected because database roles, relational constraints, and realistic restore
  tests are material learning goals.
- Full GRC web application: rejected because it would delay evidence, testing, and workpapers.

## Consequences

The implementation stays compact and uses one language, but Docker is a meaningful prerequisite and
PostgreSQL recovery adds local complexity. Exported documents are derivatives; canonical records must
be changed and re-exported rather than editing generated artifacts.
