"""Per-user sliding-window rate limits for the signed-in endpoints.

In-memory and per process: enough for a single-instance prototype. Behind several workers or
instances, each keeps its own count, so move this to a shared store (e.g. Redis) first.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from haven.api.auth import CurrentUserDep
from haven.api.errors import TooManyRequests
from haven.api.schemas import CurrentUser


class SlidingWindowRateLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> None:
        """Record one request for ``key``, or raise ``TooManyRequests`` if over the limit."""
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                raise TooManyRequests(math.ceil(hits[0] + self.window - now))
            hits.append(now)


def rate_limited(name: str) -> Callable[[Request, CurrentUser], CurrentUser]:
    """Dependency: the signed-in user, after counting this request against limiter ``name``."""

    def dependency(request: Request, user: CurrentUserDep) -> CurrentUser:
        limiter: SlidingWindowRateLimiter = request.app.state.rate_limiters[name]
        limiter.hit(user.sub)
        return user

    return dependency


PhotoScreenUser = Annotated[CurrentUser, Depends(rate_limited("photo_screen"))]
ReadAloudUser = Annotated[CurrentUser, Depends(rate_limited("read_aloud"))]
