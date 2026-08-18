"""Prescription audio transcription, parse, write-PDF, and secure share-link endpoints."""

from __future__ import annotations

import asyncio
import base64
import io
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.v1.helpers.delivery import build_expiring_prescription_download_url
from app.core.config import settings
from app.core.database import get_db
from app.models.record import ClinicalRecord
from app.services.doctor_auth import DoctorOnly, DoctorSession
from app.services.lml_parser import (
    ClinicalParseResult,
    MedicationItem,
    PHIContentError,
    parse_clinical_transcript,
)
from app.services.pdf_generator import generate_prescription_pdf, prescription_issue_timestamp
from app.services.presigned_url import resolve_presigned_prescription
from app.services.security import tokenize_patient_identifier
from app.services.transcription import (
    normalize_speak_language,
    transcribe_audio_buffer,
)

router = APIRouter(prefix="/prescription")

_MAX_AUDIO_BYTES = 10 * 1024 * 1024
_CHUNK_SIZE = 64 * 1024


class PrescriptionShareLinkRequest(BaseModel):
    """Mint a 24h pre-signed download URL for an in-memory PDF (base64)."""

    pdf_base64: str = Field(..., min_length=1, description="PDF bytes as base64")


class ParsePrescriptionRequest(BaseModel):
    """Run clinical LLM parse only — doctor reviews before signing."""

    transcripts: list[str] = Field(..., min_length=1)

    @field_validator("transcripts")
    @classmethod
    def non_empty_transcripts(cls, value: list[str]) -> list[str]:
        cleaned = [t.strip() for t in value if isinstance(t, str) and t.strip()]
        if not cleaned:
            raise ValueError("At least one non-empty transcript is required")
        return cleaned


class WritePrescriptionRequest(BaseModel):
    """
    Sign a prescription from doctor-reviewed clinical fields.

    Prefer sending edited ``clinical`` after ``/parse``. Legacy clients may still
    send ``transcripts`` alone — the server will parse then write in one step.

    Optional ``parsed_clinical`` + ``transcripts`` enable de-identified
    correction memory (not stored on the clinical record itself).
    """

    raw_identifier: str = Field(
        ..., min_length=1, description="Patient name|phone composite (tokenized server-side)"
    )
    doctor_name: str = Field(default="", max_length=120)
    transcripts: list[str] = Field(default_factory=list)
    transcript_count: int | None = Field(default=None, ge=0)
    clinical: dict[str, Any] | None = None
    parsed_clinical: dict[str, Any] | None = None
    source_language: str = Field(default="en", max_length=8)

    @field_validator("raw_identifier")
    @classmethod
    def non_blank_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("raw_identifier must not be blank")
        return stripped


def _clinical_from_payload(payload: dict[str, Any]) -> ClinicalParseResult:
    meds_raw = payload.get("medications") or []
    medications: list[MedicationItem] = []
    if isinstance(meds_raw, list):
        for item in meds_raw:
            if isinstance(item, dict) and str(item.get("name") or "").strip():
                medications.append(
                    MedicationItem(
                        name=str(item.get("name") or "").strip(),
                        dosage=str(item.get("dosage") or "").strip(),
                        frequency=str(item.get("frequency") or "").strip(),
                        duration=str(item.get("duration") or "").strip(),
                    )
                )
    return ClinicalParseResult(
        symptoms=[str(s).strip() for s in (payload.get("symptoms") or []) if str(s).strip()],
        clinical_observations=[
            str(s).strip()
            for s in (payload.get("clinical_observations") or [])
            if str(s).strip()
        ],
        diagnoses=[
            str(s).strip() for s in (payload.get("diagnoses") or []) if str(s).strip()
        ],
        medications=medications,
        phi_detected=bool(payload.get("phi_detected")),
        phi_redaction_reason=(
            str(payload["phi_redaction_reason"])
            if payload.get("phi_redaction_reason")
            else None
        ),
    )


@router.post("/transcribe")
async def transcribe_prescription_audio(
    auth: DoctorOnly,
    db: Session = Depends(get_db),
    audio: UploadFile = File(..., description="Recorded prescription audio"),
    language: str = Form(
        "en",
        description="Spoken language: en (English) or hi (Hindi→English)",
    ),
) -> dict[str, str | int]:
    """Accept prescription audio and return an English Whisper transcript."""
    try:
        source_language = normalize_speak_language(language)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    filename = audio.filename or "prescription.wav"
    content_type = audio.content_type or "audio/wav"

    memory_buffer = io.BytesIO()
    memory_buffer.name = filename  # type: ignore[attr-defined]
    total = 0

    try:
        while True:
            chunk = await audio.read(_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_AUDIO_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Audio exceeds maximum allowed size (10 MiB)",
                )
            memory_buffer.write(chunk)
            del chunk

        if total == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty audio payload",
            )

        memory_buffer.seek(0)

        try:
            from app.services.stt_memory import load_clinic_alias_map

            alias_map = load_clinic_alias_map(db, auth.clinic_id)
            transcript = await asyncio.to_thread(
                transcribe_audio_buffer,
                memory_buffer,
                source_language=source_language,
                clinic_id=auth.clinic_id,
                db=None,
                alias_map=alias_map,
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Transcription provider error: {exc}",
            ) from exc
        finally:
            try:
                if not memory_buffer.closed:
                    memory_buffer.seek(0)
                    memory_buffer.truncate(0)
                    memory_buffer.close()
            except Exception:  # noqa: BLE001
                pass

        return {
            "status": "ok",
            "filename": filename,
            "content_type": content_type,
            "bytes_received": total,
            "provider": settings.whisper_provider,
            "source_language": source_language,
            "output_language": "en",
            "transcript": transcript,
            "message": (
                "Hindi translated to English"
                if source_language == "hi"
                else "Transcription complete"
            ),
        }
    finally:
        try:
            if not memory_buffer.closed:
                memory_buffer.seek(0)
                memory_buffer.truncate(0)
                memory_buffer.close()
        except Exception:  # noqa: BLE001
            pass
        del memory_buffer


@router.post("/parse")
def parse_prescription(
    body: ParsePrescriptionRequest,
    auth: DoctorOnly,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Parse transcripts into structured clinical fields for review-before-sign."""
    consolidated = "\n\n---\n\n".join(
        f"[Segment {i + 1}]\n{text}" for i, text in enumerate(body.transcripts)
    )
    try:
        clinical = parse_clinical_transcript(
            consolidated, clinic_id=auth.clinic_id, db=db
        )
    except PHIContentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Clinical parse failed: {exc}",
        ) from exc

    return {
        "status": "ok",
        "transcript_count": len(body.transcripts),
        "clinical": clinical.model_dump(),
        "message": "Review clinical fields, then sign to write the PDF.",
    }


@router.post("/write")
def write_prescription(
    body: WritePrescriptionRequest,
    session: DoctorOnly,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Persist de-identified ClinicalRecord + PDF from doctor-reviewed clinical data.
    Raw transcripts are never stored — only a count. Doctor-only (sign & seal).
    """
    from app.models.clinic_patient import ClinicPatient
    from app.services.mrn_identity import resolve_patient_identity
    from app.services.security import normalize_mrn

    patient_name = ""
    clinic_mrn = ""
    patient_age_years = None
    try:
        raw = body.raw_identifier.strip()
        if raw.startswith("mrn|"):
            clinic_mrn = normalize_mrn(raw.split("|", 1)[1])
            blind_id = tokenize_patient_identifier(raw)
            row = db.get(ClinicPatient, (session.clinic_id, blind_id))
            if row is None and clinic_mrn:
                from app.services.mrn_identity import find_patient_by_mrn

                row = find_patient_by_mrn(db, session.clinic_id, clinic_mrn)
            if row is not None:
                patient_name = row.display_name or ""
                clinic_mrn = row.clinic_mrn or clinic_mrn
                if row.age_years is not None:
                    patient_age_years = float(row.age_years)
        elif "|" in raw:
            name_part, phone_part = raw.split("|", 1)
            resolved = resolve_patient_identity(
                db,
                clinic_id=session.clinic_id,
                patient_name=name_part,
                patient_phone=phone_part,
                actor={
                    "user_id": session.user_id,
                    "display_name": session.display_name,
                    "role": session.role,
                },
                bump_visit=False,
            )
            blind_id = resolved.blind_patient_id
            patient_name = resolved.display_name
            clinic_mrn = resolved.clinic_mrn
            db.commit()
            from app.models.clinic_patient import ClinicPatient as _CP

            prow = db.get(_CP, (session.clinic_id, blind_id))
            if prow is not None and prow.age_years is not None:
                patient_age_years = float(prow.age_years)
        else:
            blind_id = tokenize_patient_identifier(raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to tokenize patient identifier",
        ) from None

    transcript_count = body.transcript_count
    if body.clinical:
        clinical = _clinical_from_payload(body.clinical)
        if transcript_count is None:
            transcript_count = len(body.transcripts) if body.transcripts else 0
    else:
        cleaned = [t.strip() for t in body.transcripts if isinstance(t, str) and t.strip()]
        if not cleaned:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide clinical fields (after /parse) or transcripts",
            )
        consolidated = "\n\n---\n\n".join(
            f"[Segment {i + 1}]\n{text}" for i, text in enumerate(cleaned)
        )
        try:
            clinical = parse_clinical_transcript(
                consolidated, clinic_id=session.clinic_id, db=db
            )
        except PHIContentError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Clinical parse failed: {exc}",
            ) from exc
        transcript_count = len(cleaned)

    doctor = (
        body.doctor_name.strip()
        or session.display_name
        or settings.doctor_name
    )
    issued, issued_human, issued_iso = prescription_issue_timestamp()
    try:
        pdf_buffer = generate_prescription_pdf(
            clinical,
            patient_token=blind_id,
            doctor_name=doctor,
            issued_at=issued,
            patient_name=patient_name or None,
            clinic_mrn=clinic_mrn or None,
            patient_age_years=patient_age_years,
        )
        pdf_bytes = pdf_buffer.getvalue()
    except PHIContentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {exc}",
        ) from exc

    # Intentionally omit raw transcripts — structured clinical fields only.
    encounter: dict[str, Any] = {
        "type": "prescription",
        "doctor_name": doctor,
        "clinic_name": settings.clinic_name,
        "clinic_mrn": clinic_mrn or None,
        "patient_age_years": patient_age_years,
        "issued_at": issued_iso,
        "issued_at_display": issued_human,
        "transcript_count": int(transcript_count or 0),
        "symptoms": clinical.symptoms,
        "clinical_observations": clinical.clinical_observations,
        "diagnoses": clinical.diagnoses,
        "medications": [m.model_dump() for m in clinical.medications],
        "signed_by": {
            "user_id": session.user_id,
            "display_name": session.display_name,
            "role": session.role,
        },
    }

    record = ClinicalRecord(
        clinic_id=session.clinic_id,
        blind_patient_id=blind_id,
        encounter_data=encounter,
    )
    db.add(record)

    # Correction memory: transcripts + parse→final diff (not on clinical_records).
    try:
        from app.services.stt_memory import store_correction_feedback

        feedback_transcripts = [
            t.strip()
            for t in (body.transcripts or [])
            if isinstance(t, str) and t.strip()
        ]
        if body.parsed_clinical or feedback_transcripts:
            store_correction_feedback(
                db,
                clinic_id=session.clinic_id,
                blind_patient_id=blind_id,
                transcripts=feedback_transcripts,
                parsed_clinical=body.parsed_clinical,
                final_clinical={
                    "symptoms": clinical.symptoms,
                    "clinical_observations": clinical.clinical_observations,
                    "diagnoses": clinical.diagnoses,
                    "medications": [m.model_dump() for m in clinical.medications],
                },
                source_language=body.source_language or "en",
            )
    except Exception:  # noqa: BLE001
        pass

    db.commit()
    db.refresh(record)

    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    share = build_expiring_prescription_download_url(pdf_bytes)

    return {
        "status": "ok",
        "record_id": str(record.id),
        "blind_patient_id": blind_id,
        "clinic_mrn": clinic_mrn or None,
        "pdf_base64": pdf_b64,
        "download_url": share["download_url"],
        "expires_at": share["expires_at"],
        "clinical": encounter,
        "message": "Prescription signed and sealed by doctor.",
    }


@router.get("/download")
def download_presigned_prescription(
    token: str = Query(..., min_length=10, description="Signed download token"),
) -> Response:
    """Serve an ephemeral PDF when the HMAC token is valid and unexpired (24h)."""
    try:
        pdf_bytes = resolve_presigned_prescription(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download link is invalid or has expired",
        ) from None

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="prescription.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/share-link")
def create_prescription_share_link(
    body: PrescriptionShareLinkRequest,
    _auth: DoctorOnly,
) -> dict[str, object]:
    """
    Mint a 24h cryptographically signed download URL for the client to share
    via the device native share sheet or clipboard (no SMS gateway).
    """
    try:
        pdf_bytes = base64.b64decode(body.pdf_base64, validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pdf_base64 payload",
        ) from exc

    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty PDF payload",
        )

    try:
        return build_expiring_prescription_download_url(pdf_bytes)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
