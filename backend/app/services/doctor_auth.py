"""Clinic multi-user auth — doctor / staff / lab roles with durable sessions."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import delete

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.tenancy import DEFAULT_CLINIC_ID, normalize_clinic_id

Role = Literal["doctor", "staff", "lab", "receptionist"]

_MAX_PIN_FAILURES = 5
_LOCKOUT_SECONDS = 300
_SESSION_DAYS = 7

# user_id -> (failure_count, locked_until_epoch)
_PIN_FAILURES: dict[str, tuple[int, float]] = {}


@dataclass(frozen=True)
class ClinicUser:
    clinic_id: str
    user_id: str
    display_name: str
    role: Role
    pin: str  # plaintext or pbkdf2$salt$hex


@dataclass(frozen=True)
class SessionInfo:
    token: str
    clinic_id: str
    user_id: str
    display_name: str
    role: Role


def hash_pin(pin: str) -> str:
    """Return a PBKDF2 hash string suitable for CLINIC_USERS."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        (pin or "").encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return f"pbkdf2${salt}${digest.hex()}"


def verify_pin(stored: str, provided: str) -> bool:
    """Accept legacy plaintext PIN or ``pbkdf2$salt$hex`` hashes."""
    stored = (stored or "").strip()
    provided = (provided or "").strip()
    if not stored or not provided:
        return False
    if stored.startswith("pbkdf2$"):
        parts = stored.split("$", 2)
        if len(parts) != 3:
            return False
        _, salt, expected = parts
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            provided.encode("utf-8"),
            salt.encode("utf-8"),
            120_000,
        )
        return hmac.compare_digest(digest.hex(), expected)
    return hmac.compare_digest(stored, provided)


def _normalize_role(raw: str) -> Role | None:
    role_l = (raw or "").strip().lower()
    if role_l == "diagnostic":
        return "lab"
    if role_l in ("reception", "front_desk", "frontdesk"):
        return "receptionist"
    if role_l in ("doctor", "staff", "lab", "receptionist"):
        return role_l  # type: ignore[return-value]
    return None


def _parse_clinic_users() -> list[ClinicUser]:
    """
    CLINIC_USERS format (semicolon-separated)::

        user_id|Display Name|doctor|pin_or_hash
        clinic_id|user_id|Display Name|doctor|pin_or_hash

    4 fields → clinic ``default``. 5 fields → multi-tenant.
    """
    raw = (settings.clinic_users or "").strip()
    users: list[ClinicUser] = []
    if raw:
        for chunk in raw.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = [p.strip() for p in chunk.split("|")]
            clinic_id = DEFAULT_CLINIC_ID
            if len(parts) == 5:
                clinic_id, user_id, display_name, role, pin = parts
            elif len(parts) == 4:
                user_id, display_name, role, pin = parts
            else:
                continue
            role_n = _normalize_role(role)
            if role_n is None or not user_id or not pin:
                continue
            users.append(
                ClinicUser(
                    clinic_id=normalize_clinic_id(clinic_id),
                    user_id=user_id,
                    display_name=display_name or user_id,
                    role=role_n,
                    pin=pin,
                )
            )
    if users:
        return users

    pin = (settings.doctor_pin or "").strip()
    if pin and not pin.startswith("CHANGE_ME"):
        return [
            ClinicUser(
                clinic_id=DEFAULT_CLINIC_ID,
                user_id="doctor",
                display_name=(settings.doctor_name or "Doctor").strip() or "Doctor",
                role="doctor",
                pin=pin,
            )
        ]
    return []


def auth_configured() -> bool:
    return len(_parse_clinic_users()) > 0


def require_users_enforced() -> bool:
    """Production / explicit flag: refuse open local-doctor mode."""
    if settings.require_clinic_users:
        return True
    return (settings.app_env or "").strip().lower() == "production"


def list_public_users() -> list[dict[str, str]]:
    return [
        {
            "clinic_id": u.clinic_id,
            "user_id": u.user_id,
            "display_name": u.display_name,
            "role": u.role,
        }
        for u in _parse_clinic_users()
    ]


def find_user(user_id: str, clinic_id: str | None = None) -> ClinicUser | None:
    uid = (user_id or "").strip()
    cid = (clinic_id or "").strip() or None
    matches = [u for u in _parse_clinic_users() if u.user_id == uid]
    if not matches:
        return None
    if cid:
        for u in matches:
            if u.clinic_id == cid:
                return u
        return None
    if len(matches) == 1:
        return matches[0]
    # Ambiguous without clinic_id — prefer default
    for u in matches:
        if u.clinic_id == DEFAULT_CLINIC_ID:
            return u
    return matches[0]


def _check_lockout(user_id: str) -> None:
    entry = _PIN_FAILURES.get(user_id)
    if not entry:
        return
    _count, locked_until = entry
    now = time.time()
    if locked_until > now:
        remaining = int(locked_until - now)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many wrong PINs. Try again in {remaining} seconds.",
        )
    if locked_until and locked_until <= now:
        _PIN_FAILURES.pop(user_id, None)


def _record_pin_failure(user_id: str) -> None:
    count, _ = _PIN_FAILURES.get(user_id, (0, 0.0))
    count += 1
    locked_until = 0.0
    if count >= _MAX_PIN_FAILURES:
        locked_until = time.time() + _LOCKOUT_SECONDS
        count = 0
    _PIN_FAILURES[user_id] = (count, locked_until)


def _clear_pin_failures(user_id: str) -> None:
    _PIN_FAILURES.pop(user_id, None)


def unlock_user(
    user_id: str, pin: str, clinic_id: str | None = None
) -> SessionInfo:
    user = find_user(user_id, clinic_id=clinic_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown user",
        )
    lock_key = f"{user.clinic_id}:{user.user_id}"
    _check_lockout(lock_key)
    if not verify_pin(user.pin, pin):
        _record_pin_failure(lock_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN",
        )
    _clear_pin_failures(lock_key)
    token = secrets.token_urlsafe(32)
    info = SessionInfo(
        token=token,
        clinic_id=user.clinic_id,
        user_id=user.user_id,
        display_name=user.display_name,
        role=user.role,
    )
    _persist_session(info)
    return info


def _persist_session(info: SessionInfo) -> None:
    from app.models.session import ClinicSession

    expires = datetime.now(timezone.utc) + timedelta(days=_SESSION_DAYS)
    db = SessionLocal()
    try:
        db.merge(
            ClinicSession(
                token=info.token,
                clinic_id=info.clinic_id,
                user_id=info.user_id,
                display_name=info.display_name,
                role=info.role,
                expires_at=expires,
            )
        )
        db.commit()
    finally:
        db.close()


def revoke_session(token: str | None) -> None:
    if not token:
        return
    from app.models.session import ClinicSession

    key = token.strip()
    db = SessionLocal()
    try:
        db.execute(delete(ClinicSession).where(ClinicSession.token == key))
        db.commit()
    finally:
        db.close()


def get_session(token: str | None) -> SessionInfo | None:
    if not token:
        return None
    from app.models.session import ClinicSession

    key = token.strip()
    db = SessionLocal()
    try:
        row = db.get(ClinicSession, key)
        if row is None:
            return None
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            db.delete(row)
            db.commit()
            return None
        role = _normalize_role(row.role) or "staff"
        clinic_id = getattr(row, "clinic_id", None) or DEFAULT_CLINIC_ID
        return SessionInfo(
            token=row.token,
            clinic_id=clinic_id,
            user_id=row.user_id,
            display_name=row.display_name,
            role=role,
        )
    finally:
        db.close()


def purge_expired_sessions() -> int:
    from app.models.session import ClinicSession

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        result = db.execute(
            delete(ClinicSession).where(ClinicSession.expires_at < now)
        )
        db.commit()
        return int(result.rowcount or 0)
    finally:
        db.close()


def require_session(
    x_doctor_session: Annotated[str | None, Header()] = None,
) -> SessionInfo:
    configured = auth_configured()
    if not configured:
        if require_users_enforced():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="CLINIC_USERS must be set when APP_ENV=production or REQUIRE_CLINIC_USERS=true.",
            )
        return SessionInfo(
            token="",
            clinic_id=DEFAULT_CLINIC_ID,
            user_id="local",
            display_name=(settings.doctor_name or "Local doctor").strip()
            or "Local doctor",
            role="doctor",
        )
    info = get_session(x_doctor_session)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unlock required. Call POST /api/v1/auth/unlock first.",
            headers={"WWW-Authenticate": "DoctorSession"},
        )
    return info


def require_doctor(
    session: Annotated[SessionInfo, Depends(require_session)],
) -> SessionInfo:
    if session.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a doctor may sign or seal prescriptions.",
        )
    return session


def require_clinical(
    session: Annotated[SessionInfo, Depends(require_session)],
) -> SessionInfo:
    if session.role == "lab":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lab users can only upload and view diagnostic reports.",
        )
    return session


def doctor_pin_configured() -> bool:
    return auth_configured()


DoctorSession = Annotated[SessionInfo, Depends(require_session)]
DoctorOnly = Annotated[SessionInfo, Depends(require_doctor)]
ClinicalSession = Annotated[SessionInfo, Depends(require_clinical)]
