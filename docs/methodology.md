# Assessment methodology

## Assessment chain

Every material conclusion follows the same traceable chain:

> Business objective → risk → control → procedure → evidence → design conclusion → operating
> conclusion → finding → recommendation → remediation → fresh retest.

The assessment covers twenty controls across governance, identity/access, change management,
operations/recovery, monitoring/incident response, and third-party/dependency risk. Every control
maps to a verified NIST CSF 2.0 category. Selected BNM RMiT observations are limited to verified
locators and the tested aspect; they do not establish regulatory compliance.

## Conclusion rules

- Assess design and operation separately; a sound design does not prove execution.
- Missing or changed evidence produces a limitation, never an effective conclusion.
- Automated observations do not set an assessment conclusion. The recorded assessor decision does.
- Preserve conflicting evidence and explain how it affected scope, testing, and conclusion.
- Historical fixtures are synthetic. Actual collection, execution, remediation, and retest timestamps
  are recorded separately in UTC.
- Self-review is disclosed. A fictional role or generated approval is never presented as independent
  human review.

## Sampling

Use complete-population testing for small populations where practical. For larger populations,
record population definition, completeness evidence, period, exclusions, sample method, seed,
selected IDs, and rationale. A reproducible sample is not automatically representative; judgment and
limitations remain explicit.

## Evidence lifecycle

1. Collect only allowlisted fields through the read-only boundary.
2. Register the original with collection action/query, source run and period, actual UTC timestamp,
   tool version, classification, and SHA-256 hash.
3. Create a separately identified redacted derivative when needed; link it to the original and record
   fields removed.
4. Reference evidence IDs from workpapers and findings.
5. Verify hashes and references before finalizing a workpaper or snapshot.
6. Freeze the baseline before remediation; never replace original failure evidence.
7. Export only allowlisted, sanitized artifacts whose classification permits distribution.

Passwords, password hashes, MFA seeds, session tokens, connection credentials, raw backups, and real
personal data are never distribution evidence. Screenshots can add context but do not prove record
completeness or operating effectiveness on their own.

## Findings and risk

A final finding contains criteria, condition, cause, consequence, evidence or explicit limitation,
risk rationale, recommendation, owner role, target date, and status. Likelihood and impact use the
PRD's 1–5 scales; the exact matrix determines priority. Unsupported metrics and compliance language
are rejected by the claims/publication gate.

Closure requires a fresh retest linked to its remediation environment and stated criteria. A failed
retest reopens work. Passing a narrow retest does not erase broader regulatory or residual gaps.

## Exception scenarios

S01–S06 are bounded, deterministic scenario environments. Each is run in isolated project-scoped
state, investigated from observed output, and cleaned without affecting other runs. A test passes when
the assessment correctly detects an intentional exception; the failed-control conclusion stays
visible. S01, S03, S05, and S06 require implemented remediation and fresh retest evidence.
