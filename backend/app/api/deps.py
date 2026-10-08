"""FastAPI dependencies. Tests replace these through `app.dependency_overrides`."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
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

_bearer = HTTPBearer(auto_error=False, description="Admin JWT from `POST /admin/login`")


async def admin_credentials(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> HTTPAuthorizationCredentials | None:
    """Declares Bearer auth on admin routes. Token verification is added with the admin API."""
    return credentials
