from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Lightweight in-memory rate limiter.

    Provides basic protection
    against enumeration or brute-force attempts by capping requests per client IP.
    """

    def __init__(
        self,
        app,
        *,
        requests: int = 120,
        window_seconds: int = 60,
        key_func: Callable[[Request], str] | None = None,
        cleanup_interval: int | None = None,
    ):
        super().__init__(app)
        self.requests = max(1, requests)
        self.window = max(1, window_seconds)
        self.key_func = key_func or self._default_key
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._state_lock = asyncio.Lock()
        self._cleanup_interval = max(1, cleanup_interval or self.window)
        self._expiration_window = self.window * 2
        self._last_cleanup = time.monotonic()

    @staticmethod
    def _default_key(request: Request) -> str:
        client = request.client
        return client.host if client else "unknown"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        identifier = self.key_func(request)
        now = time.monotonic()
        earliest = now - self.window

        async with self._state_lock:
            self._maybe_cleanup(now)
            timestamps = self._hits[identifier]
            per_key_lock = self._locks[identifier]

        async with per_key_lock:
            # Trim timestamps outside the window
            while timestamps and timestamps[0] < earliest:
                timestamps.popleft()

            if len(timestamps) >= self.requests:
                return JSONResponse(
                    {
                        "detail": (
                            "Too many requests. Reduce your request rate and try again."
                        )
                    },
                    status_code=429,
                )

            timestamps.append(now)

        return await call_next(request)

    def _maybe_cleanup(self, now: float) -> None:
        """Remove stale client entries to keep in-memory usage bounded."""
        if now - self._last_cleanup < self._cleanup_interval:
            return

        expiration_cutoff = now - self._expiration_window
        stale_keys = [
            key
            for key, timestamps in list(self._hits.items())
            if not timestamps or timestamps[-1] < expiration_cutoff
        ]

        for key in stale_keys:
            self._hits.pop(key, None)
            self._locks.pop(key, None)

        self._last_cleanup = now
