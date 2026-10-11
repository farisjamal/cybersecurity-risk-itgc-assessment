# Source register

This register is derived from PRD v1.0. Its external references were recorded as checked on
**24 September 2026**; that date is historical provenance, not a claim that links or requirements are
currently unchanged. Recheck the exact source, date, version, locator, applicability, and retained hash
before publishing a mapping or regulatory observation.

| ID | Source and locator | Intended use | Status and boundary |
| --- | --- | --- | --- |
| R1 | [PwC Malaysia — Information Technology Risk Assurance](https://www.pwc.com/my/en/services/assurance/risk-assurance-services/it-risk-assurance.html) | Public role/service context | Checked per PRD; no endorsement or PwC methodology claimed |
| R2 | [NIST Cybersecurity Framework 2.0](https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf) | Function/category identifiers and outcome mapping | Checked per PRD; verify each category used |
| R3 | [NIST CSF 2.0 Profiles](https://www.nist.gov/cyberframework/profiles) | Current/Target Profile context | Checked per PRD; organization-specific profile remains project-authored |
| R4 | [NIST SP 1301](https://csrc.nist.gov/pubs/sp/1301/final) | Organizational Profile guidance | Checked per PRD; not an assurance standard |
| R5 | [BNM — revised RMiT publication](https://www.bnm.gov.my/-/pd-rmit-nov25) | Official publication/version entry point | Checked per PRD; selected aspects only |
| R6 | [BNM RMiT policy document, 28 November 2025](https://www.bnm.gov.my/documents/20124/938039/pd-rmit-nov25.pdf) | Selected paragraph/page mappings | Initial pointers checked per PRD; exact locator and applicability require mapping-level review |
| R6a | [BNM RMiT FAQ, July 2026](https://www.bnm.gov.my/documents/20124/938039/faq-pd-rmit-jul2026.pdf) | Clarification of selected requirements | Located per PRD; relevant answers require explicit review |
| R7 | [Docker Compose application model](https://docs.docker.com/compose/intro/compose-application-model/) | Service/network/volume architecture | Checked per PRD; exact image/runtime behavior verified locally |
| R8 | User-supplied Associate — Digital Trust and Cybersecurity job description | Portfolio capability alignment | Private supplied input; vacancy status not verified and text is not redistributed |

## Active mapping sources as of 11 October 2026

The canonical [mapping register](../assessment/mappings.yaml) supersedes the historical BNM pointers
above. It uses NIST CSF 2.0 (26 February 2024) and the
[BNM RMiT policy dated 25 September 2026](https://www.bnm.gov.my/documents/20124/938039/pd-rmit-sep26.pdf).
Source IDs are `SRC-NIST-CSF-2` and `SRC-BNM-RMIT-2026`. The retained local reference files match the
SHA-256 values recorded in that register; source PDFs are not redistributed. Selected category and
paragraph locators are verified references, while coverage remains limited to each stated aspect.
This does not establish regulatory compliance. Verified reference status does not close an untested
control or substitute for assessor judgment.

## Mapping record minimum

Each mapping records source ID, framework/version, document date, URL, retrieval date, paragraph or
category, displayed page where applicable, concise original summary, rationale, control IDs, assessment
coverage, limitations, verification status, and retained-file hash when redistribution is permitted.

Allowed source statuses are `verified_reference`, `unverified_reference`, and `not_mapped`. Allowed
coverage conclusions are `supported_for_tested_aspect`, `gap_identified`, `not_assessed`, and
`not_applicable_with_rationale`. An unverified reference blocks publication of the affected regulatory
claim.
