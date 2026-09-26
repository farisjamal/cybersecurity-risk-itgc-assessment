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


class Asset(StrictRecord):
    id: RecordId
    asset_type: Annotated[str, Field(min_length=1)]
    owner_role: Annotated[str, Field(min_length=1)]
    business_process: Annotated[str, Field(min_length=1)]
    classification: Literal["synthetic_public", "synthetic_internal", "restricted_runtime"]
    criticality: Literal["low", "medium", "high", "critical"]
    dependencies: list[Annotated[str, Field(min_length=1)]]
    components: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    data_categories: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    verification_status: Literal["documented", "runtime_unverified", "runtime_verified"]
    limitations: list[Annotated[str, Field(min_length=1)]]


class DataFlow(StrictRecord):
    id: RecordId
    name: Annotated[str, Field(min_length=1)]
    source: Annotated[str, Field(min_length=1)]
    destination: Annotated[str, Field(min_length=1)]
    data_categories: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    purpose: Annotated[str, Field(min_length=1)]
    protection: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    trust_boundary: Annotated[str, Field(min_length=1)]
    verification_status: Literal["documented", "runtime_unverified", "runtime_verified"]
    limitations: list[Annotated[str, Field(min_length=1)]]


class AssetRegister(StrictRecord):
    assets: list[Asset] = Field(min_length=1)
    data_flows: list[DataFlow] = Field(min_length=1)


class RiskRecord(StrictRecord):
    id: RecordId
    title: Annotated[str, Field(min_length=1)]
    asset_ids: list[RecordId] = Field(min_length=1)
    control_ids: list[RecordId] = Field(min_length=1)
    scenario: Annotated[str, Field(min_length=1)]
    assessment_status: Literal["unassessed", "assessed_observed"]
    likelihood: Annotated[int, Field(ge=1, le=5)] | None = None
    impact: Annotated[int, Field(ge=1, le=5)] | None = None
    rating: Annotated[int, Field(ge=1, le=25)] | None = None
    rating_rationale: str | None = None
    evidence_ids: list[RecordId]
    status: Literal["open", "monitored", "closed_verified"]
    limitations: list[Annotated[str, Field(min_length=1)]]

    @model_validator(mode="after")
    def assessed_risk_has_consistent_rating(self) -> RiskRecord:
        rating_fields = (self.likelihood, self.impact, self.rating, self.rating_rationale)
        if self.assessment_status == "unassessed":
            if any(value is not None for value in rating_fields) or self.evidence_ids:
                raise ValueError("unassessed risk cannot claim a rating or evidence")
            return self
        likelihood = self.likelihood
        impact = self.impact
        rating = self.rating
        rationale = self.rating_rationale
        if likelihood is None or impact is None or rating is None or rationale is None:
            raise ValueError("assessed risk requires likelihood, impact, rating and rationale")
        if rating != likelihood * impact:
            raise ValueError("risk rating must equal likelihood multiplied by impact")
        if not self.evidence_ids:
            raise ValueError("assessed risk requires evidence")
        return self


class RiskRegister(StrictRecord):
    risks: list[RiskRecord] = Field(min_length=1)


VerificationStatus = Literal["verified_reference", "unverified_reference", "not_mapped"]
CoverageConclusion = Literal[
    "supported_for_tested_aspect",
    "gap_identified",
    "not_assessed",
    "not_applicable_with_rationale",
]


class MappingSource(StrictRecord):
    id: RecordId
    framework: Annotated[str, Field(min_length=1)]
    version: Annotated[str, Field(min_length=1)]
    document_date: date | None
    url: Annotated[str, Field(min_length=1)]
    retrieval_date: date
    verification_status: VerificationStatus
    local_sha256: Sha256 | None = None
    limitations: list[Annotated[str, Field(min_length=1)]]


class FrameworkMapping(StrictRecord):
    id: RecordId
    source_id: RecordId
    reference_locator: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    displayed_page: Annotated[str, Field(min_length=1)] | None = None
    summary: Annotated[str, Field(min_length=1)]
    rationale: Annotated[str, Field(min_length=1)]
    control_ids: list[RecordId] = Field(min_length=1)
    evidence_ids: list[RecordId]
    current_evidence: Annotated[str, Field(min_length=1)]
    target_practice: Annotated[str, Field(min_length=1)]
    gap: Annotated[str, Field(min_length=1)]
    priority: Literal["low", "medium", "high", "critical"]
    action: Annotated[str, Field(min_length=1)]
    coverage_conclusion: CoverageConclusion
    verification_status: VerificationStatus
    limitations: list[Annotated[str, Field(min_length=1)]]


class MappingRegister(StrictRecord):
    sources: list[MappingSource] = Field(min_length=1)
    mappings: list[FrameworkMapping] = Field(min_length=1)


class EvidenceRequest(StrictRecord):
    id: RecordId
    requested_evidence: Annotated[str, Field(min_length=1)]
    provider_role: Annotated[str, Field(min_length=1)]
    due_date: date
    status: Literal["requested", "received", "incomplete", "blocked"]
    response_evidence_ids: list[RecordId]
    blocker_id: RecordId | None = None
    limitations: list[Annotated[str, Field(min_length=1)]]

    @model_validator(mode="after")
    def evidence_request_state_is_consistent(self) -> EvidenceRequest:
        if self.status == "received" and not self.response_evidence_ids:
            raise ValueError("received evidence request requires evidence IDs")
        if self.status == "blocked" and self.blocker_id is None:
            raise ValueError("blocked evidence request requires a blocker ID")
        return self


class EvidenceRequestRegister(StrictRecord):
    requests: list[EvidenceRequest] = Field(min_length=1)


class Milestone(StrictRecord):
    id: RecordId
    name: Annotated[str, Field(min_length=1)]
    status: Literal["planned", "in_progress", "partial", "completed", "blocked"]
    requirement_ids: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    evidence_references: list[Annotated[str, Field(min_length=1)]]
    blocker_ids: list[RecordId]
    decision: Annotated[str, Field(min_length=1)]
    limitations: list[Annotated[str, Field(min_length=1)]]


class MilestoneRegister(StrictRecord):
    milestones: list[Milestone] = Field(min_length=1)


class Blocker(StrictRecord):
    id: RecordId
    title: Annotated[str, Field(min_length=1)]
    status: Literal["open", "resolved"]
    affected_requirements: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    evidence_references: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    resolution_criteria: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    limitations: list[Annotated[str, Field(min_length=1)]]


class BlockerRegister(StrictRecord):
    blockers: list[Blocker] = Field(min_length=1)


class ReviewDecision(StrictRecord):
    id: RecordId
    artifact: Annotated[str, Field(min_length=1)]
    artifact_version: Annotated[str, Field(min_length=1)]
    reviewer: Annotated[str, Field(min_length=1)]
    review_type: Literal["automated_structural", "owner_self_review", "external_review"]
    comment: Annotated[str, Field(min_length=1)]
    resolution: Annotated[str, Field(min_length=1)]
    status: Literal["open", "resolved"]
    created_at: datetime
    resolved_at: datetime | None = None

    @model_validator(mode="after")
    def review_resolution_is_consistent(self) -> ReviewDecision:
        if self.status == "resolved" and self.resolved_at is None:
            raise ValueError("resolved review decision requires resolved_at")
        if self.status == "open" and self.resolved_at is not None:
            raise ValueError("open review decision cannot have resolved_at")
        return self


class AcceptanceResult(StrictRecord):
    id: Annotated[str, Field(pattern=r"^AT-(0[1-9]|1[0-9]|20)$")]
    requirement_ids: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    status: Literal["passed", "partial", "missing"]
    revision: Annotated[str, Field(min_length=1)]
    environment: Annotated[str, Field(min_length=1)]
    evidence_ids: list[RecordId]
    evidence_references: list[Annotated[str, Field(min_length=1)]]
    result: Annotated[str, Field(min_length=1)]
    limitations: list[Annotated[str, Field(min_length=1)]]
    recorded_at: datetime

    @model_validator(mode="after")
    def acceptance_state_is_supported(self) -> AcceptanceResult:
        if self.status == "passed" and not (self.evidence_ids or self.evidence_references):
            raise ValueError("passed acceptance result requires evidence")
        if self.status != "passed" and not self.limitations:
            raise ValueError("partial or missing acceptance result requires limitations")
        return self


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
