"""Patient history lookup, tokenize helper, and scanned document upload."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.record import ClinicalRecord
from app.services.clinical_search import remember_patient_identity, search_clinic_records
from app.services.doctor_auth import DoctorSession
from app.services.lml_parser import ClinicalParseResult, MedicationItem
from app.services.pdf_generator import generate_prescription_pdf, prescription_issue_timestamp
from app.services.security import (
    build_patient_raw_identifier,
    normalize_phone_digits,
    tokenize_patient_identifier,
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
    """Lock a patient by name + phone (preferred) or a pre-built raw_identifier."""

    patient_name: str | None = None
    patient_phone: str | None = None
    raw_identifier: str | None = None

    @model_validator(mode="after")
    def require_identity(self) -> TokenizeRequest:
        if self.raw_identifier and self.raw_identifier.strip():
            return self
        name = (self.patient_name or "").strip()
        phone = (self.patient_phone or "").strip()
        if not name or not phone:
            raise ValueError("patient_name and patient_phone are required")
        # Validate composite early so the API returns a clear 422.
        build_patient_raw_identifier(name, phone)
        return self


class ClinicalRecordOut(BaseModel):
    id: UUID
    blind_patient_id: str
    created_at: datetime | None
    encounter_data: dict[str, Any]

    model_config = {"from_attributes": True}


class GlobalSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=120)
    locked_blind_patient_id: str | None = Field(default=None, max_length=64)

    @field_validator("query")
    @classmethod
    def valid_query(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 2:
            raise ValueError("query must be at least 2 characters")
        return stripped


class GlobalSearchResultOut(BaseModel):
    kind: Literal["patient", "record"]
    blind_patient_id: str
    patient_name: str | None = None
    patient_phone: str | None = None
    record_id: str | None = None
    created_at: datetime | None = None
    title: str
    subtitle: str
    match_source: str
    locked_patient_priority: bool = False


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
    raw_identifier_shape: str = "name|phone_digits"


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


def _resolve_raw_identifier(body: TokenizeRequest) -> tuple[str, str | None, str | None]:
    """Return (composite_raw, name_for_blind, phone_digits_for_blind)."""
    if body.raw_identifier and body.raw_identifier.strip():
        return body.raw_identifier.strip(), None, None
    name = (body.patient_name or "").strip()
    phone = (body.patient_phone or "").strip()
    try:
        composite = build_patient_raw_identifier(name, phone)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    return composite, name, normalize_phone_digits(phone)


@router.post("/tokenize", response_model=TokenizeResponse)
def tokenize_patient(
    body: TokenizeRequest,
    _auth: DoctorSession,
) -> TokenizeResponse:
    """Return HMAC blind tokens for patient name+phone (never stored by this call)."""
    composite, name, phone_digits = _resolve_raw_identifier(body)
    blind_patient = _tokenize_or_400(composite)
    blind_name = _tokenize_or_400(name) if name else None
    blind_phone = _tokenize_or_400(phone_digits) if phone_digits else None
    if name and phone_digits:
        remember_patient_identity(
            blind_patient_id=blind_patient,
            patient_name=name,
            patient_phone=phone_digits,
        )
    return TokenizeResponse(
        blind_patient_id=blind_patient,
        blind_name_id=blind_name,
        blind_phone_id=blind_phone,
    )


@router.post("/search", response_model=list[ClinicalRecordOut])
def search_clinical_history(
    body: HistorySearchRequest,
    _auth: DoctorSession,
    db: Session = Depends(get_db),
) -> list[ClinicalRecordOut]:
    """
    Resolve a raw identifier to ``blind_patient_id`` and return matching records
    newest-first. Intentionally performs no logging of identifiers or results.
    """
    blind_id = _tokenize_or_400(body.raw_identifier)

    stmt = (
        select(ClinicalRecord)
        .where(ClinicalRecord.blind_patient_id == blind_id)
        .order_by(ClinicalRecord.created_at.desc())
    )
    records = list(db.scalars(stmt).all())
    out: list[ClinicalRecordOut] = []
    for record in records:
        data = dict(record.encounter_data or {})
        if data.get("type") == "document" and "content_base64" in data:
            data = {
                **{k: v for k, v in data.items() if k != "content_base64"},
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


@router.post("/global-search", response_model=list[GlobalSearchResultOut])
def global_search_history(
    body: GlobalSearchRequest,
    _auth: DoctorSession,
    db: Session = Depends(get_db),
) -> list[GlobalSearchResultOut]:
    """Clinic-wide patient and record search with locked-patient priority."""
    matches = search_clinic_records(
        db,
        query=body.query,
        locked_blind_patient_id=body.locked_blind_patient_id,
    )
    return [
        GlobalSearchResultOut(
            kind=item.kind,
            blind_patient_id=item.blind_patient_id,
            patient_name=item.patient_name,
            patient_phone=item.patient_phone,
            record_id=item.record_id,
            created_at=_as_utc_aware(item.created_at),
            title=item.title,
            subtitle=item.subtitle,
            match_source=item.match_source,
            locked_patient_priority=item.locked_patient_priority,
        )
        for item in matches
    ]


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
    File bytes are stored in encounter_data (POC); raw patient name is never stored.
    """
    blind_id = _tokenize_or_400(raw_identifier.strip())
    try:
        patient_name, patient_phone = raw_identifier.strip().split("|", 1)
        remember_patient_identity(
            blind_patient_id=blind_id,
            patient_name=patient_name,
            patient_phone=patient_phone,
        )
    except ValueError:
        pass

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
    encounter: dict[str, Any] = {
        "type": "document",
        "document_kind": document_kind,
        "title": (title or filename).strip()[:200],
        "filename": filename[:200],
        "content_type": content_type,
        "size_bytes": len(raw),
        "content_base64": base64.b64encode(raw).decode("ascii"),
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

    record = ClinicalRecord(blind_patient_id=blind_id, encounter_data=encounter)
    db.add(record)
    db.commit()
    db.refresh(record)

    slim = {
        **{k: v for k, v in encounter.items() if k != "content_base64"},
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
    if record is None or record.blind_patient_id != blind_id:
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
    if not b64:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document content missing",
        )

    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Corrupt document payload",
        ) from exc

    filename = str(data.get("filename") or "document")
    media = str(data.get("content_type") or "application/octet-stream")
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
    _auth: DoctorSession,
    db: Session = Depends(get_db),
) -> Response:
    """Regenerate a prescription PDF from stored clinical fields (no PHI)."""
    blind_id = _tokenize_or_400(body.raw_identifier)
    record = db.get(ClinicalRecord, record_id)
    if record is None or record.blind_patient_id != blind_id:
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
        pdf_buffer = generate_prescription_pdf(
            clinical,
            patient_token=blind_id,
            doctor_name=doctor,
            issued_at=issued_at,
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


class VitalsEntryRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    vitals: VitalsPayload = Field(default_factory=VitalsPayload)
    diagnostic_notes: str = Field(default="", max_length=2000)

    @field_validator("raw_identifier")
    @classmethod
    def non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("raw_identifier must not be blank")
        return stripped


@router.post("/vitals", response_model=ClinicalRecordOut)
def add_vitals_entry(
    body: VitalsEntryRequest,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> ClinicalRecordOut:
    """
    Staff or doctor can append vitals / diagnostic notes.
    Each entry records who entered it (user_id + display name) for audit.
    """
    blind_id = _tokenize_or_400(body.raw_identifier)
    try:
        patient_name, patient_phone = body.raw_identifier.strip().split("|", 1)
        remember_patient_identity(
            blind_patient_id=blind_id,
            patient_name=patient_name,
            patient_phone=patient_phone,
        )
    except ValueError:
        pass
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
    record = ClinicalRecord(blind_patient_id=blind_id, encounter_data=encounter)
    db.add(record)
    db.commit()
    db.refresh(record)
    return ClinicalRecordOut(
        id=record.id,
        blind_patient_id=record.blind_patient_id,
        created_at=_as_utc_aware(record.created_at),
        encounter_data=encounter,
    )
