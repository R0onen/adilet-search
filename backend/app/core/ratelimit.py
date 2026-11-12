"""In-memory sliding-window rate limiter (contracts/api.md §5).

Per process: with several backend workers each has its own counters, so the effective limit is
`workers x limit`. The deployment runs one worker; a shared store (Redis) would lift this.
"""

import hashlib
import math
import time
from collections import deque
from collections.abc import Callable

WINDOW_S = 60.0
MAX_KEYS = 50_000


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, limit: int) -> int | None:
        """Record a request. Returns None if allowed, else seconds until the next one is."""
        if limit <= 0:
            return None
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= WINDOW_S:
            hits.popleft()
        if len(hits) >= limit:
            return max(1, math.ceil(WINDOW_S - (now - hits[0])))
        hits.append(now)
        if len(self._hits) > MAX_KEYS:
            self._prune(now)
        return None

    def _prune(self, now: float) -> None:
        for key in [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= WINDOW_S]:
            del self._hits[key]


def client_key(ip: str | None, session_id: str | None) -> str:
    """Session + IP, hashed: raw addresses are not kept, even in memory."""
    return hashlib.sha256(f"{ip or '-'}|{session_id or '-'}".encode()).hexdigest()[:32]
