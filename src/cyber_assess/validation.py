"""Cross-record validation for assessment and finding chains."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cyber_assess.errors import AssessmentError, InvalidInputError
from cyber_assess.integrity import verify_file
from cyber_assess.models import (
    AcceptanceResult,
    Action,
    AssetRegister,
    BlockerRegister,
    Control,
    Engagement,
    Evidence,
    EvidenceRequestRegister,
    Finding,
    MappingRegister,
    MilestoneRegister,
    Retest,
    ReviewDecision,
    RiskRegister,
    Workpaper,
)
from cyber_assess.workflow import transition_finding
from cyber_assess.yamlio import load_model, load_models, load_yaml


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    validated_ids: tuple[str, ...] = ()


def _engagement(workspace: Path, engagement_id: str) -> Engagement:
    engagement = load_model(workspace / "assessment" / "engagement.yaml", Engagement)
    if engagement.id != engagement_id:
        raise InvalidInputError(
            f"engagement ID mismatch: requested {engagement_id}, found {engagement.id}"
        )
    return engagement


def _load_controls(path: Path) -> list[Control]:
    if not path.exists():
        return []
    raw = load_yaml(path)
    if not isinstance(raw, dict) or not isinstance(raw.get("controls"), list):
        raise InvalidInputError("controls.yaml must contain a controls list")
    controls = [Control.model_validate(item) for item in raw["controls"]]
    if len({control.id for control in controls}) != len(controls):
        raise InvalidInputError("control IDs must be unique")
    return controls


def validate_assessment(workspace: Path, engagement_id: str) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    validated: list[str] = []
    try:
        engagement = _engagement(workspace, engagement_id)
        validated.append(engagement.id)
        controls = _load_controls(workspace / "assessment" / "controls.yaml")
        validated.extend(control.id for control in controls)
        evidence = load_models(workspace / "assessment" / "evidence", Evidence)
        evidence_by_id = {item.id: item for item in evidence}
        validated.extend(evidence_by_id)
        for record in evidence:
            verify_file(workspace, record.path, record.sha256, record.size)
            if record.parent_evidence_id and record.parent_evidence_id not in evidence_by_id:
                errors.append(f"{record.id}: missing parent evidence {record.parent_evidence_id}")
        control_ids = {control.id for control in controls}
        for workpaper in load_models(workspace / "assessment" / "workpapers", Workpaper):
            validated.append(workpaper.id)
            if controls and workpaper.control_id not in control_ids:
                errors.append(f"{workpaper.id}: unknown control {workpaper.control_id}")
            missing = set(workpaper.evidence_ids).difference(evidence_by_id)
            if missing:
                errors.append(f"{workpaper.id}: missing evidence {sorted(missing)}")
        finding_result = _validate_finding_records(workspace, evidence_by_id)
        errors.extend(finding_result.errors)
        warnings.extend(finding_result.warnings)
        validated.extend(finding_result.validated_ids)
        governance_paths = (
            workspace / "assessment" / "governance",
            workspace / "assessment" / "mappings.yaml",
            workspace / "assessment" / "reviews",
            workspace / "assessment" / "acceptance",
        )
        if any(path.exists() for path in governance_paths):
            governance_result = _validate_governance_records(
                workspace,
                engagement,
                controls,
                evidence_by_id,
            )
            errors.extend(governance_result.errors)
            warnings.extend(governance_result.warnings)
            validated.extend(governance_result.validated_ids)
    except (AssessmentError, FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))
    return ValidationResult(
        not errors, tuple(errors), tuple(warnings), tuple(dict.fromkeys(validated))
    )


def validate_findings(workspace: Path, engagement_id: str) -> ValidationResult:
    errors: list[str] = []
    validated: list[str] = []
    try:
        _engagement(workspace, engagement_id)
        evidence = load_models(workspace / "assessment" / "evidence", Evidence)
        result = _validate_finding_records(workspace, {item.id: item for item in evidence})
        errors.extend(result.errors)
        validated.extend(result.validated_ids)
    except (AssessmentError, FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))
    return ValidationResult(not errors, tuple(errors), validated_ids=tuple(validated))


def validate_governance(workspace: Path, engagement_id: str) -> ValidationResult:
    """Validate governance registers and their cross-record references."""

    try:
        engagement = _engagement(workspace, engagement_id)
        controls = _load_controls(workspace / "assessment" / "controls.yaml")
        evidence = load_models(workspace / "assessment" / "evidence", Evidence)
        return _validate_governance_records(
            workspace,
            engagement,
            controls,
            {item.id: item for item in evidence},
        )
    except (AssessmentError, FileNotFoundError, ValueError) as exc:
        return ValidationResult(False, (str(exc),))


def _duplicates(values: list[str]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


def _validate_governance_records(
    workspace: Path,
    engagement: Engagement,
    controls: list[Control],
    evidence_by_id: dict[str, Evidence],
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    validated: list[str] = []
    governance = workspace / "assessment" / "governance"
    try:
        assets = load_model(governance / "assets.yaml", AssetRegister)
        risks = load_model(governance / "risks.yaml", RiskRegister)
        requests = load_model(
            governance / "evidence_requests.yaml",
            EvidenceRequestRegister,
        )
        milestones = load_model(governance / "milestones.yaml", MilestoneRegister)
        blockers = load_model(governance / "blockers.yaml", BlockerRegister)
        mappings = load_model(workspace / "assessment" / "mappings.yaml", MappingRegister)
        reviews = load_models(workspace / "assessment" / "reviews", ReviewDecision)
        acceptance = load_models(
            workspace / "assessment" / "acceptance",
            AcceptanceResult,
        )

        asset_ids = {item.id for item in assets.assets}
        control_ids = {item.id for item in controls}
        evidence_ids = set(evidence_by_id)
        blocker_ids = {item.id for item in blockers.blockers}
        source_ids = {item.id for item in mappings.sources}

        for label, ids in (
            ("asset", [item.id for item in assets.assets]),
            ("data flow", [item.id for item in assets.data_flows]),
            ("risk", [item.id for item in risks.risks]),
            ("evidence request", [item.id for item in requests.requests]),
            ("milestone", [item.id for item in milestones.milestones]),
            ("blocker", [item.id for item in blockers.blockers]),
            ("mapping source", [item.id for item in mappings.sources]),
            ("mapping", [item.id for item in mappings.mappings]),
        ):
            duplicates = _duplicates(ids)
            if duplicates:
                errors.append(f"duplicate {label} IDs: {duplicates}")

        missing_engagement_assets = set(engagement.asset_ids).difference(asset_ids)
        if missing_engagement_assets:
            errors.append(
                f"engagement references missing assets: {sorted(missing_engagement_assets)}"
            )

        for risk in risks.risks:
            if missing := set(risk.asset_ids).difference(asset_ids):
                errors.append(f"{risk.id}: missing assets {sorted(missing)}")
            if missing := set(risk.control_ids).difference(control_ids):
                errors.append(f"{risk.id}: missing controls {sorted(missing)}")
            if missing := set(risk.evidence_ids).difference(evidence_ids):
                errors.append(f"{risk.id}: missing evidence {sorted(missing)}")

        for mapping in mappings.mappings:
            if mapping.source_id not in source_ids:
                errors.append(f"{mapping.id}: missing source {mapping.source_id}")
            if missing := set(mapping.control_ids).difference(control_ids):
                errors.append(f"{mapping.id}: missing controls {sorted(missing)}")
            if missing := set(mapping.evidence_ids).difference(evidence_ids):
                errors.append(f"{mapping.id}: missing evidence {sorted(missing)}")

        nist_controls = {
            control_id
            for mapping in mappings.mappings
            if mapping.source_id == "SRC-NIST-CSF-2"
            for control_id in mapping.control_ids
        }
        if nist_controls != control_ids:
            errors.append(
                "NIST mappings do not cover every control: "
                f"missing {sorted(control_ids.difference(nist_controls))}"
            )

        for request in requests.requests:
            if missing := set(request.response_evidence_ids).difference(evidence_ids):
                errors.append(f"{request.id}: missing response evidence {sorted(missing)}")
            if request.blocker_id and request.blocker_id not in blocker_ids:
                errors.append(f"{request.id}: missing blocker {request.blocker_id}")

        for milestone in milestones.milestones:
            if missing := set(milestone.blocker_ids).difference(blocker_ids):
                errors.append(f"{milestone.id}: missing blockers {sorted(missing)}")

        expected_acceptance_ids = {f"AT-{number:02d}" for number in range(1, 21)}
        acceptance_ids = {item.id for item in acceptance}
        if acceptance_ids != expected_acceptance_ids:
            errors.append(
                "acceptance register must contain AT-01 through AT-20: "
                f"missing {sorted(expected_acceptance_ids.difference(acceptance_ids))}"
            )
        for result in acceptance:
            if missing := set(result.evidence_ids).difference(evidence_ids):
                errors.append(f"{result.id}: missing evidence {sorted(missing)}")

        validated.extend(item.id for item in assets.assets)
        validated.extend(item.id for item in assets.data_flows)
        validated.extend(item.id for item in risks.risks)
        validated.extend(item.id for item in requests.requests)
        validated.extend(item.id for item in milestones.milestones)
        validated.extend(item.id for item in blockers.blockers)
        validated.extend(item.id for item in mappings.sources)
        validated.extend(item.id for item in mappings.mappings)
        validated.extend(item.id for item in reviews)
        validated.extend(item.id for item in acceptance)
        if not reviews:
            warnings.append("no review-decision records exist")
    except (AssessmentError, FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))
    return ValidationResult(
        not errors,
        tuple(errors),
        tuple(warnings),
        tuple(dict.fromkeys(validated)),
    )


def _validate_finding_records(
    workspace: Path, evidence_by_id: dict[str, Evidence]
) -> ValidationResult:
    errors: list[str] = []
    validated: list[str] = []
    findings = load_models(workspace / "assessment" / "findings", Finding)
    actions = load_models(workspace / "assessment" / "actions", Action)
    retests = load_models(workspace / "assessment" / "retests", Retest)
    finding_by_id = {item.id: item for item in findings}
    action_by_id = {item.id: item for item in actions}
    retest_by_finding = {item.finding_id: item for item in retests}
    validated.extend(item.id for item in findings + actions + retests)
    for finding in findings:
        missing_evidence = set(finding.evidence_ids).difference(evidence_by_id)
        if missing_evidence:
            errors.append(f"{finding.id}: missing evidence {sorted(missing_evidence)}")
        if finding.status == "duplicate" and finding.duplicate_of not in finding_by_id:
            errors.append(f"{finding.id}: surviving duplicate target does not exist")
        if finding.status == "closed_verified":
            retest = retest_by_finding.get(finding.id)
            if retest is None:
                errors.append(f"{finding.id}: closed finding has no retest")
                continue
            action = action_by_id.get(retest.action_id)
            if action is None or action.finding_id != finding.id:
                errors.append(f"{finding.id}: retest action is missing or belongs elsewhere")
                continue
            missing_retest_evidence = set(retest.evidence_ids).difference(evidence_by_id)
            if missing_retest_evidence:
                errors.append(
                    f"{retest.id}: missing fresh evidence {sorted(missing_retest_evidence)}"
                )
            if action.implemented_at is None or retest.executed_at <= action.implemented_at:
                errors.append(f"{retest.id}: retest must occur after implementation")
            try:
                transition_finding(
                    finding.model_copy(update={"status": "ready_for_retest", "closed_at": None}),
                    "closed_verified",
                    retest=retest,
                    at=finding.closed_at,
                )
            except ValueError as exc:
                errors.append(f"{finding.id}: {exc}")
    return ValidationResult(not errors, tuple(errors), validated_ids=tuple(validated))
