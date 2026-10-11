"""Transactional services for authentication and portal workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.audit import (
    LOGIN_FAILURE_RULE,
    ROLE_CHANGE_RULE,
    emit_event,
    open_alert_once,
)
from bank_lab.config import Settings
from bank_lab.models import (
    AccessRequest,
    AccessReview,
    AccountStatus,
    AuditEvent,
    ChangeRecord,
    ChangeStatus,
    Decision,
    EmploymentStatus,
    LoginFailure,
    Role,
    ServiceRequest,
    ServiceRequestHistory,
    ServiceRequestStatus,
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


class DomainError(Exception):
    """Base class for safe domain failures."""


class NotFoundError(DomainError):
    pass


class ForbiddenError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class InvalidCredentialsError(DomainError):
    pass


class LoginThrottledError(DomainError):
    pass


def _add_business_days(start: datetime, days: int) -> datetime:
    """Return a deadline after ``days`` weekdays, preserving the time and timezone."""
    deadline = start
    remaining = days
    while remaining:
        deadline += timedelta(days=1)
        if deadline.weekday() < 5:
            remaining -= 1
    return deadline


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


PRIVILEGED_ROLES = {Role.ADMINISTRATOR, Role.CHANGE_APPROVER}


def require_privileged_mfa(record: Session, user: User) -> None:
    if user.role not in PRIVILEGED_ROLES:
        raise ForbiddenError("Privileged role required")
    if not record.mfa_verified:
        raise ForbiddenError("MFA verification required")


def can_read_request(user: User, request: ServiceRequest) -> bool:
    if user.role in {Role.ADMINISTRATOR, Role.CHANGE_APPROVER, Role.READ_ONLY}:
        return True
    return user.role == Role.STAFF and user.id in {request.owner_id, request.assigned_staff_id}


def can_edit_request(user: User, request: ServiceRequest) -> bool:
    if user.role == Role.ADMINISTRATOR:
        return True
    return user.role == Role.STAFF and user.id in {request.owner_id, request.assigned_staff_id}


class ServiceRequestService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def list_for(self, user: User) -> list[ServiceRequest]:
        query = select(ServiceRequest).order_by(ServiceRequest.id)
        if user.role == Role.STAFF:
            query = query.where(
                or_(
                    ServiceRequest.owner_id == user.id,
                    ServiceRequest.assigned_staff_id == user.id,
                )
            )
        return list((await self.db.execute(query)).scalars())

    async def get_for(self, request_id: str, user: User) -> ServiceRequest:
        request = await self.db.get(ServiceRequest, request_id)
        if request is None or not can_read_request(user, request):
            raise NotFoundError("Service request not found")
        return request

    async def create(self, user: User, *, category: str, description: str) -> ServiceRequest:
        if user.role == Role.READ_ONLY:
            raise ForbiddenError("Read-only users cannot create requests")
        request = ServiceRequest(
            owner_id=user.id,
            assigned_staff_id=user.id if user.role == Role.STAFF else None,
            category=category.strip(),
            description=description.strip(),
        )
        self.db.add(request)
        await self.db.flush()
        self.db.add(
            ServiceRequestHistory(
                request_id=request.id,
                actor_id=user.id,
                action="created",
                new_status=request.status,
            )
        )
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=user.id,
            action="service_request.created",
            object_type="service_request",
            object_id=request.id,
            result="success",
        )
        await self.db.commit()
        return request

    async def transition(
        self,
        request_id: str,
        user: User,
        *,
        status: ServiceRequestStatus,
        reason: str | None = None,
    ) -> ServiceRequest:
        request = await self.get_for(request_id, user)
        if not can_edit_request(user, request):
            raise ForbiddenError("Request cannot be edited")
        current = ServiceRequestStatus(request.status)
        allowed = {
            ServiceRequestStatus.OPEN: {ServiceRequestStatus.IN_PROGRESS},
            ServiceRequestStatus.IN_PROGRESS: {ServiceRequestStatus.RESOLVED},
            ServiceRequestStatus.RESOLVED: {ServiceRequestStatus.OPEN},
        }
        if status not in allowed[current]:
            raise ConflictError("Invalid service-request transition")
        if current == ServiceRequestStatus.RESOLVED and not reason:
            raise ConflictError("Reopening requires a reason")
        request.status = status
        request.updated_at = utcnow()
        self.db.add(
            ServiceRequestHistory(
                request_id=request.id,
                actor_id=user.id,
                action="reopened" if current == ServiceRequestStatus.RESOLVED else "status_changed",
                previous_status=current,
                new_status=status,
                reason=reason,
            )
        )
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=user.id,
            action="service_request.updated",
            object_type="service_request",
            object_id=request.id,
            result="success",
            context={"from": current, "to": status, "reason": reason},
        )
        await self.db.commit()
        return request


class AccessService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def submit(
        self, requester: User, target: User, requested_role: Role, rationale: str
    ) -> AccessRequest:
        if requester.role == Role.READ_ONLY:
            raise ForbiddenError("Read-only users cannot submit access requests")
        request = AccessRequest(
            user_id=target.id,
            requested_role=requested_role,
            requester_id=requester.id,
            rationale=rationale,
        )
        self.db.add(request)
        await self.db.flush()
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=requester.id,
            action="access_request.submitted",
            object_type="access_request",
            object_id=request.id,
            result="success",
        )
        await self.db.commit()
        return request

    async def decide(self, request_id: str, approver: User, decision: Decision) -> AccessRequest:
        if approver.role != Role.CHANGE_APPROVER:
            raise ForbiddenError("Change approver role required")
        request = await self.db.get(AccessRequest, request_id)
        if request is None:
            raise NotFoundError("Access request not found")
        if request.decision != Decision.PENDING:
            raise ConflictError("Access request already decided")
        if request.requester_id == approver.id:
            raise ForbiddenError("Requester cannot approve their own request")
        request.decision = decision
        request.approver_id = approver.id
        request.decided_at = utcnow()
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=approver.id,
            action="access_request.decided",
            object_type="access_request",
            object_id=request.id,
            result=decision,
        )
        await self.db.commit()
        return request

    async def apply(self, request_id: str, administrator: User) -> User:
        if administrator.role != Role.ADMINISTRATOR:
            raise ForbiddenError("Administrator role required")
        request = await self.db.get(AccessRequest, request_id)
        if request is None:
            raise NotFoundError("Access request not found")
        if request.decision != Decision.APPROVED or request.applied_at is not None:
            raise ConflictError("Approved unapplied access request required")
        if request.user_id == administrator.id and request.requested_role == Role.ADMINISTRATOR:
            raise ForbiddenError("Administrators cannot elevate their own privilege")
        user = await self.db.get(User, request.user_id)
        if user is None:
            raise NotFoundError("User not found")
        if user.employment_status != EmploymentStatus.EMPLOYED:
            raise ConflictError("Access cannot be applied to a terminated employee")
        if user.join_date > utcnow().date():
            raise ConflictError("Access cannot be activated before the employment start date")
        if user.leave_date is not None and user.leave_date <= utcnow().date():
            raise ConflictError("Access cannot be activated after the employment end date")
        previous = user.role
        user.role = request.requested_role
        user.account_status = AccountStatus.ACTIVE
        request.applied_at = utcnow()
        await self.db.execute(
            update(Session)
            .where(Session.user_id == user.id, Session.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        event = await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=administrator.id,
            action="user.role_changed",
            object_type="user",
            object_id=user.id,
            result="success",
            context={"previous_role": previous, "new_role": user.role},
        )
        if user.role == Role.ADMINISTRATOR:
            await open_alert_once(
                self.db,
                rule_id=ROLE_CHANGE_RULE,
                severity="high",
                subject_key=user.id,
                event_ids=[event.id],
            )
        await self.db.commit()
        return user

    async def deactivate(self, user_id: str, administrator: User, reason: str) -> User:
        if administrator.role != Role.ADMINISTRATOR:
            raise ForbiddenError("Administrator role required")
        if administrator.id == user_id:
            raise ForbiddenError("Administrator cannot deactivate own account")
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        user.account_status = AccountStatus.DISABLED
        now = utcnow()
        await self.db.execute(
            update(Session)
            .where(Session.user_id == user.id, Session.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=administrator.id,
            action="user.deactivated",
            object_type="user",
            object_id=user.id,
            result="success",
            context={"reason": reason},
        )
        await self.db.commit()
        return user

    async def record_review(
        self,
        reviewer: User,
        period: str,
        decisions: list[dict[str, Any]],
        action_references: list[str] | None = None,
    ) -> AccessReview:
        if reviewer.role != Role.CHANGE_APPROVER:
            raise ForbiddenError("Change approver role required")
        users = list((await self.db.execute(select(User).order_by(User.id))).scalars())
        reviewed = {str(item.get("user_id")) for item in decisions}
        population = {user.id for user in users}
        if reviewed != population:
            raise ConflictError("Access review must cover the complete account population")
        review = AccessReview(
            period=period,
            population_snapshot={
                "count": len(users),
                "user_ids": sorted(population),
                "captured_at": utcnow().isoformat(),
            },
            reviewer_role=reviewer.role,
            decisions=decisions,
            action_references=action_references or [],
            completed_at=utcnow(),
        )
        self.db.add(review)
        await self.db.flush()
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=reviewer.id,
            action="access_review.completed",
            object_type="access_review",
            object_id=review.id,
            result="success",
            context={"period": period, "population_count": len(users)},
        )
        await self.db.commit()
        return review


class ChangeService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def submit(
        self,
        requester: User,
        *,
        change_type: str,
        version_reference: str,
        description: str,
        test_evidence: str | None,
        rollback_plan: str | None,
        emergency_reason: str | None = None,
    ) -> ChangeRecord:
        if requester.role == Role.READ_ONLY:
            raise ForbiddenError("Read-only users cannot submit changes")
        if change_type == "normal" and (not test_evidence or not rollback_plan):
            raise ConflictError("Normal changes require test evidence and a rollback plan")
        if change_type == "emergency" and not emergency_reason:
            raise ConflictError("Emergency changes require a reason")
        if change_type not in {"normal", "emergency"}:
            raise ConflictError("Unsupported change type")
        submitted_at = utcnow()
        change = ChangeRecord(
            requester_id=requester.id,
            change_type=change_type,
            version_reference=version_reference,
            description=description,
            test_evidence=test_evidence,
            rollback_plan=rollback_plan,
            emergency_reason=emergency_reason,
            status=ChangeStatus.SUBMITTED,
            retrospective_due_at=_add_business_days(submitted_at, 2)
            if change_type == "emergency"
            else None,
        )
        self.db.add(change)
        await self.db.flush()
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=requester.id,
            action="change.submitted",
            object_type="change",
            object_id=change.id,
            result="success",
        )
        await self.db.commit()
        return change

    async def record_emergency_review(
        self, change_id: str, reviewer: User, review: str
    ) -> ChangeRecord:
        if reviewer.role != Role.CHANGE_APPROVER:
            raise ForbiddenError("Change approver role required")
        change = await self.db.get(ChangeRecord, change_id)
        if change is None:
            raise NotFoundError("Change not found")
        if change.change_type != "emergency":
            raise ConflictError("Retrospective review applies only to emergency changes")
        if change.requester_id == reviewer.id:
            raise ForbiddenError("Requester cannot review their own emergency change")
        if change.retrospective_review is not None:
            raise ConflictError("Emergency change already has a retrospective review")
        if not review.strip():
            raise ConflictError("Retrospective review text is required")

        reviewed_at = utcnow()
        history = [*change.decision_history]
        history.append(
            {
                "reviewer_id": reviewer.id,
                "decision": "retrospective_reviewed",
                "reason": review.strip(),
                "at": reviewed_at.isoformat(),
                "within_target": bool(
                    change.retrospective_due_at
                    and reviewed_at <= aware(change.retrospective_due_at)
                ),
            }
        )
        change.decision_history = history
        change.retrospective_review = review.strip()
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=reviewer.id,
            action="change.emergency_reviewed",
            object_type="change",
            object_id=change.id,
            result="success",
            context={"within_target": history[-1]["within_target"]},
        )
        await self.db.commit()
        return change

    async def decide(
        self, change_id: str, approver: User, decision: Decision, reason: str
    ) -> ChangeRecord:
        if approver.role != Role.CHANGE_APPROVER:
            raise ForbiddenError("Change approver role required")
        change = await self.db.get(ChangeRecord, change_id)
        if change is None:
            raise NotFoundError("Change not found")
        if change.requester_id == approver.id:
            raise ForbiddenError("Requester cannot approve their own change")
        if change.status != ChangeStatus.SUBMITTED:
            raise ConflictError("Submitted change required")
        if (
            decision == Decision.APPROVED
            and change.change_type == "normal"
            and (not change.test_evidence or not change.rollback_plan)
        ):
            raise ConflictError("Test evidence and rollback plan are required")
        history = [*change.decision_history]
        history.append(
            {
                "approver_id": approver.id,
                "decision": decision,
                "reason": reason,
                "at": utcnow().isoformat(),
            }
        )
        change.decision_history = history
        change.decision = decision
        change.approver_id = approver.id
        change.status = (
            ChangeStatus.APPROVED if decision == Decision.APPROVED else ChangeStatus.REJECTED
        )
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=approver.id,
            action="change.decided",
            object_type="change",
            object_id=change.id,
            result=decision,
        )
        await self.db.commit()
        return change

    async def deploy(
        self, change_id: str, operator: User, observed_version: str, smoke_test: str
    ) -> ChangeRecord:
        if operator.role != Role.ADMINISTRATOR:
            raise ForbiddenError("Administrator role required")
        change = await self.db.get(ChangeRecord, change_id)
        if change is None:
            raise NotFoundError("Change not found")
        if change.status != ChangeStatus.APPROVED or not smoke_test:
            raise ConflictError("Approved change and smoke test are required")
        change.status = ChangeStatus.DEPLOYED
        change.deployed_version = observed_version
        change.deployed_at = utcnow()
        change.finalized = True
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=operator.id,
            action="change.deployed",
            object_type="change",
            object_id=change.id,
            result="success",
            context={"observed_version": observed_version, "smoke_test": smoke_test},
        )
        await self.db.commit()
        return change

    async def record_rollback(self, change_id: str, operator: User, record: str) -> ChangeRecord:
        if operator.role != Role.ADMINISTRATOR:
            raise ForbiddenError("Administrator role required")
        change = await self.db.get(ChangeRecord, change_id)
        if change is None:
            raise NotFoundError("Change not found")
        if change.status != ChangeStatus.DEPLOYED:
            raise ConflictError("Only deployed changes can be rolled back")
        change.status = ChangeStatus.ROLLED_BACK
        change.rollback_record = record
        await emit_event(
            self.db,
            run_id=self.settings.run_id,
            actor_id=operator.id,
            action="change.rolled_back",
            object_type="change",
            object_id=change.id,
            result="success",
        )
        await self.db.commit()
        return change


async def list_events(db: AsyncSession, *, run_id: str | None = None) -> list[AuditEvent]:
    query = select(AuditEvent).order_by(AuditEvent.occurred_at, AuditEvent.id)
    if run_id:
        query = query.where(AuditEvent.run_id == run_id)
    return list((await db.execute(query)).scalars())


def correlation_id() -> str:
    return str(uuid4())
