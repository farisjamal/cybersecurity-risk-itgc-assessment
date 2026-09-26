# Cybersecurity Risk and ITGC Assessment

This documentation supports an independent, local-only assessment of **Example Bank Lab**, a
fictional Malaysian financial institution. The project connects business objectives, risks,
controls, tests, evidence, findings, remediation, and retest results without implying a real client
engagement or regulatory certification.

The [PRD](../PRD.md) is the delivery baseline. Use these guides in order:

1. [Setup](setup.md) — prepare a locked Python environment and contained Docker lab.
2. [Architecture](architecture.md) — understand trust boundaries and data flow.
3. [Methodology](methodology.md) — understand the twenty-control assessment and evidence rules.
4. [Testing](testing.md) — run local and CI quality gates.
5. [Demonstration](demo.md) — reproduce a representative finding-to-retest chain.
6. [Limitations](limitations.md) — keep conclusions inside the evidence boundary.
7. [Source register](source-register.md) and [claims register](claims-register.md) — inspect source
   provenance and portfolio wording.

Generated runtime evidence, backups, reports, and distribution bundles are excluded from source
control until explicitly reviewed and sanitized. Canonical assessment source records remain under
`assessment/`.
