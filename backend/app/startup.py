"""Work done once when the API process starts. Each step is best effort: the database may be
down at startup, and the API must still come up to report that through /health."""

import structlog
from sqlalchemy import text, update
from sqlalchemy.dialects.postgresql import insert

from app.db import repositories as repo
from app.db.models import AdminUser, IndexJob
from app.state import Resources

log = structlog.get_logger(__name__)


async def seed_admin(resources: Resources) -> None:
    """Create or update the admin user from ADMIN_USERNAME / ADMIN_PASSWORD_HASH."""
    settings = resources.settings
    if not settings.admin_username or not settings.admin_password_hash:
        log.info("admin_seed_skipped", reason="ADMIN_USERNAME or ADMIN_PASSWORD_HASH is not set")
        return
    stmt = insert(AdminUser).values(
        username=settings.admin_username, password_hash=settings.admin_password_hash
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["username"],
        set_={"password_hash": stmt.excluded.password_hash, "is_active": True},
    )
    async with resources.sessionmaker.begin() as session:
        await session.execute(stmt)
    log.info("admin_seeded", username=settings.admin_username)


async def fail_interrupted_api_jobs(resources: Resources) -> None:
    """A reindex started through the API runs inside the API process, so a job of that origin
    that is still 'running' when the process starts was interrupted by a restart. Jobs started
    with the CLI may really be running and are left alone."""
    async with resources.sessionmaker.begin() as session:
        result = await session.execute(
            update(IndexJob)
            .where(
                IndexJob.status.in_(("queued", "running")),
                text("params->>'origin' = 'api'"),
            )
            .values(
                status="failed",
                finished_at=repo.now_utc(),
                error="interrupted: the API process restarted while this job was running",
                message="failed: interrupted",
            )
            .returning(IndexJob.job_id)
        )
        for row in result:
            log.warning("index_job_interrupted", job_id=str(row.job_id))


async def startup_tasks(resources: Resources) -> None:
    for step in (seed_admin, fail_interrupted_api_jobs):
        try:
            await step(resources)
        except Exception as exc:
            log.warning("startup_step_failed", step=step.__name__, error=type(exc).__name__)
