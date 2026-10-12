# Assessment completion and owner review

Prepared 11 October 2026. CybersecurityProject is the main twenty-control project selected by
the owner. The separate eight-control digital-trust-itgc-lab remains a distinct compact simulation.
Moving folders does not combine their evidence, Git history or assessment conclusions.

## Observed engineering evidence

- [PostgreSQL recovery observation](../fixtures/evidence/completion/runtime-20261011.json):
  24 users, 51 service requests, 51 request-history rows, six access requests, one access review,
  twelve changes and four incidents restored to a separate empty database. Read-only application
  acceptance returned HTTP 200 and reconciled all 51 request IDs. The source was preserved.
- [Six isolated scenario chains](../fixtures/evidence/completion/scenarios-20261011.json):
  all six fresh retests passed; the main lab business digest and population counts stayed unchanged.
  Scenario containers and networks were stopped. Their volumes remain for investigation.
- [Dependency audit](../fixtures/evidence/completion/dependencies-20261011.json):
  40 locked packages, zero known advisories returned at the recorded collection time. This is
  point-in-time feed coverage. Feed failure, skipped packages and malformed results cannot produce
  a clean conclusion.
- Recovery measured 0.359882 seconds from declared logical exercise outage to application acceptance
  and 0.593947 seconds from that outage to the recoverable checkpoint. This is one logical restore,
  not a machine failure, failover or full disaster recovery exercise.
- The test suite now exercises 10,000 attributable events and exports 200 evidence records without
  truncation. Capacity-only records stay in disposable test workspaces and do not inflate assessment
  evidence counts.

Historical account/change/review dates are generated fixtures. They do not establish operation during
August 2026. The verifier adds a labelled current checkpoint so RPO uses a real committed timestamp.
Initial passwords, TOTP secrets, raw backups and database URLs remain outside the reviewed bundle.

## Control-by-control decision packet

These are observations and remaining procedures, **not owner-approved control conclusions**.
The original S01 workpaper and historical baseline remain frozen. The sixteen limitation workpapers
are retained until an attributable assessor decision replaces their incomplete conclusions.

| Control | Available evidence or observation | Work needed before a defensible conclusion |
| --- | --- | --- |
| GOV-01 | Versioned policies, asset register, live portal/PostgreSQL stack and recovery observation | Reconcile every inventory component and trust boundary to observed deployment; record owner approval |
| GOV-02 | Twenty risk records; four previously rated bounded findings | Owner assesses the sixteen remaining risks with rationale, treatment owners and review dates; do not generate ratings automatically |
| GOV-03 | Supplier-control objective and selected source mapping | Prepare and inspect both explicitly fictional supplier packs, including responsibilities, due diligence gaps and treatment |
| IAM-01 | Full 24-account observed fixture population; [four current service tests](../fixtures/evidence/completion/iam01-walkthrough-20261012.json) passed for approval-before-activation and employee eligibility; [self-approval regression](../fixtures/evidence/completion/iam01-self-approval-20261012.json) also passed with an independent-approval positive control | Historical joiner approval coverage, initial activation dates and approved role-matrix reconciliation remain unverified; current service tests do not establish August operation |
| IAM-02 | Frozen S01 baseline, action and retest; current isolated S01 reproduction | Retain bounded result; review every leaver and session in the defined population before widening the claim |
| IAM-03 | Six privileged assignments enumerated read-only from 24 accounts; twenty isolated HTTP authorization cases passed after correcting read-only scope selected by owner; baseline retained; [access rules and scope](iam03-access-review.md) documented | Six privileged assignments now have owner approval conditional on RBAC/PAM; PAM-001 and the remaining role matrix remain unverified; selected paths do not cover every endpoint or historical operation |
| IAM-04 | Preserved S03 chain; current retest checks actual password-only denial and verified MFA authorization | Substantively review the stated scope; TOTP is not phishing resistant |
| IAM-05 | All 24 accounts reconciled exactly to ARV-001; reviewer attribution absent; five malformed-decision baseline cases failed, six tests passed after validation correction; [owner decision packet](iam05-access-review.md) prepared | Current owner decisions are recorded for all 24 accounts; verify the six privileged PAM conditions and trace necessary follow-up; generated retain decisions and dates are not historical operation |
| CHG-01 | Twelve observed generated changes and independent-approval workflow tests | Inspect every normal change for independent approval before deployment and record exclusions |
| CHG-02 | Generated test-reference fields and software regression suite | Resolve each deployed change's version-specific test artifact; a reference string alone is insufficient |
| CHG-03 | Current image build and change workflow | Perform and retain an actual deployment/rollback exercise with revision, acceptance and rollback checks |
| CHG-04 | Generated emergency-change records and S04 isolated reproduction | Inspect every emergency record for reason, dated retrospective review and policy timeliness |
| OPS-01 | Preserved S05 failure/retest; current corruption rejection checks | Review preserved failure and actual hash validation; do not infer success from a job's reported status |
| OPS-02 | Actual isolated PostgreSQL restore, table reconciliation and read-only API acceptance | Review expected/actual table counts and backup hash; conclusion can cover only the measured logical exercise |
| OPS-03 | Preserved S06 chain, current isolated retest and 10,000-event regression | Review attribution and completeness across required event types, including omissions |
| OPS-04 | Live 40-package audit and explicit unavailable-feed regression checks | Owner records treatment if findings arise and acknowledges scope/date and unassessed non-Python dependencies |
| IR-01 | Threshold/deduplication tests and attributable incident fixtures | Execute and record each required trigger with expected event/alert IDs and duplicate suppression |
| IR-02 | Synthetic incident records and event investigation capabilities | Conduct a labelled tabletop with recorded human triage, containment decisions, timeline and lessons |
| DR-01 | Recovery policies and [local runbook](recovery-runbook.md) | Owner reviews dependencies, activation decision, recovery order, targets and fallback steps |
| DR-02 | Actual logical recovery timings with a fresh committed checkpoint | Review the one-run outcome and lessons; infrastructure failure/failover remains untested |

## Decisions the owner must record

PRD Sections 11.3 and 11.5 require an explicit assessor decision and a separate substantive self-review.
DEC-09 prohibits AI risk scoring or report claims without explicit human validation. Automated test
success cannot fill in those decisions or impersonate the owner.

For each control, record the selected evidence and population, executed procedure, exceptions,
design conclusion, operating conclusion, rationale and remaining limitations. Review the four existing
bounded conclusions as well as the sixteen incomplete ones. Record actual preparation/review times.
Do not backdate a new observation into the generated August period.

The owner review remains open in [REV-GOV-001](../assessment/reviews/REV-GOV-001.yaml).
All twenty acceptance criteria still apply: four currently pass and sixteen remain partial.
Fresh-machine Windows reproduction, hosted CI for the final revision, manual browser/accessibility
review and visual review of the latest rendered deliverables remain required release work.

```powershell
uv run python -m cyber_assess release-check --engagement ENG-001 --json
```

Exit code 4 means release remains blocked, even when assessment schemas validate successfully.
Public GitHub source publication was explicitly authorized on 12 October 2026. That authorization
does not close assessment blockers or approve internet-facing runtime deployment.
