"""Simple in-process rate limiter (no extra dependency)."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

_lock = Lock()
# key -> list of attempt timestamps (unix)
_hits: dict[str, list[float]] = defaultdict(list)


def clear_rate_limits() -> None:
    """Test helper — wipe in-process counters."""
    with _lock:
        _hits.clear()


def client_ip(request: Request) -> str:
    """Prefer left-most X-Forwarded-For hop (nginx), else peer address."""
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        # client, proxy1, proxy2 — take original client
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def check_rate_limit(
    request: Request,
    *,
    limit: int = 20,
    window_seconds: int = 60,
    key_prefix: str = "default",
) -> None:
    """Raise 429 if more than ``limit`` hits in ``window_seconds`` for client IP."""
    client = client_ip(request)
    key = f"{key_prefix}:{client}"
    now = time.time()
    cutoff = now - window_seconds
    with _lock:
        recent = [t for t in _hits[key] if t >= cutoff]
        if len(recent) >= limit:
            retry = int(window_seconds - (now - recent[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {max(retry, 1)} seconds.",
            )
        recent.append(now)
        _hits[key] = recent
