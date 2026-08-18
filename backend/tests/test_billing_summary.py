"""Billing charge/payment ledger and per-patient summary."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

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

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.record import ClinicalRecord
from app.services.security import build_patient_raw_identifier, tokenize_patient_identifier


@pytest.fixture(scope="module")
def client() -> TestClient:
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c


def _session(client: TestClient, user_id: str = "dr1", pin: str = "1234") -> dict[str, str]:
    from tests.auth_helpers import session_headers

    return session_headers(client, user_id, pin)


def _unique_raw(name: str) -> str:
    # 10-digit phone unique per call so shared SQLite does not collide across runs.
    phone = f"9{uuid.uuid4().int % 10**9:09d}"
    return build_patient_raw_identifier(name, phone)


def test_billing_charge_payment_due(client: TestClient) -> None:
    headers = _session(client)
    raw = _unique_raw("Billing Due Patient")

    charge = client.post(
        "/api/v1/history/billing",
        headers=headers,
        json={
            "raw_identifier": raw,
            "amount_inr": 1000,
            "note": "Consult",
            "kind": "charge",
        },
    )
    assert charge.status_code == 200, charge.text
    assert charge.json()["encounter_data"]["kind"] == "charge"

    pay = client.post(
        "/api/v1/history/billing",
        headers=headers,
        json={
            "raw_identifier": raw,
            "amount_inr": 400,
            "note": "Partial",
            "kind": "payment",
        },
    )
    assert pay.status_code == 200, pay.text
    assert pay.json()["encounter_data"]["kind"] == "payment"

    summary = client.post(
        "/api/v1/history/billing-summary",
        headers=headers,
        json={"raw_identifier": raw},
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["today_charges_inr"] == 1000.0
    assert body["total_charges_inr"] == 1000.0
    assert body["total_paid_inr"] == 400.0
    assert body["amount_due_inr"] == 600.0


def test_billing_legacy_counts_as_charge(client: TestClient) -> None:
    headers = _session(client)
    raw = _unique_raw("Legacy Bill Patient")
    blind = tokenize_patient_identifier(raw)

    db = SessionLocal()
    try:
        clinic_id = "default"
        db.add(
            ClinicalRecord(
                clinic_id=clinic_id,
                blind_patient_id=blind,
                encounter_data={
                    "type": "billing",
                    "amount_inr": 250.0,
                    "currency": "INR",
                    "note": "legacy",
                    "clinical_observations": ["Bill ₹250.00"],
                    "diagnoses": [],
                    "medications": [],
                    "symptoms": [],
                },
            )
        )
        db.commit()
    finally:
        db.close()

    summary = client.post(
        "/api/v1/history/billing-summary",
        headers=headers,
        json={"raw_identifier": raw},
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["total_charges_inr"] == 250.0
    assert body["amount_due_inr"] == 250.0
    assert body["total_paid_inr"] == 0.0


def test_billing_today_vs_prior_charge(client: TestClient) -> None:
    headers = _session(client)
    raw = _unique_raw("Prior Charge Patient")
    blind = tokenize_patient_identifier(raw)

    clinic_id = "default"

    db = SessionLocal()
    try:
        old = ClinicalRecord(
            clinic_id=clinic_id,
            blind_patient_id=blind,
            encounter_data={
                "type": "billing",
                "kind": "charge",
                "amount_inr": 300.0,
                "currency": "INR",
                "note": "yesterday",
                "clinical_observations": ["Charge ₹300.00"],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
            },
        )
        db.add(old)
        db.commit()
        db.refresh(old)
        old.created_at = datetime.now(timezone.utc) - timedelta(days=2)
        db.add(old)
        db.commit()
    finally:
        db.close()

    today = client.post(
        "/api/v1/history/billing",
        headers=headers,
        json={
            "raw_identifier": raw,
            "amount_inr": 150,
            "kind": "charge",
            "note": "today",
        },
    )
    assert today.status_code == 200, today.text

    summary = client.post(
        "/api/v1/history/billing-summary",
        headers=headers,
        json={"raw_identifier": raw},
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["today_charges_inr"] == 150.0
    assert body["total_charges_inr"] == 450.0
    assert body["amount_due_inr"] == 450.0


def test_lab_forbidden_billing(client: TestClient) -> None:
    headers = _session(client, "lab1", "9999")
    raw = _unique_raw("Lab Bill Block")
    r = client.post(
        "/api/v1/history/billing",
        headers=headers,
        json={"raw_identifier": raw, "amount_inr": 100, "kind": "charge"},
    )
    assert r.status_code == 403


def test_receptionist_can_billing(client: TestClient) -> None:
    headers = _session(client, "desk1", "1111")
    raw = _unique_raw("Reception Bill Patient")
    charge = client.post(
        "/api/v1/history/billing",
        headers=headers,
        json={
            "raw_identifier": raw,
            "amount_inr": 500,
            "kind": "charge",
            "note": "Desk fee",
        },
    )
    assert charge.status_code == 200, charge.text
    summary = client.post(
        "/api/v1/history/billing-summary",
        headers=headers,
        json={"raw_identifier": raw},
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["today_charges_inr"] == 500.0
    assert summary.json()["amount_due_inr"] == 500.0
