"""Change approval, emergency review, deployment and rollback workflows."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.audit import (
    emit_event,
)
from bank_lab.config import Settings
from bank_lab.models import (
    ChangeRecord,
    ChangeStatus,
    Decision,
    Role,
    User,
    utcnow,
)
from bank_lab.security import (
    aware,
)
from bank_lab.services.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)


def _add_business_days(start: datetime, days: int) -> datetime:
    """Return a deadline after ``days`` weekdays, preserving the time and timezone."""
    deadline = start
    remaining = days
    while remaining:
        deadline += timedelta(days=1)
        if deadline.weekday() < 5:
            remaining -= 1
    return deadline


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
