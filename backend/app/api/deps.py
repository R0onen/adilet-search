"""FastAPI dependencies. Tests replace these through `app.dependency_overrides`."""

from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.services.health import HealthService
from app.services.manifest import ManifestProvider
from app.services.qdrant_store import QdrantStore
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


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
ManifestDep = Annotated[ManifestProvider, Depends(get_manifest_provider)]
QdrantDep = Annotated[QdrantStore, Depends(get_qdrant_store)]

_bearer = HTTPBearer(auto_error=False, description="Admin JWT from `POST /admin/login`")


async def admin_credentials(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> HTTPAuthorizationCredentials | None:
    """Declares Bearer auth on admin routes. Token verification is added with the admin API."""
    return credentials
