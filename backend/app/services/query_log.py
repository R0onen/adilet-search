"""Query logging, written off the request path.

Queries are logged (a product requirement) but linked only to a salted HMAC of the client's
`X-Session-Id`, never to raw ids or IPs.
"""

import hashlib
import hmac
import re
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import repositories as repo

log = structlog.get_logger(__name__)

_SPACES = re.compile(r"\s+")
MAX_SESSION_ID_CHARS = 128


def session_hash(session_id: str | None, salt: str) -> str | None:
    if not session_id or len(session_id) > MAX_SESSION_ID_CHARS:
        return None
    return hmac.new(salt.encode(), session_id.encode(), hashlib.sha256).hexdigest()


def normalise_query(query: str) -> str:
    """Grouping key for the admin stats: lower-cased, whitespace collapsed."""
    return _SPACES.sub(" ", query).strip().lower()


class QueryLogWriter:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessionmaker

    async def write(self, values: dict[str, Any]) -> None:
        """Insert one query_logs row. Never raises: a logging failure must not break search."""
        try:
            async with self._sessions.begin() as session:
                await repo.insert_query_log(session, values)
        except Exception as exc:
            log.warning(
                "query_log_failed", error=type(exc).__name__, query_id=str(values.get("query_id"))
            )
