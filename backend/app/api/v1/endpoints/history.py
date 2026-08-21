"""Patient history lookup, tokenize helper, and scanned document upload."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.record import ClinicalRecord
from app.services.attachment_store import load_attachment, save_attachment
from app.services.doctor_auth import ClinicalSession, DoctorOnly, DoctorSession, SessionInfo
from app.services.lml_parser import ClinicalParseResult, MedicationItem
from app.services.pdf_generator import (
    generate_prescription_pdf,
    generate_referral_pdf,
    prescription_issue_timestamp,
)
from app.services.security import (
    build_patient_raw_identifier,
    normalize_mrn,
    normalize_phone_digits,
    tokenize_patient_identifier,
)
from app.services.vitals_validation import (
    temperature_to_f,
    validate_notes,
    validate_vitals_dict,
)

router = APIRouter(prefix="/history")

_MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
_ALLOWED_DOC_TYPES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    }
)


class HistorySearchRequest(BaseModel):
    """Frontend payload — raw identifier is tokenized in-memory and never stored."""

    raw_identifier: str = Field(..., min_length=1)

    @field_validator("raw_identifier")
    @classmethod
    def non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("raw_identifier must not be blank")
        return stripped


class TokenizeRequest(BaseModel):
    """Lock a patient by name + phone, optional clinic MRN, or raw_identifier."""

    patient_name: str | None = None
    patient_phone: str | None = None
    clinic_mrn: str | None = None
    raw_identifier: str | None = None

    @model_validator(mode="after")
    def require_identity(self) -> TokenizeRequest:
        if self.raw_identifier and self.raw_identifier.strip():
            return self
        name = (self.patient_name or "").strip()
        phone = (self.patient_phone or "").strip()
        mrn = (self.clinic_mrn or "").strip()
        if mrn:
            if not name:
                raise ValueError("patient_name is required with clinic_mrn")
            build_patient_raw_identifier(name, phone or "0000000000", clinic_mrn=mrn)
            return self
        if not name or not phone:
            raise ValueError("patient_name and patient_phone are required")
        build_patient_raw_identifier(name, phone)
        return self


class ClinicalRecordOut(BaseModel):
    id: UUID
    blind_patient_id: str
    created_at: datetime | None
    encounter_data: dict[str, Any]

    model_config = {"from_attributes": True}


def _as_utc_aware(value: datetime | None) -> datetime | None:
    """SQLite ``func.now()`` is naive UTC — mark it so clients convert to IST correctly."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class TokenizeResponse(BaseModel):
    blind_patient_id: str
    blind_name_id: str | None = None
    blind_phone_id: str | None = None
    clinic_mrn: str | None = None
    raw_identifier_shape: str = "name|phone_digits"
    age_years: float | None = None


class ChangePhoneRequest(BaseModel):
    """Move all history from name+old phone to name+new phone (HMAC remapped)."""

    patient_name: str = Field(..., min_length=1)
    old_phone: str = Field(..., min_length=1)
    new_phone: str = Field(..., min_length=1)
    clinic_mrn: str | None = None

    @field_validator("patient_name")
    @classmethod
    def name_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("patient name is required")
        return stripped


class ChangePhoneResponse(BaseModel):
    blind_patient_id: str
    blind_phone_id: str | None = None
    new_phone_digits: str
    records_moved: int
    clinic_mrn: str | None = None


def _tokenize_or_400(raw: str) -> str:
    try:
        return tokenize_patient_identifier(raw)
    except ValueError as exc:
        reason = str(exc)
        detail = (
            "Server SECRET_SALT is not configured. Set a real value in backend/.env and restart the API."
            if "SECRET_SALT" in reason
            else "Unable to tokenize identifier"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from None


def _resolve_raw_identifier(
    body: TokenizeRequest,
) -> tuple[str, str | None, str | None, str | None]:
    """Return (composite_raw, name, phone_digits, mrn)."""
    if body.raw_identifier and body.raw_identifier.strip():
        return body.raw_identifier.strip(), None, None, None
    name = (body.patient_name or "").strip()
    phone = (body.patient_phone or "").strip()
    mrn = normalize_mrn(body.clinic_mrn or "") or None
    try:
        composite = build_patient_raw_identifier(
            name,
            phone or ("0000000000" if mrn else ""),
            clinic_mrn=mrn,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    digits = normalize_phone_digits(phone) if phone else None
    return composite, name, digits, mrn


@router.post("/tokenize", response_model=TokenizeResponse)
def tokenize_patient(
    body: TokenizeRequest,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> TokenizeResponse:
    """Resolve/issue clinic MRN and return HMAC blind tokens for history linkage."""
    from app.services.mrn_identity import resolve_patient_identity

    try:
        resolved = resolve_patient_identity(
            db,
            clinic_id=session.clinic_id,
            patient_name=body.patient_name,
            patient_phone=body.patient_phone,
            clinic_mrn=body.clinic_mrn,
            raw_identifier=body.raw_identifier,
            actor={
                "user_id": session.user_id,
                "display_name": session.display_name,
                "role": session.role,
            },
            bump_visit=False,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None

    db.commit()
    from app.models.clinic_patient import ClinicPatient

    roster = db.get(ClinicPatient, (session.clinic_id, resolved.blind_patient_id))
    resolved_age = float(roster.age_years) if roster is not None and roster.age_years is not None else None
    blind_name = (
        _tokenize_or_400(resolved.display_name) if resolved.display_name else None
    )
    blind_phone = (
        _tokenize_or_400(resolved.phone_digits) if resolved.phone_digits else None
    )
    return TokenizeResponse(
        blind_patient_id=resolved.blind_patient_id,
        blind_name_id=blind_name,
        blind_phone_id=blind_phone,
        clinic_mrn=resolved.clinic_mrn,
        raw_identifier_shape=resolved.raw_identifier_shape,
        age_years=resolved_age,
    )


class ClinicPatientOut(BaseModel):
    blind_patient_id: str
    display_name: str
    phone_last4: str
    clinic_mrn: str = ""
    visit_count: int = 1
    last_seen_at: str | None = None
    first_seen_at: str | None = None
    has_phone: bool = False
    age_years: float | None = None


@router.get("/patients", response_model=list[ClinicPatientOut])
def list_clinic_patients(
    session: DoctorSession,
    db: Session = Depends(get_db),
    q: str | None = None,
    period: str | None = None,
) -> list[ClinicPatientOut]:
    """Directory of patients known to this clinic (search + recent filters)."""
    from datetime import timedelta

    from app.services.clinic_patients import (
        compute_visit_counts,
        list_clinic_patients_stmt,
        sync_patients_from_appointments,
    )

    sync_patients_from_appointments(db, session.clinic_id)
    db.commit()

    seen_from: datetime | None = None
    period_key = (period or "").strip().lower()
    now = datetime.now(timezone.utc)
    if period_key in {"week", "7d"}:
        seen_from = now - timedelta(days=7)
    elif period_key in {"month", "30d"}:
        seen_from = now - timedelta(days=30)

    stmt = list_clinic_patients_stmt(
        session.clinic_id, q=q, seen_from=seen_from, seen_to=None
    )
    rows = db.scalars(stmt).all()
    visit_counts = compute_visit_counts(
        db,
        session.clinic_id,
        [r.blind_patient_id for r in rows],
    )
    return [
        ClinicPatientOut(
            blind_patient_id=r.blind_patient_id,
            display_name=r.display_name,
            phone_last4=r.phone_last4 or "",
            clinic_mrn=r.clinic_mrn or "",
            visit_count=int(visit_counts.get(r.blind_patient_id, 0)),
            last_seen_at=r.last_seen_at.isoformat() if r.last_seen_at else None,
            first_seen_at=r.first_seen_at.isoformat() if r.first_seen_at else None,
            has_phone=bool(r.phone_encrypted),
            age_years=float(r.age_years) if r.age_years is not None else None,
        )
        for r in rows
    ]


class ClinicalSearchMatch(BaseModel):
    blind_patient_id: str
    display_name: str
    phone_last4: str = ""
    clinic_mrn: str = ""
    match_type: str  # "name" | "medication" | "diagnosis" | "symptom" | "treatment" | "observation"
    match_text: str  # the snippet that matched
    record_date: str | None = None


@router.get("/clinical-search", response_model=list[ClinicalSearchMatch])
def clinical_search(
    q: str,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> list[ClinicalSearchMatch]:
    """
    Universal search across patient names AND clinical record content
    (medications, diagnoses, symptoms, observations, lab results, health profile).
    Returns deduplicated matches ordered by relevance (name first, then clinical).
    Lab users see only their own uploaded results.
    """
    from app.models.clinic_patient import ClinicPatient
    from app.services.clinic_patients import list_clinic_patients_stmt

    term = (q or "").strip().lower()
    if len(term) < 2:
        return []

    results: list[ClinicalSearchMatch] = []
    seen_patient_ids: set[str] = set()

    # --- 1. Patient name / phone / MRN matches ---
    stmt = list_clinic_patients_stmt(session.clinic_id, q=term)
    patient_rows = db.scalars(stmt).all()
    patient_meta: dict[str, ClinicPatient] = {}
    for row in patient_rows:
        patient_meta[row.blind_patient_id] = row
        results.append(
            ClinicalSearchMatch(
                blind_patient_id=row.blind_patient_id,
                display_name=row.display_name,
                phone_last4=row.phone_last4 or "",
                clinic_mrn=row.clinic_mrn or "",
                match_type="name",
                match_text=row.display_name,
                record_date=None,
            )
        )
        seen_patient_ids.add(row.blind_patient_id)

    # Pre-fetch all clinic patients for name lookup in clinical hits
    all_patients = db.scalars(
        select(ClinicPatient).where(ClinicPatient.clinic_id == session.clinic_id)
    ).all()
    pid_to_patient: dict[str, ClinicPatient] = {
        p.blind_patient_id: p for p in all_patients
    }

    # --- 2. Clinical record content search ---
    record_stmt = (
        select(ClinicalRecord)
        .where(ClinicalRecord.clinic_id == session.clinic_id)
        .order_by(ClinicalRecord.created_at.desc())
    )
    records = db.scalars(record_stmt).all()

    # Track one best match per (patient, match_type) to avoid flood
    seen_clinical: set[tuple[str, str]] = set()

    for record in records:
        data: dict[str, Any] = dict(record.encounter_data or {})
        rec_type = data.get("type", "")

        # Lab users: only their own uploads
        if session.role == "lab" and rec_type not in ("document", "lab_result"):
            continue

        pid = record.blind_patient_id
        pat = pid_to_patient.get(pid)
        if pat is None:
            continue

        rec_date = (
            record.created_at.date().isoformat() if record.created_at else None
        )

        def _try_match(field_type: str, text: str) -> bool:
            """Return True and append if term in text and not already seen."""
            if term not in text.lower():
                return False
            key = (pid, field_type)
            if key in seen_clinical:
                return False
            seen_clinical.add(key)
            results.append(
                ClinicalSearchMatch(
                    blind_patient_id=pid,
                    display_name=pat.display_name,
                    phone_last4=pat.phone_last4 or "",
                    clinic_mrn=pat.clinic_mrn or "",
                    match_type=field_type,
                    match_text=text[:120],
                    record_date=rec_date,
                )
            )
            return True

        # Medications
        for med in data.get("medications") or []:
            if isinstance(med, dict):
                med_text = " ".join(
                    str(med.get(k, ""))
                    for k in ("name", "dosage", "frequency", "duration")
                    if med.get(k)
                )
                _try_match("medication", med_text)

        # Diagnoses
        for diag in data.get("diagnoses") or data.get("diagnosis") or []:
            _try_match("diagnosis", str(diag))

        # Symptoms
        for sym in data.get("symptoms") or []:
            _try_match("symptom", str(sym))

        # Clinical observations / treatment notes
        for obs in data.get("clinical_observations") or []:
            _try_match("observation", str(obs))

        # Lab result summary
        if rec_type == "lab_result":
            for k, v in data.items():
                if k in ("type", "raw_identifier", "entered_by", "entered_at"):
                    continue
                if isinstance(v, (str, int, float)) and term in str(v).lower():
                    _try_match("lab_result", f"{k}: {v}")
                    break

        # Ongoing health profile text
        for field in ("ongoing_medications", "health_issues"):
            val = data.get(field, "")
            if val:
                _try_match("treatment", str(val))

        # Document title / label
        if rec_type in ("document", "diagnostic_report"):
            label = data.get("label") or data.get("document_kind") or ""
            if label:
                _try_match("document", str(label))

    return results


@router.get("/patients/{blind_patient_id}/identity")
def clinic_patient_identity(
    blind_patient_id: str,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Return name + phone so staff can lock the patient without re-typing."""
    from app.models.clinic_patient import ClinicPatient
    from app.services.phone_crypto import decrypt_phone

    row = db.get(ClinicPatient, (session.clinic_id, blind_patient_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    phone = decrypt_phone(row.phone_encrypted)
    digits = "".join(c for c in (phone or "") if c.isdigit())
    phone_out = ""
    if len(digits) >= 10:
        phone_out = digits[-10:] if len(digits) > 10 else digits
    elif not (row.clinic_mrn or "").strip():
        raise HTTPException(
            status_code=400,
            detail="No phone or MRN stored for this patient.",
        )
    return {
        "display_name": row.display_name,
        "phone": phone_out,
        "clinic_mrn": row.clinic_mrn or "",
        "age_years": "" if row.age_years is None else str(row.age_years),
    }


class PatientAgeRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    age_years: float | None = None

    @field_validator("raw_identifier")
    @classmethod
    def age_raw_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("raw_identifier must not be blank")
        return stripped


@router.post("/patient-age")
def save_patient_age(
    body: PatientAgeRequest,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> dict[str, float | None]:
    """Persist roster age for the locked patient (all clinics)."""
    from app.services.clinic_patients import normalize_age_years, set_patient_age

    if session.role == "lab":
        raise HTTPException(status_code=403, detail="Lab cannot update patient age")
    try:
        age = None if body.age_years is None else normalize_age_years(body.age_years)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    blind_id = _tokenize_or_400(body.raw_identifier)
    row = set_patient_age(
        db,
        clinic_id=session.clinic_id,
        blind_patient_id=blind_id,
        age_years=age,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    db.commit()
    return {"age_years": row.age_years}


def _parse_lab_orders(raw: str | None) -> dict[str, list[str]]:
    selected: list[str] = []
    dismissed: list[str] = []
    if not (raw or "").strip():
        return {"selected": selected, "dismissed": dismissed}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"selected": selected, "dismissed": dismissed}
    if not isinstance(data, dict):
        return {"selected": selected, "dismissed": dismissed}

    def _ids(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in out:
                out.append(text)
            if len(out) >= 200:
                break
        return out

    return {
        "selected": _ids(data.get("selected")),
        "dismissed": _ids(data.get("dismissed")),
    }


class LabOrdersBody(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    selected: list[str] = Field(default_factory=list)
    dismissed: list[str] = Field(default_factory=list)

    @field_validator("raw_identifier")
    @classmethod
    def lab_orders_raw_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("raw_identifier must not be blank")
        return stripped


def _require_lab_orders_role(session: SessionInfo) -> None:
    if session.role not in ("doctor", "staff", "lab"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lab orders are not available for this role",
        )


@router.get("/lab-orders")
def get_lab_orders(
    raw_identifier: str,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> dict[str, list[str]]:
    """Visit diagnostic ticks stored on the clinic patient roster."""
    from app.models.clinic_patient import ClinicPatient

    _require_lab_orders_role(session)
    if not (raw_identifier or "").strip():
        raise HTTPException(status_code=400, detail="raw_identifier required")
    blind_id = _tokenize_or_400(raw_identifier.strip())
    row = db.get(ClinicPatient, (session.clinic_id, blind_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return _parse_lab_orders(row.lab_orders_json)


@router.put("/lab-orders")
def put_lab_orders(
    body: LabOrdersBody,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> dict[str, list[str]]:
    """Persist selected/dismissed diagnostics so Lab desk sees Visit ticks."""
    from app.models.clinic_patient import ClinicPatient

    _require_lab_orders_role(session)
    parsed = _parse_lab_orders(
        json.dumps({"selected": body.selected, "dismissed": body.dismissed})
    )
    blind_id = _tokenize_or_400(body.raw_identifier)
    row = db.get(ClinicPatient, (session.clinic_id, blind_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    row.lab_orders_json = json.dumps(parsed)
    db.commit()
    return parsed


@router.post("/change-phone", response_model=ChangePhoneResponse)
def change_patient_phone(
    body: ChangePhoneRequest,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> ChangePhoneResponse:
    """
    Update mobile on an MRN-keyed patient (preferred), or remap legacy name|phone history.

    When clinic_mrn is set, the blind patient id stays on ``mrn|{MRN}`` and only the
    roster phone is updated — history is not remapped.
    """
    from app.services.clinic_patients import upsert_clinic_patient
    from app.services.mrn_identity import resolve_patient_identity

    name = body.patient_name.strip()
    old_digits = normalize_phone_digits(body.old_phone)
    new_digits = normalize_phone_digits(body.new_phone)
    if len(new_digits) != 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New mobile must be exactly 10 digits",
        )
    if old_digits == new_digits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New mobile number is the same as the current one.",
        )

    mrn = normalize_mrn(body.clinic_mrn or "") or None
    if mrn:
        try:
            resolved = resolve_patient_identity(
                db,
                clinic_id=session.clinic_id,
                patient_name=name,
                patient_phone=new_digits,
                clinic_mrn=mrn,
                actor={
                    "user_id": session.user_id,
                    "display_name": session.display_name,
                    "role": session.role,
                },
                bump_visit=False,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from None
        issued, issued_human, issued_iso = prescription_issue_timestamp()
        db.add(
            ClinicalRecord(
                clinic_id=session.clinic_id,
                blind_patient_id=resolved.blind_patient_id,
                encounter_data={
                    "type": "audit",
                    "action": "phone_change",
                    "summary": "Mobile updated on MRN identity; history unchanged.",
                    "records_moved": 0,
                    "entered_by": {
                        "user_id": session.user_id,
                        "display_name": session.display_name,
                        "role": session.role,
                    },
                    "entered_at": issued_iso,
                    "entered_at_display": issued_human,
                },
            )
        )
        db.commit()
        return ChangePhoneResponse(
            blind_patient_id=resolved.blind_patient_id,
            blind_phone_id=_tokenize_or_400(new_digits),
            new_phone_digits=new_digits,
            records_moved=0,
            clinic_mrn=resolved.clinic_mrn,
        )

    # Legacy path: no MRN yet — resolve to auto-MRN and migrate old phone key
    try:
        # Ensure old records are under name|old phone then migrate via resolve
        resolved = resolve_patient_identity(
            db,
            clinic_id=session.clinic_id,
            patient_name=name,
            patient_phone=new_digits,
            actor={
                "user_id": session.user_id,
                "display_name": session.display_name,
                "role": session.role,
            },
            bump_visit=False,
        )
        # Also migrate old-phone legacy blind if different from name|new before MRN
        old_legacy_blind = _tokenize_or_400(
            build_patient_raw_identifier(name, old_digits)
        )
        if old_legacy_blind != resolved.blind_patient_id:
            from app.services.mrn_identity import _migrate_legacy_blind

            moved_extra = _migrate_legacy_blind(
                db,
                clinic_id=session.clinic_id,
                old_blind=old_legacy_blind,
                new_blind=resolved.blind_patient_id,
                actor={
                    "user_id": session.user_id,
                    "display_name": session.display_name,
                    "role": session.role,
                },
            )
        else:
            moved_extra = 0
        upsert_clinic_patient(
            db,
            clinic_id=session.clinic_id,
            blind_patient_id=resolved.blind_patient_id,
            display_name=name,
            phone_digits=new_digits,
            clinic_mrn=resolved.clinic_mrn,
            bump_visit=False,
        )
        db.commit()
        return ChangePhoneResponse(
            blind_patient_id=resolved.blind_patient_id,
            blind_phone_id=_tokenize_or_400(new_digits),
            new_phone_digits=new_digits,
            records_moved=resolved.records_migrated + moved_extra,
            clinic_mrn=resolved.clinic_mrn,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None


@router.post("/search", response_model=list[ClinicalRecordOut])
def search_clinical_history(
    body: HistorySearchRequest,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> list[ClinicalRecordOut]:
    """
    Resolve a raw identifier to ``blind_patient_id`` and return matching records
    newest-first. Lab users only receive uploaded documents (not Rx / vitals).
    """
    blind_id = _tokenize_or_400(body.raw_identifier)

    stmt = (
        select(ClinicalRecord)
        .where(
            ClinicalRecord.blind_patient_id == blind_id,
            ClinicalRecord.clinic_id == session.clinic_id,
        )
        .order_by(ClinicalRecord.created_at.desc())
    )
    records = list(db.scalars(stmt).all())
    out: list[ClinicalRecordOut] = []
    for record in records:
        data = dict(record.encounter_data or {})
        if session.role == "lab" and data.get("type") not in (
            "document",
            "lab_result",
        ):
            continue
        if data.get("type") == "document" and (
            "content_base64" in data or "content_path" in data
        ):
            data = {
                **{
                    k: v
                    for k, v in data.items()
                    if k not in ("content_base64", "content_path")
                },
                "has_content": True,
                "content_bytes": data.get("size_bytes"),
            }
        out.append(
            ClinicalRecordOut(
                id=record.id,
                blind_patient_id=record.blind_patient_id,
                created_at=_as_utc_aware(record.created_at),
                encounter_data=data,
            )
        )
    return out


@router.post("/documents", response_model=ClinicalRecordOut)
async def upload_patient_document(
    session: DoctorSession,
    raw_identifier: str = Form(..., min_length=1),
    document_kind: Literal[
        "scanned_prescription",
        "diagnostic_report",
        "other",
    ] = Form("other"),
    title: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ClinicalRecord:
    """
    Attach a scanned prescription or diagnostic report to the patient history.
    Lab users may only upload diagnostic reports.
    """
    if session.role == "lab":
        document_kind = "diagnostic_report"

    blind_id = _tokenize_or_400(raw_identifier.strip())

    content_type = (file.content_type or "application/octet-stream").lower()
    if content_type not in _ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Allowed types: PDF, JPEG, PNG, WebP",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )
    if len(raw) > _MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Document exceeds 8 MiB limit",
        )

    filename = (file.filename or "document").strip() or "document"
    issued, issued_human, issued_iso = prescription_issue_timestamp()
    content_path = save_attachment(
        blind_patient_id=blind_id,
        filename=filename,
        content=raw,
        content_type=content_type,
    )
    encounter: dict[str, Any] = {
        "type": "document",
        "document_kind": document_kind,
        "title": (title or filename).strip()[:200],
        "filename": filename[:200],
        "content_type": content_type,
        "size_bytes": len(raw),
        "content_path": content_path,
        "diagnoses": [],
        "clinical_observations": [
            f"Uploaded {document_kind.replace('_', ' ')}: {(title or filename).strip()}"
        ],
        "medications": [],
        "symptoms": [],
        "entered_by": {
            "user_id": session.user_id,
            "display_name": session.display_name,
            "role": session.role,
        },
        "entered_at": issued_iso,
        "entered_at_display": issued_human,
    }

    record = ClinicalRecord(
        clinic_id=session.clinic_id,
        blind_patient_id=blind_id,
        encounter_data=encounter,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    slim = {
        **{
            k: v
            for k, v in encounter.items()
            if k not in ("content_base64", "content_path")
        },
        "has_content": True,
    }
    return ClinicalRecordOut(
        id=record.id,
        blind_patient_id=record.blind_patient_id,
        created_at=_as_utc_aware(record.created_at),
        encounter_data=slim,
    )


class DocumentFetchRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)

    @field_validator("raw_identifier")
    @classmethod
    def non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("raw_identifier must not be blank")
        return stripped


@router.post("/documents/{record_id}/content")
def fetch_document_content(
    record_id: UUID,
    body: DocumentFetchRequest,
    _auth: DoctorSession,
    db: Session = Depends(get_db),
) -> Response:
    """Return stored document bytes after verifying patient token ownership."""
    blind_id = _tokenize_or_400(body.raw_identifier)
    record = db.get(ClinicalRecord, record_id)
    if (
        record is None
        or record.blind_patient_id != blind_id
        or getattr(record, "clinic_id", "default") != _auth.clinic_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    data = record.encounter_data or {}
    if data.get("type") != "document":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Record is not a document",
        )

    b64 = data.get("content_base64")
    content_path = data.get("content_path")
    raw: bytes | None = None
    media = str(data.get("content_type") or "application/octet-stream")
    if content_path:
        try:
            raw, media = load_attachment(str(content_path))
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document content missing on disk",
            ) from exc
    elif b64:
        try:
            raw = base64.b64decode(b64, validate=True)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Corrupt document payload",
            ) from exc
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document content missing",
        )

    filename = str(data.get("filename") or "document")
    return Response(
        content=raw,
        media_type=media,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/records/{record_id}/pdf")
def fetch_prescription_pdf(
    record_id: UUID,
    body: DocumentFetchRequest,
    _auth: ClinicalSession,
    db: Session = Depends(get_db),
) -> Response:
    """Regenerate a prescription PDF from stored clinical fields (no PHI)."""
    blind_id = _tokenize_or_400(body.raw_identifier)
    record = db.get(ClinicalRecord, record_id)
    if (
        record is None
        or record.blind_patient_id != blind_id
        or getattr(record, "clinic_id", "default") != _auth.clinic_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found",
        )

    data = record.encounter_data or {}
    if data.get("type") not in (None, "prescription", "visit"):
        if data.get("type") == "document":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Record is a document; use /documents/{id}/content",
            )

    meds_raw = data.get("medications") or []
    medications: list[MedicationItem] = []
    if isinstance(meds_raw, list):
        for item in meds_raw:
            if isinstance(item, dict):
                medications.append(
                    MedicationItem(
                        name=str(item.get("name") or ""),
                        dosage=str(item.get("dosage") or ""),
                        frequency=str(item.get("frequency") or ""),
                        duration=str(item.get("duration") or ""),
                    )
                )

    clinical = ClinicalParseResult(
        symptoms=list(data.get("symptoms") or []),
        clinical_observations=list(data.get("clinical_observations") or []),
        diagnoses=list(data.get("diagnoses") or data.get("diagnosis") or []),
        medications=[m for m in medications if m.name],
    )
    doctor = str(data.get("doctor_name") or settings.doctor_name)
    issued_at = None
    iso = data.get("issued_at")
    if isinstance(iso, str) and iso.strip():
        try:
            issued_at = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            issued_at = None

    try:
        from app.services.clinic_patients import roster_print_fields

        rx_name, rx_mrn, rx_age = roster_print_fields(
            db, _auth.clinic_id, blind_id
        )
        pdf_buffer = generate_prescription_pdf(
            clinical,
            patient_token=blind_id,
            doctor_name=doctor,
            issued_at=issued_at,
            patient_name=rx_name or None,
            clinic_mrn=rx_mrn or data.get("clinic_mrn") or None,
            patient_age_years=rx_age,
        )
        pdf_bytes = pdf_buffer.getvalue()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {exc}",
        ) from exc

    filename = f"prescription-{record_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


class VitalsPayload(BaseModel):
    blood_pressure: str = Field(default="", max_length=40)
    pulse: str = Field(default="", max_length=40)
    temperature: str = Field(default="", max_length=40)
    spo2: str = Field(default="", max_length=40)
    weight: str = Field(default="", max_length=40)
    height: str = Field(default="", max_length=40)
    respiratory_rate: str = Field(default="", max_length=40)
    hemoglobin: str = Field(default="", max_length=40)


class VitalsEntryRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    vitals: VitalsPayload = Field(default_factory=VitalsPayload)
    diagnostic_notes: str = Field(default="", max_length=2000)
    # Age in years — enables pediatric ranges when under 18.
    age_years: float | None = None
    # F (default) or C — stored as °F after conversion.
    temperature_unit: str = Field(default="F", max_length=1)

    @field_validator("raw_identifier")
    @classmethod
    def non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("raw_identifier must not be blank")
        return stripped

    @field_validator("temperature_unit")
    @classmethod
    def unit_fc(cls, value: str) -> str:
        u = (value or "F").strip().upper()
        if u not in ("F", "C"):
            raise ValueError("temperature_unit must be F or C")
        return u

    @field_validator("diagnostic_notes")
    @classmethod
    def notes_length(cls, value: str) -> str:
        err = validate_notes(value or "")
        if err:
            raise ValueError(err)
        return value

    @model_validator(mode="after")
    def ranges_with_age(self) -> VitalsEntryRequest:
        err = validate_vitals_dict(
            self.vitals.model_dump(),
            age_years=self.age_years,
            temperature_unit=self.temperature_unit,
        )
        if err:
            raise ValueError(err)
        # Persist temperature in °F for consistent trends.
        temp = (self.vitals.temperature or "").strip()
        if temp:
            self.vitals.temperature = temperature_to_f(temp, self.temperature_unit)
        return self


@router.post("/vitals", response_model=ClinicalRecordOut)
def add_vitals_entry(
    body: VitalsEntryRequest,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> ClinicalRecordOut:
    """
    Staff or doctor can append vitals / diagnostic notes.
    Each entry records who entered it (user_id + display name) for audit.
    """
    blind_id = _tokenize_or_400(body.raw_identifier)
    issued, issued_human, issued_iso = prescription_issue_timestamp()
    vitals = body.vitals.model_dump()
    notes = (body.diagnostic_notes or "").strip()
    if not any(str(v).strip() for v in vitals.values()) and not notes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter at least one vital or a diagnostic note",
        )

    summary_parts = [
        f"{k.replace('_', ' ')}={v.strip()}"
        for k, v in vitals.items()
        if isinstance(v, str) and v.strip()
    ]
    if notes:
        summary_parts.append(f"notes={notes[:120]}")

    encounter: dict[str, Any] = {
        "type": "vitals",
        "vitals": vitals,
        "diagnostic_notes": notes,
        "age_years": body.age_years,
        "clinical_observations": summary_parts,
        "diagnoses": [],
        "medications": [],
        "symptoms": [],
        "entered_by": {
            "user_id": session.user_id,
            "display_name": session.display_name,
            "role": session.role,
        },
        "entered_at": issued_iso,
        "entered_at_display": issued_human,
    }
    record = ClinicalRecord(
        clinic_id=session.clinic_id,
        blind_patient_id=blind_id,
        encounter_data=encounter,
    )
    db.add(record)
    if body.age_years is not None:
        from app.services.clinic_patients import set_patient_age

        try:
            set_patient_age(
                db,
                clinic_id=session.clinic_id,
                blind_patient_id=blind_id,
                age_years=body.age_years,
            )
        except ValueError:
            pass
    db.commit()
    db.refresh(record)
    return ClinicalRecordOut(
        id=record.id,
        blind_patient_id=record.blind_patient_id,
        created_at=_as_utc_aware(record.created_at),
        encounter_data=encounter,
    )


class LabResultRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    test_name: str = Field(..., min_length=1, max_length=120)
    value: str = Field(..., min_length=1, max_length=80)
    unit: str = Field(default="", max_length=40)
    reference_range: str = Field(default="", max_length=80)
    collected_at: str = Field(default="", max_length=40)

    @field_validator("raw_identifier", "test_name", "value")
    @classmethod
    def non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


@router.post("/lab-results", response_model=ClinicalRecordOut)
def add_lab_result(
    body: LabResultRequest,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> ClinicalRecordOut:
    """Structured lab result for timeline (doctors/staff/lab)."""
    if session.role not in ("doctor", "staff", "lab"):
        raise HTTPException(status_code=403, detail="Not allowed")
    blind_id = _tokenize_or_400(body.raw_identifier)
    issued, issued_human, issued_iso = prescription_issue_timestamp()
    summary = f"{body.test_name}={body.value}"
    if body.unit.strip():
        summary += f" {body.unit.strip()}"
    if body.reference_range.strip():
        summary += f" (ref {body.reference_range.strip()})"
    encounter: dict[str, Any] = {
        "type": "lab_result",
        "test_name": body.test_name.strip(),
        "value": body.value.strip(),
        "unit": body.unit.strip(),
        "reference_range": body.reference_range.strip(),
        "collected_at": body.collected_at.strip(),
        "clinical_observations": [summary],
        "diagnoses": [],
        "medications": [],
        "symptoms": [],
        "entered_by": {
            "user_id": session.user_id,
            "display_name": session.display_name,
            "role": session.role,
        },
        "entered_at": issued_iso,
        "entered_at_display": issued_human,
    }
    record = ClinicalRecord(
        clinic_id=session.clinic_id,
        blind_patient_id=blind_id,
        encounter_data=encounter,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ClinicalRecordOut(
        id=record.id,
        blind_patient_id=record.blind_patient_id,
        created_at=_as_utc_aware(record.created_at),
        encounter_data=encounter,
    )


class BillingEntryRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    amount_inr: float = Field(..., gt=0, le=10_000_000)
    note: str = Field(default="", max_length=200)
    kind: Literal["charge", "payment"] = "charge"

    @field_validator("raw_identifier")
    @classmethod
    def non_blank_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("note")
    @classmethod
    def trim_note(cls, value: str) -> str:
        return (value or "").strip()


class BillingSummaryOut(BaseModel):
    currency: str = "INR"
    today_charges_inr: float
    total_charges_inr: float
    total_paid_inr: float
    amount_due_inr: float


def _billing_kind(data: dict[str, Any]) -> Literal["charge", "payment"] | None:
    """Classify billing encounter; legacy rows without kind count as charge."""
    if str(data.get("type") or "").strip() != "billing":
        return None
    raw = str(data.get("kind") or "charge").strip().lower()
    if raw == "payment":
        return "payment"
    return "charge"


def _billing_amount_inr(data: dict[str, Any]) -> float | None:
    raw = data.get("amount_inr", data.get("amount"))
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        return None
    if amount <= 0 or amount > 10_000_000:
        return None
    return round(amount, 2)


def _clinic_tz_kolkata():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Asia/Kolkata")
    except Exception:  # noqa: BLE001
        return timezone.utc


@router.post("/billing", response_model=ClinicalRecordOut)
def add_billing_entry(
    body: BillingEntryRequest,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> ClinicalRecordOut:
    """Record a charge or payment (INR) for a patient — no PHI beyond blind token."""
    if session.role not in ("doctor", "staff", "receptionist"):
        raise HTTPException(status_code=403, detail="Not allowed")
    blind_id = _tokenize_or_400(body.raw_identifier)
    issued, issued_human, issued_iso = prescription_issue_timestamp()
    amount = round(float(body.amount_inr), 2)
    note = body.note
    kind = body.kind
    label = "Payment" if kind == "payment" else "Charge"
    summary = f"{label} ₹{amount:,.2f}"
    if note:
        summary += f" — {note[:120]}"
    encounter: dict[str, Any] = {
        "type": "billing",
        "kind": kind,
        "amount_inr": amount,
        "currency": "INR",
        "note": note,
        "clinical_observations": [summary],
        "diagnoses": [],
        "medications": [],
        "symptoms": [],
        "entered_by": {
            "user_id": session.user_id,
            "display_name": session.display_name,
            "role": session.role,
        },
        "entered_at": issued_iso,
        "entered_at_display": issued_human,
    }
    record = ClinicalRecord(
        clinic_id=session.clinic_id,
        blind_patient_id=blind_id,
        encounter_data=encounter,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ClinicalRecordOut(
        id=record.id,
        blind_patient_id=record.blind_patient_id,
        created_at=_as_utc_aware(record.created_at),
        encounter_data=encounter,
    )


@router.post("/billing-summary", response_model=BillingSummaryOut)
def billing_summary(
    body: HistorySearchRequest,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> BillingSummaryOut:
    """Per-patient charges / payments / amount due (clinic-scoped, de-identified)."""
    if session.role not in ("doctor", "staff", "receptionist"):
        raise HTTPException(status_code=403, detail="Not allowed")
    blind_id = _tokenize_or_400(body.raw_identifier)
    rows = db.scalars(
        select(ClinicalRecord)
        .where(
            ClinicalRecord.clinic_id == session.clinic_id,
            ClinicalRecord.blind_patient_id == blind_id,
        )
        .order_by(ClinicalRecord.created_at.asc())
    ).all()
    tz = _clinic_tz_kolkata()
    today_local = datetime.now(timezone.utc).astimezone(tz).date()
    today_charges = 0.0
    total_charges = 0.0
    total_paid = 0.0
    for record in rows:
        data = dict(record.encounter_data) if isinstance(record.encounter_data, dict) else {}
        kind = _billing_kind(data)
        if kind is None:
            continue
        amount = _billing_amount_inr(data)
        if amount is None:
            continue
        if kind == "payment":
            total_paid += amount
            continue
        total_charges += amount
        created = _as_utc_aware(record.created_at)
        if created is not None and created.astimezone(tz).date() == today_local:
            today_charges += amount
    total_charges = round(total_charges, 2)
    total_paid = round(total_paid, 2)
    today_charges = round(today_charges, 2)
    return BillingSummaryOut(
        currency="INR",
        today_charges_inr=today_charges,
        total_charges_inr=total_charges,
        total_paid_inr=total_paid,
        amount_due_inr=round(max(0.0, total_charges - total_paid), 2),
    )


class ObstetricProfileBody(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    lmp: str = Field(default="", max_length=10)
    edd: str = Field(default="", max_length=10)
    edd_source: str = Field(default="", max_length=8)
    gravida: str = Field(default="", max_length=8)
    para: str = Field(default="", max_length=8)
    abortions: str = Field(default="", max_length=8)
    living: str = Field(default="", max_length=8)
    blood_group: str = Field(default="", max_length=8)
    rh: str = Field(default="", max_length=8)
    high_risk_notes: str = Field(default="", max_length=500)

    @field_validator("raw_identifier")
    @classmethod
    def non_blank_obs_raw(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("raw_identifier must not be blank")
        return stripped

    @field_validator("edd_source")
    @classmethod
    def edd_src(cls, value: str) -> str:
        v = (value or "").strip().lower()
        if v and v not in ("lmp", "usg"):
            raise ValueError("edd_source must be lmp or usg")
        return v


class ObstetricProfileOut(BaseModel):
    lmp: str | None = None
    edd: str | None = None
    edd_source: str = ""
    gravida: str = ""
    para: str = ""
    abortions: str = ""
    living: str = ""
    blood_group: str = ""
    rh: str = ""
    high_risk_notes: str = ""
    updated_at: str | None = None


def _parse_ymd(value: str) -> str | None:
    s = (value or "").strip()
    if not s:
        return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return None


@router.get("/obstetric-profile", response_model=ObstetricProfileOut | None)
def get_obstetric_profile(
    session: ClinicalSession,
    db: Session = Depends(get_db),
    raw_identifier: str = "",
) -> ObstetricProfileOut | None:
    if not (raw_identifier or "").strip():
        raise HTTPException(status_code=400, detail="raw_identifier required")
    blind = _tokenize_or_400(raw_identifier)
    rows = db.scalars(
        select(ClinicalRecord)
        .where(
            ClinicalRecord.blind_patient_id == blind,
            ClinicalRecord.clinic_id == session.clinic_id,
        )
        .order_by(ClinicalRecord.created_at.desc())
    ).all()
    for r in rows:
        data = r.encounter_data if isinstance(r.encounter_data, dict) else {}
        if data.get("type") != "obstetric_profile":
            continue
        return ObstetricProfileOut(
            lmp=_parse_ymd(str(data.get("lmp") or "")),
            edd=_parse_ymd(str(data.get("edd") or "")),
            edd_source=str(data.get("edd_source") or ""),
            gravida=str(data.get("gravida") or ""),
            para=str(data.get("para") or ""),
            abortions=str(data.get("abortions") or ""),
            living=str(data.get("living") or ""),
            blood_group=str(data.get("blood_group") or ""),
            rh=str(data.get("rh") or ""),
            high_risk_notes=str(data.get("high_risk_notes") or ""),
            updated_at=(
                _as_utc_aware(r.created_at).isoformat() if r.created_at else None
            ),
        )
    return None


@router.put("/obstetric-profile", response_model=ObstetricProfileOut)
def put_obstetric_profile(
    body: ObstetricProfileBody,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> ObstetricProfileOut:
    """Upsert current obstetric card for the patient."""
    from datetime import date, timedelta

    blind = _tokenize_or_400(body.raw_identifier)
    issued, issued_human, issued_iso = prescription_issue_timestamp()
    lmp = _parse_ymd(body.lmp) or ""
    edd = _parse_ymd(body.edd) or ""
    edd_source = body.edd_source
    if lmp and not edd:
        try:
            y, m, d = (int(x) for x in lmp.split("-"))
            edd = (date(y, m, d) + timedelta(days=280)).isoformat()
            edd_source = edd_source or "lmp"
        except Exception:  # noqa: BLE001
            pass

    encounter: dict[str, Any] = {
        "type": "obstetric_profile",
        "lmp": lmp,
        "edd": edd,
        "edd_source": edd_source,
        "gravida": body.gravida.strip()[:8],
        "para": body.para.strip()[:8],
        "abortions": body.abortions.strip()[:8],
        "living": body.living.strip()[:8],
        "blood_group": body.blood_group.strip()[:8],
        "rh": body.rh.strip()[:8],
        "high_risk_notes": body.high_risk_notes.strip()[:500],
        "clinical_observations": [
            f"LMP={lmp or '-'}",
            f"EDD={edd or '-'}",
            (
                f"G{body.gravida or '-'}P{body.para or '-'}"
                f"A{body.abortions or '-'}L{body.living or '-'}"
            ),
        ],
        "diagnoses": [],
        "medications": [],
        "symptoms": [],
        "entered_by": {
            "user_id": session.user_id,
            "display_name": session.display_name,
            "role": session.role,
        },
        "entered_at": issued_iso,
        "entered_at_display": issued_human,
    }

    existing = None
    rows = db.scalars(
        select(ClinicalRecord)
        .where(
            ClinicalRecord.blind_patient_id == blind,
            ClinicalRecord.clinic_id == session.clinic_id,
        )
        .order_by(ClinicalRecord.created_at.desc())
    ).all()
    for r in rows:
        data = r.encounter_data if isinstance(r.encounter_data, dict) else {}
        if data.get("type") == "obstetric_profile":
            existing = r
            break

    if existing is not None:
        existing.encounter_data = encounter
        record = existing
    else:
        record = ClinicalRecord(
            clinic_id=session.clinic_id,
            blind_patient_id=blind,
            encounter_data=encounter,
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return ObstetricProfileOut(
        lmp=lmp or None,
        edd=edd or None,
        edd_source=edd_source,
        gravida=encounter["gravida"],
        para=encounter["para"],
        abortions=encounter["abortions"],
        living=encounter["living"],
        blood_group=encounter["blood_group"],
        rh=encounter["rh"],
        high_risk_notes=encounter["high_risk_notes"],
        updated_at=(
            _as_utc_aware(record.created_at).isoformat() if record.created_at else None
        ),
    )


class HealthProfileBody(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    ongoing_medications: str = Field(default="", max_length=2000)
    health_issues: str = Field(default="", max_length=2000)

    @field_validator("raw_identifier")
    @classmethod
    def non_blank_health_raw(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("raw_identifier must not be blank")
        return stripped


class HealthProfileOut(BaseModel):
    ongoing_medications: str = ""
    health_issues: str = ""
    updated_at: str | None = None


@router.get("/health-profile", response_model=HealthProfileOut | None)
def get_health_profile(
    session: ClinicalSession,
    db: Session = Depends(get_db),
    raw_identifier: str = "",
) -> HealthProfileOut | None:
    if not (raw_identifier or "").strip():
        raise HTTPException(status_code=400, detail="raw_identifier required")
    blind = _tokenize_or_400(raw_identifier)
    rows = db.scalars(
        select(ClinicalRecord)
        .where(
            ClinicalRecord.blind_patient_id == blind,
            ClinicalRecord.clinic_id == session.clinic_id,
        )
        .order_by(ClinicalRecord.created_at.desc())
    ).all()
    for r in rows:
        data = r.encounter_data if isinstance(r.encounter_data, dict) else {}
        if data.get("type") != "health_profile":
            continue
        return HealthProfileOut(
            ongoing_medications=str(data.get("ongoing_medications") or ""),
            health_issues=str(data.get("health_issues") or ""),
            updated_at=(
                _as_utc_aware(r.created_at).isoformat() if r.created_at else None
            ),
        )
    return None


@router.put("/health-profile", response_model=HealthProfileOut)
def put_health_profile(
    body: HealthProfileBody,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> HealthProfileOut:
    """Upsert ongoing medications and chronic health issues for the patient."""
    blind = _tokenize_or_400(body.raw_identifier)
    issued, issued_human, issued_iso = prescription_issue_timestamp()
    meds = body.ongoing_medications.strip()[:2000]
    issues = body.health_issues.strip()[:2000]
    encounter: dict[str, Any] = {
        "type": "health_profile",
        "ongoing_medications": meds,
        "health_issues": issues,
        "clinical_observations": [
            f"Ongoing meds: {meds or '-'}",
            f"Health issues: {issues or '-'}",
        ],
        "diagnoses": [],
        "medications": [],
        "symptoms": [],
        "entered_by": {
            "user_id": session.user_id,
            "display_name": session.display_name,
            "role": session.role,
        },
        "entered_at": issued_iso,
        "entered_at_display": issued_human,
    }

    existing = None
    rows = db.scalars(
        select(ClinicalRecord)
        .where(
            ClinicalRecord.blind_patient_id == blind,
            ClinicalRecord.clinic_id == session.clinic_id,
        )
        .order_by(ClinicalRecord.created_at.desc())
    ).all()
    for r in rows:
        data = r.encounter_data if isinstance(r.encounter_data, dict) else {}
        if data.get("type") == "health_profile":
            existing = r
            break

    if existing is not None:
        existing.encounter_data = encounter
        record = existing
    else:
        record = ClinicalRecord(
            clinic_id=session.clinic_id,
            blind_patient_id=blind,
            encounter_data=encounter,
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return HealthProfileOut(
        ongoing_medications=meds,
        health_issues=issues,
        updated_at=(
            _as_utc_aware(record.created_at).isoformat() if record.created_at else None
        ),
    )


@router.get("/case-summary")
def get_case_summary(
    session: ClinicalSession,
    db: Session = Depends(get_db),
    raw_identifier: str = "",
) -> dict[str, Any]:
    """Consolidated vitals/labs/docs/obstetric brief for the locked patient."""
    if not (raw_identifier or "").strip():
        raise HTTPException(status_code=400, detail="raw_identifier required")
    from app.services.case_summary import build_case_summary

    blind = _tokenize_or_400(raw_identifier)
    return build_case_summary(db, clinic_id=session.clinic_id, blind_patient_id=blind)


class ConsultPackRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)


@router.post("/consult-pack")
def post_consult_pack(
    body: ConsultPackRequest,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """LLM (or rule-fallback) consult pack from case summary."""
    from app.services.case_summary import build_case_summary
    from app.services.lml_parser import generate_consult_pack

    blind = _tokenize_or_400(body.raw_identifier)
    summary = build_case_summary(
        db, clinic_id=session.clinic_id, blind_patient_id=blind
    )
    pack = generate_consult_pack(summary, clinic_id=session.clinic_id)
    pack["disclaimer"] = summary.get("disclaimer")
    return pack


class RxHintsRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    medications: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/rx-hints")
def post_rx_hints(
    body: RxHintsRequest,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.services.case_summary import build_case_summary, rx_conflict_hints

    blind = _tokenize_or_400(body.raw_identifier)
    summary = build_case_summary(
        db, clinic_id=session.clinic_id, blind_patient_id=blind
    )
    return {"hints": rx_conflict_hints(summary, body.medications)}


@router.post("/documents/{record_id}/analyze")
def analyze_document(
    record_id: UUID,
    body: DocumentFetchRequest,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Extract structured findings from a diagnostic attachment."""
    from app.services.attachment_store import load_attachment
    from app.services.lml_parser import extract_diagnostic_findings, pdf_text_excerpt

    blind_id = _tokenize_or_400(body.raw_identifier)
    record = db.get(ClinicalRecord, record_id)
    if (
        record is None
        or record.blind_patient_id != blind_id
        or getattr(record, "clinic_id", "default") != session.clinic_id
    ):
        raise HTTPException(status_code=404, detail="Document not found")
    data = record.encounter_data if isinstance(record.encounter_data, dict) else {}
    if data.get("type") != "document" and not data.get("document_kind"):
        raise HTTPException(status_code=400, detail="Record is not a document")
    excerpt = ""
    path = str(data.get("content_path") or "")
    if path:
        try:
            content, ctype = load_attachment(path)
            if "pdf" in (ctype or "").lower() or path.lower().endswith(".pdf"):
                excerpt = pdf_text_excerpt(content)
        except Exception:  # noqa: BLE001
            excerpt = ""
    findings = extract_diagnostic_findings(
        title=str(data.get("title") or ""),
        filename=str(data.get("filename") or ""),
        document_kind=str(data.get("document_kind") or "other"),
        text_excerpt=excerpt,
        clinic_id=session.clinic_id,
    )
    data = dict(data)
    data["findings"] = findings
    data["findings_at"] = datetime.now(timezone.utc).isoformat()
    record.encounter_data = data
    db.commit()
    return {"status": "ok", "findings": findings}


class ReferralPackRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    note: str = Field(default="", max_length=1200)
    recipient_name: str = Field(default="", max_length=120)
    patient_display_name: str = Field(default="", max_length=120)


class ReferralHandoffRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    to_user_id: str = Field(..., min_length=1, max_length=64)
    note: str = Field(default="", max_length=1200)
    patient_display_name: str = Field(default="", max_length=120)


def _referral_patient_labels(
    db: Session,
    *,
    clinic_id: str,
    blind_patient_id: str,
    fallback_name: str = "",
) -> tuple[str, str]:
    """Return (display_name, clinic_mrn) from roster when available."""
    from app.models.clinic_patient import ClinicPatient

    row = db.get(ClinicPatient, (clinic_id, blind_patient_id))
    if row is None:
        return (fallback_name or "Patient").strip() or "Patient", ""
    name = (row.display_name or fallback_name or "Patient").strip() or "Patient"
    return name, (row.clinic_mrn or "").strip()


def _referral_snapshot(summary: dict[str, Any]) -> dict[str, Any]:
    """Short text snapshot for handoff records (no files)."""
    last_rx = summary.get("last_prescription") if isinstance(summary.get("last_prescription"), dict) else {}
    dx = last_rx.get("diagnoses") if isinstance(last_rx.get("diagnoses"), list) else []
    return {
        "narrative": str(summary.get("narrative") or "")[:500],
        "gestational_age": summary.get("gestational_age"),
        "alerts": (summary.get("alerts") or [])[:5] if isinstance(summary.get("alerts"), list) else [],
        "diagnoses": [str(x) for x in dx[:8]],
        "doctor_comments": (summary.get("doctor_comments") or [])[:5]
        if isinstance(summary.get("doctor_comments"), list)
        else [],
    }


@router.post("/referral-pack")
def post_referral_pack(
    body: ReferralPackRequest,
    session: DoctorOnly,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Build a referral PDF from the case summary and mint a 24h download URL."""
    from app.api.v1.helpers.delivery import build_expiring_prescription_download_url
    from app.services.case_summary import build_case_summary
    from app.services.tenancy import branding_for

    blind = _tokenize_or_400(body.raw_identifier)
    summary = build_case_summary(
        db, clinic_id=session.clinic_id, blind_patient_id=blind
    )
    display_name, clinic_mrn = _referral_patient_labels(
        db,
        clinic_id=session.clinic_id,
        blind_patient_id=blind,
        fallback_name=body.patient_display_name,
    )
    brand = branding_for(session.clinic_id)
    pdf_buf = generate_referral_pdf(
        summary,
        clinic_name=brand["clinic_name"],
        clinic_subtitle=brand.get("clinic_subtitle") or "",
        clinic_address=brand.get("clinic_address") or "",
        referring_doctor=session.display_name,
        patient_display_name=display_name,
        clinic_mrn=clinic_mrn,
        note=(body.note or "").strip(),
        recipient_name=(body.recipient_name or "").strip(),
    )
    pdf_bytes = pdf_buf.getvalue()
    share = build_expiring_prescription_download_url(pdf_bytes)
    return {
        "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        "download_url": share["download_url"],
        "expires_at": share["expires_at"],
        "expires_in_hours": share.get("expires_in_hours"),
        "summary_meta": {
            "patient_display_name": display_name,
            "clinic_mrn": clinic_mrn,
            "has_narrative": bool(summary.get("narrative")),
            "alert_count": len(summary.get("alerts") or [])
            if isinstance(summary.get("alerts"), list)
            else 0,
        },
    }


@router.post("/referral-handoff")
def post_referral_handoff(
    body: ReferralHandoffRequest,
    session: DoctorOnly,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Notify a same-clinic doctor; they already have chart access."""
    from app.services.case_summary import build_case_summary
    from app.services.doctor_auth import find_user

    to_uid = (body.to_user_id or "").strip()
    if to_uid == session.user_id:
        raise HTTPException(status_code=400, detail="Cannot hand off to yourself")
    target = find_user(to_uid, session.clinic_id)
    if target is None or target.role != "doctor":
        raise HTTPException(
            status_code=400,
            detail="Recipient must be a doctor on this clinic roster",
        )

    blind = _tokenize_or_400(body.raw_identifier)
    summary = build_case_summary(
        db, clinic_id=session.clinic_id, blind_patient_id=blind
    )
    display_name, clinic_mrn = _referral_patient_labels(
        db,
        clinic_id=session.clinic_id,
        blind_patient_id=blind,
        fallback_name=body.patient_display_name,
    )
    raw = (body.raw_identifier or "").strip()
    # Prefer MRN-shaped identifier for re-lock when available
    lock_raw = f"mrn|{clinic_mrn}" if clinic_mrn else raw
    now = datetime.now(timezone.utc)
    encounter = {
        "type": "referral",
        "status": "open",
        "from_user_id": session.user_id,
        "from_display_name": session.display_name,
        "to_user_id": target.user_id,
        "to_display_name": target.display_name,
        "note": (body.note or "").strip()[:1200],
        "patient_display_name": display_name,
        "clinic_mrn": clinic_mrn,
        "raw_identifier": lock_raw,
        "blind_patient_id": blind,
        "snapshot": _referral_snapshot(summary),
        "created_at": now.isoformat(),
        "clinical_observations": [
            f"Case handoff to {target.display_name}"
            + (f": {(body.note or '').strip()[:200]}" if (body.note or "").strip() else "")
        ],
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
    return {
        "status": "ok",
        "id": str(rec.id),
        "to_user_id": target.user_id,
        "to_display_name": target.display_name,
        "patient_display_name": display_name,
    }


@router.get("/referrals/inbox")
def list_referral_inbox(
    session: DoctorOnly,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Open handoffs addressed to the current doctor."""
    rows = db.scalars(
        select(ClinicalRecord)
        .where(ClinicalRecord.clinic_id == session.clinic_id)
        .order_by(ClinicalRecord.created_at.desc())
        .limit(200)
    ).all()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = row.encounter_data if isinstance(row.encounter_data, dict) else {}
        if data.get("type") != "referral":
            continue
        if str(data.get("to_user_id") or "") != session.user_id:
            continue
        if str(data.get("status") or "open").lower() == "acknowledged":
            continue
        out.append(
            {
                "id": str(row.id),
                "blind_patient_id": row.blind_patient_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "from_user_id": data.get("from_user_id"),
                "from_display_name": data.get("from_display_name"),
                "patient_display_name": data.get("patient_display_name"),
                "clinic_mrn": data.get("clinic_mrn") or "",
                "raw_identifier": data.get("raw_identifier") or "",
                "note": data.get("note") or "",
                "status": data.get("status") or "open",
            }
        )
        if len(out) >= 40:
            break
    return out


@router.post("/referral-handoff/{record_id}/ack")
def ack_referral_handoff(
    record_id: UUID,
    session: DoctorOnly,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Mark a handoff as acknowledged by the receiving doctor."""
    row = db.get(ClinicalRecord, record_id)
    if row is None or getattr(row, "clinic_id", "default") != session.clinic_id:
        raise HTTPException(status_code=404, detail="Handoff not found")
    data = row.encounter_data if isinstance(row.encounter_data, dict) else {}
    if data.get("type") != "referral":
        raise HTTPException(status_code=400, detail="Record is not a referral handoff")
    if str(data.get("to_user_id") or "") != session.user_id:
        raise HTTPException(status_code=403, detail="Not the handoff recipient")
    updated = dict(data)
    updated["status"] = "acknowledged"
    updated["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    updated["acknowledged_by"] = session.user_id
    row.encounter_data = updated
    db.commit()
    return {"status": "ok"}
