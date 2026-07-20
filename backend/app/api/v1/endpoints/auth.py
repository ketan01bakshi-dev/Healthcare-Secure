"""Clinic unlock — multi-user doctor/staff sessions."""

from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.services.doctor_auth import (
    auth_configured,
    get_session,
    list_public_users,
    revoke_session,
    unlock_user,
)

router = APIRouter(prefix="/auth")


class UnlockRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    pin: str = Field(..., min_length=1, max_length=64)


class UnlockResponse(BaseModel):
    status: str
    session_token: str | None = None
    auth_required: bool
    user_id: str | None = None
    display_name: str | None = None
    role: str | None = None
    message: str


@router.get("/status")
def auth_status() -> dict[str, object]:
    required = auth_configured()
    return {
        "auth_required": required,
        "users": list_public_users() if required else [],
        "message": (
            "Select your user and enter PIN"
            if required
            else "Auth disabled (set CLINIC_USERS or DOCTOR_PIN)"
        ),
    }


@router.get("/me")
def auth_me(x_doctor_session: str | None = Header(default=None)) -> dict[str, object]:
    if not auth_configured():
        return {
            "authenticated": True,
            "user_id": "local",
            "display_name": "Local doctor",
            "role": "doctor",
        }
    info = get_session(x_doctor_session)
    if info is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user_id": info.user_id,
        "display_name": info.display_name,
        "role": info.role,
    }


@router.post("/unlock", response_model=UnlockResponse)
def unlock(body: UnlockRequest) -> UnlockResponse:
    if not auth_configured():
        return UnlockResponse(
            status="ok",
            session_token=None,
            auth_required=False,
            user_id="local",
            display_name="Local doctor",
            role="doctor",
            message="Auth disabled; no users configured.",
        )
    info = unlock_user(body.user_id, body.pin)
    return UnlockResponse(
        status="ok",
        session_token=info.token,
        auth_required=True,
        user_id=info.user_id,
        display_name=info.display_name,
        role=info.role,
        message=f"Unlocked as {info.display_name} ({info.role}). Concurrent sessions allowed.",
    )


@router.post("/lock")
def lock(x_doctor_session: str | None = Header(default=None)) -> dict[str, str]:
    revoke_session(x_doctor_session)
    return {"status": "ok", "message": "Session cleared."}
