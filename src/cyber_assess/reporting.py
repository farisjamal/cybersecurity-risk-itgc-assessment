"""Deterministic, reconciled inputs for the portfolio deliverables.

The generator intentionally emits a narrow projection of canonical records. It
does not copy evidence payloads, evidence paths, queries, backup files, secrets,
or unrestricted narrative fields into the reporting layer.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath

from pydantic import BaseModel

from cyber_assess.errors import InvalidInputError
from cyber_assess.models import (
    Action,
    Control,
    Engagement,
    Evidence,
    ExportSnapshot,
    Finding,
    Retest,
    Workpaper,
)
from cyber_assess.snapshots import load_snapshot, verify_snapshot
from cyber_assess.yamlio import load_model, load_yaml

_OUTPUT_NAMES = (
    "claims-evidence-index.json",
    "executive-report-input.md",
    "presentation-input.md",
    "reconciliation.json",
    "remediation-roadmap-input.json",
    "workbook-input.json",
)


@dataclass(frozen=True)
class _FrozenRecords:
    engagement: Engagement
    controls: tuple[Control, ...]
    evidence: tuple[Evidence, ...]
    workpapers: tuple[Workpaper, ...]
    findings: tuple[Finding, ...]
    actions: tuple[Action, ...]
    retests: tuple[Retest, ...]


def _json_text(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _iso(value: date | datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _snapshot_record_paths(snapshot: ExportSnapshot, directory: str) -> list[str]:
    expected_parent = PurePosixPath("assessment") / directory
    paths: list[str] = []
    for source in snapshot.source_hashes:
        path = PurePosixPath(source.path)
        if path.parent == expected_parent and path.suffix == ".yaml":
            paths.append(source.path)
    return sorted(paths)


def _load_frozen_models[ModelT: BaseModel](
    workspace: Path,
    snapshot: ExportSnapshot,
    directory: str,
    model: type[ModelT],
) -> tuple[ModelT, ...]:
    records = tuple(
        load_model(workspace / path, model) for path in _snapshot_record_paths(snapshot, directory)
    )
    ids = [getattr(record, "id", None) for record in records]
    if len(ids) != len(set(ids)):
        raise InvalidInputError(f"duplicate {directory} IDs in snapshot")
    return records


def _load_frozen_records(workspace: Path, snapshot: ExportSnapshot) -> _FrozenRecords:
    frozen_paths = {source.path for source in snapshot.source_hashes}
    engagement_path = "assessment/engagement.yaml"
    controls_path = "assessment/controls.yaml"
    if engagement_path not in frozen_paths or controls_path not in frozen_paths:
        raise InvalidInputError("snapshot omits the engagement or control register")

    engagement = load_model(workspace / engagement_path, Engagement)
    raw_controls = load_yaml(workspace / controls_path)
    if not isinstance(raw_controls, dict) or not isinstance(raw_controls.get("controls"), list):
        raise InvalidInputError("controls.yaml must contain a controls list")
    controls = tuple(Control.model_validate(item) for item in raw_controls["controls"])
    if len({item.id for item in controls}) != len(controls):
        raise InvalidInputError("control IDs must be unique")

    return _FrozenRecords(
        engagement=engagement,
        controls=controls,
        evidence=_load_frozen_models(workspace, snapshot, "evidence", Evidence),
        workpapers=_load_frozen_models(workspace, snapshot, "workpapers", Workpaper),
        findings=_load_frozen_models(workspace, snapshot, "findings", Finding),
        actions=_load_frozen_models(workspace, snapshot, "actions", Action),
        retests=_load_frozen_models(workspace, snapshot, "retests", Retest),
    )


def _require_subset(label: str, referenced: set[str], available: set[str]) -> None:
    missing = sorted(referenced.difference(available))
    if missing:
        raise InvalidInputError(f"{label} reference missing frozen records: {missing}")


def _reconcile(snapshot: ExportSnapshot, records: _FrozenRecords) -> dict[str, object]:
    if records.engagement.id != snapshot.engagement_id:
        raise InvalidInputError("snapshot engagement does not match frozen engagement")

    control_ids = {item.id for item in records.controls}
    evidence_ids = {item.id for item in records.evidence}
    finding_ids = {item.id for item in records.findings}
    action_ids = {item.id for item in records.actions}

    if sorted(snapshot.baseline_ids) != sorted(finding_ids):
        raise InvalidInputError("snapshot baseline IDs do not match frozen findings")
    if sorted(snapshot.retest_ids) != sorted(item.id for item in records.retests):
        raise InvalidInputError("snapshot retest IDs do not match frozen retests")

    _require_subset(
        "workpaper control",
        {item.control_id for item in records.workpapers},
        control_ids,
    )
    _require_subset(
        "finding control",
        {control_id for item in records.findings for control_id in item.control_ids},
        control_ids,
    )
    _require_subset(
        "workpaper evidence",
        {evidence_id for item in records.workpapers for evidence_id in item.evidence_ids},
        evidence_ids,
    )
    _require_subset(
        "finding evidence",
        {evidence_id for item in records.findings for evidence_id in item.evidence_ids},
        evidence_ids,
    )
    _require_subset(
        "retest evidence",
        {evidence_id for item in records.retests for evidence_id in item.evidence_ids},
        evidence_ids,
    )
    _require_subset(
        "action finding",
        {item.finding_id for item in records.actions},
        finding_ids,
    )
    _require_subset(
        "retest finding",
        {item.finding_id for item in records.retests},
        finding_ids,
    )
    _require_subset(
        "retest action",
        {item.action_id for item in records.retests},
        action_ids,
    )
    action_finding = {item.id: item.finding_id for item in records.actions}
    mismatched_retests = sorted(
        item.id for item in records.retests if action_finding[item.action_id] != item.finding_id
    )
    if mismatched_retests:
        raise InvalidInputError(
            f"retests and actions refer to different findings: {mismatched_retests}"
        )

    workpaper_controls = {item.control_id for item in records.workpapers}
    assessed_controls = {
        item.control_id
        for item in records.workpapers
        if item.design_status != "not_assessed" and item.operating_status != "not_tested"
    }
    return {
        "schema_version": "1.0",
        "snapshot_id": snapshot.id,
        "engagement_id": snapshot.engagement_id,
        "frozen_at": _iso(snapshot.created_at),
        "record_counts": {
            "actions": len(records.actions),
            "controls": len(records.controls),
            "evidence": len(records.evidence),
            "findings": len(records.findings),
            "retests": len(records.retests),
            "workpapers": len(records.workpapers),
        },
        "relationship_counts": {
            "finding_evidence_links": sum(len(item.evidence_ids) for item in records.findings),
            "retest_evidence_links": sum(len(item.evidence_ids) for item in records.retests),
            "workpaper_evidence_links": sum(len(item.evidence_ids) for item in records.workpapers),
        },
        "control_coverage": {
            "workpapers_present": len(workpaper_controls),
            "workpapers_missing": len(records.controls) - len(workpaper_controls),
            "assessed": len(assessed_controls),
            "total": len(records.controls),
            "unassessed": len(records.controls) - len(assessed_controls),
            "state": (
                "complete_within_declared_scope"
                if len(assessed_controls) == len(records.controls)
                else "partial"
            ),
        },
        "snapshot_alignment": {
            "baseline_ids_match": True,
            "retest_ids_match": True,
            "unmatched_references": 0,
        },
    }


def _limitations(records: _FrozenRecords, snapshot: ExportSnapshot) -> list[str]:
    workpapers_present = len({item.control_id for item in records.workpapers})
    assessed = len(
        {
            item.control_id
            for item in records.workpapers
            if item.design_status != "not_assessed" and item.operating_status != "not_tested"
        }
    )
    return [
        "This is synthetic, local-lab material and is not evidence from a real institution.",
        (
            "The assessment is self-reviewed and is not an independent audit, "
            "certification, or assurance opinion."
        ),
        (
            f"{workpapers_present} of {len(records.controls)} registered controls have frozen "
            f"workpapers; {assessed} have executed assessment conclusions in this snapshot."
        ),
        (
            "Evidence payloads, filesystem paths, queries, secrets, and backup "
            "contents are intentionally excluded."
        ),
        (
            "PDF artifacts, when present, are local derivatives with a separate render manifest "
            "and require visual review before distribution."
        ),
        f"All results are frozen to snapshot {snapshot.id} at {_iso(snapshot.created_at)}.",
    ]


def _workbook_input(
    snapshot: ExportSnapshot,
    records: _FrozenRecords,
    reconciliation: dict[str, object],
    limitations: list[str],
) -> dict[str, object]:
    workpaper_by_control = {item.control_id: item for item in records.workpapers}
    findings_by_control: dict[str, list[Finding]] = {}
    for finding in records.findings:
        for control_id in finding.control_ids:
            findings_by_control.setdefault(control_id, []).append(finding)
    controls: list[dict[str, object]] = []
    for control in sorted(records.controls, key=lambda item: item.id):
        workpaper = workpaper_by_control.get(control.id)
        controls.append(
            {
                "control_id": control.id,
                "domain": control.domain,
                "risk_ids": sorted(control.risk_ids),
                "criteria_references": sorted(control.criteria_references),
                "nist_categories": sorted(control.nist_categories),
                "has_frozen_workpaper": workpaper is not None,
                "workpaper_id": workpaper.id if workpaper else None,
                "design_status": workpaper.design_status if workpaper else "not_assessed",
                "operating_status": workpaper.operating_status if workpaper else "not_tested",
                "finding_ids": sorted(item.id for item in findings_by_control.get(control.id, [])),
            }
        )
    return {
        "schema_version": "1.0",
        "snapshot_id": snapshot.id,
        "engagement_id": snapshot.engagement_id,
        "title": records.engagement.name,
        "review_mode": records.engagement.review_mode,
        "reconciliation": reconciliation,
        "controls": controls,
        "limitations": limitations,
    }


def _roadmap_input(
    snapshot: ExportSnapshot, records: _FrozenRecords, limitations: list[str]
) -> dict[str, object]:
    actions_by_finding: dict[str, list[Action]] = {}
    retests_by_finding: dict[str, list[Retest]] = {}
    for action in records.actions:
        actions_by_finding.setdefault(action.finding_id, []).append(action)
    for retest in records.retests:
        retests_by_finding.setdefault(retest.finding_id, []).append(retest)
    items: list[dict[str, object]] = []
    for finding in sorted(records.findings, key=lambda item: item.id):
        items.append(
            {
                "finding_id": finding.id,
                "control_ids": sorted(finding.control_ids),
                "risk_rating": finding.rating,
                "finding_status": finding.status,
                "owner_role": finding.owner_role,
                "effort": finding.effort,
                "target_date": finding.target_date.isoformat(),
                "actions": [
                    {
                        "action_id": action.id,
                        "status": action.status,
                        "owner_role": action.owner_role,
                        "target_date": action.target_date.isoformat(),
                        "closure_criteria_count": len(action.closure_criteria),
                    }
                    for action in sorted(
                        actions_by_finding.get(finding.id, []), key=lambda item: item.id
                    )
                ],
                "retests": [
                    {
                        "retest_id": retest.id,
                        "action_id": retest.action_id,
                        "result": retest.result,
                        "decision": retest.decision,
                        "fresh_evidence": retest.fresh_evidence,
                        "executed_at": _iso(retest.executed_at),
                    }
                    for retest in sorted(
                        retests_by_finding.get(finding.id, []), key=lambda item: item.id
                    )
                ],
            }
        )
    return {
        "schema_version": "1.0",
        "snapshot_id": snapshot.id,
        "engagement_id": snapshot.engagement_id,
        "items": items,
        "limitations": limitations,
    }


def _claims_evidence_index(
    snapshot: ExportSnapshot, records: _FrozenRecords, limitations: list[str]
) -> dict[str, object]:
    evidence_by_id = {item.id: item for item in records.evidence}
    claims: list[dict[str, object]] = []
    allowed_evidence_ids: set[str] = set()
    for workpaper in sorted(records.workpapers, key=lambda item: item.id):
        sanitized_ids = sorted(
            evidence_id
            for evidence_id in workpaper.evidence_ids
            if evidence_by_id[evidence_id].sensitivity == "sanitized"
        )
        allowed_evidence_ids.update(sanitized_ids)
        claims.append(
            {
                "claim_id": f"CLAIM-{workpaper.id}",
                "control_id": workpaper.control_id,
                "workpaper_id": workpaper.id,
                "claim": (
                    f"Control {workpaper.control_id} was assessed as "
                    f"{workpaper.design_status} for design and "
                    f"{workpaper.operating_status} for operation within the tested scope."
                ),
                "sanitized_evidence_ids": sanitized_ids,
                "withheld_evidence_count": len(workpaper.evidence_ids) - len(sanitized_ids),
                "review_mode": workpaper.review_mode,
            }
        )
    evidence = [
        {
            "evidence_id": item.id,
            "media_type": item.media_type,
            "provenance": item.provenance,
            "collected_at": _iso(item.collected_at),
            "classification": "sanitized",
        }
        for item in sorted(records.evidence, key=lambda item: item.id)
        if item.id in allowed_evidence_ids and item.sensitivity == "sanitized"
    ]
    return {
        "schema_version": "1.0",
        "snapshot_id": snapshot.id,
        "engagement_id": snapshot.engagement_id,
        "claims": claims,
        "evidence": evidence,
        "limitations": limitations,
    }


def _executive_markdown(
    snapshot: ExportSnapshot,
    records: _FrozenRecords,
    reconciliation: dict[str, object],
    limitations: list[str],
) -> str:
    coverage = reconciliation["control_coverage"]
    assert isinstance(coverage, dict)
    lines = [
        f"# Executive report input: {records.engagement.name}",
        "",
        f"- Snapshot: `{snapshot.id}`",
        f"- Frozen at: `{_iso(snapshot.created_at)}`",
        f"- Review mode: `{records.engagement.review_mode}`",
        (
            f"- Control coverage: {coverage['assessed']} of {coverage['total']} "
            f"(`{coverage['state']}`)"
        ),
        f"- Findings: {len(records.findings)}",
        (
            "- Verified closures: "
            f"{sum(item.status == 'closed_verified' for item in records.findings)}"
        ),
        "",
        "## Finding register summary",
        "",
        "| Finding | Controls | Rating | Status | Target |",
        "| --- | --- | ---: | --- | --- |",
    ]
    lines.extend(
        f"| `{item.id}` | {', '.join(f'`{value}`' for value in sorted(item.control_ids))} "
        f"| {item.rating} | `{item.status}` | {item.target_date.isoformat()} |"
        for item in sorted(records.findings, key=lambda item: item.id)
    )
    if not records.findings:
        lines.append("| None | - | - | - | - |")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in limitations)
    return "\n".join(lines) + "\n"


def _presentation_markdown(
    snapshot: ExportSnapshot,
    records: _FrozenRecords,
    reconciliation: dict[str, object],
    limitations: list[str],
) -> str:
    coverage = reconciliation["control_coverage"]
    assert isinstance(coverage, dict)
    lines = [
        "# Presentation input",
        "",
        "## Slide 1 - Scope",
        "",
        f"- Engagement: {records.engagement.name}",
        f"- Snapshot: `{snapshot.id}`",
        f"- Review mode: `{records.engagement.review_mode}`",
        "",
        "## Slide 2 - Coverage",
        "",
        f"- Registered controls: {coverage['total']}",
        f"- Controls with frozen workpapers: {coverage['assessed']}",
        f"- Coverage state: `{coverage['state']}`",
        "",
        "## Slide 3 - Findings and remediation",
        "",
        f"- Findings: {len(records.findings)}",
        f"- Actions: {len(records.actions)}",
        f"- Retests: {len(records.retests)}",
        "",
        "## Slide 4 - Evidence chain",
        "",
        (
            "- Sanitized evidence records: "
            f"{sum(item.sensitivity == 'sanitized' for item in records.evidence)}"
        ),
        "- Payloads and paths are excluded; use the claims/evidence index for traceability.",
        "",
        "## Slide 5 - Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in limitations)
    return "\n".join(lines) + "\n"


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _manifest(snapshot: ExportSnapshot, directory: Path) -> dict[str, object]:
    artifacts: list[dict[str, object]] = []
    for name in _OUTPUT_NAMES:
        path = directory / name
        payload = path.read_bytes()
        artifacts.append(
            {
                "path": name,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
                "classification": "sanitized_reporting_input",
            }
        )
    return {
        "schema_version": "1.0",
        "snapshot_id": snapshot.id,
        "engagement_id": snapshot.engagement_id,
        "generated_at": _iso(snapshot.created_at),
        "artifacts": artifacts,
        "limitations": [
            "Manifest hashes demonstrate output integrity, not independent authenticity.",
            "The listed artifacts contain reporting inputs rather than final Office deliverables.",
        ],
    }


def create_deliverable_inputs(
    workspace: Path, snapshot_id: str, *, output_root: Path | None = None
) -> Path:
    """Create an atomic, deterministic reporting-input bundle from one snapshot."""
    workspace = workspace.resolve()
    verify_snapshot(workspace, snapshot_id)
    snapshot = load_snapshot(workspace, snapshot_id)
    records = _load_frozen_records(workspace, snapshot)
    reconciliation = _reconcile(snapshot, records)
    limitations = _limitations(records, snapshot)

    export_root = (output_root or workspace / "outputs" / "reporting").resolve()
    export_root.mkdir(parents=True, exist_ok=True)
    destination = export_root / snapshot.id
    if destination.exists():
        raise FileExistsError(f"reporting input bundle already exists: {destination}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{snapshot.id}.", dir=export_root))
    try:
        _write_text(
            temporary / "workbook-input.json",
            _json_text(_workbook_input(snapshot, records, reconciliation, limitations)),
        )
        _write_text(
            temporary / "remediation-roadmap-input.json",
            _json_text(_roadmap_input(snapshot, records, limitations)),
        )
        _write_text(
            temporary / "claims-evidence-index.json",
            _json_text(_claims_evidence_index(snapshot, records, limitations)),
        )
        _write_text(
            temporary / "reconciliation.json",
            _json_text(reconciliation),
        )
        _write_text(
            temporary / "executive-report-input.md",
            _executive_markdown(snapshot, records, reconciliation, limitations),
        )
        _write_text(
            temporary / "presentation-input.md",
            _presentation_markdown(snapshot, records, reconciliation, limitations),
        )
        _write_text(
            temporary / "reporting-manifest.json",
            _json_text(_manifest(snapshot, temporary)),
        )

        # A second verification narrows the check/read/publish race: no result is
        # published if a frozen source changed while inputs were being rendered.
        verify_snapshot(workspace, snapshot_id)
        os.replace(temporary, destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination
