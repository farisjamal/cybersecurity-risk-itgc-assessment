from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from cyber_assess.models import (
    AcceptanceResult,
    AssetRegister,
    BlockerRegister,
    Control,
    EvidenceRequestRegister,
    MappingRegister,
    MilestoneRegister,
    RiskRecord,
    RiskRegister,
)
from cyber_assess.validation import validate_governance
from cyber_assess.yamlio import load_model, load_models, load_yaml

ROOT = Path(__file__).resolve().parents[2]


def _controls() -> list[Control]:
    raw = load_yaml(ROOT / "assessment" / "controls.yaml")
    return [Control.model_validate(item) for item in raw["controls"]]


def test_governance_records_are_schema_valid_and_cross_referenced() -> None:
    result = validate_governance(ROOT, "ENG-001")

    assert result.valid, result.errors
    assert not result.errors
    assert {f"AT-{number:02d}" for number in range(1, 21)}.issubset(result.validated_ids)


def test_asset_and_risk_register_cover_the_engagement_and_control_catalogue() -> None:
    assets = load_model(
        ROOT / "assessment" / "governance" / "assets.yaml",
        AssetRegister,
    )
    risks = load_model(
        ROOT / "assessment" / "governance" / "risks.yaml",
        RiskRegister,
    )
    controls = _controls()

    assert {asset.id for asset in assets.assets} == {"ASSET-PORTAL"}
    assert len(assets.data_flows) == 3
    assert all(flow.verification_status == "runtime_unverified" for flow in assets.data_flows)
    assert {risk.id for risk in risks.risks} == {
        risk_id for control in controls for risk_id in control.risk_ids
    }
    assert len(risks.risks) == 20
    assessed = {
        risk.id: risk for risk in risks.risks if risk.assessment_status == "assessed_observed"
    }
    assert set(assessed) == {"RISK-IAM-02", "RISK-IAM-04", "RISK-OPS-01", "RISK-OPS-03"}
    assert assessed["RISK-IAM-02"].rating == 20


def test_mapping_register_uses_verified_current_primary_sources() -> None:
    register = load_model(ROOT / "assessment" / "mappings.yaml", MappingRegister)
    sources = {source.id: source for source in register.sources}
    nist_mappings = {
        mapping.control_ids[0]: mapping
        for mapping in register.mappings
        if mapping.source_id == "SRC-NIST-CSF-2"
    }

    assert len(nist_mappings) == 20
    for control in _controls():
        mapping = nist_mappings[control.id]
        assert mapping.reference_locator == control.nist_categories
        assert mapping.verification_status == "verified_reference"
    assert sources["SRC-NIST-CSF-2"].local_sha256 == (
        "3c31f46fee98cac0c4323453e5109291a213b4de7fef8c058af9bf67f717433c"
    )
    assert sources["SRC-BNM-RMIT-2026"].local_sha256 == (
        "d7b8e6753a78514e90fbfe0cef6bd40ff8bccbfc60e17c7575db4cec1fba6cd6"
    )
    assert all(source.verification_status == "verified_reference" for source in register.sources)
    assert any(mapping.source_id == "SRC-BNM-RMIT-2026" for mapping in register.mappings)


def test_acceptance_register_records_gaps_instead_of_unsupported_passes() -> None:
    results = load_models(ROOT / "assessment" / "acceptance", AcceptanceResult)
    by_id = {result.id: result for result in results}

    assert set(by_id) == {f"AT-{number:02d}" for number in range(1, 21)}
    assert {result.status for result in results} == {"passed", "partial"}
    assert {result.id for result in results if result.status == "passed"} == {
        "AT-08",
        "AT-10",
        "AT-13",
        "AT-14",
    }
    assert by_id["AT-19"].status == "partial"
    assert all(result.limitations for result in results if result.status != "passed")
    assert set(by_id["AT-13"].evidence_ids) == {
        "EVID-S01-BASELINE",
        "EVID-S01-RETEST",
        "EVID-S03-BASELINE",
        "EVID-S03-RETEST",
        "EVID-S05-BASELINE",
        "EVID-S05-RETEST",
        "EVID-S06-BASELINE",
        "EVID-S06-RETEST",
    }


def test_governance_workflow_records_keep_open_gaps_attributable() -> None:
    governance = ROOT / "assessment" / "governance"
    requests = load_model(governance / "evidence_requests.yaml", EvidenceRequestRegister)
    milestones = load_model(governance / "milestones.yaml", MilestoneRegister)
    blockers = load_model(governance / "blockers.yaml", BlockerRegister)

    assert {request.status for request in requests.requests} == {
        "received",
        "incomplete",
        "blocked",
    }
    assert any(milestone.status == "blocked" for milestone in milestones.milestones)
    assert {blocker.id for blocker in blockers.blockers if blocker.status == "resolved"} == {
        "BLK-RUNTIME-001",
        "BLK-MAPPING-001",
    }
    assert {blocker.id for blocker in blockers.blockers if blocker.status == "open"} == {
        "BLK-ASSESS-001",
        "BLK-DELIVERY-001",
        "BLK-REVIEW-001",
    }
    assert all(blocker.resolution_criteria for blocker in blockers.blockers)


def test_assessed_risk_requires_consistent_rating_and_evidence() -> None:
    with pytest.raises(ValidationError, match="risk rating must equal"):
        RiskRecord.model_validate(
            {
                "schema_version": "1.0",
                "id": "RISK-TEST-01",
                "title": "Inconsistent risk",
                "asset_ids": ["ASSET-PORTAL"],
                "control_ids": ["GOV-01"],
                "scenario": "Test scenario",
                "assessment_status": "assessed_observed",
                "likelihood": 2,
                "impact": 3,
                "rating": 5,
                "rating_rationale": "Test only",
                "evidence_ids": ["EVID-TEST-01"],
                "status": "open",
                "limitations": ["Test only"],
            }
        )


def test_governance_validation_rejects_unknown_acceptance_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(ROOT / "assessment", workspace / "assessment")
    acceptance_path = workspace / "assessment" / "acceptance" / "AT-13.yaml"
    payload = yaml.safe_load(acceptance_path.read_text(encoding="utf-8"))
    payload["evidence_ids"] = ["EVID-NOT-REGISTERED"]
    acceptance_path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )

    result = validate_governance(workspace, "ENG-001")

    assert not result.valid
    assert "AT-13: missing evidence ['EVID-NOT-REGISTERED']" in result.errors
