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
    ):
        super().__init__(app)
        self.requests = max(1, requests)
        self.window = max(1, window_seconds)
        self.key_func = key_func or self._default_key
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

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

        async with self._lock:
            timestamps = self._hits[identifier]

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
