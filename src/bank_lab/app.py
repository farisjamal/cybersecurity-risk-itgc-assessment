"""FastAPI application factory and thin HTTP adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, cast
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bank_lab.config import Settings
from bank_lab.database import Base, build_engine, build_session_factory, get_db
from bank_lab.models import (
    AccessRequest,
    Alert,
    ChangeRecord,
    Decision,
    Role,
    ServiceRequest,
    ServiceRequestStatus,
    Session,
    User,
)
from bank_lab.security import (
    AuthenticationError,
    CsrfError,
    MfaError,
    resolve_session,
    verify_csrf,
)
from bank_lab.services import (
    AccessService,
    AuthService,
    ChangeService,
    ConflictError,
    ForbiddenError,
    InvalidCredentialsError,
    LoginThrottledError,
    NotFoundError,
    ServiceRequestService,
    list_events,
    require_privileged_mfa,
)

SESSION_COOKIE = "bank_session"
CSRF_COOKIE = "bank_csrf"


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class MfaInput(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class RequestCreate(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=4000)


class RequestTransition(BaseModel):
    status: ServiceRequestStatus
    reason: str | None = Field(default=None, max_length=1000)


class AccessCreate(BaseModel):
    user_id: str
    requested_role: Role
    rationale: str = Field(min_length=1, max_length=2000)


class DecisionInput(BaseModel):
    decision: Decision
    reason: str = Field(default="Decision recorded", min_length=1, max_length=2000)


class DeactivateInput(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ChangeCreate(BaseModel):
    change_type: str = Field(pattern=r"^(normal|emergency)$")
    version_reference: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=4000)
    test_evidence: str | None = Field(default=None, max_length=2000)
    rollback_plan: str | None = Field(default=None, max_length=2000)
    emergency_reason: str | None = Field(default=None, max_length=2000)


class Message(BaseModel):
    message: str


class AuthOutput(BaseModel):
    authenticated: bool
    mfa_required: bool
    user_id: str
    role: str


class RequestOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_id: str
    assigned_staff_id: str | None
    category: str
    description: str
    status: str


class AccessOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    requested_role: str
    requester_id: str
    approver_id: str | None
    decision: str


class ChangeOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    requester_id: str
    change_type: str
    version_reference: str
    status: str
    approver_id: str | None
    decision: str


class EventOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    run_id: str
    actor_id: str | None
    action: str
    object_type: str
    object_id: str | None
    result: str
    correlation_id: str
    context: dict[str, Any]


class AlertOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    rule_id: str
    severity: str
    status: str
    subject_key: str
    related_event_ids: list[str]


@dataclass(frozen=True)
class CurrentIdentity:
    session: Session
    user: User


Db = Annotated[AsyncSession, Depends(get_db)]


async def current_identity(request: Request, db: Db) -> CurrentIdentity:
    settings: Settings = request.app.state.settings
    try:
        session, user = await resolve_session(db, request.cookies.get(SESSION_COOKIE), settings)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail="Authentication required") from exc
    await db.commit()
    return CurrentIdentity(session=session, user=user)


Identity = Annotated[CurrentIdentity, Depends(current_identity)]


async def csrf_identity(
    request: Request,
    identity: Identity,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> CurrentIdentity:
    try:
        verify_csrf(
            identity.session,
            x_csrf_token,
            request.cookies.get(CSRF_COOKIE),
            request.app.state.settings,
        )
    except CsrfError as exc:
        raise HTTPException(status_code=403, detail="CSRF validation failed") from exc
    return identity


CsrfIdentity = Annotated[CurrentIdentity, Depends(csrf_identity)]


async def privileged_identity(request: Request, identity: CsrfIdentity) -> CurrentIdentity:
    settings: Settings = request.app.state.settings
    if not (
        settings.environment == "scenario"
        and settings.scenario_id == "S03"
        and settings.run_id.startswith("cyber-assess-scenario-s03-")
    ):
        try:
            require_privileged_mfa(identity.session, identity.user)
        except ForbiddenError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    return identity


PrivilegedIdentity = Annotated[CurrentIdentity, Depends(privileged_identity)]


def _set_auth_cookies(response: Response, token: str, csrf_token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings()
    engine = build_engine(runtime_settings)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if runtime_settings.auto_create_schema:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        yield
        await engine.dispose()

    application = FastAPI(
        title=runtime_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.engine = engine
    application.state.session_factory = session_factory
    template_path = Path(runtime_settings.templates_dir)
    application.state.templates = Jinja2Templates(directory=str(template_path))

    @application.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Response:
        correlation = request.headers.get("X-Correlation-ID") or str(uuid4())
        request.state.correlation_id = correlation
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        response.headers["X-Correlation-ID"] = correlation
        return response

    @application.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(ForbiddenError)
    async def forbidden_handler(_request: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @application.exception_handler(ConflictError)
    async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.get("/health", response_model=Message)
    async def health() -> Message:
        return Message(message="ok")

    @application.get("/ready", response_model=Message)
    async def ready(db: Db) -> Message:
        try:
            await db.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="not ready") from exc
        return Message(message="ready")

    @application.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> Response:
        return cast(
            Response,
            application.state.templates.TemplateResponse(
                request,
                "index.html",
                {
                    "title": runtime_settings.app_name,
                    "run_id": runtime_settings.run_id,
                    "scenario_id": runtime_settings.scenario_id,
                    "environment": runtime_settings.environment,
                },
            ),
        )

    @application.get("/auth/login", response_class=HTMLResponse)
    async def login_page(request: Request) -> Response:
        return cast(
            Response,
            application.state.templates.TemplateResponse(request, "login.html", {}),
        )

    @application.post("/auth/login", response_model=AuthOutput)
    async def login(
        payload: LoginInput, request: Request, response: Response, db: Db
    ) -> AuthOutput:
        source_ip = request.client.host if request.client else "unknown"
        try:
            result = await AuthService(db, runtime_settings).login(
                payload.email,
                payload.password,
                source_ip=source_ip,
                correlation_id=request.state.correlation_id,
            )
        except (InvalidCredentialsError, LoginThrottledError) as exc:
            raise HTTPException(status_code=401, detail="Invalid email or password") from exc
        _set_auth_cookies(
            response,
            result.session.token,
            result.session.csrf_token,
            runtime_settings,
        )
        user = await db.get(User, result.session.record.user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return AuthOutput(
            authenticated=True,
            mfa_required=result.mfa_required,
            user_id=user.id,
            role=user.role,
        )

    @application.post("/auth/mfa", response_model=Message)
    async def mfa(payload: MfaInput, identity: CsrfIdentity, db: Db) -> Message:
        try:
            await AuthService(db, runtime_settings).complete_mfa(
                identity.session, identity.user, payload.code
            )
        except MfaError as exc:
            raise HTTPException(status_code=401, detail="MFA verification failed") from exc
        return Message(message="MFA verified")

    @application.post("/auth/logout", response_model=Message)
    async def logout(identity: CsrfIdentity, response: Response, db: Db) -> Message:
        await AuthService(db, runtime_settings).logout(identity.session, identity.user)
        _clear_auth_cookies(response)
        return Message(message="signed out")

    @application.get("/requests", response_model=list[RequestOutput])
    async def requests_list(identity: Identity, db: Db) -> list[ServiceRequest]:
        return await ServiceRequestService(db, runtime_settings).list_for(identity.user)

    @application.get("/requests/{request_id}", response_model=RequestOutput)
    async def request_detail(request_id: str, identity: Identity, db: Db) -> ServiceRequest:
        return await ServiceRequestService(db, runtime_settings).get_for(request_id, identity.user)

    @application.post(
        "/requests", response_model=RequestOutput, status_code=status.HTTP_201_CREATED
    )
    async def request_create(
        payload: RequestCreate, identity: CsrfIdentity, db: Db
    ) -> ServiceRequest:
        return await ServiceRequestService(db, runtime_settings).create(
            identity.user, category=payload.category, description=payload.description
        )

    @application.patch("/requests/{request_id}", response_model=RequestOutput)
    async def request_transition(
        request_id: str,
        payload: RequestTransition,
        identity: CsrfIdentity,
        db: Db,
    ) -> ServiceRequest:
        return await ServiceRequestService(db, runtime_settings).transition(
            request_id, identity.user, status=payload.status, reason=payload.reason
        )

    @application.get("/admin/users", response_model=list[dict[str, str | None]])
    async def users_list(identity: PrivilegedIdentity, db: Db) -> list[dict[str, str | None]]:
        if identity.user.role != Role.ADMINISTRATOR:
            raise ForbiddenError("Administrator role required")
        users = list((await db.execute(select(User).order_by(User.id))).scalars())
        return [
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "account_status": user.account_status,
                "employment_status": user.employment_status,
            }
            for user in users
        ]

    @application.post("/admin/users/{user_id}/deactivate", response_model=Message)
    async def deactivate(
        user_id: str,
        payload: DeactivateInput,
        identity: PrivilegedIdentity,
        db: Db,
    ) -> Message:
        await AccessService(db, runtime_settings).deactivate(user_id, identity.user, payload.reason)
        return Message(message="user deactivated and active sessions revoked")

    @application.post(
        "/access-requests", response_model=AccessOutput, status_code=status.HTTP_201_CREATED
    )
    async def access_submit(payload: AccessCreate, identity: CsrfIdentity, db: Db) -> AccessRequest:
        target = await db.get(User, payload.user_id)
        if target is None:
            raise NotFoundError("User not found")
        return await AccessService(db, runtime_settings).submit(
            identity.user, target, payload.requested_role, payload.rationale
        )

    @application.post("/access-requests/{request_id}/decision", response_model=AccessOutput)
    async def access_decide(
        request_id: str,
        payload: DecisionInput,
        identity: PrivilegedIdentity,
        db: Db,
    ) -> AccessRequest:
        return await AccessService(db, runtime_settings).decide(
            request_id, identity.user, payload.decision
        )

    @application.post("/access-requests/{request_id}/apply", response_model=Message)
    async def access_apply(request_id: str, identity: PrivilegedIdentity, db: Db) -> Message:
        await AccessService(db, runtime_settings).apply(request_id, identity.user)
        return Message(message="approved access change applied and sessions revoked")

    @application.post("/changes", response_model=ChangeOutput, status_code=status.HTTP_201_CREATED)
    async def change_submit(payload: ChangeCreate, identity: CsrfIdentity, db: Db) -> ChangeRecord:
        return await ChangeService(db, runtime_settings).submit(
            identity.user,
            change_type=payload.change_type,
            version_reference=payload.version_reference,
            description=payload.description,
            test_evidence=payload.test_evidence,
            rollback_plan=payload.rollback_plan,
            emergency_reason=payload.emergency_reason,
        )

    @application.post("/changes/{change_id}/decision", response_model=ChangeOutput)
    async def change_decide(
        change_id: str,
        payload: DecisionInput,
        identity: PrivilegedIdentity,
        db: Db,
    ) -> ChangeRecord:
        return await ChangeService(db, runtime_settings).decide(
            change_id, identity.user, payload.decision, payload.reason
        )

    @application.get("/events", response_model=list[EventOutput])
    async def events(identity: Identity, db: Db, run_id: str | None = None) -> list[Any]:
        require_privileged_mfa(identity.session, identity.user)
        return await list_events(db, run_id=run_id)

    @application.get("/alerts", response_model=list[AlertOutput])
    async def alerts(identity: Identity, db: Db) -> list[Alert]:
        require_privileged_mfa(identity.session, identity.user)
        return list((await db.execute(select(Alert).order_by(Alert.created_at))).scalars())

    return application


app = create_app()
