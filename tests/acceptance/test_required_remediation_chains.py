from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from bank_lab.database import Base, build_session_factory
from bank_lab.models import RunStatus, ScenarioRun
from bank_lab.scenarios import remediate_scenario, retest_scenario, run_scenario
from bank_lab.seed import seed_database
from cyber_assess.integrity import verify_file
from cyber_assess.models import Action, Evidence, Finding, Retest
from cyber_assess.validation import validate_findings
from cyber_assess.yamlio import load_models

WORKSPACE = Path(__file__).resolve().parents[2]

SCENARIO_EXPECTATIONS = {
    "S03": {
        "fixture_directory": "s03",
        "baseline_file": "baseline_mfa_observation.json",
        "retest_file": "retest_mfa_observation.json",
        "baseline_keys": ("password_only_privileged_allowed",),
        "retest_keys": ("password_only_denied", "mfa_session_allowed"),
    },
    "S05": {
        "fixture_directory": "s05",
        "baseline_file": "baseline_backup_observation.json",
        "retest_file": "retest_backup_observation.json",
        "baseline_keys": ("reported_success", "valid"),
        "retest_keys": ("corrupt_backup_rejected", "failed_original_preserved"),
    },
    "S06": {
        "fixture_directory": "s06",
        "baseline_file": "baseline_event_observation.json",
        "retest_file": "retest_event_observation.json",
        "baseline_keys": ("action", "event_emitted"),
        "retest_keys": ("event_emitted",),
    },
}


@pytest.fixture
async def seeded_db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = build_session_factory(engine)
    async with factory() as session:
        with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
            await seed_database(session, password_factory=lambda: "Fixture-Pass-42!")
        yield session
    await engine.dispose()


def _fixture(scenario: str, filename: str) -> dict[str, object]:
    directory = str(SCENARIO_EXPECTATIONS[scenario]["fixture_directory"])
    path = WORKSPACE / "fixtures" / "evidence" / directory / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


@pytest.mark.acceptance
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_id", ["S03", "S05", "S06"])
async def test_recorded_required_remediation_matches_deterministic_replay(
    seeded_db: AsyncSession, scenario_id: str
) -> None:
    expected = SCENARIO_EXPECTATIONS[scenario_id]
    resource_name = f"cyber-assess-scenario-{scenario_id.lower()}-fixture"
    baseline_fixture = _fixture(scenario_id, str(expected["baseline_file"]))
    retest_fixture = _fixture(scenario_id, str(expected["retest_file"]))

    baseline = await run_scenario(seeded_db, scenario_id, resource_name)
    frozen_observations = dict(baseline.observations)
    remediation = await remediate_scenario(seeded_db, scenario_id, baseline.run_id, resource_name)
    retest = await retest_scenario(seeded_db, scenario_id, baseline.run_id, remediation.run_id)

    assert baseline.status == RunStatus.FROZEN
    assert remediation.status == RunStatus.COMPLETED
    assert retest.status == RunStatus.COMPLETED
    assert retest.observations["passed"] is True
    assert baseline_fixture["resource_name"] == resource_name
    assert retest_fixture["resource_name"] == resource_name
    for key in expected["baseline_keys"]:
        assert baseline_fixture[key] == baseline.observations[key]
    for key in expected["retest_keys"]:
        assert retest_fixture[key] == retest.observations[key]

    preserved = await seeded_db.get(ScenarioRun, baseline.run_id)
    assert preserved is not None
    assert preserved.status == RunStatus.FROZEN
    assert preserved.observations == frozen_observations


@pytest.mark.acceptance
def test_required_remediation_records_are_traceable_and_closed() -> None:
    findings_result = validate_findings(WORKSPACE, "ENG-001")
    assert findings_result.valid, findings_result.errors

    evidence = {item.id: item for item in load_models(WORKSPACE / "assessment/evidence", Evidence)}
    findings = {item.id: item for item in load_models(WORKSPACE / "assessment/findings", Finding)}
    actions = {
        item.finding_id: item for item in load_models(WORKSPACE / "assessment/actions", Action)
    }
    retests = {
        item.finding_id: item for item in load_models(WORKSPACE / "assessment/retests", Retest)
    }
    for scenario_id in ("S03", "S05", "S06"):
        finding_id = f"FIND-{scenario_id}-001"
        baseline_evidence = evidence[f"EVID-{scenario_id}-BASELINE"]
        retest_evidence = evidence[f"EVID-{scenario_id}-RETEST"]
        finding = findings[finding_id]
        action = actions[finding_id]
        retest = retests[finding_id]
        assert finding.status == "closed_verified"
        assert action.status == "implemented"
        assert action.closure_criteria == retest.closure_criteria
        assert retest.fresh_evidence is True
        assert retest.result == "passed"
        assert retest.decision == "accept_closure"
        assert retest.executed_at > action.implemented_at
        assert retest_evidence.parent_evidence_id == baseline_evidence.id
        verify_file(
            WORKSPACE,
            baseline_evidence.path,
            baseline_evidence.sha256,
            baseline_evidence.size,
        )
        verify_file(
            WORKSPACE,
            retest_evidence.path,
            retest_evidence.sha256,
            retest_evidence.size,
        )
        assert finding_id in findings_result.validated_ids
        assert retest.id in findings_result.validated_ids
