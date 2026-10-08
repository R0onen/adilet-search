"""`POST /feedback` (contracts/api.md): validate the query and upsert the rating."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import APIError
from app.db import repositories as repo
from app.schemas.feedback import FeedbackRequest


class FeedbackService:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessionmaker

    async def submit(self, request: FeedbackRequest, session_hash: str | None) -> None:
        async with self._sessions.begin() as session:
            if not await repo.query_exists(session, request.query_id):
                raise APIError(404, f"Query {request.query_id} not found")
            await repo.upsert_feedback(
                session,
                {
                    "query_id": request.query_id,
                    "session_hash": session_hash,
                    "target": request.target,
                    # Feedback on the answer is not about one article.
                    "article_id": request.article_id if request.target == "result" else None,
                    "rating": request.rating,
                    "comment": request.comment,
                },
            )
