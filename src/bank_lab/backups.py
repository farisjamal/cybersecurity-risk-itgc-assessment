"""Portable logical backup, hash validation, and isolated restore support."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.database import Base
from bank_lab.models import (
    AccessRequest,
    AccessReview,
    BackupRun,
    ChangeRecord,
    Incident,
    RunStatus,
    ServiceRequest,
    ServiceRequestHistory,
    User,
    utcnow,
)

BACKUP_SCHEMA = "bank-lab-backup/1.0"
BACKUP_MODELS = (
    User,
    ServiceRequest,
    ServiceRequestHistory,
    AccessRequest,
    AccessReview,
    ChangeRecord,
    Incident,
)


class BackupError(Exception):
    """Backup validation or restoration failed safely."""


@dataclass(frozen=True)
class BackupResult:
    record_id: str
    path: Path
    sha256: str
    counts: dict[str, int]


@dataclass(frozen=True)
class RestoreResult:
    valid: bool
    counts: dict[str, int]
    started_at: datetime
    ended_at: datetime


def _encode(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _row(model: type[Any], instance: Any) -> dict[str, Any]:
    return {
        column.name: _encode(getattr(instance, column.name)) for column in model.__table__.columns
    }


def _safe_path(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise BackupError("backup path escapes the configured output root") from exc
    return candidate_resolved


async def create_backup(
    db: AsyncSession,
    output_root: Path,
    run_id: str,
    *,
    dataset_reference: str = "bank-lab-business-data",
) -> BackupResult:
    await asyncio.to_thread(output_root.mkdir, parents=True, exist_ok=True)
    record = BackupRun(
        run_id=run_id,
        dataset_reference=dataset_reference,
        status=RunStatus.STARTED,
    )
    db.add(record)
    await db.flush()
    tables: dict[str, list[dict[str, Any]]] = {}
    for model in BACKUP_MODELS:
        rows = list((await db.execute(select(model).order_by(model.id))).scalars())
        tables[model.__tablename__] = [_row(model, item) for item in rows]
    payload = {
        "schema": BACKUP_SCHEMA,
        "run_id": run_id,
        "dataset_reference": dataset_reference,
        "tables": tables,
    }
    content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    path = _safe_path(output_root, output_root / f"backup-{record.id}.json")
    await asyncio.to_thread(path.write_bytes, content)
    written = await asyncio.to_thread(path.read_bytes)
    if hashlib.sha256(written).hexdigest() != digest:
        record.status = RunStatus.FAILED
        record.validation_result = {"verified": False, "reason": "post-write hash mismatch"}
        record.ended_at = utcnow()
        await db.commit()
        raise BackupError("backup failed post-write verification")
    record.artifact_path = str(path)
    record.artifact_sha256 = digest
    record.status = RunStatus.COMPLETED
    record.validation_result = {"verified": True, "schema": BACKUP_SCHEMA}
    record.ended_at = utcnow()
    await db.commit()
    return BackupResult(
        record_id=record.id,
        path=path,
        sha256=digest,
        counts={name: len(rows) for name, rows in tables.items()},
    )


def load_and_validate_backup(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not path.is_file():
        raise BackupError("backup artifact does not exist")
    content = path.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if not expected_sha256 or not hmac.compare_digest(actual, expected_sha256):
        raise BackupError("backup hash validation failed")
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("backup is not valid JSON") from exc
    if payload.get("schema") != BACKUP_SCHEMA or not isinstance(payload.get("tables"), dict):
        raise BackupError("unsupported backup schema")
    expected_tables = {model.__tablename__ for model in BACKUP_MODELS}
    if set(payload["tables"]) != expected_tables:
        raise BackupError("backup table set is incomplete or unexpected")
    return cast(dict[str, Any], payload)


def _decode_row(model: type[Any], row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    for column in model.__table__.columns:
        value = result.get(column.name)
        if value is None:
            continue
        if isinstance(column.type, type(User.__table__.c.join_date.type)):
            result[column.name] = date.fromisoformat(value)
        elif isinstance(column.type, type(User.__table__.c.created_at.type)):
            result[column.name] = datetime.fromisoformat(value)
    return result


def _comparable_row(model: type[Any], row: dict[str, Any]) -> dict[str, Any]:
    """Compare logical values across SQLite and PostgreSQL timezone representations."""
    decoded = _decode_row(model, row)
    return {
        key: (
            value.replace(tzinfo=UTC).isoformat()
            if isinstance(value, datetime) and value.tzinfo is None
            else value.astimezone(UTC).isoformat()
            if isinstance(value, datetime)
            else value
        )
        for key, value in decoded.items()
    }


async def restore_test(
    target_db: AsyncSession,
    backup_path: Path,
    expected_sha256: str,
) -> RestoreResult:
    """Restore into a caller-provided isolated, empty database session."""

    started = utcnow()
    payload = load_and_validate_backup(backup_path, expected_sha256)
    # Refuse to erase data even if a caller accidentally supplies the source DB.
    for table in Base.metadata.sorted_tables:
        count = (await target_db.execute(select(func.count()).select_from(table))).scalar_one()
        if count:
            raise BackupError("restore target must be an empty isolated database")
    counts: dict[str, int] = {}
    try:
        for model in BACKUP_MODELS:
            rows = payload["tables"][model.__tablename__]
            target_db.add_all([model(**_decode_row(model, row)) for row in rows])
            await target_db.flush()
            restored = list(
                (
                    await target_db.execute(
                        select(model).order_by(model.id).execution_options(populate_existing=True)
                    )
                ).scalars()
            )
            counts[model.__tablename__] = len(restored)
            expected_rows = sorted(rows, key=lambda row: row["id"])
            actual_values = [_comparable_row(model, _row(model, item)) for item in restored]
            expected_values = [_comparable_row(model, item) for item in expected_rows]
            if actual_values != expected_values:
                raise BackupError("restored business records do not reconcile to the backup")
        await target_db.commit()
    except Exception as exc:
        await target_db.rollback()
        raise BackupError("isolated restore failed") from exc
    return RestoreResult(valid=True, counts=counts, started_at=started, ended_at=utcnow())
