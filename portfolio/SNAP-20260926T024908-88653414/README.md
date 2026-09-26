# Reviewed portfolio bundle

This bundle is frozen to `SNAP-20260926T024908-88653414` for the simulated Example Bank Lab.
It contains synthetic, self-reviewed portfolio material only. It is not a real-client assessment,
independent audit, certification, or regulatory-compliance opinion.

## What is included

- `assessment-workbook.xlsx`: generated 14-sheet assessment workbook.
- `engagement-brief.*`: Markdown, HTML, and visually reviewed A4 PDF.
- `executive-report.*`: Markdown, HTML, and visually reviewed A4 PDF.
- `presentation.html` and `executive-presentation.pdf`: seven slides; English speaker notes remain
  in the HTML source and are intentionally hidden in the PDF.
- `remediation-roadmap.*`: reconciled roadmap in CSV and JSON.
- `sanitized-evidence-package.zip`: allowlisted snapshot sources with no runtime secrets or backup
  payloads.
- `claims-evidence-index.json`, `evidence-manifest.json`, `artifact-manifest.json`,
  `pdf-render-manifest.json`, and `distribution-manifest.json`: traceability and integrity metadata.
- `snapshot.yaml` and `reconciliation.json`: frozen source hashes and cross-record counts.

## Honest status

- Twenty of twenty controls have frozen workpapers.
- Four controls have executed assessment conclusions and verified local remediation/retest chains:
  IAM-02/S01, IAM-04/S03, OPS-01/S05, and OPS-03/S06.
- Sixteen workpapers remain explicitly `not_assessed`/`not_tested` limitation records.
- The canonical acceptance register records one passed, seventeen partial, and two missing tests.
- NIST/RMiT mappings remain marked `unverified_reference` until their locators receive source-level
  verification.

## Reproduce and verify

From the repository root:

```powershell
uv run python -m cyber_assess verify --snapshot SNAP-20260926T024908-88653414 --json
uv run python -m cyber_assess export --snapshot SNAP-20260926T024908-88653414 --json
uv run python -m cyber_assess report-inputs --snapshot SNAP-20260926T024908-88653414 --json
uv run python -m cyber_assess artifacts --snapshot SNAP-20260926T024908-88653414 --json
./scripts/render-pdfs.ps1 -SnapshotId SNAP-20260926T024908-88653414
```

The core generator refuses to overwrite an existing destination. Render into a clean ignored output
directory when reproducing. Compare SHA-256 values against the manifests; matching hashes detect
change but do not provide independent authenticity.
