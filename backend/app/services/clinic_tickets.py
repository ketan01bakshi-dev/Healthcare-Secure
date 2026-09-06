"""Clinic gate tickets — prove clinic password before PIN unlock (Postgres-backed)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete

from app.core.config import settings
from app.core.database import SessionLocal


def _ticket_ttl_seconds() -> int:
    ttl = int(getattr(settings, "clinic_ticket_ttl_seconds", 0) or 0)
    return ttl if ttl > 0 else 8 * 60 * 60


def mint_clinic_ticket(clinic_id: str) -> str:
    """Issue an opaque ticket bound to clinic_id (valid for the configured TTL)."""
    cid = (clinic_id or "").strip() or "default"
    token = secrets.token_urlsafe(32)
    digest = hmac.new(
        (settings.secret_key or "dev").encode("utf-8"),
        f"{cid}:{token}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]
    ticket = f"{token}.{digest}"
    expires = datetime.now(timezone.utc) + timedelta(seconds=_ticket_ttl_seconds())
    db = SessionLocal()
    try:
        purge_expired_tickets(db=db)
        from app.models.session import ClinicGateTicket

        db.merge(
            ClinicGateTicket(
                ticket=ticket,
                clinic_id=cid,
                expires_at=expires,
            )
        )
        db.commit()
    finally:
        db.close()
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
    db = SessionLocal()
    try:
        from app.models.session import ClinicGateTicket

        purge_expired_tickets(db=db)
        row = db.get(ClinicGateTicket, raw)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clinic unlock expired. Enter clinic name and password again.",
            )
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            db.delete(row)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clinic unlock expired. Enter clinic name and password again.",
            )
        clinic_id = row.clinic_id
    finally:
        db.close()
    if expected_clinic_id:
        want = (expected_clinic_id or "").strip() or "default"
        if clinic_id != want:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clinic ticket does not match selected clinic",
            )
    return clinic_id


def purge_expired_tickets(*, db=None) -> int:
    from app.models.session import ClinicGateTicket

    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        result = db.execute(
            delete(ClinicGateTicket).where(ClinicGateTicket.expires_at < now)
        )
        if own_session:
            db.commit()
        return int(result.rowcount or 0)
    finally:
        if own_session:
            db.close()
