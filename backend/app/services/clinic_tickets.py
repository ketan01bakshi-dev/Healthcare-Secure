"""Short-lived clinic tickets — prove clinic password before PIN unlock."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time

from fastapi import HTTPException, status

from app.core.config import settings

_TICKET_TTL_SECONDS = 600  # 10 minutes
_LOCK = threading.Lock()
# token -> (clinic_id, expires_epoch)
_TICKETS: dict[str, tuple[str, float]] = {}


def mint_clinic_ticket(clinic_id: str) -> str:
    """Issue a single-use-capable opaque ticket bound to clinic_id."""
    cid = (clinic_id or "").strip() or "default"
    token = secrets.token_urlsafe(32)
    # Bind token material to secret so forged tokens fail even if dict is empty
    digest = hmac.new(
        (settings.secret_key or "dev").encode("utf-8"),
        f"{cid}:{token}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]
    ticket = f"{token}.{digest}"
    expires = time.time() + _TICKET_TTL_SECONDS
    with _LOCK:
        _purge_locked()
        _TICKETS[ticket] = (cid, expires)
    return ticket


def verify_clinic_ticket(ticket: str | None, expected_clinic_id: str | None = None) -> str:
    """
    Validate ticket and return clinic_id.
    Does not consume the ticket (doctor may retry PIN within the TTL).
    """
    raw = (ticket or "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clinic unlock required before PIN sign-in",
        )
    now = time.time()
    with _LOCK:
        _purge_locked()
        entry = _TICKETS.get(raw)
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clinic unlock expired. Enter clinic name and password again.",
            )
        clinic_id, expires = entry
        if expires < now:
            _TICKETS.pop(raw, None)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clinic unlock expired. Enter clinic name and password again.",
            )
    if expected_clinic_id:
        want = (expected_clinic_id or "").strip() or "default"
        if clinic_id != want:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clinic ticket does not match selected clinic",
            )
    return clinic_id


def _purge_locked() -> None:
    now = time.time()
    dead = [k for k, (_, exp) in _TICKETS.items() if exp < now]
    for k in dead:
        _TICKETS.pop(k, None)
