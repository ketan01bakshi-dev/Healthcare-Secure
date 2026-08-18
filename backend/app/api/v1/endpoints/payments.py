"""Razorpay UPI QR payment endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.payment_intent import PaymentIntent
from app.models.record import ClinicalRecord
from app.services.doctor_auth import DoctorSession
from app.services.pdf_generator import prescription_issue_timestamp
from app.services.razorpay_client import (
    RazorpayError,
    create_upi_qr,
    payments_configured,
    verify_webhook_signature,
)
from app.services.security import tokenize_patient_identifier

router = APIRouter(prefix="/payments")

_BILLING_ROLES = frozenset({"doctor", "staff", "receptionist"})


class CreateQrRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)
    amount_inr: float | None = Field(default=None, gt=0, le=10_000_000)

    @field_validator("raw_identifier")
    @classmethod
    def non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class QrPaymentOut(BaseModel):
    payment_id: str
    amount_inr: float
    currency: str = "INR"
    status: str
    qr_string: str = ""
    qr_image_base64: str = ""
    qr_image_url: str = ""
    expires_at: str | None = None


class PaymentStatusOut(BaseModel):
    payment_id: str
    amount_inr: float
    status: str
    billing_record_id: str | None = None


def _tokenize_or_400(raw: str) -> str:
    try:
        return tokenize_patient_identifier(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid patient identifier") from exc


def _billing_kind(data: dict[str, Any]) -> str | None:
    if str(data.get("type") or "").strip() != "billing":
        return None
    raw = str(data.get("kind") or "charge").strip().lower()
    return "payment" if raw == "payment" else "charge"


def _billing_amount(data: dict[str, Any]) -> float | None:
    raw = data.get("amount_inr", data.get("amount"))
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        return None
    if amount <= 0 or amount > 10_000_000:
        return None
    return round(amount, 2)


def _amount_due_inr(db: Session, clinic_id: str, blind_id: str) -> float:
    rows = db.scalars(
        select(ClinicalRecord).where(
            ClinicalRecord.clinic_id == clinic_id,
            ClinicalRecord.blind_patient_id == blind_id,
        )
    ).all()
    total_charges = 0.0
    total_paid = 0.0
    for record in rows:
        data = dict(record.encounter_data) if isinstance(record.encounter_data, dict) else {}
        kind = _billing_kind(data)
        if kind is None:
            continue
        amount = _billing_amount(data)
        if amount is None:
            continue
        if kind == "payment":
            total_paid += amount
        else:
            total_charges += amount
    return round(max(0.0, total_charges - total_paid), 2)


def _require_payments() -> None:
    if not payments_configured():
        raise HTTPException(
            status_code=503,
            detail="Payments not configured",
        )


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _mark_paid_and_ledger(
    db: Session,
    intent: PaymentIntent,
    *,
    note: str = "UPI QR (Razorpay)",
) -> ClinicalRecord | None:
    """Idempotent: if already paid with billing_record_id, no-op."""
    if intent.status == "paid" and intent.billing_record_id is not None:
        return None
    if intent.status == "paid" and intent.billing_record_id is None:
        # Recover ledger if status flipped without record
        pass
    elif intent.status not in ("created", "qr_active", "paid"):
        return None

    issued, issued_human, issued_iso = prescription_issue_timestamp()
    amount = round(float(intent.amount_inr), 2)
    summary = f"Payment ₹{amount:,.2f} — {note[:120]}"
    encounter: dict[str, Any] = {
        "type": "billing",
        "kind": "payment",
        "amount_inr": amount,
        "currency": "INR",
        "note": note[:200],
        "payment_intent_id": str(intent.id),
        "provider": "razorpay",
        "clinical_observations": [summary],
        "diagnoses": [],
        "medications": [],
        "symptoms": [],
        "entered_by": {
            "user_id": "razorpay",
            "display_name": "Razorpay UPI",
            "role": "system",
        },
        "entered_at": issued_iso,
        "entered_at_display": issued_human,
    }
    record = ClinicalRecord(
        clinic_id=intent.clinic_id,
        blind_patient_id=intent.blind_patient_id,
        encounter_data=encounter,
    )
    db.add(record)
    db.flush()
    intent.status = "paid"
    intent.billing_record_id = record.id
    intent.updated_at = datetime.now(timezone.utc)
    db.add(intent)
    db.commit()
    db.refresh(record)
    return record


@router.get("/status")
def payments_feature_status(session: DoctorSession) -> dict[str, bool]:
    """Lightweight flag for UI (auth required)."""
    if session.role not in _BILLING_ROLES:
        raise HTTPException(status_code=403, detail="Not allowed")
    return {"payments_enabled": payments_configured()}


@router.post("/qr", response_model=QrPaymentOut)
def create_payment_qr(
    body: CreateQrRequest,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> QrPaymentOut:
    if session.role not in _BILLING_ROLES:
        raise HTTPException(status_code=403, detail="Not allowed")
    _require_payments()
    blind_id = _tokenize_or_400(body.raw_identifier)
    if body.amount_inr is not None:
        amount = round(float(body.amount_inr), 2)
    else:
        amount = _amount_due_inr(db, session.clinic_id, blind_id)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Nothing due — enter an amount")

    intent = PaymentIntent(
        clinic_id=session.clinic_id,
        blind_patient_id=blind_id,
        amount_inr=amount,
        currency="INR",
        provider="razorpay",
        status="created",
    )
    db.add(intent)
    db.flush()

    try:
        qr = create_upi_qr(
            amount_inr=amount,
            description=f"Clinic fee {str(intent.id)[:8]}",
            notes={
                "payment_intent_id": str(intent.id),
                "clinic_id": session.clinic_id,
            },
        )
    except RazorpayError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    expires = datetime.fromtimestamp(int(qr["expires_at_unix"]), tz=timezone.utc)
    intent.provider_qr_id = str(qr.get("provider_qr_id") or "")
    intent.provider_order_id = str(qr.get("provider_order_id") or "")
    intent.qr_string = str(qr.get("qr_string") or "")[:1024]
    intent.qr_image_url = str(qr.get("qr_image_url") or "")[:1024]
    intent.status = "qr_active"
    intent.expires_at = expires
    intent.updated_at = datetime.now(timezone.utc)
    db.add(intent)
    db.commit()
    db.refresh(intent)

    return QrPaymentOut(
        payment_id=str(intent.id),
        amount_inr=amount,
        status=intent.status,
        qr_string=intent.qr_string,
        qr_image_base64=str(qr.get("qr_image_base64") or ""),
        qr_image_url=intent.qr_image_url,
        expires_at=expires.isoformat(),
    )


@router.get("/{payment_id}", response_model=PaymentStatusOut)
def get_payment_status(
    payment_id: UUID,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> PaymentStatusOut:
    if session.role not in _BILLING_ROLES:
        raise HTTPException(status_code=403, detail="Not allowed")
    intent = db.get(PaymentIntent, payment_id)
    if intent is None or intent.clinic_id != session.clinic_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    # Expire stale QR
    exp = _as_utc(intent.expires_at)
    if (
        intent.status == "qr_active"
        and exp is not None
        and exp < datetime.now(timezone.utc)
    ):
        intent.status = "expired"
        intent.updated_at = datetime.now(timezone.utc)
        db.add(intent)
        db.commit()
    return PaymentStatusOut(
        payment_id=str(intent.id),
        amount_inr=float(intent.amount_inr),
        status=intent.status,
        billing_record_id=str(intent.billing_record_id)
        if intent.billing_record_id
        else None,
    )


@router.post("/webhook/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    import json

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    event = str(payload.get("event") or "")
    entity = (payload.get("payload") or {})
    # Prefer payment entity notes; also support qr_code / payment_link paid events
    payment_entity = (entity.get("payment") or {}).get("entity") or {}
    qr_entity = (entity.get("qr_code") or {}).get("entity") or {}
    link_entity = (entity.get("payment_link") or {}).get("entity") or {}

    notes = (
        payment_entity.get("notes")
        or qr_entity.get("notes")
        or link_entity.get("notes")
        or {}
    )
    intent_id_raw = notes.get("payment_intent_id") or ""
    qr_id = str(
        qr_entity.get("id")
        or payment_entity.get("qr_code_id")
        or link_entity.get("id")
        or ""
    )

    intent: PaymentIntent | None = None
    if intent_id_raw:
        try:
            intent = db.get(PaymentIntent, UUID(str(intent_id_raw)))
        except Exception:  # noqa: BLE001
            intent = None
    if intent is None and qr_id:
        intent = db.scalars(
            select(PaymentIntent).where(
                (PaymentIntent.provider_qr_id == qr_id)
                | (PaymentIntent.provider_order_id == qr_id)
            )
        ).first()

    paid_events = {
        "payment.captured",
        "qr_code.credited",
        "qr.credited",
        "payment_link.paid",
    }
    link_paid = str(link_entity.get("status") or "").lower() == "paid"
    if (
        event not in paid_events
        and str(payment_entity.get("status") or "") != "captured"
        and not link_paid
    ):
        return {"status": "ignored"}

    if intent is None:
        return {"status": "unknown_payment"}

    if intent.status == "paid" and intent.billing_record_id is not None:
        return {"status": "already_paid"}

    _mark_paid_and_ledger(db, intent)
    return {"status": "ok"}


@router.post("/{payment_id}/mock-pay")
def mock_pay_payment(
    payment_id: UUID,
    session: DoctorSession,
    db: Session = Depends(get_db),
) -> PaymentStatusOut:
    """Test-only: simulate successful UPI pay when RAZORPAY_MOCK=true."""
    if not settings.razorpay_mock:
        raise HTTPException(status_code=404, detail="Not found")
    if session.role not in _BILLING_ROLES:
        raise HTTPException(status_code=403, detail="Not allowed")
    intent = db.get(PaymentIntent, payment_id)
    if intent is None or intent.clinic_id != session.clinic_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    _mark_paid_and_ledger(db, intent, note="UPI QR (mock)")
    db.refresh(intent)
    return PaymentStatusOut(
        payment_id=str(intent.id),
        amount_inr=float(intent.amount_inr),
        status=intent.status,
        billing_record_id=str(intent.billing_record_id)
        if intent.billing_record_id
        else None,
    )
