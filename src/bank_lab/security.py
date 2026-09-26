"""Password, session, CSRF, and TOTP primitives.

Only hashes of opaque session and CSRF values are persisted. Authentication
errors intentionally remain generic at the HTTP boundary.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pyotp
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.config import Settings
from bank_lab.models import AccountStatus, Session, User

PASSWORD_HASH = PasswordHash.recommended()
_DUMMY_HASH = PASSWORD_HASH.hash("dummy-password-used-only-to-equalize-verification")


class AuthenticationError(Exception):
    """Authentication could not be completed."""


class SessionExpiredError(AuthenticationError):
    """Session is missing, revoked, idle, or absolutely expired."""


class CsrfError(AuthenticationError):
    """The CSRF proof did not match the active session."""


class MfaError(AuthenticationError):
    """MFA verification failed or a code was replayed."""


@dataclass(frozen=True)
class IssuedSession:
    record: Session
    token: str
    csrf_token: str


def now_utc() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, stored_hash: str | None) -> bool:
    candidate = stored_hash or _DUMMY_HASH
    try:
        valid = PASSWORD_HASH.verify(password, candidate)
    except Exception:
        valid = False
    return bool(stored_hash) and valid


def digest_secret(value: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), value.encode(), hashlib.sha256).hexdigest()


def constant_time_match(value: str, expected_hash: str, pepper: str) -> bool:
    return hmac.compare_digest(digest_secret(value, pepper), expected_hash)


def issue_session(user: User, settings: Settings, *, now: datetime | None = None) -> IssuedSession:
    issued_at = now or now_utc()
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    record = Session(
        token_hash=digest_secret(token, settings.session_pepper),
        csrf_hash=digest_secret(csrf_token, settings.session_pepper),
        user_id=user.id,
        issued_at=issued_at,
        last_activity_at=issued_at,
        expires_at=issued_at + timedelta(hours=settings.session_absolute_hours),
        mfa_verified=False,
    )
    return IssuedSession(record=record, token=token, csrf_token=csrf_token)


async def resolve_session(
    db: AsyncSession,
    token: str | None,
    settings: Settings,
    *,
    now: datetime | None = None,
    touch: bool = True,
) -> tuple[Session, User]:
    if not token:
        raise SessionExpiredError
    current = now or now_utc()
    token_hash = digest_secret(token, settings.session_pepper)
    record = (
        await db.execute(select(Session).where(Session.token_hash == token_hash))
    ).scalar_one_or_none()
    if record is None or record.revoked_at is not None:
        raise SessionExpiredError
    if aware(record.expires_at) <= current:
        raise SessionExpiredError
    if aware(record.last_activity_at) + timedelta(minutes=settings.session_idle_minutes) <= current:
        raise SessionExpiredError
    user = await db.get(User, record.user_id)
    if user is None or user.account_status != AccountStatus.ACTIVE:
        raise SessionExpiredError
    if touch:
        record.last_activity_at = current
        await db.flush()
    return record, user


def verify_csrf(
    record: Session, supplied: str | None, cookie: str | None, settings: Settings
) -> None:
    if not supplied or not cookie or not hmac.compare_digest(supplied, cookie):
        raise CsrfError
    if not constant_time_match(supplied, record.csrf_hash, settings.session_pepper):
        raise CsrfError


def matching_totp_counter(secret: str, code: str, at: datetime) -> int | None:
    totp = pyotp.TOTP(secret)
    base_counter = int(at.timestamp()) // totp.interval
    for counter in range(base_counter - 1, base_counter + 2):
        generated = totp.at(counter * totp.interval)
        if hmac.compare_digest(generated, code):
            return counter
    return None


def verify_totp(user: User, code: str, at: datetime | None = None) -> int:
    if not user.totp_secret:
        raise MfaError("MFA is not enrolled")
    counter = matching_totp_counter(user.totp_secret, code, at or now_utc())
    if counter is None:
        raise MfaError("Invalid MFA code")
    if user.totp_last_counter is not None and counter <= user.totp_last_counter:
        raise MfaError("MFA code was already used")
    return counter
