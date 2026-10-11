import os
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pyotp
import pytest
from httpx import ASGITransport, AsyncClient

from bank_lab.app import create_app
from bank_lab.config import Settings
from bank_lab.database import Base
from bank_lab.models import AuditEvent, User
from bank_lab.security import hash_password
from bank_lab.seed import seed_database

PASSWORD = "Synthetic-Portal-Password-42!"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"


@pytest.fixture
async def portal(tmp_path: Path) -> AsyncIterator[tuple[AsyncClient, object]]:
    database_url = os.environ.get("BANK_LAB_DATABASE_URL") or (
        f"sqlite+aiosqlite:///{tmp_path / 'portal.db'}"
    )
    settings = Settings(
        database_url=database_url,
        session_pepper="integration-session-pepper",
        templates_dir=Path("templates"),
        auto_create_schema=False,
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with app.state.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        async with app.state.session_factory() as session:
            with patch("bank_lab.seed.hash_password", side_effect=lambda value: f"test:{value}"):
                await seed_database(
                    session,
                    password_factory=lambda: PASSWORD,
                    totp_factory=lambda: TOTP_SECRET,
                )
            for user_id in ("USR-001", "USR-007", "USR-019"):
                account = await session.get(User, user_id)
                assert account
                account.password_hash = hash_password(PASSWORD)
            await session.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, app


async def login(client: AsyncClient, email: str) -> dict[str, object]:
    response = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()


def csrf_header(client: AsyncClient) -> dict[str, str]:
    token = client.cookies.get("bank_csrf")
    assert token
    return {"X-CSRF-Token": token}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_csrf_mfa_and_privileged_endpoint(portal: tuple[AsyncClient, object]) -> None:
    client, _app = portal
    body = await login(client, "user01@example.test")
    assert body["mfa_required"] is True
    denied = await client.get("/events")
    assert denied.status_code == 403
    no_csrf = await client.post("/auth/mfa", json={"code": "000000"})
    assert no_csrf.status_code == 403
    code = pyotp.TOTP(TOTP_SECRET).now()
    verified = await client.post("/auth/mfa", json={"code": code}, headers=csrf_header(client))
    assert verified.status_code == 200
    replay = await client.post("/auth/mfa", json={"code": code}, headers=csrf_header(client))
    assert replay.status_code == 401
    events = await client.get("/events")
    assert events.status_code == 200
    assert any(item["action"] == "authentication.mfa" for item in events.json())


@pytest.mark.integration
@pytest.mark.asyncio
async def test_staff_object_scope_and_read_only_mutation_denial(
    portal: tuple[AsyncClient, object],
) -> None:
    client, _app = portal
    await login(client, "user07@example.test")
    visible = await client.get("/requests")
    assert visible.status_code == 200
    assert visible.json()
    inaccessible = next(
        number
        for number in range(1, 51)
        if f"REQ-{number:03d}" not in {item["id"] for item in visible.json()}
    )
    hidden = await client.get(f"/requests/REQ-{inaccessible:03d}")
    assert hidden.status_code == 404
    created = await client.post(
        "/requests",
        json={"category": "test", "description": "Synthetic integration request."},
        headers=csrf_header(client),
    )
    assert created.status_code == 201

    client.cookies.clear()
    await login(client, "user19@example.test")
    denied = await client.post(
        "/requests",
        json={"category": "test", "description": "Must not persist."},
        headers=csrf_header(client),
    )
    assert denied.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_five_failed_logins_throttle_and_raise_alert(
    portal: tuple[AsyncClient, object],
) -> None:
    client, app = portal
    for _ in range(5):
        response = await client.post(
            "/auth/login",
            json={"email": "user07@example.test", "password": "wrong-password"},
        )
        assert response.status_code == 401
    blocked = await client.post(
        "/auth/login",
        json={"email": "user07@example.test", "password": PASSWORD},
    )
    assert blocked.status_code == 401
    async with app.state.session_factory() as session:
        from sqlalchemy import select

        from bank_lab.models import Alert

        alerts = list((await session.execute(select(Alert))).scalars())
        assert len(alerts) == 1
        assert alerts[0].rule_id == "five-login-failures-five-minutes"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deactivation_invalidates_existing_cookie_and_new_login(
    portal: tuple[AsyncClient, object],
) -> None:
    staff_client, app = portal
    await login(staff_client, "user07@example.test")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as admin:
        await login(admin, "user01@example.test")
        code = pyotp.TOTP(TOTP_SECRET).now()
        assert (
            await admin.post("/auth/mfa", json={"code": code}, headers=csrf_header(admin))
        ).status_code == 200
        response = await admin.post(
            "/admin/users/USR-007/deactivate",
            json={"reason": "Synthetic leaver event"},
            headers=csrf_header(admin),
        )
        assert response.status_code == 200
    assert (await staff_client.get("/requests")).status_code == 401
    staff_client.cookies.clear()
    assert (
        await staff_client.post(
            "/auth/login", json={"email": "user07@example.test", "password": PASSWORD}
        )
    ).status_code == 401


@pytest.mark.integration
@pytest.mark.acceptance
@pytest.mark.asyncio
async def test_ten_thousand_audit_events_remain_attributable_and_are_not_truncated(
    portal: tuple[AsyncClient, object],
) -> None:
    client, app = portal
    async with app.state.session_factory() as session:
        session.add_all(
            [
                AuditEvent(
                    id=f"CAPACITY-{number:05d}",
                    run_id="RUN-CAPACITY",
                    actor_id="USR-001",
                    action="capacity.observed",
                    object_type="synthetic_record",
                    object_id=str(number),
                    result="success",
                    correlation_id=f"CORR-{number:05d}",
                )
                for number in range(10000)
            ]
        )
        await session.commit()
    await login(client, "user01@example.test")
    verified = await client.post(
        "/auth/mfa", json={"code": pyotp.TOTP(TOTP_SECRET).now()}, headers=csrf_header(client)
    )
    assert verified.status_code == 200
    response = await client.get("/events", params={"run_id": "RUN-CAPACITY"})
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 10000
    assert len({event["correlation_id"] for event in events}) == 10000
    assert {event["actor_id"] for event in events} == {"USR-001"}
