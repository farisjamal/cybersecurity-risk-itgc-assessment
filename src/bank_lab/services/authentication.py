"""Login throttling, session lifecycle and privileged MFA policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.audit import (
    LOGIN_FAILURE_RULE,
    emit_event,
    open_alert_once,
)
from bank_lab.config import Settings
from bank_lab.models import (
    AccountStatus,
    LoginFailure,
    Role,
    Session,
    User,
    utcnow,
)
from bank_lab.security import (
    IssuedSession,
    MfaError,
    aware,
    issue_session,
    now_utc,
    verify_password,
    verify_totp,
)
from bank_lab.services.errors import (
    ForbiddenError,
    InvalidCredentialsError,
    LoginThrottledError,
)

PRIVILEGED_ROLES = {Role.ADMINISTRATOR, Role.CHANGE_APPROVER}


@dataclass(frozen=True)
class AuthResult:
    session: IssuedSession
    mfa_required: bool


class AuthService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def login(
        self,
        email: str,
        password: str,
        *,
        source_ip: str = "unknown",
        correlation_id: str | None = None,
        now: datetime | None = None,
    ) -> AuthResult:
        current = now or now_utc()
        key = email.strip().casefold()
        window_start = current - timedelta(minutes=self.settings.login_window_minutes)
        recent_failures = int(
            (
                await self.db.execute(
                    select(func.count(LoginFailure.id)).where(
                        LoginFailure.account_key == key,
                        LoginFailure.occurred_at >= window_start,
                    )
                )
            ).scalar_one()
        )
        if recent_failures >= self.settings.login_failure_limit:
            raise LoginThrottledError("Authentication temporarily unavailable")

        user = (
            await self.db.execute(select(User).where(func.lower(User.email) == key))
        ).scalar_one_or_none()
        valid = verify_password(password, user.password_hash if user else None)
        if not valid or user is None or user.account_status != AccountStatus.ACTIVE:
            failure = LoginFailure(account_key=key, source_ip=source_ip, occurred_at=current)
            self.db.add(failure)
            event = await emit_event(
                self.db,
                run_id=self.settings.run_id,
                actor_id=user.id if user else None,
                action="authentication.login",
                object_type="user",
                object_id=user.id if user else None,
                result="failure",
                correlation_id=correlation_id,
                context={"account_key": key, "source_ip": source_ip},
            )
            if recent_failures + 1 >= self.settings.login_failure_limit:
                await open_alert_once(
                    self.db,
                    rule_id=LOGIN_FAILURE_RULE,
                    severity="medium",
                    subject_key=key,
                    event_ids=[event.id],
                )
            await self.db.commit()
            raise InvalidCredentialsError("Invalid email or password")

        issued = issue_session(user, self.settings, now=current)
        self.db.add(issued.record)
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=user.id,
            action="authentication.login",
            object_type="session",
            object_id=issued.record.id,
            result="success",
            correlation_id=correlation_id,
            context={"source_ip": source_ip, "mfa_pending": user.role in PRIVILEGED_ROLES},
        )
        await self.db.commit()
        return AuthResult(session=issued, mfa_required=user.role in PRIVILEGED_ROLES)

    async def complete_mfa(
        self,
        record: Session,
        user: User,
        code: str,
        *,
        now: datetime | None = None,
    ) -> None:
        current = now or now_utc()
        if record.mfa_blocked_until and aware(record.mfa_blocked_until) > current:
            raise MfaError("MFA verification temporarily blocked")
        try:
            counter = verify_totp(user, code, current)
        except MfaError:
            record.mfa_failures += 1
            if record.mfa_failures >= 5:
                record.mfa_blocked_until = current + timedelta(minutes=5)
            await emit_event(
                self.db,
                run_id=self.settings.run_id,
                actor_id=user.id,
                action="authentication.mfa",
                object_type="session",
                object_id=record.id,
                result="failure",
            )
            await self.db.commit()
            raise
        user.totp_last_counter = counter
        record.mfa_verified = True
        record.mfa_failures = 0
        record.mfa_blocked_until = None
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=user.id,
            action="authentication.mfa",
            object_type="session",
            object_id=record.id,
            result="success",
        )
        await self.db.commit()

    async def logout(self, record: Session, user: User) -> None:
        record.revoked_at = utcnow()
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=user.id,
            action="authentication.logout",
            object_type="session",
            object_id=record.id,
            result="success",
        )
        await self.db.commit()


def require_privileged_mfa(record: Session, user: User) -> None:
    if user.role not in PRIVILEGED_ROLES:
        raise ForbiddenError("Privileged role required")
    if not record.mfa_verified:
        raise ForbiddenError("MFA verification required")
