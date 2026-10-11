"""Distinguish structural validation from completion of the agreed release criteria."""

from __future__ import annotations

from pathlib import Path

from cyber_assess.models import (
    AcceptanceResult,
    BlockerRegister,
    FrameworkMapping,
    MappingRegister,
    MappingSource,
    ReviewDecision,
    Workpaper,
)
from cyber_assess.validation import validate_assessment
from cyber_assess.yamlio import load_model, load_models


def release_readiness(workspace: Path, engagement_id: str) -> dict[str, object]:
    validation = validate_assessment(workspace, engagement_id)
    problems = list(validation.errors)
    if validation.valid:
        assessment = workspace / "assessment"
        workpapers = load_models(assessment / "workpapers", Workpaper)
        incomplete = sorted(
            item.control_id
            for item in workpapers
            if item.design_status == "not_assessed" or item.operating_status == "not_tested"
        )
        if len({item.control_id for item in workpapers}) != 20:
            problems.append("Exactly twenty controls must have workpapers before final release.")
        if incomplete:
            problems.append("Control conclusions remain incomplete: " + ", ".join(incomplete))
        for result in load_models(assessment / "acceptance", AcceptanceResult):
            if result.status != "passed":
                problems.append(f"{result.id}: {result.status}")
        blockers = load_model(assessment / "governance/blockers.yaml", BlockerRegister)
        problems.extend(f"{item.id}: open" for item in blockers.blockers if item.status == "open")
        mappings = load_model(assessment / "mappings.yaml", MappingRegister)
        references: list[MappingSource | FrameworkMapping] = [*mappings.sources, *mappings.mappings]
        problems.extend(
            f"{item.id}: reference unverified"
            for item in references
            if item.verification_status != "verified_reference"
        )
        reviews = load_models(assessment / "reviews", ReviewDecision)
        if not any(
            item.review_type == "owner_self_review" and item.status == "resolved"
            for item in reviews
        ):
            problems.append("Project-owner substantive self-review has not been recorded.")
        problems.extend(f"{item.id}: review open" for item in reviews if item.status == "open")
    return {"ready": not problems, "structurally_valid": validation.valid, "blockers": problems}
