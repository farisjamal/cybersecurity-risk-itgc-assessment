"""Structured audit event and alert generation."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.models import Alert, AlertStatus, AuditEvent

ROLE_CHANGE_RULE = "administrative-role-change"
LOGIN_FAILURE_RULE = "five-login-failures-five-minutes"


async def emit_event(
    db: AsyncSession,
    *,
    run_id: str,
    actor_id: str | None,
    action: str,
    object_type: str,
    object_id: str | None,
    result: str,
    correlation_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        run_id=run_id,
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        result=result,
        correlation_id=correlation_id or str(uuid4()),
        context=context or {},
    )
    db.add(event)
    await db.flush()
    return event


async def open_alert_once(
    db: AsyncSession,
    *,
    rule_id: str,
    severity: str,
    subject_key: str,
    event_ids: list[str],
) -> Alert:
    existing = (
        await db.execute(
            select(Alert).where(
                Alert.rule_id == rule_id,
                Alert.subject_key == subject_key,
                Alert.status == AlertStatus.OPEN,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        merged = list(dict.fromkeys([*existing.related_event_ids, *event_ids]))
        existing.related_event_ids = merged
        await db.flush()
        return existing
    alert = Alert(
        rule_id=rule_id,
        severity=severity,
        subject_key=subject_key,
        related_event_ids=event_ids,
    )
    db.add(alert)
    await db.flush()
    return alert
