"""Observe PostgreSQL populations and an isolated restore without exporting secrets.

Run inside this project's app container. Raw backups stay in its runtime volume.
The separate restore database is retained for review; no source data is deleted.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC
from pathlib import Path
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bank_lab.app import create_app
from bank_lab.backups import create_backup, restore_test
from bank_lab.config import Settings
from bank_lab.database import Base
from bank_lab.models import AccessReview, ChangeRecord, ServiceRequest, User, utcnow
from bank_lab.security import issue_session
from bank_lab.services import ServiceRequestService


async def main() -> None:
    settings = Settings()
    url = make_url(settings.database_url)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("This verification requires the documented PostgreSQL stack")
    suffix = uuid4().hex[:12]
    restore_name = f"cyber_assess_restore_{suffix}"
    started = utcnow()
    source_engine = create_async_engine(url)
    factory = async_sessionmaker(source_engine, expire_on_commit=False)
    async with factory() as source:
        users = list((await source.execute(select(User).order_by(User.id))).scalars())
        if len(users) != 24:
            raise RuntimeError("Seed the expected 24-account population first")
        requester = next(user for user in users if user.id == "USR-007")
        marker = await ServiceRequestService(source, settings).create(
            requester, category="recovery checkpoint", description=f"Synthetic checkpoint {suffix}"
        )
        # This record was committed now; historical fixture timestamps are not RPO evidence.
        await source.refresh(marker)
        committed_at = marker.updated_at
        if committed_at.tzinfo is None:
            committed_at = committed_at.replace(tzinfo=UTC)
        backup = await create_backup(source, Path("runtime/recovery"), f"RUN-RECOVERY-{suffix}")
        source_ids = list((await source.execute(select(ServiceRequest.id))).scalars())
        changes = list(
            (await source.execute(select(ChangeRecord).order_by(ChangeRecord.id))).scalars()
        )
        reviews = list(
            (await source.execute(select(AccessReview).order_by(AccessReview.id))).scalars()
        )

    admin_engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as connection:
        # Identifier is generated solely from a fixed prefix and uuid hex.
        await connection.execute(text(f'CREATE DATABASE "{restore_name}"'))
    await admin_engine.dispose()
    target_url = url.set(database=restore_name)
    target_engine = create_async_engine(target_url)
    async with target_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    target_factory = async_sessionmaker(target_engine, expire_on_commit=False)
    outage_at = utcnow()
    async with target_factory() as target:
        restored = await restore_test(target, backup.path, backup.sha256)

    target_settings = Settings(
        database_url=target_url.render_as_string(hide_password=False),
        session_pepper=settings.session_pepper,
    )
    app = create_app(target_settings)
    async with app.router.lifespan_context(app):
        async with app.state.session_factory() as target:
            reader = await target.get(User, "USR-019")
            assert reader
            issued = issue_session(reader, target_settings)
            target.add(issued.record)
            await target.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("bank_session", issued.token)
            response = await client.get("/requests")
            if response.status_code != 200:
                raise RuntimeError("Restored application acceptance failed")
            recovered_ids = {item["id"] for item in response.json()}
            if recovered_ids != set(source_ids):
                raise RuntimeError("Restored API population does not reconcile")
    accepted_at = utcnow()
    async with factory() as source:
        after_ids = list((await source.execute(select(ServiceRequest.id))).scalars())
        if set(after_ids) != set(source_ids):
            raise RuntimeError("Source population changed during isolated restore")
    result = {
        "schema_version": "1.0",
        "run_id": f"RUN-RUNTIME-{suffix.upper()}",
        "started_at": started.isoformat(),
        "accepted_at": accepted_at.isoformat(),
        "database_backend": "postgresql",
        "restore_database": restore_name,
        "restored_counts": restored.counts,
        "backup_sha256": backup.sha256,
        "source_unchanged_during_restore": True,
        "application_acceptance": {"status": 200, "reconciled_requests": len(recovered_ids)},
        "recovery": {
            "scope": "logical restore and read-only API acceptance; no infrastructure outage",
            "outage_at": outage_at.isoformat(),
            "latest_recoverable_committed_record_at": committed_at.isoformat(),
            "rto_seconds": (accepted_at - outage_at).total_seconds(),
            "rpo_seconds": (outage_at - committed_at).total_seconds(),
            "rto_target_seconds": 1800,
            "rpo_target_seconds": 86400,
        },
        "users": [
            {
                "id": user.id,
                "role": user.role,
                "account_status": user.account_status,
                "employment_status": user.employment_status,
                "join_date": str(user.join_date),
                "leave_date": str(user.leave_date) if user.leave_date else None,
            }
            for user in users
        ],
        "changes": [
            {
                "id": change.id,
                "type": change.change_type,
                "requester_id": change.requester_id,
                "approver_id": change.approver_id,
                "decision": change.decision,
                "status": change.status,
                "version": change.version_reference,
                "test_evidence": change.test_evidence,
                "rollback_plan": change.rollback_plan,
                "retrospective_review": change.retrospective_review,
            }
            for change in changes
        ],
        "access_reviews": [
            {
                "id": review.id,
                "population_snapshot": review.population_snapshot,
                "decisions": review.decisions,
            }
            for review in reviews
        ],
        "limitations": [
            "Historical rows are generated fixtures, not observed business history.",
            "Timing covers one logical restore on this machine, not full disaster recovery.",
            "The verifier added one clearly labelled synthetic checkpoint before backup.",
            "Raw backups and credentials remain restricted in the app runtime volume.",
        ],
    }
    await target_engine.dispose()
    await source_engine.dispose()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
