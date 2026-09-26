"""Strict Pydantic contracts for the canonical assessment records."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0"
SchemaVersion = Literal["1.0"]
RecordId = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_-]{2,63}$")]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class StrictRecord(BaseModel):
    """Common record behavior: explicit versions and no silent field drift."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    schema_version: SchemaVersion


class AssessmentPeriod(StrictRecord):
    start: date
    end: date

    @model_validator(mode="after")
    def valid_order(self) -> AssessmentPeriod:
        if self.end < self.start:
            raise ValueError("assessment period end must not precede start")
        return self


class Engagement(StrictRecord):
    id: RecordId
    version: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    business_context: Annotated[str, Field(min_length=1)]
    scope: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    exclusions: list[str]
    assessment_period: AssessmentPeriod
    asset_ids: list[RecordId] = Field(min_length=1)
    policy_ids: list[RecordId] = Field(min_length=1)
    criteria_source_ids: list[RecordId] = Field(min_length=1)
    owner_role: Annotated[str, Field(min_length=1)]
    review_mode: Literal["self_reviewed", "external_reviewed"]
    created_at: datetime


class Control(StrictRecord):
    id: RecordId
    version: Annotated[str, Field(min_length=1)]
    domain: Literal["governance", "access", "change", "operations", "incident", "recovery"]
    objective: Annotated[str, Field(min_length=1)]
    risk_ids: list[RecordId] = Field(min_length=1)
    owner_role: Annotated[str, Field(min_length=1)]
    frequency: Annotated[str, Field(min_length=1)]
    procedure: Annotated[str, Field(min_length=1)]
    criteria_references: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    nist_categories: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)


class Evidence(StrictRecord):
    id: RecordId
    path: Annotated[str, Field(min_length=1)]
    sha256: Sha256
    size: Annotated[int, Field(ge=0)]
    media_type: Annotated[str, Field(min_length=1)]
    collector: Annotated[str, Field(min_length=1)]
    collected_at: datetime
    source_period: Annotated[str, Field(min_length=1)]
    run_id: RecordId
    provenance: Literal["observed_lab", "synthetic_record", "authored_policy", "external_reference"]
    sensitivity: Literal["sanitized", "internal", "restricted"]
    parent_evidence_id: RecordId | None = None
    query_or_action: Annotated[str, Field(min_length=1)]
    tool_version: Annotated[str, Field(min_length=1)]
    redactions: list[str] = Field(default_factory=list)


DesignStatus = Literal[
    "adequate", "partially_adequate", "inadequate", "not_assessed", "not_applicable"
]
OperatingStatus = Literal[
    "effective_in_tested_scope",
    "exceptions_identified",
    "not_operated",
    "insufficient_evidence",
    "not_tested",
    "not_applicable",
]


class Workpaper(StrictRecord):
    id: RecordId
    control_id: RecordId
    control_version: Annotated[str, Field(min_length=1)]
    risk_ids: list[RecordId] = Field(min_length=1)
    criteria: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    procedure_version: Annotated[str, Field(min_length=1)]
    test_type: Literal["inspection", "reperformance", "inquiry", "walkthrough", "combined"]
    test_period: Annotated[str, Field(min_length=1)]
    population_source: Annotated[str, Field(min_length=1)]
    population_hash: Sha256
    population_count: Annotated[int, Field(ge=0)]
    population_query: Annotated[str, Field(min_length=1)]
    selected_record_ids: list[str]
    selection_rationale: Annotated[str, Field(min_length=1)]
    sample_seed: int | None = None
    exclusions: list[str]
    expected_behavior: Annotated[str, Field(min_length=1)]
    actual_results: Annotated[str, Field(min_length=1)]
    evidence_ids: list[RecordId]
    exceptions: list[str]
    limitations: list[str]
    design_status: DesignStatus
    operating_status: OperatingStatus
    assessor_decision: Annotated[str, Field(min_length=1)]
    preparer: Annotated[str, Field(min_length=1)]
    review_mode: Literal["self_reviewed", "external_reviewed"]
    review_comments: list[str]
    prepared_at: datetime
    reviewed_at: datetime

    @model_validator(mode="after")
    def effective_requires_evidence(self) -> Workpaper:
        if self.operating_status == "effective_in_tested_scope" and not self.evidence_ids:
            raise ValueError("effective operating conclusion requires evidence")
        if self.reviewed_at < self.prepared_at:
            raise ValueError("review timestamp cannot precede preparation")
        return self


FindingStatus = Literal[
    "draft",
    "reviewed",
    "open",
    "in_progress",
    "ready_for_retest",
    "closed_verified",
    "risk_accepted",
    "duplicate",
]


class Finding(StrictRecord):
    id: RecordId
    title: Annotated[str, Field(min_length=1)]
    service_ids: list[str] = Field(min_length=1)
    control_ids: list[RecordId] = Field(min_length=1)
    criteria_reference: Annotated[str, Field(min_length=1)]
    condition: Annotated[str, Field(min_length=1)]
    evidence_ids: list[RecordId] = Field(min_length=1)
    cause: Annotated[str, Field(min_length=1)]
    cause_status: Literal["confirmed", "hypothesis", "unknown"]
    consequence: Annotated[str, Field(min_length=1)]
    likelihood: Annotated[int, Field(ge=1, le=5)]
    impact: Annotated[int, Field(ge=1, le=5)]
    rating: Annotated[int, Field(ge=1, le=25)]
    rating_rationale: Annotated[str, Field(min_length=1)]
    recommendation: Annotated[str, Field(min_length=1)]
    alternatives_tradeoff: Annotated[str, Field(min_length=1)]
    owner_role: Annotated[str, Field(min_length=1)]
    effort: Literal["small", "medium", "large"]
    target_date: date
    status: FindingStatus
    limitations: Annotated[str, Field(min_length=1)]
    duplicate_of: RecordId | None = None
    created_at: datetime
    closed_at: datetime | None = None

    @model_validator(mode="after")
    def consistent_rating_and_disposition(self) -> Finding:
        if self.rating != self.likelihood * self.impact:
            raise ValueError("rating must equal likelihood multiplied by impact")
        if self.status == "duplicate" and not self.duplicate_of:
            raise ValueError("duplicate disposition requires a surviving finding ID")
        if self.status != "duplicate" and self.duplicate_of:
            raise ValueError("duplicate_of is only valid for duplicate findings")
        return self


class Action(StrictRecord):
    id: RecordId
    finding_id: RecordId
    owner_role: Annotated[str, Field(min_length=1)]
    target_date: date
    status: Literal["planned", "in_progress", "implemented", "blocked"]
    fix_reference: Annotated[str, Field(min_length=1)]
    implementation_summary: Annotated[str, Field(min_length=1)]
    closure_criteria: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    proposed_likelihood: Annotated[int, Field(ge=1, le=5)]
    proposed_impact: Annotated[int, Field(ge=1, le=5)]
    proposed_residual_risk_rationale: Annotated[str, Field(min_length=1)]
    implemented_at: datetime | None = None

    @model_validator(mode="after")
    def implemented_has_timestamp(self) -> Action:
        if self.status == "implemented" and self.implemented_at is None:
            raise ValueError("implemented action requires implemented_at")
        return self


class Retest(StrictRecord):
    id: RecordId
    finding_id: RecordId
    action_id: RecordId
    test_run_id: RecordId
    evidence_ids: list[RecordId] = Field(min_length=1)
    closure_criteria: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    executed_at: datetime
    fresh_evidence: bool
    result: Literal["passed", "failed"]
    decision: Literal["accept_closure", "reopen"]
    limitations: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def decision_matches_result(self) -> Retest:
        expected = "accept_closure" if self.result == "passed" else "reopen"
        if self.decision != expected:
            raise ValueError("retest decision must match result")
        if self.result == "passed" and not self.fresh_evidence:
            raise ValueError("passed retest requires fresh evidence")
        return self


class SnapshotSource(StrictRecord):
    path: str
    sha256: Sha256
    size: Annotated[int, Field(ge=0)]


class ExportSnapshot(StrictRecord):
    id: RecordId
    engagement_id: RecordId
    generator_version: str
    created_at: datetime
    source_hashes: list[SnapshotSource] = Field(min_length=1)
    baseline_ids: list[RecordId]
    retest_ids: list[RecordId]
