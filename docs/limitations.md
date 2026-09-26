# Limitations and honest-use boundary

## What this project can demonstrate

- A reproducible local lab with synthetic users, requests, changes, events, and recovery exercises.
- A structured twenty-control assessment with traceable evidence or explicit limitations.
- Selected NIST CSF 2.0 and BNM RMiT literacy within documented mappings.
- The owner's engineering, testing, assessment reasoning, remediation, and English communication.

## What it cannot establish

- A real client engagement, external audit, independent assurance opinion, or regulator approval.
- Compliance with BNM RMiT, NIST CSF, ISO/IEC 27001, NACSA requirements, or another complete regime.
- Production security, resilience, availability, operating effectiveness, or thirty days of real
  activity.
- Independent review when the builder and assessor are the same person.
- Phishing-resistant authentication; the TOTP exercise is not phishing resistant.
- Effectiveness of real bank, supplier, payment, cloud, physical, or enterprise identity systems.
- Risk-reduction percentages, business outcomes, or hiring outcomes without separate evidence.

## Evidence constraints

Fixtures dated 1–30 August 2026 are generated history. They are not observations collected during that
period. Actual collection, run, remediation, restore, and export times are recorded when commands run.
Screenshots supplement but do not establish completeness. Schema and hash checks establish structure
and change detection, not truth or independent custody.

Source mappings can become stale. A source marked `verified_reference` records the version and locator
that was checked; it does not imply full-document coverage. An unavailable vulnerability feed or
reference must produce a dated limitation rather than a clean result.

## Environment constraints

The supported release is a local loopback lab. HTTP is accepted only with the documented development
cookie configuration. Remote hosting, public tunnels, multi-tenancy, enterprise SSO, high availability,
and production secrets management are out of scope. Database/runtime state lives in local Docker
volumes and is not an independent backup strategy.

Windows and Linux CI exercise different portions of the portability claim. A final handoff must record
the exact local hardware, OS, Docker, Python, `uv`, image, dependency, and revision versions actually
tested.
