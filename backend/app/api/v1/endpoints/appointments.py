"""Appointments API — schedule visits and send SMS confirmation / reminders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.appointment import Appointment
from app.services.doctor_auth import ClinicalSession, DoctorSession, get_session
from app.services.phone_crypto import decrypt_phone, encrypt_phone
from app.services.security import tokenize_patient_identifier
from app.services.sms import send_sms
from app.services.tenancy import branding_for

router = APIRouter(prefix="/appointments")

_PATIENT_TAB_NOTE = "source:patient_tab"


class BookRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=120)
    raw_identifier: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=20)
    clinic_mrn: str = Field(default="", max_length=64)
    scheduled_at: datetime
    duration_minutes: int = Field(default=15, ge=5, le=240)
    reason: str = Field(default="", max_length=240)
    notes: str = Field(default="", max_length=500)
    modality: str = Field(default="in_person", max_length=20)
    send_sms: bool = True


class NextAppointmentRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=120)
    raw_identifier: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=10, max_length=20)
    scheduled_at: datetime
    reason: str = Field(default="Next appointment", max_length=240)
    duration_minutes: int = Field(default=15, ge=5, le=240)
    modality: str = Field(default="in_person", max_length=20)
    send_sms: bool = False


class AppointmentOut(BaseModel):
    id: str
    clinic_id: str
    display_name: str
    phone_last4: str
    scheduled_at: str | None
    duration_minutes: int
    reason: str
    modality: str = "in_person"
    status: str
    sms_status: str
    created_by: str
    notes: str


def _normalize_modality(raw: str) -> str:
    v = (raw or "").strip().lower().replace("-", "_")
    if v in ("video", "tele", "teleconsult", "video_consult", "telehealth"):
        return "video"
    return "in_person"


def _parse_dt(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clinic_tz():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Asia/Kolkata")
    except Exception:  # noqa: BLE001
        return timezone.utc


def _sms_body(
    *,
    name: str,
    when: datetime,
    clinic_name: str,
    reason: str,
    modality: str = "in_person",
) -> str:
    try:
        local = when.astimezone(_clinic_tz())
    except Exception:  # noqa: BLE001
        local = when.astimezone() if when.tzinfo else when.replace(tzinfo=timezone.utc)
    when_s = local.strftime("%d %b %Y %I:%M %p IST")
    reason_bit = f" ({reason})" if reason else ""
    kind = "video consult" if modality == "video" else "appointment"
    return (
        f"{clinic_name}: {kind} for {name} on {when_s}{reason_bit}. "
        f"Reply to clinic if you need to reschedule."
    )


def _reminder_sms_body(
    *,
    name: str,
    when: datetime,
    clinic_name: str,
    reason: str,
    modality: str = "in_person",
) -> str:
    return "Reminder: " + _sms_body(
        name=name,
        when=when,
        clinic_name=clinic_name,
        reason=reason,
        modality=modality,
    )


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    session: DoctorSession,
    db: Session = Depends(get_db),
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[AppointmentOut]:
    if session.role == "lab":
        raise HTTPException(status_code=403, detail="Lab cannot manage appointments")
    stmt = (
        select(Appointment)
        .where(Appointment.clinic_id == session.clinic_id)
        .order_by(Appointment.scheduled_at.asc())
    )
    if from_date is not None:
        stmt = stmt.where(Appointment.scheduled_at >= _parse_dt(from_date))
    if to_date is not None:
        stmt = stmt.where(Appointment.scheduled_at <= _parse_dt(to_date))
    if status_filter:
        stmt = stmt.where(Appointment.status == status_filter.strip().lower())
    rows = db.scalars(stmt).all()
    return [AppointmentOut(**r.to_public()) for r in rows]


@router.post("", response_model=AppointmentOut)
def book_appointment(
    body: BookRequest,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> AppointmentOut:
    from app.services.mrn_identity import find_patient_by_mrn, resolve_patient_identity
    from app.services.security import normalize_mrn, normalize_phone_digits

    digits = normalize_phone_digits(body.phone or "")
    mrn = normalize_mrn(body.clinic_mrn or "")
    raw = (body.raw_identifier or "").strip()
    if raw.startswith("mrn|") and not mrn:
        mrn = normalize_mrn(raw.split("|", 1)[1])

    if len(digits) != 10 and not mrn:
        raise HTTPException(
            status_code=400,
            detail="Provide a 10-digit phone or a clinic MRN",
        )
    if len(digits) != 10:
        digits = ""

    try:
        resolved = resolve_patient_identity(
            db,
            clinic_id=session.clinic_id,
            patient_name=body.display_name.strip(),
            patient_phone=digits or None,
            clinic_mrn=mrn or None,
            raw_identifier=raw or (f"mrn|{mrn}" if mrn else None),
            actor={
                "user_id": session.user_id,
                "display_name": session.display_name,
                "role": session.role,
            },
            bump_visit=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    blind = resolved.blind_patient_id
    display_name = (resolved.display_name or body.display_name).strip()

    # Prefer entered phone; else roster phone for SMS / identity open.
    sms_digits = digits
    if len(sms_digits) != 10 and resolved.phone_digits:
        sms_digits = normalize_phone_digits(resolved.phone_digits)
    if len(sms_digits) != 10 and resolved.clinic_mrn:
        roster = find_patient_by_mrn(db, session.clinic_id, resolved.clinic_mrn)
        if roster and roster.phone_encrypted:
            sms_digits = normalize_phone_digits(decrypt_phone(roster.phone_encrypted))
    if len(sms_digits) != 10:
        sms_digits = ""

    when = _parse_dt(body.scheduled_at)
    if when < datetime.now(timezone.utc) - timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="scheduled_at is in the past")

    modality = _normalize_modality(body.modality)
    brand = branding_for(session.clinic_id)
    row = Appointment(
        clinic_id=session.clinic_id,
        blind_patient_id=blind,
        display_name=display_name,
        phone_encrypted=encrypt_phone(sms_digits) if sms_digits else "",
        phone_last4=sms_digits[-4:] if sms_digits else "",
        scheduled_at=when,
        duration_minutes=str(body.duration_minutes),
        reason=(body.reason or "").strip()[:240],
        modality=modality,
        status="booked",
        created_by=session.display_name,
        notes=(body.notes or "").strip()[:500],
    )
    sms_result: dict[str, Any] = {"status": "skipped"}
    if body.send_sms and sms_digits:
        try:
            sms_result = send_sms(
                to_phone=sms_digits,
                message=_sms_body(
                    name=row.display_name,
                    when=when,
                    clinic_name=brand["clinic_name"],
                    reason=row.reason,
                    modality=modality,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            sms_result = {"status": "error", "detail": str(exc)[:200]}
    elif body.send_sms and not sms_digits:
        sms_result = {"status": "skipped", "detail": "no_phone"}
    row.sms_status = str(sms_result.get("status") or "unknown")
    if sms_result.get("provider"):
        row.sms_status = f"{row.sms_status}:{sms_result['provider']}"

    db.add(row)
    from app.services.clinic_patients import upsert_clinic_patient

    upsert_clinic_patient(
        db,
        clinic_id=session.clinic_id,
        blind_patient_id=blind,
        display_name=row.display_name,
        phone_digits=sms_digits,
        clinic_mrn=resolved.clinic_mrn,
        bump_visit=False,
        seen_at=when,
    )
    db.commit()
    db.refresh(row)
    return AppointmentOut(**row.to_public())


@router.get("/next", response_model=AppointmentOut | None)
def get_next_appointment(
    session: ClinicalSession,
    db: Session = Depends(get_db),
    raw_identifier: str = Query(..., min_length=1),
) -> AppointmentOut | None:
    """Soonest future booked appointment for this patient (Patient tab)."""
    try:
        blind = tokenize_patient_identifier(raw_identifier.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    now = datetime.now(timezone.utc)
    row = db.scalars(
        select(Appointment)
        .where(
            Appointment.clinic_id == session.clinic_id,
            Appointment.blind_patient_id == blind,
            Appointment.status == "booked",
            Appointment.scheduled_at >= now,
        )
        .order_by(Appointment.scheduled_at.asc())
        .limit(1)
    ).first()
    if row is None:
        return None
    return AppointmentOut(**row.to_public())


@router.post("/next", response_model=AppointmentOut)
def set_next_appointment(
    body: NextAppointmentRequest,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> AppointmentOut:
    """Upsert the patient's next appointment from the Patient tab."""
    try:
        blind = tokenize_patient_identifier(body.raw_identifier.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    digits = "".join(c for c in body.phone if c.isdigit())
    if len(digits) < 10:
        raise HTTPException(status_code=400, detail="Phone must have at least 10 digits")

    when = _parse_dt(body.scheduled_at)
    if when < datetime.now(timezone.utc) - timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="scheduled_at is in the past")

    existing = db.scalars(
        select(Appointment).where(
            Appointment.clinic_id == session.clinic_id,
            Appointment.blind_patient_id == blind,
            Appointment.status == "booked",
            Appointment.notes.contains(_PATIENT_TAB_NOTE),
        )
    ).first()

    brand = branding_for(session.clinic_id)
    reason = (body.reason or "Next appointment").strip()[:240]
    modality = _normalize_modality(body.modality)

    if existing is not None:
        existing.display_name = body.display_name.strip()
        existing.phone_encrypted = encrypt_phone(digits)
        existing.phone_last4 = digits[-4:]
        existing.scheduled_at = when
        existing.duration_minutes = str(body.duration_minutes)
        existing.reason = reason
        existing.modality = modality
        existing.created_by = session.display_name
        row = existing
    else:
        row = Appointment(
            clinic_id=session.clinic_id,
            blind_patient_id=blind,
            display_name=body.display_name.strip(),
            phone_encrypted=encrypt_phone(digits),
            phone_last4=digits[-4:],
            scheduled_at=when,
            duration_minutes=str(body.duration_minutes),
            reason=reason,
            modality=modality,
            status="booked",
            created_by=session.display_name,
            notes=_PATIENT_TAB_NOTE,
        )
        db.add(row)

    if body.send_sms:
        try:
            sms_result = send_sms(
                to_phone=digits,
                message=_sms_body(
                    name=row.display_name,
                    when=when,
                    clinic_name=brand["clinic_name"],
                    reason=row.reason,
                    modality=modality,
                ),
            )
            row.sms_status = str(sms_result.get("status") or "unknown")
            if sms_result.get("provider"):
                row.sms_status = f"{row.sms_status}:{sms_result['provider']}"
        except Exception as exc:  # noqa: BLE001
            row.sms_status = f"error:{str(exc)[:80]}"

    from app.services.clinic_patients import upsert_clinic_patient

    upsert_clinic_patient(
        db,
        clinic_id=session.clinic_id,
        blind_patient_id=blind,
        display_name=row.display_name,
        phone_digits=digits,
        bump_visit=False,
        seen_at=when,
    )
    db.commit()
    db.refresh(row)
    return AppointmentOut(**row.to_public())


@router.post("/remind-upcoming")
def remind_upcoming(
    db: Session = Depends(get_db),
    x_doctor_session: str | None = Header(default=None),
    x_reminder_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Send SMS for booked appointments falling on tomorrow (Asia/Kolkata)."""
    clinic_id: str | None = None
    token = (settings.appointment_reminder_token or "").strip()
    if token and x_reminder_token and x_reminder_token.strip() == token:
        clinic_id = None  # all clinics
    else:
        info = get_session(x_doctor_session) if x_doctor_session else None
        if info is None:
            from app.services.doctor_auth import auth_configured

            if auth_configured():
                raise HTTPException(
                    status_code=401, detail="Session or reminder token required"
                )
            clinic_id = "default"
        else:
            if info.role == "lab":
                raise HTTPException(status_code=403, detail="Lab cannot send reminders")
            clinic_id = info.clinic_id

    tz = _clinic_tz()
    now_local = datetime.now(tz)
    tomorrow = (now_local + timedelta(days=1)).date()
    start_local = datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    day_tag = f"day_before:{tomorrow.isoformat()}"

    stmt = select(Appointment).where(
        Appointment.status == "booked",
        Appointment.scheduled_at >= start_utc,
        Appointment.scheduled_at < end_utc,
    )
    if clinic_id is not None:
        stmt = stmt.where(Appointment.clinic_id == clinic_id)
    rows = db.scalars(stmt).all()

    sent = 0
    skipped = 0
    errors: list[str] = []
    for row in rows:
        if day_tag in (row.sms_status or ""):
            skipped += 1
            continue
        phone = decrypt_phone(row.phone_encrypted)
        if not phone:
            skipped += 1
            continue
        brand = branding_for(row.clinic_id)
        when = (
            row.scheduled_at
            if row.scheduled_at.tzinfo
            else row.scheduled_at.replace(tzinfo=timezone.utc)
        )
        try:
            result = send_sms(
                to_phone=phone,
                message=_reminder_sms_body(
                    name=row.display_name,
                    when=when,
                    clinic_name=brand["clinic_name"],
                    reason=row.reason,
                    modality=getattr(row, "modality", None) or "in_person",
                ),
            )
            status = str(result.get("status") or "unknown")
            provider = str(result.get("provider") or "")
            row.sms_status = f"{day_tag}:{status}:{provider}".strip(":")
            sent += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{row.id}:{str(exc)[:80]}")
            row.sms_status = f"{day_tag}:error"
    db.commit()
    return {
        "status": "ok",
        "tomorrow": tomorrow.isoformat(),
        "candidates": len(rows),
        "sent": sent,
        "skipped": skipped,
        "errors": errors,
    }


@router.post("/{appointment_id}/remind")
def remind_appointment(
    appointment_id: UUID,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(Appointment, appointment_id)
    if row is None or row.clinic_id != session.clinic_id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if row.status in ("cancelled", "done"):
        raise HTTPException(status_code=400, detail=f"Cannot remind {row.status} appointment")
    phone = decrypt_phone(row.phone_encrypted)
    if not phone:
        raise HTTPException(status_code=400, detail="No phone stored for SMS")
    brand = branding_for(session.clinic_id)
    try:
        result = send_sms(
            to_phone=phone,
            message=_reminder_sms_body(
                name=row.display_name,
                when=row.scheduled_at
                if row.scheduled_at.tzinfo
                else row.scheduled_at.replace(tzinfo=timezone.utc),
                clinic_name=brand["clinic_name"],
                reason=row.reason,
                modality=getattr(row, "modality", None) or "in_person",
            ),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from None
    row.sms_status = f"reminded:{result.get('status')}:{result.get('provider', '')}"
    db.commit()
    return {"status": "ok", "sms": result}


@router.post("/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: UUID,
    session: ClinicalSession,
    db: Session = Depends(get_db),
    notify: bool = True,
) -> dict[str, Any]:
    row = db.get(Appointment, appointment_id)
    if row is None or row.clinic_id != session.clinic_id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    row.status = "cancelled"
    sms: dict[str, Any] | None = None
    if notify:
        phone = decrypt_phone(row.phone_encrypted)
        if phone:
            brand = branding_for(session.clinic_id)
            try:
                sms = send_sms(
                    to_phone=phone,
                    message=(
                        f"{brand['clinic_name']}: appointment for {row.display_name} "
                        f"has been cancelled. Call the clinic to reschedule."
                    ),
                )
                row.sms_status = f"cancel:{sms.get('status')}"
            except Exception as exc:  # noqa: BLE001
                sms = {"status": "error", "detail": str(exc)[:200]}
    db.commit()
    return {"status": "ok", "sms": sms}


@router.get("/{appointment_id}/patient-identity")
def patient_identity(
    appointment_id: UUID,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Return name + phone so staff can lock the same patient without re-entry."""
    if session.role == "lab":
        raise HTTPException(status_code=403, detail="Lab cannot open appointment patients")
    row = db.get(Appointment, appointment_id)
    if row is None or row.clinic_id != session.clinic_id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    phone = decrypt_phone(row.phone_encrypted)
    if not phone:
        raise HTTPException(
            status_code=400,
            detail="No phone stored for this appointment — enter patient details manually.",
        )
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        raise HTTPException(status_code=400, detail="Stored phone is incomplete")
    return {
        "display_name": row.display_name,
        "phone": digits[-10:] if len(digits) > 10 else digits,
    }


@router.post("/{appointment_id}/done")
def complete_appointment(
    appointment_id: UUID,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    row = db.get(Appointment, appointment_id)
    if row is None or row.clinic_id != session.clinic_id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    row.status = "done"
    db.commit()
    return {"status": "ok"}
