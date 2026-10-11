"""Allowlisted, disposable failure scenarios S01-S06."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.audit import emit_event
from bank_lab.backups import BackupError, load_and_validate_backup
from bank_lab.models import (
    AccountStatus,
    AuditEvent,
    BackupRun,
    ChangeRecord,
    ChangeStatus,
    Decision,
    EmploymentStatus,
    Role,
    RunStatus,
    ScenarioRun,
    Session,
    User,
    utcnow,
)
from bank_lab.services import ForbiddenError, require_privileged_mfa


class ScenarioError(Exception):
    """A scenario request was unsafe, unsupported, or inconsistent."""


@dataclass(frozen=True)
class ScenarioDefinition:
    id: str
    condition: str
    remediation_required: bool


@dataclass(frozen=True)
class ScenarioResult:
    run_id: str
    scenario_id: str
    status: str
    observations: dict[str, object]


SCENARIOS = {
    "S01": ScenarioDefinition("S01", "Terminated identity retains access and a session", True),
    "S02": ScenarioDefinition("S02", "Unjustified administrator role", False),
    "S03": ScenarioDefinition("S03", "Privileged action accepts password-only session", True),
    "S04": ScenarioDefinition("S04", "Self-approved change lacks test evidence", False),
    "S05": ScenarioDefinition("S05", "Backup success points to corrupt artifact", True),
    "S06": ScenarioDefinition("S06", "Administrative action omits required event", True),
}
_RESOURCE_PATTERN = re.compile(r"^cyber-assess-scenario-(s0[1-6])-[a-z0-9-]{1,48}$")


def _validate_scope(scenario_id: str, resource_name: str) -> ScenarioDefinition:
    definition = SCENARIOS.get(scenario_id.upper())
    match = _RESOURCE_PATTERN.fullmatch(resource_name)
    if definition is None or match is None or match.group(1).upper() != scenario_id.upper():
        raise ScenarioError("scenario ID or disposable resource name is not allowlisted")
    return definition


async def run_scenario(db: AsyncSession, scenario_id: str, resource_name: str) -> ScenarioResult:
    definition = _validate_scope(scenario_id, resource_name)
    existing = (
        await db.execute(
            select(ScenarioRun).where(
                ScenarioRun.resource_name == resource_name,
                ScenarioRun.run_kind == "baseline",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return ScenarioResult(
            existing.id, existing.scenario_id, existing.status, existing.observations
        )

    observations: dict[str, object]
    if definition.id == "S01":
        user = (
            (
                await db.execute(
                    select(User)
                    .where(User.employment_status == EmploymentStatus.TERMINATED)
                    .order_by(User.id)
                )
            )
            .scalars()
            .first()
        )
        if user is None:
            raise ScenarioError("S01 requires a terminated fixture identity")
        user.account_status = AccountStatus.ACTIVE
        weak_session = Session(
            token_hash=f"scenario-only-{resource_name}",
            csrf_hash=f"scenario-only-csrf-{resource_name}",
            user_id=user.id,
            issued_at=utcnow(),
            last_activity_at=utcnow(),
            expires_at=utcnow() + timedelta(hours=8),
            mfa_verified=False,
        )
        db.add(weak_session)
        await db.flush()
        observations = {"user_id": user.id, "session_id": weak_session.id, "access_retained": True}
    elif definition.id == "S02":
        user = (
            (await db.execute(select(User).where(User.role == Role.STAFF).order_by(User.id)))
            .scalars()
            .first()
        )
        if user is None:
            raise ScenarioError("S02 requires a staff fixture identity")
        user.role = Role.ADMINISTRATOR
        observations = {"user_id": user.id, "unapproved_role": Role.ADMINISTRATOR}
    elif definition.id == "S03":
        observations = {"password_only_privileged_allowed": True, "scope": resource_name}
    elif definition.id == "S04":
        requester = (
            (
                await db.execute(
                    select(User).where(User.role == Role.CHANGE_APPROVER).order_by(User.id)
                )
            )
            .scalars()
            .first()
        )
        if requester is None:
            raise ScenarioError("S04 requires a change approver")
        change = ChangeRecord(
            requester_id=requester.id,
            approver_id=requester.id,
            change_type="normal",
            version_reference="scenario-s04",
            description="Intentionally invalid isolated scenario change.",
            test_evidence=None,
            rollback_plan="Restore previous scenario image.",
            decision=Decision.APPROVED,
            status=ChangeStatus.DEPLOYED,
            deployed_version="scenario-s04",
            deployed_at=utcnow(),
            finalized=True,
        )
        db.add(change)
        await db.flush()
        observations = {"change_id": change.id, "self_approved": True, "test_evidence": None}
    elif definition.id == "S05":
        backup = BackupRun(
            run_id=resource_name,
            dataset_reference="scenario-corrupt-dataset",
            artifact_path=f"scenario://{resource_name}/corrupt.json",
            artifact_sha256="0" * 64,
            status=RunStatus.COMPLETED,
            validation_result={"reported_success": True, "actual_integrity": "corrupt"},
            ended_at=utcnow(),
        )
        db.add(backup)
        await db.flush()
        observations = {"backup_id": backup.id, "reported_success": True, "valid": False}
    else:
        user = (
            (await db.execute(select(User).where(User.role == Role.STAFF).order_by(User.id)))
            .scalars()
            .first()
        )
        if user is None:
            raise ScenarioError("S06 requires a staff fixture identity")
        user.account_status = AccountStatus.DISABLED
        observations = {"user_id": user.id, "action": "user.deactivated", "event_emitted": False}

    run = ScenarioRun(
        scenario_id=definition.id,
        resource_name=resource_name,
        run_kind="baseline",
        status=RunStatus.FROZEN,
        injected_condition=definition.condition,
        observations=observations,
        frozen_at=utcnow(),
    )
    db.add(run)
    await db.commit()
    return ScenarioResult(run.id, run.scenario_id, run.status, run.observations)


async def remediate_scenario(
    db: AsyncSession,
    scenario_id: str,
    baseline_run_id: str,
    resource_name: str,
) -> ScenarioResult:
    definition = _validate_scope(scenario_id, resource_name)
    baseline = await db.get(ScenarioRun, baseline_run_id)
    if (
        baseline is None
        or baseline.scenario_id != definition.id
        or baseline.run_kind != "baseline"
        or baseline.status != RunStatus.FROZEN
    ):
        raise ScenarioError("matching frozen baseline run is required")
    observations: dict[str, object] = {"baseline_run_id": baseline.id}
    if definition.id == "S01":
        user = await db.get(User, str(baseline.observations["user_id"]))
        if user is None:
            raise ScenarioError("baseline user no longer exists")
        user.account_status = AccountStatus.DISABLED
        sessions = list(
            (
                await db.execute(
                    select(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None))
                )
            ).scalars()
        )
        now = utcnow()
        for session in sessions:
            session.revoked_at = now
        observations.update({"user_id": user.id, "sessions_revoked": len(sessions)})
    elif definition.id == "S02":
        user = await db.get(User, str(baseline.observations["user_id"]))
        if user is None:
            raise ScenarioError("baseline user no longer exists")
        user.role = Role.STAFF
        observations.update({"user_id": user.id, "role": Role.STAFF})
    elif definition.id == "S03":
        observations["privileged_mfa_enforced"] = True
    elif definition.id == "S04":
        change = await db.get(ChangeRecord, str(baseline.observations["change_id"]))
        if change is None:
            raise ScenarioError("baseline change no longer exists")
        change.test_evidence = "S04 remediation test evidence"
        change.approver_id = "USR-003" if change.requester_id != "USR-003" else "USR-004"
        observations.update({"change_id": change.id, "separation_restored": True})
    elif definition.id == "S05":
        backup = await db.get(BackupRun, str(baseline.observations["backup_id"]))
        if backup is None:
            raise ScenarioError("baseline backup no longer exists")
        backup.status = RunStatus.FAILED
        backup.validation_result = {"verified": False, "reason": "hash validation failed"}
        observations.update({"failed_backup_preserved": backup.id, "validation_enforced": True})
    else:
        user_id = str(baseline.observations["user_id"])
        event = await emit_event(
            db,
            run_id=resource_name,
            actor_id="USR-001",
            action="user.deactivated",
            object_type="user",
            object_id=user_id,
            result="success",
            context={"reperformed_for": "S06 remediation"},
        )
        observations.update({"user_id": user_id, "event_id": event.id, "event_emitted": True})
    run = ScenarioRun(
        scenario_id=definition.id,
        resource_name=resource_name,
        run_kind="remediation",
        status=RunStatus.COMPLETED,
        baseline_run_id=baseline.id,
        injected_condition=f"Remediation for {definition.id}",
        observations=observations,
    )
    db.add(run)
    await db.commit()
    return ScenarioResult(run.id, run.scenario_id, run.status, run.observations)


async def retest_scenario(
    db: AsyncSession,
    scenario_id: str,
    baseline_run_id: str,
    remediation_run_id: str,
) -> ScenarioResult:
    definition = SCENARIOS.get(scenario_id.upper())
    baseline = await db.get(ScenarioRun, baseline_run_id)
    remediation = await db.get(ScenarioRun, remediation_run_id)
    if (
        definition is None
        or baseline is None
        or remediation is None
        or baseline.scenario_id != definition.id
        or remediation.scenario_id != definition.id
        or remediation.baseline_run_id != baseline.id
        or baseline.status != RunStatus.FROZEN
    ):
        raise ScenarioError("linked baseline and remediation runs are required")
    passed = False
    evidence: dict[str, object] = {}
    if definition.id == "S01":
        user = await db.get(User, str(baseline.observations["user_id"]))
        active_sessions = list(
            (
                await db.execute(
                    select(Session).where(
                        Session.user_id == str(baseline.observations["user_id"]),
                        Session.revoked_at.is_(None),
                    )
                )
            ).scalars()
        )
        passed = bool(
            user and user.account_status == AccountStatus.DISABLED and not active_sessions
        )
        evidence = {"login_allowed": False, "active_session_count": len(active_sessions)}
    elif definition.id == "S02":
        user = await db.get(User, str(baseline.observations["user_id"]))
        passed = bool(user and user.role == Role.STAFF)
        evidence = {"actual_role": user.role if user else None}
    elif definition.id == "S03":
        administrator = await db.get(User, "USR-001")
        if administrator is None:
            raise ScenarioError("S03 requires the administrator fixture")
        probe = Session(user_id=administrator.id, mfa_verified=False)
        denied = False
        try:
            require_privileged_mfa(probe, administrator)
        except ForbiddenError:
            denied = True
        probe.mfa_verified = True
        allowed = True
        try:
            require_privileged_mfa(probe, administrator)
        except ForbiddenError:
            allowed = False
        passed = denied and allowed
        evidence = {"password_only_denied": denied, "mfa_session_allowed": allowed}
    elif definition.id == "S04":
        change = await db.get(ChangeRecord, str(baseline.observations["change_id"]))
        passed = bool(change and change.approver_id != change.requester_id and change.test_evidence)
        evidence = {
            "separate_approver": passed,
            "test_evidence_present": bool(change and change.test_evidence),
        }
    elif definition.id == "S05":
        backup = await db.get(BackupRun, str(baseline.observations["backup_id"]))
        rejected = False
        with tempfile.TemporaryDirectory(prefix="cyber-assess-s05-") as directory:
            corrupt = Path(directory) / "corrupt.json"
            corrupt.write_bytes(b"intentionally corrupt scenario backup")
            try:
                load_and_validate_backup(corrupt, "0" * 64)
            except BackupError:
                rejected = True
        passed = bool(rejected and backup and backup.status == RunStatus.FAILED)
        evidence = {"corrupt_backup_rejected": rejected, "failed_original_preserved": bool(backup)}
    else:
        event_id = remediation.observations.get("event_id")
        passed = bool(event_id and await db.get(AuditEvent, event_id))
        evidence = {"event_emitted": passed, "event_id": event_id}
    run = ScenarioRun(
        scenario_id=definition.id,
        resource_name=f"{baseline.resource_name}-retest-{remediation.id[:8]}",
        run_kind="retest",
        status=RunStatus.COMPLETED if passed else RunStatus.FAILED,
        baseline_run_id=baseline.id,
        injected_condition=f"Fresh retest for {definition.id}",
        observations={"passed": passed, **evidence},
    )
    db.add(run)
    await db.commit()
    return ScenarioResult(run.id, run.scenario_id, run.status, run.observations)
