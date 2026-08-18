"""Video consultation — mint Jitsi rooms and SMS invite links (no call recording)."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.record import ClinicalRecord
from app.services.doctor_auth import DoctorOnly
from app.services.phone_crypto import decrypt_phone
from app.services.rate_limit import check_rate_limit
from app.services.security import tokenize_patient_identifier
from app.services.sms import send_sms
from app.services.tenancy import branding_for, get_clinic

router = APIRouter(prefix="/video-consult")


class SessionRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1, max_length=200)
    appointment_id: str | None = Field(default=None, max_length=64)
    write_timeline: bool = True


class InviteSmsRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1, max_length=200)
    join_url: str = Field(..., min_length=8, max_length=500)
    appointment_id: str | None = Field(default=None, max_length=64)


def _clinic_allows_video(clinic_id: str) -> bool:
    clinic = get_clinic(clinic_id)
    return "video_consult" in clinic.features


def _slug_clinic(clinic_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "", (clinic_id or "default").lower())
    return (cleaned or "default")[:24]


def _room_name(*, clinic_id: str, blind_patient_id: str, when: datetime) -> str:
    digest = hashlib.sha256(
        f"{clinic_id}:{blind_patient_id}".encode("utf-8")
    ).hexdigest()[:10]
    stamp = when.astimezone(timezone.utc).strftime("%Y%m%d%H%M")
    return f"aoc-{_slug_clinic(clinic_id)}-{digest}-{stamp}"


def _jitsi_urls(room: str) -> tuple[str, str]:
    base = (settings.jitsi_base_url or "https://meet.jit.si").rstrip("/")
    join = f"{base}/{room}"
    # Same public room; doctor UI may add userInfo via hash/query later
    return join, join


def _tokenize_or_400(raw: str) -> str:
    try:
        return tokenize_patient_identifier((raw or "").strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/session")
def create_video_session(
    body: SessionRequest,
    session: DoctorOnly,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Mint an opaque Jitsi room for the locked patient (doctor only)."""
    if not _clinic_allows_video(session.clinic_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Video consult is not enabled for this clinic",
        )
    if (settings.video_consult_provider or "jitsi").strip().lower() != "jitsi":
        raise HTTPException(
            status_code=501,
            detail=f"Unsupported video provider: {settings.video_consult_provider}",
        )

    blind = _tokenize_or_400(body.raw_identifier)
    appt_id: str | None = None
    if body.appointment_id:
        try:
            uid = UUID(body.appointment_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid appointment_id") from exc
        row = db.get(Appointment, uid)
        if row is None or row.clinic_id != session.clinic_id:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if row.blind_patient_id != blind:
            raise HTTPException(
                status_code=400,
                detail="Appointment does not match locked patient",
            )
        appt_id = str(row.id)

    now = datetime.now(timezone.utc)
    room = _room_name(clinic_id=session.clinic_id, blind_patient_id=blind, when=now)
    join_url, doctor_url = _jitsi_urls(room)

    record_id: str | None = None
    if body.write_timeline:
        encounter = {
            "type": "video_consult",
            "room_name": room,
            "join_url": join_url,
            "provider": "jitsi",
            "appointment_id": appt_id,
            "started_at": now.isoformat(),
            "started_by": {
                "user_id": session.user_id,
                "display_name": session.display_name,
                "role": session.role,
            },
            "clinical_observations": [f"Video consult started ({room})"],
            "diagnoses": [],
            "medications": [],
            "symptoms": [],
        }
        rec = ClinicalRecord(
            clinic_id=session.clinic_id,
            blind_patient_id=blind,
            encounter_data=encounter,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        record_id = str(rec.id)

    return {
        "status": "ok",
        "provider": "jitsi",
        "room_name": room,
        "join_url": join_url,
        "doctor_url": doctor_url,
        "doctor_display_name": session.display_name,
        "appointment_id": appt_id,
        "record_id": record_id,
        "hint": (
            "Pause or mute the call before using Voice Rx — mic audio cannot serve both."
        ),
    }


@router.post("/invite-sms")
def invite_video_sms(
    body: InviteSmsRequest,
    request: Request,
    session: DoctorOnly,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """SMS the patient a video join link (no PHI in URL)."""
    check_rate_limit(
        request, limit=10, window_seconds=60, key_prefix="video_invite_sms"
    )
    if not _clinic_allows_video(session.clinic_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Video consult is not enabled for this clinic",
        )

    join_url = (body.join_url or "").strip()
    base = (settings.jitsi_base_url or "https://meet.jit.si").rstrip("/")
    if not join_url.startswith(base + "/") and not join_url.startswith(
        "https://meet.jit.si/"
    ):
        raise HTTPException(status_code=400, detail="join_url host not allowed")

    blind = _tokenize_or_400(body.raw_identifier)
    phone = ""
    if body.appointment_id:
        try:
            uid = UUID(body.appointment_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid appointment_id") from exc
        row = db.get(Appointment, uid)
        if row is None or row.clinic_id != session.clinic_id:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if row.blind_patient_id != blind:
            raise HTTPException(
                status_code=400,
                detail="Appointment does not match locked patient",
            )
        phone = decrypt_phone(row.phone_encrypted)

    if not phone:
        # Fall back to latest appointment for this patient with a phone
        from sqlalchemy import select

        rows = db.scalars(
            select(Appointment)
            .where(
                Appointment.clinic_id == session.clinic_id,
                Appointment.blind_patient_id == blind,
                Appointment.phone_encrypted != "",
            )
            .order_by(Appointment.scheduled_at.desc())
            .limit(5)
        ).all()
        for r in rows:
            phone = decrypt_phone(r.phone_encrypted)
            if phone:
                break

    if not phone or len("".join(c for c in phone if c.isdigit())) < 10:
        raise HTTPException(
            status_code=400,
            detail="No phone on file for SMS invite — use Copy link or device SMS",
        )

    brand = branding_for(session.clinic_id)
    message = (
        f"{brand['clinic_name']}: Video consult. Join on your phone browser: {join_url}"
    )
    try:
        result = send_sms(to_phone=phone, message=message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)[:200]) from None

    return {
        "status": "ok",
        "sms_status": str(result.get("status") or "unknown"),
        "provider": result.get("provider"),
        "phone_last4": "".join(c for c in phone if c.isdigit())[-4:],
    }
