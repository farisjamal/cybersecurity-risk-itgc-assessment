from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bank_lab.config import Settings
from bank_lab.database import Base
from bank_lab.models import (
    AccountStatus,
    Alert,
    AuditEvent,
    ChangeRecord,
    Decision,
    EmploymentStatus,
    Role,
    Session,
    User,
)
from bank_lab.scenarios import ScenarioError, remediate_scenario, retest_scenario, run_scenario
from bank_lab.seed import seed_database
from bank_lab.services import AccessService, ChangeService, ConflictError, ForbiddenError


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_business_records_are_stable(db: AsyncSession) -> None:
    with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
        first = await seed_database(db, 42, password_factory=lambda: "Fixture-Pass-42!")
        second = await seed_database(db, 42, password_factory=lambda: "Different-Pass-42!")
    assert first.created is True
    assert second.created is False
    assert first.counts == {
        "users": 24,
        "service_requests": 50,
        "access_reviews": 1,
        "changes": 12,
        "backup_history": 8,
        "incidents": 4,
    }
    assert first.business_digest == second.business_digest
    assert all(
        user.email.endswith("@example.test") for user in (await db.execute(select(User))).scalars()
    )


@pytest.mark.asyncio
async def test_deactivation_revokes_every_active_session(db: AsyncSession) -> None:
    with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
        await seed_database(db, password_factory=lambda: "Fixture-Pass-42!")
    administrator = await db.get(User, "USR-001")
    target = await db.get(User, "USR-007")
    assert administrator and target
    db.add(
        Session(
            token_hash="a" * 64,
            csrf_hash="b" * 64,
            user_id=target.id,
            expires_at=target.created_at,
        )
    )
    await db.commit()
    await AccessService(db, Settings(session_pepper="pepper")).deactivate(
        target.id, administrator, "Synthetic leaver recorded"
    )
    sessions = list(
        (await db.execute(select(Session).where(Session.user_id == target.id))).scalars()
    )
    assert target.account_status == AccountStatus.DISABLED
    assert sessions and all(record.revoked_at is not None for record in sessions)


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["terminated", "not_started", "employment_ended"])
async def test_approved_access_cannot_activate_an_ineligible_employee(
    db: AsyncSession, state: str
) -> None:
    with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
        await seed_database(db, password_factory=lambda: "Fixture-Pass-42!")
    admin = await db.get(User, "USR-001")
    approver = await db.get(User, "USR-003")
    target = await db.get(User, "USR-007")
    assert admin and approver and target
    target.account_status = AccountStatus.PENDING
    service = AccessService(db, Settings(session_pepper="pepper"))
    request = await service.submit(admin, target, Role.ADMINISTRATOR, "Joiner request")
    await service.decide(request.id, approver, Decision.APPROVED)
    if state == "terminated":
        target.employment_status = EmploymentStatus.TERMINATED
    elif state == "not_started":
        target.join_date = datetime.now(UTC).date() + timedelta(days=1)
    else:
        target.leave_date = datetime.now(UTC).date()
    await db.commit()

    with pytest.raises(ConflictError, match="Access cannot"):
        await service.apply(request.id, admin)

    assert target.account_status == AccountStatus.PENDING
    assert target.role == Role.STAFF
    assert request.applied_at is None
    changed = list(
        (await db.execute(select(Alert).where(Alert.subject_key == target.id))).scalars()
    )
    assert changed == []


@pytest.mark.asyncio
async def test_pending_joiner_requires_approval_before_activation(db: AsyncSession) -> None:
    with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
        await seed_database(db, password_factory=lambda: "Fixture-Pass-42!")
    admin = await db.get(User, "USR-001")
    approver = await db.get(User, "USR-003")
    target = await db.get(User, "USR-007")
    assert admin and approver and target
    target.account_status = AccountStatus.PENDING
    await db.commit()
    service = AccessService(db, Settings(session_pepper="pepper"))
    request = await service.submit(admin, target, Role.STAFF, "Approved fictional joiner")
    with pytest.raises(ConflictError, match="Approved unapplied"):
        await service.apply(request.id, admin)
    assert target.account_status == AccountStatus.PENDING
    await service.decide(request.id, approver, Decision.APPROVED)
    activated = await service.apply(request.id, admin)
    assert activated.account_status == AccountStatus.ACTIVE
    assert request.applied_at is not None


@pytest.mark.asyncio
async def test_access_self_approval_is_rejected_without_activating_account(
    db: AsyncSession,
) -> None:
    with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
        await seed_database(db, password_factory=lambda: "Fixture-Pass-42!")
    requester = await db.get(User, "USR-003")
    independent_approver = await db.get(User, "USR-004")
    administrator = await db.get(User, "USR-001")
    target = await db.get(User, "USR-007")
    assert requester and independent_approver and administrator and target
    target.account_status = AccountStatus.PENDING
    await db.commit()
    service = AccessService(db, Settings(session_pepper="pepper"))
    request = await service.submit(requester, target, Role.STAFF, "Synthetic joiner approval test")

    with pytest.raises(ForbiddenError, match="Requester cannot approve their own request"):
        await service.decide(request.id, requester, Decision.APPROVED)

    await db.refresh(request)
    await db.refresh(target)
    assert request.decision == Decision.PENDING
    assert request.approver_id is None
    assert request.decided_at is None
    assert request.applied_at is None
    assert target.account_status == AccountStatus.PENDING
    decisions = await db.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.object_id == request.id,
            AuditEvent.action == "access_request.decided",
        )
    )
    assert decisions == 0
    with pytest.raises(ConflictError, match="Approved unapplied"):
        await service.apply(request.id, administrator)

    await service.decide(request.id, independent_approver, Decision.APPROVED)
    activated = await service.apply(request.id, administrator)
    assert request.approver_id == independent_approver.id
    assert request.decision == Decision.APPROVED
    assert request.applied_at is not None
    assert activated.account_status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_change_self_approval_and_missing_evidence_are_rejected(db: AsyncSession) -> None:
    with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
        await seed_database(db, password_factory=lambda: "Fixture-Pass-42!")
    approver = await db.get(User, "USR-003")
    assert approver
    service = ChangeService(db, Settings(session_pepper="pepper"))
    with pytest.raises(Exception, match="test evidence"):
        await service.submit(
            approver,
            change_type="normal",
            version_reference="v-test",
            description="Synthetic missing evidence case",
            test_evidence=None,
            rollback_plan="rollback",
        )
    change = ChangeRecord(
        requester_id=approver.id,
        change_type="normal",
        version_reference="v-test",
        description="Synthetic self approval case",
        test_evidence="tests passed",
        rollback_plan="rollback",
        status="submitted",
    )
    db.add(change)
    await db.commit()
    with pytest.raises(ForbiddenError, match="own change"):
        await service.decide(change.id, approver, Decision.APPROVED, "self")


@pytest.mark.asyncio
async def test_role_change_revokes_sessions_and_opens_one_deduplicated_alert(
    db: AsyncSession,
) -> None:
    with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
        await seed_database(db, password_factory=lambda: "Fixture-Pass-42!")
    admin = await db.get(User, "USR-001")
    approver = await db.get(User, "USR-003")
    target = await db.get(User, "USR-007")
    assert admin and approver and target
    access = AccessService(db, Settings(session_pepper="pepper"))
    for number in range(2):
        request = await access.submit(admin, target, Role.ADMINISTRATOR, f"Approved case {number}")
        await access.decide(request.id, approver, Decision.APPROVED)
        if number == 0:
            db.add(
                Session(
                    token_hash="c" * 64,
                    csrf_hash="d" * 64,
                    user_id=target.id,
                    expires_at=target.created_at,
                )
            )
            await db.commit()
        await access.apply(request.id, admin)
        target.role = Role.STAFF
        await db.commit()
    alert_count = int((await db.execute(select(func.count(Alert.id)))).scalar_one())
    assert alert_count == 1
    sessions = list(
        (await db.execute(select(Session).where(Session.user_id == target.id))).scalars()
    )
    assert sessions and all(record.revoked_at for record in sessions)


@pytest.mark.asyncio
async def test_scenario_scope_and_frozen_retest_chain(db: AsyncSession) -> None:
    with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
        await seed_database(db, password_factory=lambda: "Fixture-Pass-42!")
    with pytest.raises(ScenarioError, match="allowlisted"):
        await run_scenario(db, "S01", "unrelated-project")
    baseline = await run_scenario(db, "S01", "cyber-assess-scenario-s01-test")
    remediation = await remediate_scenario(
        db, "S01", baseline.run_id, "cyber-assess-scenario-s01-test"
    )
    retest = await retest_scenario(db, "S01", baseline.run_id, remediation.run_id)
    assert baseline.status == "frozen"
    assert remediation.status == "completed"
    assert retest.status == "completed"
    assert retest.observations["passed"] is True
