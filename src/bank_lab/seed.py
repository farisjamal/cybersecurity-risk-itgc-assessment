"""Deterministic synthetic population for the local lab."""

from __future__ import annotations

import hashlib
import json
import random
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import pyotp
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.models import (
    AccessRequest,
    AccessReview,
    AccountStatus,
    BackupRun,
    ChangeRecord,
    ChangeStatus,
    Decision,
    EmploymentStatus,
    Incident,
    Role,
    RunStatus,
    ServiceRequest,
    ServiceRequestHistory,
    ServiceRequestStatus,
    User,
)
from bank_lab.security import hash_password

FIXTURE_START = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
GENERATOR_VERSION = "1.0"


@dataclass(frozen=True)
class SeedSummary:
    seed: int
    generator_version: str
    counts: dict[str, int]
    business_digest: str
    created: bool
    initial_passwords: dict[str, str] = field(default_factory=dict, repr=False)
    totp_secrets: dict[str, str] = field(default_factory=dict, repr=False)


def _stable_id(prefix: str, number: int) -> str:
    return f"{prefix}-{number:03d}"


def _business_digest(users: list[User], requests: list[ServiceRequest]) -> str:
    payload = {
        "users": [
            {
                "id": item.id,
                "name": item.name,
                "email": item.email,
                "role": item.role,
                "account_status": item.account_status,
                "employment_status": item.employment_status,
                "join_date": item.join_date.isoformat(),
                "leave_date": item.leave_date.isoformat() if item.leave_date else None,
            }
            for item in sorted(users, key=lambda value: value.id)
        ],
        "requests": [
            {
                "id": item.id,
                "owner_id": item.owner_id,
                "assigned_staff_id": item.assigned_staff_id,
                "category": item.category,
                "description": item.description,
                "status": item.status,
            }
            for item in sorted(requests, key=lambda value: value.id)
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


async def _summary(db: AsyncSession, seed: int, created: bool) -> SeedSummary:
    users = list((await db.execute(select(User).order_by(User.id))).scalars())
    requests = list(
        (await db.execute(select(ServiceRequest).order_by(ServiceRequest.id))).scalars()
    )
    model_counts = {
        "users": len(users),
        "service_requests": len(requests),
        "access_reviews": int((await db.execute(select(func.count(AccessReview.id)))).scalar_one()),
        "changes": int((await db.execute(select(func.count(ChangeRecord.id)))).scalar_one()),
        "backup_history": int((await db.execute(select(func.count(BackupRun.id)))).scalar_one()),
        "incidents": int((await db.execute(select(func.count(Incident.id)))).scalar_one()),
    }
    return SeedSummary(
        seed=seed,
        generator_version=GENERATOR_VERSION,
        counts=model_counts,
        business_digest=_business_digest(users, requests),
        created=created,
    )


async def seed_database(
    db: AsyncSession,
    seed: int = 42,
    *,
    password_factory: Callable[[], str] | None = None,
    totp_factory: Callable[[], str] | None = None,
) -> SeedSummary:
    """Create the required synthetic populations once.

    Business identifiers and fields are deterministic for ``seed``. Authentication
    material is intentionally random and excluded from the stable digest. Newly
    generated credentials are returned only to the direct caller and never logged.
    """

    existing = int((await db.execute(select(func.count(User.id)))).scalar_one())
    if existing:
        return await _summary(db, seed, False)

    rng = random.Random(seed)  # noqa: S311 - deterministic synthetic fixtures
    make_password = password_factory or (lambda: f"Lab-{secrets.token_urlsafe(15)}-9a!")
    make_totp = totp_factory or pyotp.random_base32
    roles = [
        *([Role.ADMINISTRATOR] * 2),
        *([Role.CHANGE_APPROVER] * 4),
        *([Role.STAFF] * 12),
        *([Role.READ_ONLY] * 6),
    ]
    passwords: dict[str, str] = {}
    totp_secrets: dict[str, str] = {}
    users: list[User] = []
    terminated_indexes = {17, 22, 23}
    for index, role in enumerate(roles, start=1):
        email = f"user{index:02d}@example.test"
        password = make_password()
        passwords[email] = password
        totp_secret = make_totp() if role in {Role.ADMINISTRATOR, Role.CHANGE_APPROVER} else None
        if totp_secret:
            totp_secrets[email] = totp_secret
        terminated = index in terminated_indexes
        user = User(
            id=_stable_id("USR", index),
            name=f"Fictional User {index:02d}",
            email=email,
            password_hash=hash_password(password),
            role=role,
            account_status=AccountStatus.DISABLED if terminated else AccountStatus.ACTIVE,
            employment_status=(
                EmploymentStatus.TERMINATED if terminated else EmploymentStatus.EMPLOYED
            ),
            manager_id=None if index <= 2 else _stable_id("USR", 1 + (index % 2)),
            join_date=date(2024 + (index % 2), 1 + (index % 6), 1 + (index % 20)),
            leave_date=date(2026, 8, 10 + index % 10) if terminated else None,
            totp_secret=totp_secret,
            created_at=FIXTURE_START + timedelta(minutes=index),
        )
        users.append(user)
    db.add_all(users)
    await db.flush()

    categories = ["account enquiry", "address update", "statement request", "service issue"]
    request_rows: list[ServiceRequest] = []
    staff_ids = [_stable_id("USR", i) for i in range(7, 19)]
    owner_ids = [_stable_id("USR", i) for i in range(7, 25)]
    for index in range(1, 51):
        owner_id = owner_ids[rng.randrange(len(owner_ids))]
        assigned_id = staff_ids[rng.randrange(len(staff_ids))]
        status = list(ServiceRequestStatus)[index % 3]
        created_at = FIXTURE_START + timedelta(hours=index * 3)
        request = ServiceRequest(
            id=_stable_id("REQ", index),
            owner_id=owner_id,
            assigned_staff_id=assigned_id,
            category=categories[index % len(categories)],
            description=f"Synthetic service request {index:02d}; no real customer data.",
            status=status,
            created_at=created_at,
            updated_at=created_at + timedelta(hours=index % 5),
        )
        request_rows.append(request)
        db.add(request)
        db.add(
            ServiceRequestHistory(
                id=_stable_id("HIS", index),
                request_id=request.id,
                actor_id=owner_id,
                action="fixture_created",
                new_status=status,
                created_at=created_at,
            )
        )

    for index in range(1, 7):
        db.add(
            AccessRequest(
                id=_stable_id("ACC", index),
                user_id=_stable_id("USR", 6 + index),
                requested_role=Role.STAFF,
                requester_id=_stable_id("USR", 1),
                approver_id=_stable_id("USR", 3),
                decision=Decision.APPROVED,
                rationale="Synthetic joiner provisioning fixture.",
                decided_at=FIXTURE_START + timedelta(days=index),
                applied_at=FIXTURE_START + timedelta(days=index, minutes=10),
                created_at=FIXTURE_START + timedelta(days=index, minutes=-10),
            )
        )

    db.add(
        AccessReview(
            id="ARV-001",
            period="2026-Q3",
            population_snapshot={"count": 24, "user_ids": [user.id for user in users]},
            reviewer_role=Role.CHANGE_APPROVER,
            decisions=[{"user_id": user.id, "decision": "retain"} for user in users],
            action_references=[],
            completed_at=FIXTURE_START + timedelta(days=29),
            created_at=FIXTURE_START + timedelta(days=28),
        )
    )

    for index in range(1, 13):
        emergency = index > 10
        requester_id = _stable_id("USR", 7 + (index % 10))
        approver_id = _stable_id("USR", 3 + (index % 4))
        db.add(
            ChangeRecord(
                id=_stable_id("CHG", index),
                requester_id=requester_id,
                change_type="emergency" if emergency else "normal",
                version_reference=f"lab-v1.0.{index}",
                description=f"Synthetic change record {index:02d}.",
                test_evidence=None if emergency else f"TEST-{index:03d}",
                rollback_plan=f"Return to lab-v1.0.{max(0, index - 1)}",
                emergency_reason="Synthetic urgent service recovery." if emergency else None,
                approver_id=approver_id,
                decision=Decision.APPROVED,
                decision_history=[
                    {
                        "approver_id": approver_id,
                        "decision": "approved",
                        "at": (FIXTURE_START + timedelta(days=index)).isoformat(),
                    }
                ],
                status=ChangeStatus.DEPLOYED,
                deployed_version=f"lab-v1.0.{index}",
                deployed_at=FIXTURE_START + timedelta(days=index, hours=1),
                retrospective_due_at=(FIXTURE_START + timedelta(days=index + 2))
                if emergency
                else None,
                retrospective_review="Synthetic retrospective completed." if emergency else None,
                finalized=True,
                created_at=FIXTURE_START + timedelta(days=index),
            )
        )

    for index in range(1, 9):
        started = FIXTURE_START + timedelta(days=index * 3)
        db.add(
            BackupRun(
                id=_stable_id("BKP", index),
                run_id="FIXTURE-HISTORY",
                started_at=started,
                ended_at=started + timedelta(minutes=2),
                artifact_path=f"synthetic://backup-{index:03d}",
                artifact_sha256=hashlib.sha256(f"fixture-{seed}-{index}".encode()).hexdigest(),
                status=RunStatus.COMPLETED,
                dataset_reference=f"DATASET-{index:03d}",
                validation_result={"synthetic": True, "verified": True},
                created_at=started,
            )
        )

    for index in range(1, 5):
        db.add(
            Incident(
                id=_stable_id("INC", index),
                title=f"Synthetic historical incident {index:02d}",
                severity="medium" if index < 4 else "high",
                status="closed",
                related_event_ids=[],
                timeline=[
                    {"at": (FIXTURE_START + timedelta(days=index)).isoformat(), "event": "detected"}
                ],
                containment_decision="Synthetic tabletop containment decision.",
                escalation_record="No external message sent; exercise record only.",
                lessons="Synthetic lesson for control assessment.",
                created_at=FIXTURE_START + timedelta(days=index),
            )
        )

    await db.commit()
    result = await _summary(db, seed, True)
    return SeedSummary(
        seed=result.seed,
        generator_version=result.generator_version,
        counts=result.counts,
        business_digest=result.business_digest,
        created=True,
        initial_passwords=passwords,
        totp_secrets=totp_secrets,
    )
