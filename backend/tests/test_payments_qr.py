"""Razorpay UPI QR payment tests (mock gateway)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_healthcare.db"
os.environ["SECRET_SALT"] = "test_salt_not_for_production_0123456789abcdef"
os.environ["SECRET_KEY"] = "test_secret_key_not_for_production_01234567"
os.environ["CLINICS"] = (
    "default|Test Clinic|||testpass|"
    "voice_rx,labs,queue,appointments,analytics,obstetric,video_consult"
)
os.environ["CLINIC_USERS"] = (
    "dr1|Dr Test|doctor|1234;"
    "nurse1|Nurse Test|staff|5678;"
    "lab1|Lab Test|lab|9999;"
    "desk1|Front Desk|receptionist|1111"
)
os.environ["APP_ENV"] = "development"
os.environ["REQUIRE_CLINIC_USERS"] = "false"
os.environ["WHISPER_PRELOAD"] = "false"
os.environ["PAYMENTS_ENABLED"] = "true"
os.environ["RAZORPAY_MOCK"] = "true"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "whsec_test"

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.security import build_patient_raw_identifier

get_settings.cache_clear()


@pytest.fixture(scope="module")
def client() -> TestClient:
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c


def _session(client: TestClient, user_id: str = "dr1", pin: str = "1234") -> dict[str, str]:
    from tests.auth_helpers import session_headers

    return session_headers(client, user_id, pin)


def _unique_raw(name: str) -> str:
    phone = f"9{uuid.uuid4().int % 10**9:09d}"
    return build_patient_raw_identifier(name, phone)


def _sign(body: bytes) -> str:
    return hmac.new(b"whsec_test", body, hashlib.sha256).hexdigest()


def test_create_qr_and_mock_pay(client: TestClient) -> None:
    headers = _session(client)
    raw = _unique_raw("QR Pay Patient")
    # Seed a charge so amount due defaults work
    charge = client.post(
        "/api/v1/history/billing",
        headers=headers,
        json={"raw_identifier": raw, "amount_inr": 750, "kind": "charge"},
    )
    assert charge.status_code == 200, charge.text

    status = client.get("/api/v1/payments/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["payments_enabled"] is True

    qr = client.post(
        "/api/v1/payments/qr",
        headers=headers,
        json={"raw_identifier": raw},
    )
    assert qr.status_code == 200, qr.text
    body = qr.json()
    assert body["amount_inr"] == 750.0
    assert body["status"] == "qr_active"
    assert body["qr_string"]
    payment_id = body["payment_id"]

    paid = client.post(f"/api/v1/payments/{payment_id}/mock-pay", headers=headers)
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert paid.json()["billing_record_id"]

    summary = client.post(
        "/api/v1/history/billing-summary",
        headers=headers,
        json={"raw_identifier": raw},
    )
    assert summary.status_code == 200
    assert summary.json()["total_paid_inr"] == 750.0
    assert summary.json()["amount_due_inr"] == 0.0


def test_webhook_idempotent(client: TestClient) -> None:
    headers = _session(client)
    raw = _unique_raw("Webhook Pay Patient")
    client.post(
        "/api/v1/history/billing",
        headers=headers,
        json={"raw_identifier": raw, "amount_inr": 200, "kind": "charge"},
    )
    qr = client.post(
        "/api/v1/payments/qr",
        headers=headers,
        json={"raw_identifier": raw, "amount_inr": 200},
    )
    assert qr.status_code == 200, qr.text
    payment_id = qr.json()["payment_id"]
    qr_id = "qr_test_webhook_1"
    # Patch provider_qr_id via DB for webhook lookup by notes
    from app.core.database import SessionLocal
    from app.models.payment_intent import PaymentIntent
    from uuid import UUID

    db = SessionLocal()
    try:
        intent = db.get(PaymentIntent, UUID(payment_id))
        assert intent is not None
        intent.provider_qr_id = qr_id
        db.add(intent)
        db.commit()
    finally:
        db.close()

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_1",
                    "status": "captured",
                    "notes": {"payment_intent_id": payment_id},
                    "qr_code_id": qr_id,
                }
            }
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")
    wh_headers = {"X-Razorpay-Signature": _sign(raw_body)}

    r1 = client.post(
        "/api/v1/payments/webhook/razorpay",
        content=raw_body,
        headers=wh_headers,
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] in ("ok", "already_paid")

    r2 = client.post(
        "/api/v1/payments/webhook/razorpay",
        content=raw_body,
        headers=wh_headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "already_paid"

    summary = client.post(
        "/api/v1/history/billing-summary",
        headers=headers,
        json={"raw_identifier": raw},
    )
    assert summary.json()["total_paid_inr"] == 200.0
    assert summary.json()["amount_due_inr"] == 0.0


def test_lab_forbidden_qr(client: TestClient) -> None:
    headers = _session(client, "lab1", "9999")
    raw = _unique_raw("Lab QR Block")
    r = client.post(
        "/api/v1/payments/qr",
        headers=headers,
        json={"raw_identifier": raw, "amount_inr": 100},
    )
    assert r.status_code == 403
