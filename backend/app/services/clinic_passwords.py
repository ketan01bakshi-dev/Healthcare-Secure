"""Clinic password resolution and doctor-PIN recovery tokens."""

from __future__ import annotations

import secrets
import threading
import time

from fastapi import HTTPException, status

from app.core.database import SessionLocal
from app.models.clinic_credential import ClinicCredential
from app.services.doctor_auth import (
    find_user,
    hash_pin,
    verify_pin,
    _check_lockout,
    _clear_pin_failures,
    _record_pin_failure,
)
from app.services.tenancy import find_clinic_by_name_or_id, get_clinic

_RESET_TTL_SECONDS = 600
_RESET_LOCK = threading.Lock()
# token -> (clinic_id, user_id, expires_epoch)
_RESET_TOKENS: dict[str, tuple[str, str, float]] = {}


def get_clinic_password(clinic_id: str) -> str:
    """DB override wins; else CLINICS env password; else empty."""
    cid = (clinic_id or "").strip() or "default"
    db = SessionLocal()
    try:
        row = db.get(ClinicCredential, cid)
        if row and (row.password_hash or "").strip():
            return row.password_hash.strip()
    finally:
        db.close()
    clinic = get_clinic(cid)
    return (clinic.password or "").strip()


def set_clinic_password(
    clinic_id: str, new_password: str, *, updated_by_user_id: str
) -> None:
    cid = (clinic_id or "").strip() or "default"
    hashed = hash_pin(new_password)
    db = SessionLocal()
    try:
        row = db.get(ClinicCredential, cid)
        if row is None:
            row = ClinicCredential(
                clinic_id=cid,
                password_hash=hashed,
                updated_by_user_id=updated_by_user_id,
            )
            db.add(row)
        else:
            row.password_hash = hashed
            row.updated_by_user_id = updated_by_user_id
        db.commit()
    finally:
        db.close()


def list_clinic_doctors(clinic_id: str) -> list[dict[str, str]]:
    from app.services.doctor_auth import list_public_users

    cid = (clinic_id or "").strip() or "default"
    return [
        {
            "user_id": u["user_id"],
            "display_name": u["display_name"],
            "role": u["role"],
            "clinic_id": u.get("clinic_id") or "default",
        }
        for u in list_public_users()
        if (u.get("clinic_id") or "default") == cid and u.get("role") == "doctor"
    ]


def preview_clinic_doctors(
    clinic_name: str, password: str
) -> dict[str, object]:
    """Return doctor profiles only after clinic password is verified."""
    clinic = find_clinic_by_name_or_id(clinic_name)
    if clinic is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown clinic",
        )
    stored = get_clinic_password(clinic.clinic_id)
    provided = (password or "").strip()
    if not stored:
        from app.core.config import settings

        if (settings.app_env or "").strip().lower() == "production":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clinic password is not configured",
            )
        if not provided:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid clinic password",
            )
    elif not verify_pin(stored, provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid clinic password",
        )
    doctors = list_clinic_doctors(clinic.clinic_id)
    return {
        "status": "ok",
        "clinic_id": clinic.clinic_id,
        "name": clinic.name,
        "doctors": doctors,
    }


def issue_clinic_password_reset_token(
    clinic_name: str, user_id: str, pin: str
) -> dict[str, object]:
    clinic = find_clinic_by_name_or_id(clinic_name)
    if clinic is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify clinic recovery details",
        )
    user = find_user(user_id, clinic_id=clinic.clinic_id)
    if user is None or user.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify clinic recovery details",
        )
    lock_key = f"{user.clinic_id}:{user.user_id}"
    _check_lockout(lock_key)
    if not verify_pin(user.pin, pin):
        _record_pin_failure(lock_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify clinic recovery details",
        )
    _clear_pin_failures(lock_key)

    token = secrets.token_urlsafe(32)
    expires = time.time() + _RESET_TTL_SECONDS
    with _RESET_LOCK:
        # Drop expired tokens opportunistically
        now = time.time()
        for key, (_c, _u, exp) in list(_RESET_TOKENS.items()):
            if exp <= now:
                _RESET_TOKENS.pop(key, None)
        _RESET_TOKENS[token] = (clinic.clinic_id, user.user_id, expires)

    return {
        "status": "ok",
        "reset_token": token,
        "clinic_id": clinic.clinic_id,
        "expires_in_seconds": _RESET_TTL_SECONDS,
        "message": "Doctor verified. Set a new clinic password.",
    }


def reset_clinic_password_with_token(reset_token: str, new_password: str) -> dict[str, str]:
    token = (reset_token or "").strip()
    password = (new_password or "").strip()
    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New clinic password must be at least 6 characters",
        )
    with _RESET_LOCK:
        entry = _RESET_TOKENS.pop(token, None)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset link expired or invalid. Start again.",
        )
    clinic_id, user_id, expires = entry
    if expires <= time.time():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset link expired or invalid. Start again.",
        )
    set_clinic_password(clinic_id, password, updated_by_user_id=user_id)
    return {
        "status": "ok",
        "clinic_id": clinic_id,
        "message": "Clinic password updated. Sign in with the new password.",
    }
