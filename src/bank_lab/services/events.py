"""Ordered audit-event reads and correlation identifier generation."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.models import (
    AuditEvent,
)


async def list_events(db: AsyncSession, *, run_id: str | None = None) -> list[AuditEvent]:
    query = select(AuditEvent).order_by(AuditEvent.occurred_at, AuditEvent.id)
    if run_id:
        query = query.where(AuditEvent.run_id == run_id)
    return list((await db.execute(query)).scalars())


def correlation_id() -> str:
    return str(uuid4())
