from __future__ import annotations

from pathlib import Path

from cyber_assess.validation import validate_assessment, validate_findings


def test_canonical_s01_chain_is_traceable_and_closed() -> None:
    workspace = Path(__file__).resolve().parents[2]
    assessment = validate_assessment(workspace, "ENG-001")
    findings = validate_findings(workspace, "ENG-001")

    assert assessment.valid, assessment.errors
    assert findings.valid, findings.errors
    assert "FIND-S01-001" in findings.validated_ids
    assert "RETEST-S01-001" in findings.validated_ids
