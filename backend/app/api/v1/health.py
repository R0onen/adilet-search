import asyncio

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import HealthServiceDep, ManifestDep, QdrantDep, SettingsDep
from app.api.responses import errors
from app.schemas.health import HealthResponse, VersionResponse
from app.services.health import overall_status

router = APIRouter(tags=["system"])
log = structlog.get_logger(__name__)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    responses={503: {"model": HealthResponse, "description": "Search cannot work (`down`)"}},
)
async def health(
    health_service: HealthServiceDep, manifest: ManifestDep, settings: SettingsDep
) -> JSONResponse:
    components, loaded = await asyncio.gather(health_service.components(), manifest.get())
    status = overall_status(components)
    body = HealthResponse(
        status=status,
        components=components,
        pipeline_version=loaded.pipeline_version if loaded else None,
        app_version=settings.app_version,
    )
    return JSONResponse(
        status_code=503 if status == "down" else 200, content=body.model_dump(mode="json")
    )


@router.get("/version", response_model=VersionResponse, summary="Versions", responses=errors())
async def version(
    manifest: ManifestDep, qdrant: QdrantDep, settings: SettingsDep
) -> VersionResponse:
    loaded = await manifest.get()
    try:
        collection = await asyncio.wait_for(qdrant.alias_target(), settings.health_timeout_s)
    except Exception as exc:  # Qdrant down must not break /version
        log.warning("alias_lookup_failed", error=type(exc).__name__)
        collection = None
    return VersionResponse(
        app_version=settings.app_version,
        git_sha=settings.git_sha,
        pipeline_version=loaded.pipeline_version if loaded else None,
        index_collection=collection,
    )
