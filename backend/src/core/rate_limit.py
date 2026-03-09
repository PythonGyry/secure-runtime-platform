"""
Rate limiting and brute-force protection.

- license/check: 15 req/min per IP, 3s delay on failed check
- license/info: 30 req/min per IP
- admin/login: 5 req/min per IP, 5s delay on failed login

Custom implementation (no SlowAPI) to avoid 422 body parsing issues.
"""
from __future__ import annotations

import time
import threading
from collections import defaultdict
from typing import Callable

from fastapi import Request
from starlette.responses import JSONResponse

# Delays (seconds) on failed attempts — робить brute-force непрактичним
LICENSE_CHECK_FAIL_DELAY = 3
ADMIN_LOGIN_FAIL_DELAY = 5

# In-memory store: {(ip, scope): [(timestamp, ...), ...]}
# Sliding window: keep only timestamps within the window
_store: dict[tuple[str, str], list[float]] = defaultdict(list)
_store_lock = threading.Lock()

# Limits: scope -> (max_requests, window_seconds)
_LIMITS: dict[str, tuple[int, int]] = {
    "license/info": (30, 60),
    "license/check": (15, 60),
    "admin/login": (5, 60),
}


def _get_client_ip(request: Request) -> str:
    """Get client IP from request (supports X-Forwarded-For behind proxy)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def _check_limit(scope: str, request: Request) -> None:
    """Raise 429 if limit exceeded. Thread-safe sliding window."""
    ip = _get_client_ip(request)
    if scope not in _LIMITS:
        return
    max_req, window_sec = _LIMITS[scope]
    now = time.monotonic()
    cutoff = now - window_sec
    key = (ip, scope)
    with _store_lock:
        timestamps = _store[key]
        timestamps[:] = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= max_req:
            raise RateLimitExceeded(scope=scope, retry_after=window_sec)
        timestamps.append(now)


class RateLimitExceeded(Exception):
    def __init__(self, scope: str, retry_after: int) -> None:
        self.scope = scope
        self.retry_after = retry_after


def rate_limit_dep(scope: str) -> Callable:
    """FastAPI dependency for rate limiting. Does NOT touch request body."""

    def dep(request: Request) -> None:
        _check_limit(scope, request)

    return dep


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle RateLimitExceeded with 429 and Retry-After header."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."},
        headers={"Retry-After": str(exc.retry_after)},
    )
