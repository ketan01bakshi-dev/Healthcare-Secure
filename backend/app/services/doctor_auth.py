"""Clinic multi-user auth — doctor (sign/seal) vs staff (vitals/diagnostics)."""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings

Role = Literal["doctor", "staff"]


@dataclass(frozen=True)
class ClinicUser:
    user_id: str
    display_name: str
    role: Role
    pin: str


@dataclass(frozen=True)
class SessionInfo:
    token: str
    user_id: str
    display_name: str
    role: Role


# Multiple concurrent sessions (one token per unlocked device/user).
_SESSIONS: dict[str, SessionInfo] = {}


def _parse_clinic_users() -> list[ClinicUser]:
    """
    CLINIC_USERS format (semicolon-separated)::
        user_id|Display Name|doctor|pin;user_id2|Name|staff|pin2
    """
    raw = (settings.clinic_users or "").strip()
    users: list[ClinicUser] = []
    if raw:
        for chunk in raw.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = [p.strip() for p in chunk.split("|")]
            if len(parts) != 4:
                continue
            user_id, display_name, role, pin = parts
            role_l = role.lower()
            if role_l not in ("doctor", "staff") or not user_id or not pin:
                continue
            users.append(
                ClinicUser(
                    user_id=user_id,
                    display_name=display_name or user_id,
                    role=role_l,  # type: ignore[arg-type]
                    pin=pin,
                )
            )
    if users:
        return users

    # Backward compatible: single doctor from DOCTOR_PIN.
    pin = (settings.doctor_pin or "").strip()
    if pin and not pin.startswith("CHANGE_ME"):
        return [
            ClinicUser(
                user_id="doctor",
                display_name=(settings.doctor_name or "Doctor").strip() or "Doctor",
                role="doctor",
                pin=pin,
            )
        ]
    return []


def auth_configured() -> bool:
    return len(_parse_clinic_users()) > 0


def list_public_users() -> list[dict[str, str]]:
    """Users without PINs — for the unlock picker."""
    return [
        {
            "user_id": u.user_id,
            "display_name": u.display_name,
            "role": u.role,
        }
        for u in _parse_clinic_users()
    ]


def find_user(user_id: str) -> ClinicUser | None:
    uid = (user_id or "").strip()
    for user in _parse_clinic_users():
        if user.user_id == uid:
            return user
    return None


def unlock_user(user_id: str, pin: str) -> SessionInfo:
    user = find_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown user",
        )
    if not hmac.compare_digest((pin or "").strip(), user.pin):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN",
        )
    token = secrets.token_urlsafe(32)
    info = SessionInfo(
        token=token,
        user_id=user.user_id,
        display_name=user.display_name,
        role=user.role,
    )
    _SESSIONS[token] = info
    return info


def revoke_session(token: str | None) -> None:
    if token:
        _SESSIONS.pop(token.strip(), None)


def get_session(token: str | None) -> SessionInfo | None:
    if not token:
        return None
    return _SESSIONS.get(token.strip())


def require_session(
    x_doctor_session: Annotated[str | None, Header()] = None,
) -> SessionInfo:
    """
    Require any unlocked clinic user when auth is configured.

    When auth is disabled (no users), return a synthetic doctor session so local
    POC flows keep working.
    """
    if not auth_configured():
        return SessionInfo(
            token="",
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
    """Sign / seal / prescription write — doctors only."""
    if session.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a doctor may sign or seal prescriptions.",
        )
    return session


# Backward-compatible aliases used by existing endpoints.
def doctor_pin_configured() -> bool:
    return auth_configured()


DoctorSession = Annotated[SessionInfo, Depends(require_session)]
DoctorOnly = Annotated[SessionInfo, Depends(require_doctor)]
