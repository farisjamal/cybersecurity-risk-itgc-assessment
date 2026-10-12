# IAM-05 access-review decision packet

Prepared 12 October 2026. Current inspection of a fictional local lab; all account data is synthetic.

## Observed reconciliation

ARV-001 has 24 decisions for 24 accounts. Exact account IDs and snapshot count match; no missing,
unknown or duplicate IDs. Every generated decision says `retain`. The review stores a reviewer role,
but no named reviewer ID or matching completion event. Its August timestamps do not prove an actual
quarterly review. There are no recorded follow-up action references; this alone does not prove an
action was required or completed. Retain on a disabled identity does not mean reactivate it.

## Current account checklist

On 12 October 2026, project owner Faris Jamal explicitly provided the current dispositions below
in the project chat. Automation transcribed them in the hash-registered
[owner decision record](../fixtures/evidence/completion/owner-access-decisions-20261012.json) and
[open scoped review](../assessment/reviews/REV-OWNER-ACCESS-20261012.yaml). These decisions apply
to the current synthetic population; they do not backdate or replace generated ARV-001.

| Account | Role | Account status | Employment | Generated decision | Owner review |
| --- | --- | --- | --- | --- | --- |
| USR-001 | administrator | active | employed | retain | Conditional: RBAC + PAM-001 |
| USR-002 | administrator | active | employed | retain | Conditional: RBAC + PAM-001 |
| USR-003 | change_approver | active | employed | retain | Conditional: RBAC + PAM-001 |
| USR-004 | change_approver | active | employed | retain | Conditional: RBAC + PAM-001 |
| USR-005 | change_approver | active | employed | retain | Conditional: RBAC + PAM-001 |
| USR-006 | change_approver | active | employed | retain | Conditional: RBAC + PAM-001 |
| USR-007 | staff | active | employed | retain | Approved: current scoped access |
| USR-008 | staff | active | employed | retain | Approved: current scoped access |
| USR-009 | staff | active | employed | retain | Approved: current scoped access |
| USR-010 | staff | active | employed | retain | Approved: current scoped access |
| USR-011 | staff | active | employed | retain | Approved: current scoped access |
| USR-012 | staff | active | employed | retain | Approved: current scoped access |
| USR-013 | staff | active | employed | retain | Approved: current scoped access |
| USR-014 | staff | active | employed | retain | Approved: current scoped access |
| USR-015 | staff | active | employed | retain | Approved: current scoped access |
| USR-016 | staff | active | employed | retain | Approved: current scoped access |
| USR-017 | staff | disabled | terminated | retain | Denied access; keep disabled |
| USR-018 | staff | active | employed | retain | Approved: current scoped access |
| USR-019 | read_only | active | employed | retain | Approved: current scoped access |
| USR-020 | read_only | active | employed | retain | Approved: current scoped access |
| USR-021 | read_only | active | employed | retain | Approved: current scoped access |
| USR-022 | read_only | disabled | terminated | retain | Denied access; keep disabled |
| USR-023 | read_only | disabled | terminated | retain | Denied access; keep disabled |
| USR-024 | read_only | active | employed | retain | Approved: current scoped access |

## Current workflow tests

Five baseline negative cases failed because the service accepted duplicate/conflicting or absent,
blank and non-string decisions. The correction requires exactly one non-empty decision per account.
Six current tests pass, including complete-population reconciliation and attributable completion
events. Rejected records persist no new review or completion event. Baseline and retest evidence are
retained separately. Tests use disposable SQLite and do not create a main-lab human review.

Non-empty strings are a structural check, not a judgment that a decision is appropriate. Follow-up
references are not automatically resolved or verified. Overall IAM-05 remains `not_assessed` /
`insufficient_evidence`; privileged approval conditions and appropriate follow-up evidence remain open.

## Local deployment verification

The corrected app is running locally. All five invalid-review cases were rejected before any write
in a PostgreSQL READ ONLY transaction; review count remained one and completion-event count remained
zero. No human review was created. Full suites passed 166 tests on Windows (86.12% coverage) and
Linux/PostgreSQL (86.15%). New service cases use SQLite on both platforms; the read-only main-lab
smoke separately verifies the PostgreSQL boundary.

## Rationale and unresolved privileged condition

The 15 employed nonprivileged accounts retain their current scoped access to support daily work.
Employment is a business need, not authorization for unrestricted access. Read-only users retain
only own/assigned request visibility and cannot change requests. The six privileged accounts are
needed for maintenance and change approval, but the owner's approval explicitly requires RBAC
and PAM. Current tests demonstrate selected RBAC/MFA boundaries; they do not establish full PAM.

**PAM-001 remains open.** Define and demonstrate a proportionate approval, temporary elevation or
credential checkout followed by expiry, revocation and attributable activity review before closing the condition.
No credential vaulting, temporary privilege elevation or privileged session recording is claimed.
Existing privileged accounts are still active in the local lab under the observed RBAC/MFA rules;
this decision record does not enforce the missing PAM condition.

USR-017, USR-022 and USR-023 remain disabled because employment ended. Preserve their identities
for traceability. There is no evidence here that they committed a security breach; allowing
unjustified active access would violate the access-control principle. Overall IAM-03/IAM-05 and
the final PRD v1 release remain incomplete.
