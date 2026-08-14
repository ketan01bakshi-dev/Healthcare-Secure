"""Clinic unlock — multi-user doctor/staff sessions."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.clinic_passwords import (
    get_clinic_password,
    issue_clinic_password_reset_token,
    preview_clinic_doctors,
    reset_clinic_password_with_token,
)
from app.services.clinic_tickets import mint_clinic_ticket, verify_clinic_ticket
from app.services.doctor_auth import (
    auth_configured,
    get_session,
    list_public_users,
    revoke_session,
    unlock_user,
    verify_pin,
)
from app.services.rate_limit import check_rate_limit
from app.services.tenancy import find_clinic_by_name_or_id, public_clinic_dict

router = APIRouter(prefix="/auth")


class UnlockRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    pin: str = Field(..., min_length=1, max_length=64)
    clinic_id: str | None = Field(default=None, max_length=64)
    clinic_ticket: str | None = Field(default=None, max_length=256)


class UnlockResponse(BaseModel):
    status: str
    session_token: str | None = None
    auth_required: bool
    clinic_id: str | None = None
    user_id: str | None = None
    display_name: str | None = None
    role: str | None = None
    message: str


class ClinicUnlockRequest(BaseModel):
    clinic_name: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=128)


class ClinicPasswordPreviewRequest(BaseModel):
    clinic_name: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=128)


class ClinicPasswordRecoverRequest(BaseModel):
    clinic_name: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=64)
    pin: str = Field(..., min_length=1, max_length=64)


class ClinicPasswordResetRequest(BaseModel):
    reset_token: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


def _is_production() -> bool:
    return (settings.app_env or "").strip().lower() == "production"


@router.get("/status")
def auth_status() -> dict[str, object]:
    """Public probe only — never list clinics or user roster."""
    required = auth_configured()
    return {
        "auth_required": required,
        "message": (
            "Enter clinic name and password, then select a profile and PIN"
            if required
            else "Auth disabled (set CLINIC_USERS or DOCTOR_PIN)"
        ),
    }


@router.get("/me")
def auth_me(x_doctor_session: str | None = Header(default=None)) -> dict[str, object]:
    if not auth_configured():
        return {
            "authenticated": True,
            "clinic_id": "default",
            "user_id": "local",
            "display_name": "Local doctor",
            "role": "doctor",
        }
    info = get_session(x_doctor_session)
    if info is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "clinic_id": info.clinic_id,
        "user_id": info.user_id,
        "display_name": info.display_name,
        "role": info.role,
    }


@router.post("/clinic-unlock")
def clinic_unlock(body: ClinicUnlockRequest, request: Request) -> dict[str, object]:
    """Gate 1: verify clinic name + password; return branding, features, roster + ticket."""
    check_rate_limit(
        request, limit=20, window_seconds=60, key_prefix="auth_clinic_unlock"
    )
    clinic = find_clinic_by_name_or_id(body.clinic_name)
    if clinic is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown clinic",
        )
    stored = get_clinic_password(clinic.clinic_id)
    provided = (body.password or "").strip()
    if stored:
        if not verify_pin(stored, provided):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid clinic password",
            )
    else:
        # Production must have a configured clinic password — never accept any string.
        if _is_production():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clinic password is not configured",
            )
        if not provided:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid clinic password",
            )

    users = [
        u
        for u in list_public_users()
        if (u.get("clinic_id") or "default") == clinic.clinic_id
    ]
    pub = public_clinic_dict(clinic)
    ticket = mint_clinic_ticket(clinic.clinic_id)
    return {
        "status": "ok",
        "clinic_id": clinic.clinic_id,
        "name": clinic.name,
        "address": clinic.address,
        "subtitle": clinic.subtitle,
        "features": pub["features"],
        "users": users,
        "clinic_ticket": ticket,
        "message": f"Clinic unlocked: {clinic.name}",
    }


@router.post("/clinic-password/preview")
def clinic_password_preview(
    body: ClinicPasswordPreviewRequest, request: Request
) -> dict[str, object]:
    """Return doctor profiles after clinic password (forgot-password step A)."""
    check_rate_limit(
        request, limit=20, window_seconds=60, key_prefix="auth_clinic_pw_preview"
    )
    return preview_clinic_doctors(body.clinic_name, body.password)


@router.post("/clinic-password/recover")
def clinic_password_recover(
    body: ClinicPasswordRecoverRequest, request: Request
) -> dict[str, object]:
    """Prove doctor PIN → short-lived single-use reset token."""
    check_rate_limit(
        request, limit=20, window_seconds=60, key_prefix="auth_clinic_pw_recover"
    )
    return issue_clinic_password_reset_token(
        body.clinic_name, body.user_id, body.pin
    )


@router.post("/clinic-password/reset")
def clinic_password_reset(
    body: ClinicPasswordResetRequest, request: Request
) -> dict[str, str]:
    """Consume reset token and persist new clinic password hash in Postgres."""
    check_rate_limit(
        request, limit=20, window_seconds=60, key_prefix="auth_clinic_pw_reset"
    )
    return reset_clinic_password_with_token(body.reset_token, body.new_password)


@router.post("/unlock", response_model=UnlockResponse)
def unlock(body: UnlockRequest, request: Request) -> UnlockResponse:
    check_rate_limit(request, limit=20, window_seconds=60, key_prefix="auth_unlock")
    if not auth_configured():
        return UnlockResponse(
            status="ok",
            session_token=None,
            auth_required=False,
            clinic_id="default",
            user_id="local",
            display_name="Local doctor",
            role="doctor",
            message="Auth disabled; no users configured.",
        )
    ticket_clinic = verify_clinic_ticket(body.clinic_ticket, body.clinic_id)
    clinic_id = body.clinic_id or ticket_clinic
    info = unlock_user(body.user_id, body.pin, clinic_id=clinic_id)
    if info.clinic_id != ticket_clinic:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clinic ticket does not match user clinic",
        )
    return UnlockResponse(
        status="ok",
        session_token=info.token,
        auth_required=True,
        clinic_id=info.clinic_id,
        user_id=info.user_id,
        display_name=info.display_name,
        role=info.role,
        message=(
            f"Unlocked as {info.display_name} ({info.role}) @ {info.clinic_id}. "
            "Concurrent sessions allowed."
        ),
    )


@router.post("/lock")
def lock(x_doctor_session: str | None = Header(default=None)) -> dict[str, str]:
    revoke_session(x_doctor_session)
    return {"status": "ok", "message": "Session cleared."}
