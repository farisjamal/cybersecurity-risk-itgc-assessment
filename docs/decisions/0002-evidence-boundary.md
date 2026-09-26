# ADR-0002: Separate lab and assessment evidence boundary

- Status: Accepted
- Date: 25 September 2026
- Requirements: FR-09, FR-11–FR-16, NFR-04, NFR-10

## Context

The assessed application must not be able to rewrite the conclusions or evidence used to assess it.
Remediation must also preserve the original failure evidence.

## Decision

Keep runtime lab state and canonical assessment records in separate storage. The application image
contains only application source and receives no mount for `assessment/`, `outputs/`, or `portfolio/`.
Collection uses an allowlisted, read-only boundary. Evidence is registered with provenance and hash;
redactions become linked derivatives. Snapshots freeze source references before export. Exports are
atomic and one-way.

## Alternatives considered

- Evidence-upload API in the portal: rejected because it crosses the trust boundary and expands attack
  surface.
- Mutable “latest evidence” paths: rejected because replacement would break traceability.
- Screenshots as primary proof: rejected because they do not establish completeness.

## Consequences

The workflow uses more IDs and storage, and human review remains required. In return, baseline failure,
remediation, and retest evidence can be reconciled without silently overwriting history.
