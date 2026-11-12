"""FastAPI dependencies. Tests replace these through `app.dependency_overrides`."""

import hmac
from collections.abc import AsyncIterator, Callable
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import metrics
from app.core.config import Settings
from app.core.errors import APIError
from app.core.ratelimit import client_key
from app.core.security import InvalidToken, decode_token
from app.services.admin import AdminService
from app.services.answer import AnswerService
from app.services.background import BackgroundRunner
from app.services.feedback import FeedbackService
from app.services.health import HealthService
from app.services.manifest import ManifestProvider
from app.services.qdrant_store import QdrantStore
from app.services.query_log import QueryLogWriter
from app.services.search import SearchService
from app.state import Resources


def get_resources(request: Request) -> Resources:
    return cast(Resources, request.app.state.resources)


ResourcesDep = Annotated[Resources, Depends(get_resources)]


def get_settings_dep(resources: ResourcesDep) -> Settings:
    return resources.settings


def get_health_service(resources: ResourcesDep) -> HealthService:
    return resources.health


def get_manifest_provider(resources: ResourcesDep) -> ManifestProvider:
    return resources.manifest


def get_qdrant_store(resources: ResourcesDep) -> QdrantStore:
    return resources.qdrant


def get_search_service(resources: ResourcesDep) -> SearchService:
    return resources.search


def get_answer_service(resources: ResourcesDep) -> AnswerService:
    return resources.answer


def get_feedback_service(resources: ResourcesDep) -> FeedbackService:
    return resources.feedback


def get_query_log_writer(resources: ResourcesDep) -> QueryLogWriter:
    return resources.query_log


def get_background(resources: ResourcesDep) -> BackgroundRunner:
    return resources.background


def get_admin_service(resources: ResourcesDep) -> AdminService:
    return resources.admin


async def get_session(resources: ResourcesDep) -> AsyncIterator[AsyncSession]:
    async with resources.sessionmaker() as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
AnswerServiceDep = Annotated[AnswerService, Depends(get_answer_service)]
FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]
QueryLogDep = Annotated[QueryLogWriter, Depends(get_query_log_writer)]
BackgroundDep = Annotated[BackgroundRunner, Depends(get_background)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
ManifestDep = Annotated[ManifestProvider, Depends(get_manifest_provider)]
QdrantDep = Annotated[QdrantStore, Depends(get_qdrant_store)]
AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]

_bearer = HTTPBearer(auto_error=False, description="Admin JWT from `POST /admin/login`")


async def admin_credentials(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: SettingsDep,
) -> str:
    """Protects the admin routes: a valid, unexpired admin JWT is required. Returns the user."""
    challenge = {"WWW-Authenticate": "Bearer"}
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError(401, "Authentication required", headers=challenge)
    try:
        payload = decode_token(credentials.credentials, settings.jwt_secret)
    except InvalidToken as exc:
        raise APIError(401, "Invalid or expired token", headers=challenge) from exc
    return str(payload["sub"])


def has_api_key(request: Request, settings: Settings) -> bool:
    """A valid `X-API-Key` (server-to-server integration). Compared in constant time."""
    sent = request.headers.get("x-api-key")
    if not sent or not settings.api_keys:
        return False
    return any(hmac.compare_digest(sent.encode(), key.encode()) for key in settings.api_keys)


def rate_limit(scope: str) -> Callable[..., None]:
    """Dependency: a per-minute limit for `scope`, per session + IP (contracts/api.md §5)."""

    def check(request: Request, resources: ResourcesDep) -> None:
        settings = resources.settings
        limit = int(getattr(settings, f"rate_limit_{scope}"))
        if has_api_key(request, settings):
            limit *= settings.api_key_limit_factor
        ip = request.client.host if request.client else None
        key = f"{scope}:{client_key(ip, request.headers.get('x-session-id'))}"
        retry_after = resources.rate_limiter.check(key, limit)
        if retry_after is not None:
            metrics.RATE_LIMITED.labels(scope).inc()
            raise APIError(
                429,
                f"Too many requests: at most {limit} per minute",
                headers={"Retry-After": str(retry_after)},
            )

    return check
