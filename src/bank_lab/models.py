"""Database model for the assessed portal and its control evidence."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from bank_lab.database import Base

SCHEMA_VERSION = "1.0"


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Role(StrEnum):
    ADMINISTRATOR = "administrator"
    CHANGE_APPROVER = "change_approver"
    STAFF = "staff"
    READ_ONLY = "read_only"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    PENDING = "pending"


class EmploymentStatus(StrEnum):
    EMPLOYED = "employed"
    TERMINATED = "terminated"


class Decision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ServiceRequestStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class ChangeStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"


class AlertStatus(StrEnum):
    OPEN = "open"
    TRIAGED = "triaged"
    CLOSED = "closed"


class RunStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    FROZEN = "frozen"


class RecordMixin:
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    schema_version: Mapped[str] = mapped_column(String(16), default=SCHEMA_VERSION)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(RecordMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('administrator','change_approver','staff','read_only')",
            name="ck_users_role",
        ),
        CheckConstraint(
            "account_status IN ('active','disabled','pending')",
            name="ck_users_account_status",
        ),
        CheckConstraint(
            "employment_status IN ('employed','terminated')",
            name="ck_users_employment_status",
        ),
    )

    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default=Role.STAFF)
    account_status: Mapped[str] = mapped_column(String(24), default=AccountStatus.PENDING)
    employment_status: Mapped[str] = mapped_column(String(24), default=EmploymentStatus.EMPLOYED)
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    join_date: Mapped[date] = mapped_column(Date)
    leave_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_last_counter: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Session(RecordMixin, Base):
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mfa_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_failures: Mapped[int] = mapped_column(Integer, default=0)
    mfa_blocked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LoginFailure(RecordMixin, Base):
    __tablename__ = "login_failures"
    __table_args__ = (Index("ix_login_failure_account_time", "account_key", "occurred_at"),)

    account_key: Mapped[str] = mapped_column(String(255))
    source_ip: Mapped[str] = mapped_column(String(64), default="unknown")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ServiceRequest(RecordMixin, Base):
    __tablename__ = "service_requests"
    __table_args__ = (
        CheckConstraint("status IN ('open','in_progress','resolved')", name="ck_request_status"),
    )

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_staff_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default=ServiceRequestStatus.OPEN)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ServiceRequestHistory(RecordMixin, Base):
    __tablename__ = "service_request_history"

    request_id: Mapped[str] = mapped_column(ForeignKey("service_requests.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    previous_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AccessRequest(RecordMixin, Base):
    __tablename__ = "access_requests"
    __table_args__ = (
        CheckConstraint("decision IN ('pending','approved','rejected')", name="ck_access_decision"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    requested_role: Mapped[str] = mapped_column(String(32))
    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approver_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision: Mapped[str] = mapped_column(String(24), default=Decision.PENDING)
    rationale: Mapped[str] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AccessReview(RecordMixin, Base):
    __tablename__ = "access_reviews"

    period: Mapped[str] = mapped_column(String(32))
    population_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    reviewer_role: Mapped[str] = mapped_column(String(32))
    decisions: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    action_references: Mapped[list[str]] = mapped_column(JSON, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChangeRecord(RecordMixin, Base):
    __tablename__ = "change_records"
    __table_args__ = (
        CheckConstraint("change_type IN ('normal','emergency')", name="ck_change_type"),
        CheckConstraint(
            "status IN ('draft','submitted','approved','rejected','deployed','rolled_back')",
            name="ck_change_status",
        ),
    )

    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    change_type: Mapped[str] = mapped_column(String(24), default="normal")
    version_reference: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    test_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approver_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision: Mapped[str] = mapped_column(String(24), default=Decision.PENDING)
    decision_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default=ChangeStatus.DRAFT)
    deployed_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rollback_record: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrospective_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retrospective_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    finalized: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditEvent(RecordMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_run_action_time", "run_id", "action", "occurred_at"),)

    run_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    object_type: Mapped[str] = mapped_column(String(80))
    object_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    result: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Alert(RecordMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("status IN ('open','triaged','closed')", name="ck_alert_status"),
    )

    rule_id: Mapped[str] = mapped_column(String(80), index=True)
    rule_version: Mapped[str] = mapped_column(String(24), default="1.0")
    severity: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default=AlertStatus.OPEN)
    subject_key: Mapped[str] = mapped_column(String(255), index=True)
    related_event_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    triage_record: Mapped[str | None] = mapped_column(Text, nullable=True)
    containment_record: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_record: Mapped[str | None] = mapped_column(Text, nullable=True)


class Incident(RecordMixin, Base):
    __tablename__ = "incidents"

    title: Mapped[str] = mapped_column(String(160))
    severity: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(32))
    related_event_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    containment_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_record: Mapped[str | None] = mapped_column(Text, nullable=True)
    lessons: Mapped[str | None] = mapped_column(Text, nullable=True)


class BackupRun(RecordMixin, Base):
    __tablename__ = "backup_runs"

    run_id: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default=RunStatus.STARTED)
    dataset_reference: Mapped[str] = mapped_column(String(100))
    validation_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ScenarioRun(RecordMixin, Base):
    __tablename__ = "scenario_runs"
    __table_args__ = (
        UniqueConstraint("resource_name", "run_kind", name="uq_scenario_resource_kind"),
    )

    scenario_id: Mapped[str] = mapped_column(String(8), index=True)
    resource_name: Mapped[str] = mapped_column(String(120))
    run_kind: Mapped[str] = mapped_column(String(24), default="baseline")
    status: Mapped[str] = mapped_column(String(24), default=RunStatus.STARTED)
    baseline_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("scenario_runs.id"), nullable=True
    )
    injected_condition: Mapped[str] = mapped_column(Text)
    observations: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
