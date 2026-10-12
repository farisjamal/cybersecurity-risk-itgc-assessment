# Cybersecurity Risk and ITGC Assessment

This documentation supports an independent, local-only assessment of **Example Bank Lab**, a
fictional Malaysian financial institution. The project connects business objectives, risks,
controls, tests, evidence, findings, remediation, and retest results without implying a real client
engagement or regulatory certification.

The [PRD](../PRD.md) is the delivery baseline. Use these guides in order:

1. [Setup](setup.md) â€” prepare a locked Python environment and contained Docker lab.
2. [Architecture](architecture.md) â€” understand trust boundaries and data flow.
   Use the [repository layout](repository-layout.md) to locate implementation, infrastructure,
   scripts, canonical assessment data and local generated outputs.
3. [Methodology](methodology.md) â€” understand the twenty-control assessment and evidence rules.
4. [Testing](testing.md) â€” run local and CI quality gates.
5. [Demonstration](demo.md) â€” reproduce a representative finding-to-retest chain.
6. [Limitations](limitations.md) â€” keep conclusions inside the evidence boundary.
7. [Security publication review](security-publication-review.md) â€” inspect source exclusions,
   secret/history checks, container remediation and residual advisories.
8. [Source register](source-register.md) and [claims register](claims-register.md) â€” inspect source
   provenance and portfolio wording.

Current account authorization and its open PAM condition are recorded in the
[IAM-03 scope](iam03-access-review.md) and [IAM-05 owner decision packet](iam05-access-review.md).
Publication is source sharing; sixteen control conclusions and final PRD v1 acceptance remain incomplete.

Generated runtime evidence, backups, reports, and distribution bundles are excluded from source
control until explicitly reviewed and sanitized. Canonical assessment source records remain under
`assessment/`.
