"""Create a minimal, valid engagement without overwriting existing records."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from cyber_assess.models import AssessmentPeriod, Engagement
from cyber_assess.yamlio import dump_yaml


def initialize_engagement(workspace: Path, engagement_id: str) -> Path:
    assessment = workspace.resolve() / "assessment"
    destination = assessment / "engagement.yaml"
    if destination.exists():
        raise FileExistsError(f"engagement already exists: {destination}")
    for directory in (
        "evidence",
        "workpapers",
        "findings",
        "actions",
        "retests",
        "snapshots",
        "scenario_runs",
    ):
        (assessment / directory).mkdir(parents=True, exist_ok=True)
    engagement = Engagement(
        schema_version="1.0",
        id=engagement_id,
        version="1.0",
        name="Example Bank Lab assessment",
        business_context=(
            "Independent educational assessment of a fictional Malaysian financial "
            "institution's internal service-request portal."
        ),
        scope=["Example Bank Lab portal and its supporting assessment records"],
        exclusions=["Real banking infrastructure", "Independent assurance opinion"],
        assessment_period=AssessmentPeriod(
            schema_version="1.0", start=date(2026, 8, 1), end=date(2026, 8, 30)
        ),
        asset_ids=["ASSET-PORTAL"],
        policy_ids=["POL-01"],
        criteria_source_ids=["SRC-NIST-CSF-2"],
        owner_role="project_owner_assessor",
        review_mode="self_reviewed",
        created_at=datetime.now(UTC),
    )
    dump_yaml(destination, engagement)
    return destination
