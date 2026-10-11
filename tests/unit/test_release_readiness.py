from pathlib import Path

from cyber_assess.readiness import release_readiness


def test_schema_valid_records_do_not_imply_release_completion() -> None:
    result = release_readiness(Path(__file__).resolve().parents[2], "ENG-001")
    assert result["structurally_valid"] is True
    assert result["ready"] is False
    assert any("self-review" in issue for issue in result["blockers"])


def test_missing_assessment_never_reports_ready(tmp_path: Path) -> None:
    result = release_readiness(tmp_path, "ENG-MISSING")
    assert result["ready"] is False
    assert result["structurally_valid"] is False
    assert result["blockers"]
