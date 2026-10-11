# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Reproducible Python 3.12 project and dependency lock.
- Local FastAPI/PostgreSQL lab foundation with secure-by-default configuration.
- File-based assessment engine, evidence integrity checks, and S01 traceability baseline.
- Test, documentation, CI, and repository-governance foundations.

### Changed

- Grouped Docker assets under `infra/docker` and scripts by lab, quality and reporting purpose.
- Split portal services into domain modules while preserving the public service imports.
- Packaged portal templates with the application and removed dependence on the execution directory.
- Moved review harness documentation under `docs/quality` and added a repository ownership guide.

### Security

- Loopback-only host exposure and no PostgreSQL host port.
- Opaque server-side sessions, Argon2 password hashing, role checks, CSRF controls,
  MFA enforcement, session revocation, and bounded scenario execution are release gates.

[Unreleased]: https://github.com/farisjamal/cybersecurity-risk-itgc-assessment/compare/HEAD
