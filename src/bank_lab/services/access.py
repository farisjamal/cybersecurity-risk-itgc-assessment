"""Access approval, account activation, deactivation and periodic reviews."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.audit import (
    ROLE_CHANGE_RULE,
    emit_event,
    open_alert_once,
)
from bank_lab.config import Settings
from bank_lab.models import (
    AccessRequest,
    AccessReview,
    AccountStatus,
    Decision,
    EmploymentStatus,
    Role,
    Session,
    User,
    utcnow,
)
from bank_lab.services.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)


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
