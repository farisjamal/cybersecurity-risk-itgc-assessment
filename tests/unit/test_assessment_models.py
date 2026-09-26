from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cyber_assess.integrity import PathOutsideWorkspaceError, resolve_within, sha256_file
from cyber_assess.models import Evidence, Finding, Retest
from cyber_assess.risk import RiskBand, calculate_risk
from cyber_assess.sampling import select_sample
from cyber_assess.workflow import InvalidTransitionError, transition_finding


def test_risk_score_uses_exact_prd_bands() -> None:
    assert calculate_risk(1, 4).band is RiskBand.LOW
    assert calculate_risk(3, 3).band is RiskBand.MEDIUM
    assert calculate_risk(4, 4).band is RiskBand.HIGH
    assert calculate_risk(5, 5).band is RiskBand.CRITICAL


@pytest.mark.parametrize("likelihood,impact", [(0, 1), (1, 6), (-1, 2)])
def test_risk_score_rejects_values_outside_one_to_five(likelihood: int, impact: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 5"):
        calculate_risk(likelihood, impact)


def test_sampling_selects_all_small_populations() -> None:
    population = [f"REC-{number:02d}" for number in range(25)]
    result = select_sample(population, seed=42)
    assert result.selected_ids == tuple(population)
    assert result.method == "complete_population"


def test_sampling_is_deterministic_and_always_includes_high_risk() -> None:
    population = [f"REC-{number:02d}" for number in range(40)]
    first = select_sample(population, seed=42, high_risk_ids={"REC-38", "REC-39"})
    second = select_sample(population, seed=42, high_risk_ids={"REC-38", "REC-39"})
    assert first == second
    assert set(("REC-38", "REC-39")).issubset(first.selected_ids)
    assert len(first.selected_ids) == 12


def test_evidence_path_must_remain_inside_workspace(tmp_path: Path) -> None:
    with pytest.raises(PathOutsideWorkspaceError):
        resolve_within(tmp_path, "../outside.json")


def test_evidence_hash_is_verified(tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text('{"result":"denied"}', encoding="utf-8")
    digest = sha256_file(artifact)

    record = Evidence(
        schema_version="1.0",
        id="EVID-S01-RETEST",
        path="evidence.json",
        sha256=digest,
        size=artifact.stat().st_size,
        media_type="application/json",
        collector="cyber_assess",
        collected_at="2026-09-25T14:00:00Z",
        source_period="2026-09-25T14:00:00Z/2026-09-25T14:01:00Z",
        run_id="RUN-S01-RETEST",
        provenance="observed_lab",
        sensitivity="sanitized",
        query_or_action="Attempt login and reuse the baseline session after deactivation",
        tool_version="0.1.0",
    )
    assert record.sha256 == digest


def test_unknown_schema_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            schema_version="2.0",
            id="EVID-001",
            path="evidence.json",
            sha256="0" * 64,
            size=0,
            media_type="application/json",
            collector="test",
            collected_at="2026-09-25T14:00:00Z",
            source_period="2026-09-25T14:00:00Z/2026-09-25T14:01:00Z",
            run_id="RUN-001",
            provenance="synthetic_record",
            sensitivity="sanitized",
            query_or_action="test",
            tool_version="test",
        )


def _open_finding() -> Finding:
    return Finding(
        schema_version="1.0",
        id="FIND-S01-001",
        title="Terminated identity retained portal access",
        service_ids=["example-bank-portal"],
        control_ids=["IAM-02"],
        criteria_reference="POL-02",
        condition="A terminated staff identity could authenticate and reuse a session.",
        evidence_ids=["EVID-S01-BASELINE"],
        cause="Scenario injection retained account state and session validity.",
        cause_status="confirmed",
        consequence="Unauthorized access to synthetic service requests remained possible.",
        likelihood=5,
        impact=4,
        rating=20,
        rating_rationale="Directly reproducible access with significant service exposure.",
        recommendation="Deactivate the account and revoke every active session atomically.",
        alternatives_tradeoff=(
            "Shorter session expiry reduces exposure but does not remove login access."
        ),
        owner_role="simulated_system_administrator",
        effort="small",
        target_date="2026-10-09",
        status="open",
        limitations="Local simulation; no enterprise directory was assessed.",
        created_at="2026-09-25T14:10:00Z",
    )


def test_finding_cannot_close_without_fresh_accepted_retest() -> None:
    with pytest.raises(InvalidTransitionError, match="accepted fresh retest"):
        transition_finding(_open_finding(), "closed_verified", retest=None)


def test_failed_retest_returns_finding_to_in_progress() -> None:
    finding = _open_finding().model_copy(update={"status": "ready_for_retest"})
    retest = Retest(
        schema_version="1.0",
        id="RETEST-S01-001",
        finding_id=finding.id,
        action_id="ACT-S01-001",
        test_run_id="RUN-S01-RETEST",
        evidence_ids=["EVID-S01-RETEST"],
        closure_criteria=["New login and the baseline session are both denied."],
        executed_at="2026-09-25T15:00:00Z",
        fresh_evidence=True,
        result="failed",
        decision="reopen",
        limitations="Local simulation.",
    )
    transitioned = transition_finding(finding, "closed_verified", retest=retest)
    assert transitioned.status == "in_progress"
