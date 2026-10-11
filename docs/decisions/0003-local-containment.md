# ADR-0003: Local containment and secure default

- Status: Accepted
- Date: 25 September 2026
- Requirements: DEC-08, NFR-01, NFR-02, NFR-10

## Context

The portal is a local educational simulation containing intentionally vulnerable scenario states. It
does not need public reachability, and publishing PostgreSQL would create needless exposure.

## Decision

Clarification verified on 11 October 2026: the database uses only an internal network. The default
application additionally needs a UI bridge for Docker to publish its explicit loopback port.
That bridge permits application egress; no application outbound-denial guarantee is made.
Scenario and verification overrides retain internal-only networking and no host ports.

Publish the application only at `127.0.0.1:8000`. Do not publish a database port. Use an internal
Compose network, named volumes, runtime-injected secrets, a non-root application user, read-only root
filesystem, dropped capabilities, and `no-new-privileges`. Exception behavior requires an explicit,
bounded scenario run; the default remains secure.

Local HTTP is allowed only on loopback with `HttpOnly` and `SameSite` cookies. Remote deployment is out
of scope and would require TLS, secure cookies, managed secrets, and a separate threat/design review.

## Alternatives considered

- Host-publish PostgreSQL for convenience: rejected; use service-to-service networking or scoped
  operator commands.
- Public preview/tunnel: rejected because the scenario environment is not designed for hostile internet
  traffic.
- Run everything directly on the OneDrive path: rejected because active database/runtime files should
  not be synchronized.

## Consequences

Reviewers need Docker and must use project commands for database operations. The contained design is
appropriate for the stated lab, but it is not production deployment evidence.
