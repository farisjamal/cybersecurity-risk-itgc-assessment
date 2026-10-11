"""Service-request ownership policy, creation and status transitions."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.audit import (
    emit_event,
)
from bank_lab.config import Settings
from bank_lab.models import (
    Role,
    ServiceRequest,
    ServiceRequestHistory,
    ServiceRequestStatus,
    User,
    utcnow,
)
from bank_lab.services.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)


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
