# Claims register

This file is a publication gate, not a marketing draft. A claim becomes usable only after its evidence
links resolve in a frozen snapshot and the cited acceptance results pass on the final revision.

Historical evidence anchor: snapshot `SNAP-20260926T024908-88653414`. Current 11 October 2026
observations are registered under `fixtures/evidence/completion` and summarized in the
[review packet](assessment-review.md). Only four controls have recorded conclusions; sixteen remain
incomplete. The acceptance register has four passed and sixteen partial criteria. Candidate final
assessment claims remain pending until the final revision, snapshot and substantive review agree.

| Claim ID | Candidate wording | Required evidence | Current state |
| --- | --- | --- | --- |
| CLM-01 | Built a local FastAPI/PostgreSQL control-assessment lab for a fictional financial institution, with server-side authorization, audit events, and isolated recovery exercises. | Revision, AT-03–AT-08 results, architecture, run evidence | Pending final acceptance |
| CLM-02 | Assessed 20 cybersecurity and ITGC controls using traceable workpapers mapped to NIST CSF 2.0 and selected sourced BNM RMiT aspects. | Final control count, AT-10–AT-12, mapping register, source verification | Pending final snapshot |
| CLM-03 | Investigated six bounded control-exception scenarios and implemented fresh remediation/retest paths for S01, S03, S05, and S06. | Scenario manifest, immutable baseline evidence, four passed retests, AT-13–AT-14 | Pending final acceptance |
| CLM-04 | Generated a reconciled assessment workbook, executive report, presentation, and sanitized evidence index from one validated snapshot. | Snapshot ID, DEL-03–DEL-08, reconciliation/visual review, AT-15–AT-16 | Pending final export |

## Prohibited or unsupported wording

- “Audited a Malaysian bank” or any implication of a real client engagement.
- “Ensured BNM/NIST/ISO compliance,” “certified,” or “provided independent assurance.”
- “Reduced risk by 80%,” “achieved 100% detection,” or another metric without a reproducible
  numerator, denominator, method, and measurement log.
- “Led a team/client engagement” when the work was performed by the sole owner using simulated roles.
- Any completed-work claim while its state above remains pending, failed, incomplete, or stale.

## Promotion rule

To change `Pending` to `Verified`, record the final Git revision, snapshot ID, artifact/evidence IDs,
commands executed, acceptance result IDs, actual counts, and review date. If a later change invalidates
an artifact or test, return the claim to `Pending` until reverified.
