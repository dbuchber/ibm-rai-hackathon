"""Per-client sliding-window rate limit and client IP resolution (behind Cloudflare/Caddy)."""

from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request


def client_ip(request: Request) -> str:
    h = request.headers
    if h.get("cf-connecting-ip"):
        return h["cf-connecting-ip"].strip()
    if h.get("x-forwarded-for"):
        return h["x-forwarded-for"].split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, limit: int, window: float = 3600.0, clock: Callable[[], float] = time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def retry_after(self, key: str) -> int | None:
        """Seconds until a slot frees up, or None if the key is under its limit."""
        q, now = self._hits[key], self.clock()
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) < self.limit:
            return None
        return max(1, math.ceil(q[0] + self.window - now))

    def record(self, key: str) -> None:
        self._hits[key].append(self.clock())
