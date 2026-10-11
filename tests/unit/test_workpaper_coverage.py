from __future__ import annotations

import hashlib
from pathlib import Path

from cyber_assess.models import Control, Evidence, Workpaper
from cyber_assess.validation import validate_assessment
from cyber_assess.yamlio import load_models, load_yaml

ROOT = Path(__file__).resolve().parents[2]
EMPTY_CONTENT_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
FROZEN_S01_SHA256 = "a259cf712b19a32f8a2d3c47079d9c7e2a82b2989f70e81522665c9ee6735bfd"


def _controls() -> list[Control]:
    payload = load_yaml(ROOT / "assessment" / "controls.yaml")
    return [Control.model_validate(item) for item in payload["controls"]]


def _workpapers() -> list[Workpaper]:
    return load_models(ROOT / "assessment" / "workpapers", Workpaper)


def test_each_of_the_twenty_controls_has_exactly_one_workpaper() -> None:
    controls = _controls()
    workpapers = _workpapers()

    assert len(controls) == 20
    assert len(workpapers) == 20
    assert len({workpaper.control_id for workpaper in workpapers}) == 20
    assert {workpaper.control_id for workpaper in workpapers} == {
        control.id for control in controls
    }


def test_workpapers_distinguish_unexecuted_controls_from_bounded_scenario_retests() -> None:
    limitation_workpapers = [
        workpaper for workpaper in _workpapers() if workpaper.id.endswith("-LIMITATION")
    ]
    tested_controls = {"IAM-04", "OPS-01", "OPS-03"}
    unexecuted = [
        workpaper
        for workpaper in limitation_workpapers
        if workpaper.control_id not in tested_controls
    ]
    bounded_retests = [
        workpaper for workpaper in limitation_workpapers if workpaper.control_id in tested_controls
    ]

    assert len(limitation_workpapers) == 19
    assert len(unexecuted) == 16
    assert len(bounded_retests) == 3
    for workpaper in unexecuted:
        assert workpaper.design_status == "not_assessed"
        assert workpaper.operating_status == "not_tested"
        assert workpaper.population_source == "not_collected"
        assert workpaper.population_hash == EMPTY_CONTENT_SHA256
        assert workpaper.population_count == 0
        assert workpaper.selected_record_ids == []
        assert workpaper.exceptions == []
        assert workpaper.assessor_decision.startswith("Retain no conclusion")
        assert any(
            "project-owner substantive review remains outstanding" in limitation.lower()
            for limitation in workpaper.limitations
        )
        assert any(
            "no control procedure was executed" in limitation.lower()
            for limitation in workpaper.limitations
        )
    for workpaper in bounded_retests:
        assert workpaper.design_status == "partially_adequate"
        assert workpaper.operating_status == "effective_in_tested_scope"
        assert workpaper.population_count == 1
        assert workpaper.selected_record_ids
        assert workpaper.exceptions
        assert any(
            "project-owner substantive review remains outstanding" in limitation.lower()
            for limitation in workpaper.limitations
        )


def test_limitation_workpapers_preserve_policy_and_observed_evidence_provenance() -> None:
    evidence = {item.id: item for item in load_models(ROOT / "assessment" / "evidence", Evidence)}

    for workpaper in _workpapers():
        if not workpaper.id.endswith("-LIMITATION"):
            continue
        provenances = {evidence[evidence_id].provenance for evidence_id in workpaper.evidence_ids}
        assert provenances.issubset({"authored_policy", "observed_lab"})
        for evidence_id in workpaper.evidence_ids:
            if evidence[evidence_id].provenance == "observed_lab":
                assert workpaper.operating_status == "effective_in_tested_scope"


def test_s01_workpaper_remains_identical_to_the_frozen_snapshot() -> None:
    path = ROOT / "assessment" / "workpapers" / "WP-IAM-02-S01.yaml"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    assert digest == FROZEN_S01_SHA256


def test_complete_workpaper_set_passes_cross_record_validation() -> None:
    for record in load_models(ROOT / "assessment" / "evidence", Evidence):
        if record.sensitivity == "sanitized" and record.media_type == "application/json":
            # Git checks out JSON as LF; recorded byte hashes must survive that conversion.
            assert b"\r\n" not in (ROOT / record.path).read_bytes()
    result = validate_assessment(ROOT, "ENG-001")

    assert result.valid, result.errors
    assert not result.errors
    assert {workpaper.id for workpaper in _workpapers()}.issubset(result.validated_ids)
