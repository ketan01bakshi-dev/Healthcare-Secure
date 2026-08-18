"""Allocate clinic MRNs and resolve patient identity to a stable mrn|{MRN} key."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.clinic_mrn_counter import ClinicMrnCounter
from app.models.clinic_patient import ClinicPatient
from app.models.record import ClinicalRecord
from app.services.clinic_patients import upsert_clinic_patient
from app.services.phone_crypto import decrypt_phone
from app.services.security import (
    build_patient_raw_identifier,
    normalize_mrn,
    normalize_phone_digits,
    tokenize_patient_identifier,
)


def allocate_clinic_mrn(db: Session, clinic_id: str) -> str:
    """Return next `{CLINIC}-{NNNNNN}` under a locked counter row."""
    cid = (clinic_id or "default").strip() or "default"
    prefix = re.sub(r"[^A-Z0-9]", "", cid.upper()) or "CLINIC"

    row = db.execute(
        select(ClinicMrnCounter)
        .where(ClinicMrnCounter.clinic_id == cid)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        row = ClinicMrnCounter(clinic_id=cid, next_value=1)
        db.add(row)
        db.flush()
        # Re-select with lock in case of races on engines that support it
        row = db.execute(
            select(ClinicMrnCounter)
            .where(ClinicMrnCounter.clinic_id == cid)
            .with_for_update()
        ).scalar_one()

    n = int(row.next_value or 1)
    row.next_value = n + 1
    db.flush()
    return f"{prefix}-{n:06d}"


def find_patient_by_phone(
    db: Session, clinic_id: str, phone_digits: str
) -> ClinicPatient | None:
    """Match roster by encrypted phone (narrowed by last4)."""
    digits = normalize_phone_digits(phone_digits)
    if len(digits) != 10:
        return None
    last4 = digits[-4:]
    candidates = db.scalars(
        select(ClinicPatient).where(
            ClinicPatient.clinic_id == clinic_id,
            ClinicPatient.phone_last4 == last4,
        )
    ).all()
    for row in candidates:
        stored = decrypt_phone(row.phone_encrypted or "")
        stored_digits = normalize_phone_digits(stored)
        if stored_digits == digits:
            return row
    # Fallback: scan all with encrypted phones (small clinics)
    if not candidates:
        all_rows = db.scalars(
            select(ClinicPatient).where(ClinicPatient.clinic_id == clinic_id)
        ).all()
        for row in all_rows:
            if not row.phone_encrypted:
                continue
            stored = decrypt_phone(row.phone_encrypted)
            if normalize_phone_digits(stored) == digits:
                return row
    return None


def find_patient_by_mrn(
    db: Session, clinic_id: str, clinic_mrn: str
) -> ClinicPatient | None:
    mrn = normalize_mrn(clinic_mrn)
    if not mrn:
        return None
    return db.scalars(
        select(ClinicPatient).where(
            ClinicPatient.clinic_id == clinic_id,
            ClinicPatient.clinic_mrn == mrn,
        )
    ).first()


def _migrate_legacy_blind(
    db: Session,
    *,
    clinic_id: str,
    old_blind: str,
    new_blind: str,
    actor: dict[str, str] | None = None,
) -> int:
    if not old_blind or not new_blind or old_blind == new_blind:
        return 0
    result = db.execute(
        update(ClinicalRecord)
        .where(
            ClinicalRecord.blind_patient_id == old_blind,
            ClinicalRecord.clinic_id == clinic_id,
        )
        .values(blind_patient_id=new_blind)
    )
    moved = int(result.rowcount or 0)
    if moved:
        now = datetime.now(timezone.utc).isoformat()
        db.add(
            ClinicalRecord(
                clinic_id=clinic_id,
                blind_patient_id=new_blind,
                encounter_data={
                    "type": "audit",
                    "action": "mrn_link",
                    "summary": f"Linked {moved} visit(s) to clinic MRN identity.",
                    "records_moved": moved,
                    "entered_by": actor or {},
                    "entered_at": now,
                },
            )
        )
    # Drop obsolete phone-keyed roster row if present
    old_row = db.get(ClinicPatient, (clinic_id, old_blind))
    if old_row is not None and old_blind != new_blind:
        db.delete(old_row)
    return moved


@dataclass
class ResolvedPatientIdentity:
    blind_patient_id: str
    clinic_mrn: str
    display_name: str
    phone_digits: str | None
    raw_identifier: str
    raw_identifier_shape: str
    records_migrated: int = 0


def resolve_patient_identity(
    db: Session,
    *,
    clinic_id: str,
    patient_name: str | None = None,
    patient_phone: str | None = None,
    clinic_mrn: str | None = None,
    raw_identifier: str | None = None,
    actor: dict[str, str] | None = None,
    bump_visit: bool = True,
) -> ResolvedPatientIdentity:
    """
    Always resolve to an MRN-keyed blind id.

    - Name + MRN → use that MRN
    - Name + phone → reuse roster MRN or allocate a new one
    - raw_identifier `mrn|…` → use as-is
    - raw_identifier `name|phone` → treat as name+phone and convert to MRN
    """
    name = (patient_name or "").strip()
    digits = normalize_phone_digits(patient_phone or "") if patient_phone else ""
    mrn = normalize_mrn(clinic_mrn or "")

    raw = (raw_identifier or "").strip()
    if raw.startswith("mrn|"):
        mrn = normalize_mrn(raw.split("|", 1)[1])
        if not mrn:
            raise ValueError("clinic MRN is required")
        if not name:
            existing = find_patient_by_mrn(db, clinic_id, mrn)
            name = (existing.display_name if existing else "") or mrn
    elif raw and "|" in raw and not mrn:
        # Legacy name|phone composite from clients
        parts = raw.split("|", 1)
        if not name:
            name = parts[0].strip()
        if not digits:
            digits = normalize_phone_digits(parts[1])

    if mrn:
        if not name:
            raise ValueError("patient_name is required with clinic_mrn")
        composite = build_patient_raw_identifier(
            name, digits or "0000000000", clinic_mrn=mrn
        )
        blind = tokenize_patient_identifier(composite)
        migrated = 0
        if digits and len(digits) == 10:
            legacy = build_patient_raw_identifier(name, digits)
            legacy_blind = tokenize_patient_identifier(legacy)
            migrated = _migrate_legacy_blind(
                db,
                clinic_id=clinic_id,
                old_blind=legacy_blind,
                new_blind=blind,
                actor=actor,
            )
        upsert_clinic_patient(
            db,
            clinic_id=clinic_id,
            blind_patient_id=blind,
            display_name=name,
            phone_digits=digits if len(digits) == 10 else "",
            clinic_mrn=mrn,
            bump_visit=bump_visit,
        )
        return ResolvedPatientIdentity(
            blind_patient_id=blind,
            clinic_mrn=mrn,
            display_name=name,
            phone_digits=digits if len(digits) == 10 else None,
            raw_identifier=f"mrn|{mrn}",
            raw_identifier_shape="mrn|{clinic_mrn}",
            records_migrated=migrated,
        )

    if not name or not digits or len(digits) != 10:
        raise ValueError("patient_name and a 10-digit patient_phone are required")

    existing = find_patient_by_phone(db, clinic_id, digits)
    if existing and normalize_mrn(existing.clinic_mrn or ""):
        mrn = normalize_mrn(existing.clinic_mrn)
        if existing.display_name:
            name = existing.display_name
    else:
        mrn = allocate_clinic_mrn(db, clinic_id)

    composite = build_patient_raw_identifier(name, digits, clinic_mrn=mrn)
    blind = tokenize_patient_identifier(composite)
    legacy = build_patient_raw_identifier(name, digits)
    legacy_blind = tokenize_patient_identifier(legacy)
    migrated = _migrate_legacy_blind(
        db,
        clinic_id=clinic_id,
        old_blind=legacy_blind,
        new_blind=blind,
        actor=actor,
    )
    # If an older roster row existed under phone-keyed blind without MRN, migrate fields
    if existing and existing.blind_patient_id != blind:
        _migrate_legacy_blind(
            db,
            clinic_id=clinic_id,
            old_blind=existing.blind_patient_id,
            new_blind=blind,
            actor=actor,
        )

    upsert_clinic_patient(
        db,
        clinic_id=clinic_id,
        blind_patient_id=blind,
        display_name=name,
        phone_digits=digits,
        clinic_mrn=mrn,
        bump_visit=bump_visit,
    )
    return ResolvedPatientIdentity(
        blind_patient_id=blind,
        clinic_mrn=mrn,
        display_name=name,
        phone_digits=digits,
        raw_identifier=f"mrn|{mrn}",
        raw_identifier_shape="mrn|{clinic_mrn}",
        records_migrated=migrated,
    )
