from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from pydantic import ValidationError

from bank_lab.config import Settings
from bank_lab.models import AccountStatus, Role, ServiceRequest, Session, User
from bank_lab.security import (
    CsrfError,
    MfaError,
    digest_secret,
    hash_password,
    issue_session,
    verify_csrf,
    verify_password,
    verify_totp,
)
from bank_lab.services import can_edit_request, can_read_request, require_privileged_mfa


def user(role: Role = Role.STAFF) -> User:
    return User(
        id="USR-T",
        name="Fictional Tester",
        email="tester@example.test",
        password_hash="unused",
        role=role,
        account_status=AccountStatus.ACTIVE,
        join_date=datetime(2026, 1, 1).date(),
    )


def test_argon2_password_hash_and_generic_verification() -> None:
    encoded = hash_password("Correct-Horse-Example-42!")
    assert encoded.startswith("$argon2")
    assert verify_password("Correct-Horse-Example-42!", encoded)
    assert not verify_password("wrong", encoded)
    assert not verify_password("wrong", None)
    with pytest.raises(ValueError, match="at least 12"):
        hash_password("short")


def test_opaque_session_and_csrf_values_are_only_stored_as_hashes() -> None:
    settings = Settings(session_pepper="test-pepper")
    issued = issue_session(user(), settings, now=datetime(2026, 9, 25, tzinfo=UTC))
    assert issued.token not in issued.record.token_hash
    assert issued.csrf_token not in issued.record.csrf_hash
    assert issued.record.token_hash == digest_secret(issued.token, settings.session_pepper)
    verify_csrf(issued.record, issued.csrf_token, issued.csrf_token, settings)
    with pytest.raises(CsrfError):
        verify_csrf(issued.record, "wrong", issued.csrf_token, settings)


def test_totp_replay_counter_is_rejected() -> None:
    at = datetime(2026, 9, 25, 8, 30, tzinfo=UTC)
    account = user(Role.ADMINISTRATOR)
    account.totp_secret = pyotp.random_base32()
    code = pyotp.TOTP(account.totp_secret).at(at)
    counter = verify_totp(account, code, at)
    account.totp_last_counter = counter
    with pytest.raises(MfaError, match="already used"):
        verify_totp(account, code, at)


def test_privileged_action_requires_verified_mfa() -> None:
    account = user(Role.ADMINISTRATOR)
    record = Session(
        token_hash="a" * 64,
        csrf_hash="b" * 64,
        user_id=account.id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        mfa_verified=False,
    )
    with pytest.raises(Exception, match="MFA verification required"):
        require_privileged_mfa(record, account)
    record.mfa_verified = True
    require_privileged_mfa(record, account)


@pytest.mark.parametrize(
    ("role", "owner", "assigned", "read", "edit"),
    [
        (Role.ADMINISTRATOR, False, False, True, True),
        (Role.CHANGE_APPROVER, False, False, True, False),
        (Role.READ_ONLY, False, False, True, False),
        (Role.STAFF, True, False, True, True),
        (Role.STAFF, False, True, True, True),
        (Role.STAFF, False, False, False, False),
    ],
)
def test_object_authorization_matrix(
    role: Role, owner: bool, assigned: bool, read: bool, edit: bool
) -> None:
    account = user(role)
    request = ServiceRequest(
        id="REQ-X",
        owner_id=account.id if owner else "OTHER",
        assigned_staff_id=account.id if assigned else "ASSIGNEE",
        category="synthetic",
        description="Synthetic test request.",
    )
    assert can_read_request(account, request) is read
    assert can_edit_request(account, request) is edit


def test_scenario_configuration_cannot_leak_into_default_environment() -> None:
    with pytest.raises(ValidationError, match="scenario_id"):
        Settings(environment="development", scenario_id="S03")
    with pytest.raises(ValidationError, match="secure cookies"):
        Settings(environment="production", cookie_secure=False)
