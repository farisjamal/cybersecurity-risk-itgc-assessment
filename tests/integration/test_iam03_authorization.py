"""Current HTTP authorization checks against the implemented lab role rules.

These rules are observed implementation expectations, not an owner-approved matrix.
Every case creates its own SQLite database and never uses a configured lab database.
"""

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pyotp
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from bank_lab.app import create_app
from bank_lab.config import Settings
from bank_lab.database import Base
from bank_lab.models import ServiceRequest, ServiceRequestHistory, User
from bank_lab.security import hash_password
from bank_lab.seed import seed_database

PASSWORD = "Synthetic-IAM03-Test-Password!"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"
pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def isolated_portal(tmp_path: Path) -> AsyncIterator[tuple[AsyncClient, FastAPI]]:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'iam03.db'}",
        environment="test",
        scenario_id=None,
        cookie_secure=False,
        session_pepper="iam03-disposable-test-pepper",
        run_id="RUN-IAM03-TEST",
        auto_create_schema=False,
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with app.state.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with app.state.session_factory() as session:
            password_hash = hash_password(PASSWORD)
            with patch("bank_lab.seed.hash_password", return_value=password_hash):
                await seed_database(
                    session, password_factory=lambda: PASSWORD, totp_factory=lambda: TOTP_SECRET
                )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, app


def csrf(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": str(client.cookies["bank_csrf"])}


async def sign_in(client: AsyncClient, number: int, *, mfa: bool = True) -> None:
    response = await client.post(
        "/auth/login", json={"email": f"user{number:02d}@example.test", "password": PASSWORD}
    )
    assert response.status_code == 200
    if response.json()["mfa_required"] and mfa:
        verified = await client.post(
            "/auth/mfa", json={"code": pyotp.TOTP(TOTP_SECRET).now()}, headers=csrf(client)
        )
        assert verified.status_code == 200


@pytest.mark.parametrize("number", [1, 2, 3, 4, 5, 6, 7, 19])
async def test_privileged_account_endpoint_boundaries(
    isolated_portal: tuple[AsyncClient, FastAPI], number: int
) -> None:
    client, app = isolated_portal
    await sign_in(client, number, mfa=False)
    assert (await client.get("/admin/users", headers=csrf(client))).status_code == 403
    assert (await client.get("/events")).status_code == 403
    if number <= 6:
        verified = await client.post(
            "/auth/mfa", json={"code": pyotp.TOTP(TOTP_SECRET).now()}, headers=csrf(client)
        )
        assert verified.status_code == 200
        assert (await client.get("/events")).status_code == 200

    users = await client.get("/admin/users", headers=csrf(client))
    if number <= 2:
        assert users.status_code == 200
        assert len(users.json()) == 24
    else:
        assert users.status_code == 403
        if number <= 6:
            assert users.json()["detail"] == "Administrator role required"
        denied = await client.post(
            "/admin/users/USR-008/deactivate",
            json={"reason": "Synthetic prohibited role attempt"},
            headers=csrf(client),
        )
        assert denied.status_code == 403
        async with app.state.session_factory() as session:
            target = await session.get(User, "USR-008")
            assert target and target.account_status == "active"


@pytest.mark.parametrize("number", [1, 3, 7, 19])
@pytest.mark.parametrize("relation", ["owner", "assigned", "unrelated"])
async def test_request_scope_and_mutation_matrix(
    isolated_portal: tuple[AsyncClient, FastAPI], number: int, relation: str
) -> None:
    client, app = isolated_portal
    user_id = f"USR-{number:03d}"
    async with app.state.session_factory() as session:
        session.add(
            ServiceRequest(
                id="MATRIX-REQ",
                owner_id=user_id if relation == "owner" else "USR-009",
                assigned_staff_id=user_id if relation == "assigned" else "USR-010",
                category="synthetic-matrix",
                description="Disposable authorization exercise",
                status="open",
            )
        )
        await session.commit()
    await sign_in(client, number)
    visible = await client.get("/requests")
    assert visible.status_code == 200
    allowed_read = number not in {7, 19} or relation != "unrelated"
    assert ("MATRIX-REQ" in {item["id"] for item in visible.json()}) == allowed_read
    if number in {7, 19}:
        assert all(
            user_id in {item["owner_id"], item["assigned_staff_id"]} for item in visible.json()
        )
    detail = await client.get("/requests/MATRIX-REQ")
    assert detail.status_code == (200 if allowed_read else 404)
    changed = await client.patch(
        "/requests/MATRIX-REQ", json={"status": "in_progress"}, headers=csrf(client)
    )
    allowed_edit = number == 1 or (number == 7 and relation != "unrelated")
    assert changed.status_code == (200 if allowed_edit else (403 if allowed_read else 404))
    async with app.state.session_factory() as session:
        record = await session.get(ServiceRequest, "MATRIX-REQ")
        assert record and record.status == ("in_progress" if allowed_edit else "open")
        history_count = await session.scalar(
            select(func.count())
            .select_from(ServiceRequestHistory)
            .where(ServiceRequestHistory.request_id == "MATRIX-REQ")
        )
        assert history_count == int(allowed_edit)
    if number == 19:
        created = await client.post(
            "/requests",
            json={"category": "denied", "description": "Read-only creation must be denied"},
            headers=csrf(client),
        )
        assert created.status_code == 403
