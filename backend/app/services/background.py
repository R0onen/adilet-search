"""Fire-and-forget tasks off the request path (query logs), drained on shutdown.

FastAPI's BackgroundTasks do not run when the handler raises, but failed searches are logged
too, so the backend keeps its own small task set.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class BackgroundRunner:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @property
    def pending(self) -> int:
        return len(self._tasks)

    async def drain(self, timeout_s: float = 10.0) -> None:
        if not self._tasks:
            return
        _, pending = await asyncio.wait(set(self._tasks), timeout=timeout_s)
        for task in pending:
            task.cancel()
        if pending:
            log.warning("background_tasks_cancelled", count=len(pending))
