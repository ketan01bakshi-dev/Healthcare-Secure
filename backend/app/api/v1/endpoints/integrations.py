"""External integrations: ABHA / ABDM gateway and HL7 ORU ingest."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.record import ClinicalRecord
from app.services import abdm_client
from app.services.doctor_auth import ClinicalSession, DoctorSession
from app.services.pdf_generator import prescription_issue_timestamp
from app.services.security import (
    normalize_abha_id,
    tokenize_patient_identifier,
)

router = APIRouter(prefix="/integrations")


class AbhaLinkRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    abha_number: str = Field(..., min_length=8, max_length=64)
    consent_acknowledged: bool = False
    txn_id: str | None = None
    linking_token: str | None = None


class AbhaOtpRequest(BaseModel):
    abha_address_or_number: str = Field(..., min_length=3, max_length=64)


class AbhaConfirmRequest(BaseModel):
    txn_id: str = Field(..., min_length=8)
    otp: str = Field(..., min_length=4, max_length=12)


def _store_abha_link(
    *,
    db: Session,
    session: ClinicalSession,
    blind: str,
    abha_raw: str,
    mode: str,
    linking_token: str | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    digits = normalize_abha_id(abha_raw)
    token_src = (
        f"abha|{digits}" if len(digits) >= 8 else f"abha|{abha_raw.strip().lower()}"
    )
    blind_abha = tokenize_patient_identifier(token_src)
    link_blind = None
    if linking_token:
        link_blind = tokenize_patient_identifier(f"abdm_link|{linking_token}")

    issued, issued_human, issued_iso = prescription_issue_timestamp()
    summary = (
        "ABHA verified via ABDM OTP"
        if mode.startswith("abdm")
        else "ABHA linked (local HMAC)"
    )
    encounter = {
        "type": "abha_link",
        "mode": mode,
        "blind_abha_id": blind_abha,
        "blind_linking_token": link_blind,
        "abha_digits_len": len(digits) if digits else 0,
        "profile_name": (profile or {}).get("name") if profile else None,
        "summary": summary,
        "clinical_observations": [
            summary
            + (
                " — linking token stored as HMAC only."
                if link_blind
                else " — no cleartext ABHA stored."
            )
        ],
        "diagnoses": [],
        "medications": [],
        "symptoms": [],
        "entered_by": {
            "user_id": session.user_id,
            "display_name": session.display_name,
            "role": session.role,
            "clinic_id": session.clinic_id,
        },
        "entered_at": issued_iso,
        "entered_at_display": issued_human,
    }
    record = ClinicalRecord(
        clinic_id=session.clinic_id,
        blind_patient_id=blind,
        encounter_data=encounter,
    )
    db.add(record)
    db.commit()
    return {
        "status": "linked" if mode.startswith("abdm") else "linked_local",
        "mode": mode,
        "blind_abha_id": blind_abha,
        "record_id": str(record.id),
    }


@router.get("/abha/status")
def abha_status(_auth: DoctorSession) -> dict[str, Any]:
    st = abdm_client.get_status()
    return {
        "abdm_enabled": st.enabled,
        "mode": st.mode,
        "gateway_url": st.gateway_url,
        "cm_id": st.cm_id,
        "facility_id": st.facility_id,
        "mock": st.mock,
        "message": st.message,
    }


@router.post("/abha/otp/request")
def abha_request_otp(
    body: AbhaOtpRequest,
    session: ClinicalSession,
) -> dict[str, Any]:
    """Start ABDM MOBILE_OTP verification (or mock OTP)."""
    st = abdm_client.get_status()
    if not st.enabled:
        raise HTTPException(
            status_code=400,
            detail=(
                "ABDM not configured. Set ABDM_CLIENT_ID/SECRET or ABDM_MOCK=true, "
                "or use POST /abha/link for local HMAC-only link."
            ),
        )
    try:
        return abdm_client.request_mobile_otp(
            abha_address_or_number=body.abha_address_or_number,
            clinic_id=session.clinic_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)[:400]) from None


@router.post("/abha/otp/confirm")
def abha_confirm_otp(
    body: AbhaConfirmRequest,
    _session: ClinicalSession,
) -> dict[str, Any]:
    try:
        return abdm_client.confirm_otp(txn_id=body.txn_id, otp=body.otp)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)[:400]) from None


@router.get("/abha/txn/{txn_id}")
def abha_txn_status(txn_id: str, _auth: ClinicalSession) -> dict[str, Any]:
    entry = abdm_client.get_txn(txn_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Unknown transaction")
    safe = {k: v for k, v in entry.items() if k != "auth_token"}
    safe["has_linking_token"] = bool(entry.get("auth_token"))
    return safe


@router.post("/abha/link")
def link_abha(
    body: AbhaLinkRequest,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Link ABHA to the patient chart.

    - With ``txn_id`` after OTP confirm: ABDM-verified link (HMAC of token).
    - Without ABDM: local HMAC of ABHA number (consent required).
    """
    if not body.consent_acknowledged:
        raise HTTPException(
            status_code=400,
            detail="Patient consent must be acknowledged before linking ABHA.",
        )
    try:
        blind = tokenize_patient_identifier(body.raw_identifier.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    linking_token = body.linking_token
    profile: dict[str, Any] | None = None
    mode = "local_hash"

    if body.txn_id:
        entry = abdm_client.get_txn(body.txn_id)
        if not entry:
            raise HTTPException(status_code=400, detail="Unknown ABDM txn_id")
        if entry.get("status") != "confirmed" and not entry.get("auth_token"):
            raise HTTPException(
                status_code=400,
                detail="Complete OTP confirm before linking with this txn_id",
            )
        linking_token = linking_token or entry.get("auth_token")
        profile = (
            entry.get("profile") if isinstance(entry.get("profile"), dict) else None
        )
        mode = (
            "abdm_mock"
            if entry.get("mock") or abdm_client.get_status().mock
            else "abdm_otp"
        )
        abha_value = str(entry.get("abha") or body.abha_number)
    else:
        digits = normalize_abha_id(body.abha_number)
        if len(digits) < 8 and "@" not in body.abha_number:
            raise HTTPException(status_code=400, detail="ABHA number looks too short")
        abha_value = body.abha_number.strip()
        if abdm_client.get_status().enabled:
            mode = "local_hash_while_abdm_available"

    try:
        result = _store_abha_link(
            db=db,
            session=session,
            blind=blind,
            abha_raw=abha_value,
            mode=mode,
            linking_token=linking_token,
            profile=profile,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    result["message"] = (
        "ABHA linked with ABDM verification."
        if mode.startswith("abdm")
        else "ABHA hash stored locally (no national API call)."
    )
    return result


@router.post("/abdm/callback/{path:path}")
async def abdm_gateway_callback(path: str, request: Request) -> dict[str, str]:
    """Receive async ABDM gateway callbacks (on-init / on-confirm / …)."""
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return abdm_client.handle_callback(path, payload)


class Hl7IngestRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    hl7_message: str = Field(..., min_length=10)


def _parse_oru_obx(message: str) -> list[dict[str, str]]:
    """Minimal HL7 v2 ORU^R01 OBX extractor (pipe-delimited)."""
    results: list[dict[str, str]] = []
    for line in message.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not line.startswith("OBX|"):
            continue
        parts = line.split("|")
        code = parts[3] if len(parts) > 3 else ""
        name = code.split("^")[1] if "^" in code else code
        value = parts[5] if len(parts) > 5 else ""
        units = parts[6] if len(parts) > 6 else ""
        ref = parts[7] if len(parts) > 7 else ""
        if name or value:
            results.append(
                {
                    "test_name": (name or "Lab").strip()[:120],
                    "value": (value or "").strip()[:80],
                    "unit": (units or "").strip()[:40],
                    "reference_range": (ref or "").strip()[:80],
                }
            )
    return results


def _parse_msh_control_id(message: str) -> str:
    for line in message.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith("MSH|"):
            parts = line.split("|")
            if len(parts) > 9 and parts[9].strip():
                return parts[9].strip()[:50]
    return "UNKNOWN"


def _build_msa_ack(*, success: bool, control_id: str, text: str) -> str:
    """Minimal HL7 v2 MSA ACK (pipe-delimited, \\r segment terminator)."""
    now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    ack_code = "AA" if success else "AE"
    msh = (
        f"MSH|^~\\&|AarogyaOneConnect|Clinic|Sender|Facility|{now}||ACK^R01|{control_id}|P|2.5"
    )
    msa = f"MSA|{ack_code}|{control_id}|{text}"
    return f"{msh}\r{msa}\r"


@router.post("/hl7/oru")
def ingest_hl7_oru(
    body: Hl7IngestRequest,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Accept an HL7 v2 ORU message and store extracted OBX rows as lab_result encounters.

    Returns a simple MSA ACK string for LIS/device clients (not full MLLP framing).
    """
    if session.role not in ("doctor", "staff", "lab"):
        raise HTTPException(status_code=403, detail="Not allowed")
    control_id = _parse_msh_control_id(body.hl7_message)
    try:
        blind = tokenize_patient_identifier(body.raw_identifier.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                "hl7_ack": _build_msa_ack(
                    success=False, control_id=control_id, text=str(exc)[:80]
                ),
            },
        ) from None

    rows = _parse_oru_obx(body.hl7_message)
    if not rows:
        msg = "No OBX segments found. Send an HL7 ORU^R01 style message."
        raise HTTPException(
            status_code=400,
            detail={
                "message": msg,
                "hl7_ack": _build_msa_ack(
                    success=False, control_id=control_id, text="No OBX"
                ),
            },
        )

    issued, issued_human, issued_iso = prescription_issue_timestamp()
    created = 0
    for row in rows:
        summary = f"{row['test_name']}={row['value']}"
        if row["unit"]:
            summary += f" {row['unit']}"
        encounter = {
            "type": "lab_result",
            "source": "hl7_oru",
            **row,
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
        db.add(
            ClinicalRecord(
                clinic_id=session.clinic_id,
                blind_patient_id=blind,
                encounter_data=encounter,
            )
        )
        created += 1
    db.commit()
    ack = _build_msa_ack(
        success=True,
        control_id=control_id,
        text=f"Imported {created} OBX",
    )
    return {
        "status": "ok",
        "results_imported": created,
        "hl7_ack": ack,
        "message": "MSA ACK included for device/LIS clients (MLLP framing not required).",
    }
