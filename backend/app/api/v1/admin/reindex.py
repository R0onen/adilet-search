from pathlib import Path
from uuid import UUID

import structlog
from fastapi import APIRouter

from app.api.deps import ResourcesDep
from app.api.responses import errors
from app.api.v1.admin.system import job_model
from app.core.errors import APIError
from app.db.models import IndexJob
from app.schemas.admin import Job, JobRef, ReindexRequest
from indexer.pipeline import Indexer, IndexOptions, JobConflict

router = APIRouter()
log = structlog.get_logger(__name__)

# Marks jobs started through the API, so a restart can fail the ones it interrupted.
API_ORIGIN = "api"


@router.post(
    "/reindex",
    status_code=202,
    response_model=JobRef,
    summary="Start a reindex job into a new collection",
    responses=errors(401, 409, 422, 503),
)
async def reindex(body: ReindexRequest, resources: ResourcesDep) -> JobRef:
    """Builds a new collection in the background and switches the alias only on success: the
    current index keeps serving while the job runs and if it fails."""
    manifest = await resources.manifest.get()
    if manifest is None:
        raise APIError(503, "The model manifest is not available", code="upstream_unavailable")
    data_dir = Path(resources.settings.data_dir) / body.source
    if not (data_dir / "chunks.parquet").exists():
        raise APIError(422, f"No corpus at {data_dir.as_posix()} (chunks.parquet is missing)")
    embeddings = data_dir.parent / "index" / f"embeddings_{manifest.pipeline_version}.parquet"
    precomputed = embeddings if body.use_precomputed_embeddings and embeddings.exists() else None

    indexer = Indexer(resources.sessionmaker, resources.qdrant, resources.ml, manifest)
    try:
        job_id = await indexer.create_job(
            {
                "origin": API_ORIGIN,
                "source": body.source,
                "data_dir": data_dir.as_posix(),
                "embeddings": precomputed.as_posix() if precomputed else None,
            }
        )
    except JobConflict as exc:
        raise APIError(409, "An index job is already queued or running") from exc

    async def run() -> None:
        try:
            await indexer.run(IndexOptions(data_dir=data_dir, embeddings=precomputed), job_id)
            resources.index_info.invalidate()
        except Exception as exc:  # the job row already says "failed"; nothing to return to
            log.warning("reindex_failed", job_id=str(job_id), error=type(exc).__name__)

    resources.background.spawn(run())
    return JobRef(job_id=job_id)


@router.get(
    "/jobs/{job_id}",
    response_model=Job,
    summary="Job status and progress",
    responses=errors(401, 404, 422),
)
async def get_job(job_id: UUID, resources: ResourcesDep) -> Job:
    async with resources.sessionmaker() as session:
        job = await session.get(IndexJob, job_id)
    if job is None:
        raise APIError(404, "Job not found")
    return job_model(job)
