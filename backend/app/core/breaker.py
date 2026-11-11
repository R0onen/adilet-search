"""Circuit breaker: stop calling a dependency that keeps failing, then probe it again.

closed -> (N consecutive failures) -> open -> (after reset_s) -> half-open: one trial call;
its success closes the circuit, its failure opens it again.
"""

import time
from collections.abc import Callable

import structlog

log = structlog.get_logger(__name__)


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failures: int = 5,
        reset_s: float = 20.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self._threshold = failures
        self._reset_s = reset_s
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._trial_in_flight = False

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        return "half-open" if self._clock() - self._opened_at >= self._reset_s else "open"

    def allow(self) -> bool:
        """May the dependency be called now? In half-open state only one trial call may."""
        state = self.state
        if state == "closed":
            return True
        if state == "half-open" and not self._trial_in_flight:
            self._trial_in_flight = True
            return True
        return False

    def success(self) -> None:
        if self._opened_at is not None:
            log.info("circuit_closed", breaker=self.name)
        self._failures = 0
        self._opened_at = None
        self._trial_in_flight = False

    def failure(self) -> None:
        self._failures += 1
        self._trial_in_flight = False
        if self._opened_at is not None or self._failures >= self._threshold:
            if self._opened_at is None:
                log.warning("circuit_opened", breaker=self.name, failures=self._failures)
            self._opened_at = self._clock()
