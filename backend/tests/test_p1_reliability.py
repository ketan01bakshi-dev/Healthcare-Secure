"""Unit tests for auth, vitals ranges, phone normalize, and role gates."""

from __future__ import annotations

import os

# Use an isolated SQLite DB for tests before app imports.
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
    "lab1|Lab Test|lab|9999"
)
os.environ["APP_ENV"] = "development"
os.environ["REQUIRE_CLINIC_USERS"] = "false"
os.environ["WHISPER_PRELOAD"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.doctor_auth import (
    hash_pin,
    unlock_user,
    verify_pin,
)
from app.services.security import (
    build_patient_raw_identifier,
    normalize_phone_digits,
    tokenize_patient_identifier,
)
from app.services.vitals_validation import validate_temperature, validate_vitals_dict


@pytest.fixture(scope="module")
def client() -> TestClient:
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c


def _session(client: TestClient, user_id: str, pin: str) -> dict[str, str]:
    from tests.auth_helpers import session_headers

    return session_headers(client, user_id, pin)


def test_normalize_phone_indian() -> None:
    assert normalize_phone_digits("+91 98765 43210") == "9876543210"
    assert normalize_phone_digits("09876543210") == "9876543210"


def test_build_and_tokenize_stable() -> None:
    raw = build_patient_raw_identifier("Ada Lovelace", "9876543210")
    assert raw == "Ada Lovelace|9876543210"
    a = tokenize_patient_identifier(raw)
    b = tokenize_patient_identifier(raw)
    assert a == b
    assert len(a) == 64


def test_pin_hash_roundtrip() -> None:
    hashed = hash_pin("1234")
    assert hashed.startswith("pbkdf2$")
    assert verify_pin(hashed, "1234")
    assert not verify_pin(hashed, "0000")
    assert verify_pin("plain", "plain")


def test_vitals_temperature_fahrenheit() -> None:
    assert validate_temperature("") is None
    assert validate_temperature("98.6") is None
    assert validate_temperature("90") is not None
    assert validate_vitals_dict({"pulse": "10"}) is not None
    assert validate_vitals_dict({"pulse": "72", "blood_pressure": "120/80"}) is None


def test_auth_status_hides_roster(client: TestClient) -> None:
    r = client.get("/api/v1/auth/status")
    assert r.status_code == 200
    body = r.json()
    assert body["auth_required"] is True
    assert "users" not in body
    assert "clinics" not in body
    assert "message" in body


def test_lab_forbidden_vitals(client: TestClient) -> None:
    headers = _session(client, "lab1", "9999")
    raw = build_patient_raw_identifier("Pat", "9123456789")
    r = client.post(
        "/api/v1/history/vitals",
        headers=headers,
        json={
            "raw_identifier": raw,
            "vitals": {"pulse": "72"},
            "diagnostic_notes": "",
        },
    )
    assert r.status_code == 403


def test_staff_can_save_vitals(client: TestClient) -> None:
    headers = _session(client, "nurse1", "5678")
    raw = build_patient_raw_identifier("Pat", "9123456780")
    r = client.post(
        "/api/v1/history/vitals",
        headers=headers,
        json={
            "raw_identifier": raw,
            "vitals": {"pulse": "72"},
            "diagnostic_notes": "",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["encounter_data"]["type"] == "vitals"


def test_phone_change_remaps(client: TestClient) -> None:
    import uuid

    headers = _session(client, "dr1", "1234")
    name = f"Remap Patient {uuid.uuid4().hex[:8]}"
    # Unique 10-digit phones so shared SQLite does not collide across runs.
    suffix = int(uuid.uuid4().hex[:8], 16) % 10_000_000
    old = f"9{suffix:09d}"[:10]
    new = f"8{(suffix + 1) % 10_000_000:09d}"[:10]
    raw_old = build_patient_raw_identifier(name, old)
    v = client.post(
        "/api/v1/history/vitals",
        headers=headers,
        json={
            "raw_identifier": raw_old,
            "vitals": {"pulse": "80"},
            "diagnostic_notes": "",
        },
    )
    assert v.status_code == 200, v.text
    r = client.post(
        "/api/v1/history/change-phone",
        headers=headers,
        json={
            "patient_name": name,
            "old_phone": old,
            "new_phone": new,
        },
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["records_moved"] >= 1
    # After MRN allocation, history lives under mrn|{MRN}, not name|new_phone.
    mrn = payload.get("clinic_mrn")
    assert mrn, payload
    raw_new = build_patient_raw_identifier(name, new, clinic_mrn=mrn)
    hist = client.post(
        "/api/v1/history/search",
        headers=headers,
        json={"raw_identifier": raw_new},
    )
    assert hist.status_code == 200
    types = [x["encounter_data"].get("type") for x in hist.json()]
    assert "vitals" in types
    assert "audit" in types


def test_unlock_wrong_pin(client: TestClient) -> None:
    from tests.auth_helpers import clinic_ticket

    ticket = clinic_ticket(client)
    r = client.post(
        "/api/v1/auth/unlock",
        json={"user_id": "dr1", "pin": "0000", "clinic_ticket": ticket},
    )
    assert r.status_code == 401


def test_unlock_requires_clinic_ticket(client: TestClient) -> None:
    r = client.post(
        "/api/v1/auth/unlock",
        json={"user_id": "dr1", "pin": "1234"},
    )
    assert r.status_code == 401
    assert "clinic" in (r.json().get("detail") or "").lower()


def test_abdm_mock_otp_and_link(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.abdm_mock", True)
    monkeypatch.setattr("app.services.abdm_client.settings.abdm_mock", True)
    headers = _session(client, "dr1", "1234")
    st = client.get("/api/v1/integrations/abha/status", headers=headers)
    assert st.status_code == 200
    assert st.json()["abdm_enabled"] is True
    otp_req = client.post(
        "/api/v1/integrations/abha/otp/request",
        headers=headers,
        json={"abha_address_or_number": "12-3456-7890-1234"},
    )
    assert otp_req.status_code == 200, otp_req.text
    txn = otp_req.json()["txn_id"]
    conf = client.post(
        "/api/v1/integrations/abha/otp/confirm",
        headers=headers,
        json={"txn_id": txn, "otp": "123456"},
    )
    assert conf.status_code == 200, conf.text
    assert conf.json().get("linking_token")
    raw = build_patient_raw_identifier("Abha Pat", "9111111111")
    link = client.post(
        "/api/v1/integrations/abha/link",
        headers=headers,
        json={
            "raw_identifier": raw,
            "abha_number": "12345678901234",
            "consent_acknowledged": True,
            "txn_id": txn,
            "linking_token": conf.json()["linking_token"],
        },
    )
    assert link.status_code == 200, link.text
    assert link.json()["mode"].startswith("abdm")


def test_book_appointment_console_sms(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.sms_provider", "console")
    monkeypatch.setattr("app.services.sms.settings.sms_provider", "console")
    headers = _session(client, "dr1", "1234")
    from datetime import datetime, timedelta, timezone

    when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    raw = build_patient_raw_identifier("Appt Pat", "9222222222")
    r = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "display_name": "Appt Pat",
            "raw_identifier": raw,
            "phone": "9222222222",
            "scheduled_at": when,
            "reason": "Follow-up",
            "send_sms": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "booked"
    assert "sent" in (body.get("sms_status") or "")
    listed = client.get("/api/v1/appointments?status=booked", headers=headers)
    assert listed.status_code == 200
    assert any(a["id"] == body["id"] for a in listed.json())


def test_auth_status_does_not_list_clinics(client: TestClient) -> None:
    r = client.get("/api/v1/auth/status")
    assert r.status_code == 200
    body = r.json()
    assert "clinics" not in body
    assert "users" not in body
    assert body.get("auth_required") is True
