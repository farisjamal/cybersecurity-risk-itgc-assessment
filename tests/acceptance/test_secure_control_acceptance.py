from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bank_lab.config import Settings
from bank_lab.database import Base
from bank_lab.models import AuditEvent, ChangeStatus, Decision, Session, User
from bank_lab.security import MfaError, SessionExpiredError, digest_secret, resolve_session
from bank_lab.seed import seed_database
from bank_lab.services import AccessService, AuthService, ChangeService, ConflictError


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
            await seed_database(session, 42, password_factory=lambda: "Fixture-Pass-42!")
        yield session
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.acceptance
@pytest.mark.parametrize("state", ["revoked", "absolute_expired", "idle_expired"])
async def test_revoked_and_expired_sessions_are_rejected(db: AsyncSession, state: str) -> None:
    settings = Settings(session_pepper="acceptance-pepper")
    current = datetime(2026, 9, 26, 2, 30, tzinfo=UTC)
    token = f"session-token-{state}"
    record = Session(
        token_hash=digest_secret(token, settings.session_pepper),
        csrf_hash="b" * 64,
        user_id="USR-001",
        issued_at=current - timedelta(hours=2),
        last_activity_at=current - timedelta(minutes=1),
        expires_at=current + timedelta(hours=1),
    )
    if state == "revoked":
        record.revoked_at = current - timedelta(seconds=1)
    elif state == "absolute_expired":
        record.expires_at = current
    else:
        record.last_activity_at = current - timedelta(minutes=settings.session_idle_minutes)
    db.add(record)
    await db.commit()

    with pytest.raises(SessionExpiredError):
        await resolve_session(db, token, settings, now=current)


@pytest.mark.asyncio
@pytest.mark.acceptance
async def test_mfa_failures_are_rate_limited_after_five_attempts(db: AsyncSession) -> None:
    admin = await db.get(User, "USR-001")
    assert admin and admin.totp_secret
    settings = Settings(session_pepper="acceptance-pepper")
    current = datetime(2026, 9, 26, 2, 30, tzinfo=UTC)
    record = Session(
        token_hash="c" * 64,
        csrf_hash="d" * 64,
        user_id=admin.id,
        issued_at=current,
        last_activity_at=current,
        expires_at=current + timedelta(hours=1),
    )
    db.add(record)
    await db.commit()
    service = AuthService(db, settings)

    for _ in range(5):
        with pytest.raises(MfaError, match="Invalid MFA code"):
            await service.complete_mfa(record, admin, "000000", now=current)
    with pytest.raises(MfaError, match="temporarily blocked"):
        await service.complete_mfa(record, admin, "000000", now=current)

    assert record.mfa_failures == 5
    assert record.mfa_blocked_until == current + timedelta(minutes=5)


@pytest.mark.asyncio
@pytest.mark.acceptance
async def test_access_review_rejects_incomplete_population_and_emits_completion_event(
    db: AsyncSession,
) -> None:
    reviewer = await db.get(User, "USR-003")
    assert reviewer
    service = AccessService(db, Settings(session_pepper="acceptance-pepper"))

    with pytest.raises(ConflictError, match="complete account population"):
        await service.record_review(
            reviewer,
            "2026-Q3",
            [{"user_id": "USR-001", "decision": "retain"}],
        )

    users = list((await db.execute(select(User).order_by(User.id))).scalars())
    review = await service.record_review(
        reviewer,
        "2026-Q3",
        [{"user_id": user.id, "decision": "retain"} for user in users],
    )
    event = (
        await db.execute(
            select(AuditEvent).where(
                AuditEvent.action == "access_review.completed",
                AuditEvent.object_id == review.id,
            )
        )
    ).scalar_one()

    assert review.population_snapshot["count"] == 24
    assert event.actor_id == reviewer.id
    assert event.context["population_count"] == 24


@pytest.mark.asyncio
@pytest.mark.acceptance
async def test_change_deploy_rollback_and_emergency_follow_up_are_attributable(
    db: AsyncSession,
) -> None:
    administrator = await db.get(User, "USR-001")
    requester = await db.get(User, "USR-007")
    approver = await db.get(User, "USR-003")
    assert administrator and requester and approver
    service = ChangeService(db, Settings(session_pepper="acceptance-pepper"))

    normal = await service.submit(
        requester,
        change_type="normal",
        version_reference="v-acceptance",
        description="Fictional acceptance change",
        test_evidence="unit and smoke tests passed",
        rollback_plan="restore prior image",
    )
    await service.decide(normal.id, approver, Decision.APPROVED, "Evidence reviewed")
    await service.deploy(normal.id, administrator, "v-acceptance", "HTTP 200")
    await service.record_rollback(normal.id, administrator, "Restored prior image")
    assert normal.status == ChangeStatus.ROLLED_BACK
    assert normal.rollback_record == "Restored prior image"

    friday = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
    monday = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    with patch("bank_lab.services.changes.utcnow", return_value=friday):
        emergency = await service.submit(
            administrator,
            change_type="emergency",
            version_reference="v-emergency",
            description="Fictional containment change",
            test_evidence=None,
            rollback_plan=None,
            emergency_reason="Contain a simulated access issue",
        )
    assert emergency.retrospective_due_at == datetime(2026, 9, 29, 12, 0, tzinfo=UTC)

    with patch("bank_lab.services.changes.utcnow", return_value=monday):
        reviewed = await service.record_emergency_review(
            emergency.id,
            approver,
            "Confirmed the exception, impact, and follow-up actions.",
        )
    assert reviewed.retrospective_review
    assert reviewed.decision_history[-1]["reviewer_id"] == approver.id
    assert reviewed.decision_history[-1]["within_target"] is True
    actions = set(
        (
            await db.execute(
                select(AuditEvent.action).where(AuditEvent.object_id.in_([normal.id, emergency.id]))
            )
        ).scalars()
    )
    assert {
        "change.submitted",
        "change.decided",
        "change.deployed",
        "change.rolled_back",
        "change.emergency_reviewed",
    }.issubset(actions)
