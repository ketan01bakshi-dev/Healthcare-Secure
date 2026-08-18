"""Upsert and list clinic patient roster rows."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinic_patient import ClinicPatient
from app.services.phone_crypto import encrypt_phone


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def upsert_clinic_patient(
    db: Session,
    *,
    clinic_id: str,
    blind_patient_id: str,
    display_name: str,
    phone_digits: str = "",
    clinic_mrn: str = "",
    age_years: float | None = None,
    bump_visit: bool = True,
    seen_at: datetime | None = None,
) -> ClinicPatient:
    """Create or refresh a roster row. Encrypted phone kept when digits provided."""
    now = seen_at or datetime.now(timezone.utc)
    name = (display_name or "").strip()[:120]
    digits = "".join(c for c in (phone_digits or "") if c.isdigit())
    mrn = (clinic_mrn or "").strip()[:64]
    row = db.get(ClinicPatient, (clinic_id, blind_patient_id))
    if row is None:
        # Same transaction may already have a pending INSERT (e.g. resolve_patient_identity
        # then book_appointment both upsert). db.get() does not see unflushed new rows.
        for obj in db.new:
            if (
                isinstance(obj, ClinicPatient)
                and obj.clinic_id == clinic_id
                and obj.blind_patient_id == blind_patient_id
            ):
                row = obj
                break
    if row is None:
        row = ClinicPatient(
            clinic_id=clinic_id,
            blind_patient_id=blind_patient_id,
            display_name=name or "Patient",
            phone_last4=digits[-4:] if len(digits) >= 4 else "",
            phone_encrypted=encrypt_phone(digits) if digits else "",
            clinic_mrn=mrn,
            age_years=age_years,
            visit_count=1,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(row)
    else:
        if name:
            row.display_name = name
        if digits:
            row.phone_last4 = digits[-4:]
            row.phone_encrypted = encrypt_phone(digits)
        if mrn:
            row.clinic_mrn = mrn
        if age_years is not None:
            row.age_years = age_years
        if bump_visit:
            row.visit_count = int(row.visit_count or 0) + 1
        last = _as_utc(row.last_seen_at)
        when = _as_utc(now) or now
        if last is None or when >= last:
            row.last_seen_at = when
    return row


def sync_patients_from_appointments(db: Session, clinic_id: str) -> int:
    """Backfill roster from appointment rows (idempotent for missing keys)."""
    rows = db.scalars(
        select(Appointment).where(Appointment.clinic_id == clinic_id)
    ).all()
    added = 0
    for appt in rows:
        existing = db.get(ClinicPatient, (clinic_id, appt.blind_patient_id))
        if existing is None:
            upsert_clinic_patient(
                db,
                clinic_id=clinic_id,
                blind_patient_id=appt.blind_patient_id,
                display_name=appt.display_name,
                phone_digits="",
                bump_visit=False,
                seen_at=appt.scheduled_at or appt.created_at,
            )
            row = db.get(ClinicPatient, (clinic_id, appt.blind_patient_id))
            if row is not None:
                if appt.phone_encrypted and not row.phone_encrypted:
                    row.phone_encrypted = appt.phone_encrypted
                if appt.phone_last4 and not row.phone_last4:
                    row.phone_last4 = appt.phone_last4
            added += 1
        else:
            if appt.display_name and (
                not existing.display_name or existing.display_name == "Patient"
            ):
                existing.display_name = appt.display_name
            if appt.phone_last4 and not existing.phone_last4:
                existing.phone_last4 = appt.phone_last4
            if appt.phone_encrypted and not existing.phone_encrypted:
                existing.phone_encrypted = appt.phone_encrypted
            when = _as_utc(appt.scheduled_at or appt.created_at)
            existing_last = _as_utc(existing.last_seen_at)
            if when and (existing_last is None or when > existing_last):
                existing.last_seen_at = when
    return added


def list_clinic_patients_stmt(
    clinic_id: str,
    *,
    q: str | None = None,
    seen_from: datetime | None = None,
    seen_to: datetime | None = None,
) -> Select[tuple[ClinicPatient]]:
    stmt = select(ClinicPatient).where(ClinicPatient.clinic_id == clinic_id)
    needle = (q or "").strip()
    if needle:
        like = f"%{needle}%"
        clauses = [ClinicPatient.display_name.ilike(like)]
        digits = "".join(c for c in needle if c.isdigit())
        if digits:
            clauses.append(ClinicPatient.phone_last4.contains(digits[-4:]))
            clauses.append(ClinicPatient.clinic_mrn.ilike(f"%{digits}%"))
        else:
            clauses.append(ClinicPatient.clinic_mrn.ilike(like))
        stmt = stmt.where(or_(*clauses))
    if seen_from is not None:
        stmt = stmt.where(ClinicPatient.last_seen_at >= seen_from)
    if seen_to is not None:
        stmt = stmt.where(ClinicPatient.last_seen_at <= seen_to)
    return stmt.order_by(ClinicPatient.last_seen_at.desc())


def normalize_age_years(value: float | int | None) -> float | None:
    if value is None:
        return None
    age = float(value)
    if age != age:  # NaN
        raise ValueError("Age must be a number")
    if age < 0 or age > 130:
        raise ValueError("Age must be between 0 and 130 years")
    return round(age, 2)


def format_age_label(age_years: float | None) -> str:
    if age_years is None:
        return ""
    try:
        age = normalize_age_years(age_years)
    except ValueError:
        return ""
    if age is None:
        return ""
    if abs(age - round(age)) < 0.001:
        n = int(round(age))
        return f"{n} year" if n == 1 else f"{n} years"
    return f"{age:g} years"


def set_patient_age(
    db: Session,
    *,
    clinic_id: str,
    blind_patient_id: str,
    age_years: float | None,
) -> ClinicPatient | None:
    row = db.get(ClinicPatient, (clinic_id, blind_patient_id))
    if row is None:
        return None
    row.age_years = None if age_years is None else normalize_age_years(age_years)
    return row


def roster_print_fields(
    db: Session, clinic_id: str, blind_patient_id: str
) -> tuple[str, str, float | None]:
    """Return (display_name, clinic_mrn, age_years) for prescription printing."""
    row = db.get(ClinicPatient, (clinic_id, blind_patient_id))
    if row is None:
        return "", "", None
    age = float(row.age_years) if row.age_years is not None else None
    return row.display_name or "", row.clinic_mrn or "", age
