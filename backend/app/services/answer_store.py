"""Persist an /answer request: its query-log row and its answer row, in one transaction."""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import repositories as repo

log = structlog.get_logger(__name__)


class AnswerStore:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessionmaker

    async def save(self, log_values: dict[str, Any], answer_values: dict[str, Any]) -> None:
        """Never raises: a logging failure must not affect the user."""
        try:
            async with self._sessions.begin() as session:
                await repo.insert_query_log(session, log_values)
                await repo.insert_answer(session, answer_values)
        except Exception as exc:
            log.warning(
                "answer_log_failed",
                error=type(exc).__name__,
                query_id=str(log_values.get("query_id")),
            )
