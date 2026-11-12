import asyncio
import time

import structlog
from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import HealthServiceDep, ManifestDep, ResourcesDep
from app.api.responses import errors
from app.db import repositories as repo
from app.db.models import IndexJob
from app.schemas.admin import IndexInfo, Job, PipelineInfo, SystemResponse
from app.schemas.ml import Manifest

router = APIRouter()
log = structlog.get_logger(__name__)


def job_model(job: IndexJob) -> Job:
    return Job(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        message=job.error if job.status == "failed" and job.error else job.message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _model_label(info: object | None) -> str | None:
    """`id@revision` (short), as the admin panel shows it."""
    if info is None:
        return None
    revision = getattr(info, "revision", None)
    name = str(getattr(info, "id", ""))
    return f"{name}@{str(revision)[:7]}" if revision else name


def pipeline_info(manifest: Manifest | None) -> PipelineInfo:
    if manifest is None:
        return PipelineInfo()
    return PipelineInfo(
        pipeline_version=manifest.pipeline_version,
        embedder=_model_label(manifest.embedder),
        reranker=_model_label(manifest.reranker),
        generator=_model_label(manifest.generator),
        index_compat_id=manifest.index_compat_id,
    )


@router.get(
    "/system",
    response_model=SystemResponse,
    summary="Components, pipeline and index status",
    responses=errors(401),
)
async def system(
    resources: ResourcesDep, health: HealthServiceDep, manifest: ManifestDep
) -> SystemResponse:
    settings = resources.settings
    components, loaded = await asyncio.gather(health.components(), manifest.get())

    collection = points = state = last_job = None
    try:
        collection = await asyncio.wait_for(
            resources.qdrant.alias_target(), settings.health_timeout_s
        )
        if collection is not None:
            points = await asyncio.wait_for(
                resources.qdrant.count(collection), settings.health_timeout_s
            )
    except Exception as exc:  # Qdrant down: the page still renders, with what is known
        log.warning("index_lookup_failed", error=type(exc).__name__)
    try:
        async with resources.sessionmaker() as session:
            if collection is not None:
                state = await repo.get_index_state(session, collection)
            last_job = await session.scalar(
                select(IndexJob).order_by(IndexJob.created_at.desc()).limit(1)
            )
    except Exception as exc:
        log.warning("index_state_lookup_failed", error=type(exc).__name__)

    index_compat_id = state.index_compat_id if state else None
    return SystemResponse(
        components=components,
        app_version=settings.app_version,
        git_sha=settings.git_sha,
        uptime_s=int(time.monotonic() - resources.started_at),
        pipeline=pipeline_info(loaded),
        index=IndexInfo(
            alias=resources.qdrant.alias,
            collection=collection,
            points=points,
            documents=state.documents_count if state else None,
            articles=state.articles_count if state else None,
            index_compat_id=index_compat_id,
            compatible=bool(
                loaded and index_compat_id and index_compat_id == loaded.index_compat_id
            ),
            last_job=job_model(last_job) if last_job else None,
        ),
    )
