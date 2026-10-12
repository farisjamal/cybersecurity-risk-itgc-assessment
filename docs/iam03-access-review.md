# IAM-03 current authorization review

Prepared 12 October 2026. This is an observed implementation review of a fictional local lab.
The owner selected ownership/assignment-limited reading for `read_only` on 12 October 2026.
The remaining table entries are observed implementation rules, not a fully owner-approved role
matrix, and do not establish historical operation.

## Population and test scope

A read-only PostgreSQL query enumerated 24 accounts. The privileged population is USR-001 and
USR-002 (administrator), and USR-003 through USR-006 (change approver). This enumeration establishes
current assignments, not the business authorization for those assignments.

Twenty HTTP test cases execute against freshly seeded, independent SQLite databases. All six
privileged fixture identities and one staff/read-only representative are covered for the selected
privileged endpoints. Four role representatives are each tested as owner, assignee and unrelated user
for request listing, detail and status transitions. The main lab is not modified by these tests.

## Observed rules and expected HTTP results

| Operation | Administrator | Change approver | Staff | Read-only |
| --- | --- | --- | --- | --- |
| GET /admin/users before MFA | 403 | 403 | 403 | 403 |
| GET /admin/users after valid MFA for privileged identities | 200 | 403 | 403, role denied | 403, role denied |
| GET /events before MFA | 403 | 403 | 403 | 403 |
| GET /events after valid MFA for privileged identities | 200 | 200 | 403, role denied | 403, role denied |
| POST /admin/users/{id}/deactivate by non-administrator | Not exercised here | 403 | 403 | 403 |
| GET /requests/{id} | 200 | 200 | 200 if owner/assignee; otherwise 404 | 200 if owner/assignee; otherwise 404 |
| PATCH /requests/{id}, open to in_progress | 200 | 403 | 200 if owner/assignee; otherwise 404 | 403 if visible; otherwise 404 |
| POST /requests by read-only identity | Not exercised here | Not exercised here | Not exercised here | 403 |

Valid CSRF headers are supplied for protected calls so role-denial results are not confused with
missing-CSRF denial. Privileged role restrictions are checked after successful MFA. Denied status
changes leave the request and its history unchanged; denied deactivation leaves the target active.

Cross-owner reading by administrators and change approvers remains an observed implementation rule
pending owner review. Read-only users previously had global reading; the owner selected own/assigned
requests only. List and detail enforcement now apply that scope, while all read-only mutations remain
denied. This current correction does not retroactively authorize the earlier behavior.

## Conclusion and remaining decisions

The initial twenty tests matched the previous implementation, including global read-only reading.
After the owner's scope selection, the source was corrected and twenty cases passed again for the
updated expectations. Baseline and retest evidence are retained separately.

The selected current HTTP paths matched the updated rules in twenty tests. Overall IAM-03 remains
`not_assessed` / `insufficient_evidence` until the owner reviews an explicit role matrix, validates the
six assignments and addresses any scope differences. Not every endpoint/verb, every staff/read-only
identity, historical role change or scenario S02 is covered by this run. The full twenty-case HTTP
matrix uses SQLite. A separate smoke on the updated PostgreSQL main lab confirmed that USR-019 sees
exactly one eligible request and receives 404 for an unrelated request. Selected account/request
business digests matched before and after the app update; login/session audit rows naturally change.

Full suites passed 161 tests on Windows (86.09% coverage) and Linux/PostgreSQL (86.12%). The new
IAM-03 matrix retains its explicit isolated SQLite boundary on both platforms.

Evidence and source hashes are registered in the IAM-03 workpaper. Raw JUnit metadata remains in
ignored runtime storage. No password, MFA seed, session cookie or database URL is in the bundle.

## Current owner disposition

On 12 October 2026 the owner conditionally approved all six privileged assignments for system
health and maintenance, requiring RBAC and PAM. See the
[account decision packet](iam05-access-review.md). The PAM-001 follow-up is open: current RBAC,
TOTP MFA, audit events and revocation do not demonstrate privileged credential vaulting or
approval-based temporary elevation. This conditional business authorization does not complete
the full owner-approved endpoint/role matrix or historical IAM-03 assessment.
