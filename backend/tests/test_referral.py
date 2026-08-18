"""Referral PDF + same-clinic handoff APIs."""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite:///./test_referral.db"
os.environ["SECRET_SALT"] = "test_salt_not_for_production_0123456789abcdef"
os.environ["SECRET_KEY"] = "test_secret_key_not_for_production_01234567"
os.environ["CLINICS"] = (
    "default|Test Clinic|||testpass|"
    "voice_rx,labs,queue,appointments,analytics,obstetric,video_consult"
)
os.environ["CLINIC_USERS"] = (
    "dr1|Dr Test|doctor|1234;"
    "dr2|Dr Two|doctor|2345;"
    "nurse1|Nurse Test|staff|5678;"
    "lab1|Lab Test|lab|9999"
)
os.environ["APP_ENV"] = "development"
os.environ["REQUIRE_CLINIC_USERS"] = "false"
os.environ["WHISPER_PRELOAD"] = "false"
os.environ["PUBLIC_API_BASE_URL"] = "http://testserver"

import base64

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.pdf_generator import generate_referral_pdf
from app.services.security import build_patient_raw_identifier


@pytest.fixture()
def client() -> TestClient:
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c


def _session(client: TestClient, user_id: str, pin: str) -> dict[str, str]:
    from tests.auth_helpers import session_headers

    return session_headers(client, user_id, pin)


def test_generate_referral_pdf_nonempty() -> None:
    summary = {
        "narrative": "Follow-up for rising BP.",
        "vitals_latest": {"systolic": "132", "diastolic": "88", "weight": "64"},
        "vitals_trends": {"weight": {"latest": 64, "delta": 1.5, "direction": "rising"}},
        "labs_recent": [{"title": "CBC", "at": "2026-07-01", "results": {"Hb": "10.4"}}],
        "documents_recent": [
            {"title": "USG", "document_kind": "ultrasound", "findings": {"summary": "OK"}}
        ],
        "doctor_comments": [{"at": "2026-07-01", "by": "Dr Test", "text": "Counsel rest"}],
        "last_prescription": {
            "diagnoses": ["GHTN watch"],
            "medications": [{"name": "Labetalol", "dosage": "100mg", "frequency": "BD"}],
        },
        "alerts": [{"message": "BP elevated"}],
        "disclaimer": "Decision support only.",
    }
    buf = generate_referral_pdf(
        summary,
        clinic_name="Test Clinic",
        referring_doctor="Dr Test",
        patient_display_name="Appt Pat",
        clinic_mrn="DEFAULT-000001",
        note="Please review BP trend.",
        recipient_name="Dr External",
    )
    data = buf.getvalue()
    assert data.startswith(b"%PDF")
    assert len(data) > 500


def test_referral_pack_doctor_ok(client: TestClient) -> None:
    headers = _session(client, "dr1", "1234")
    raw = build_patient_raw_identifier("Ref Pat", "9333333333")
    # Seed a vitals row via tokenize + vitals
    tok = client.post(
        "/api/v1/history/tokenize",
        headers=headers,
        json={"patient_name": "Ref Pat", "patient_phone": "9333333333"},
    )
    assert tok.status_code == 200, tok.text
    raw_out = f"mrn|{tok.json()['clinic_mrn']}"
    vitals = client.post(
        "/api/v1/history/vitals",
        headers=headers,
        json={
            "raw_identifier": raw_out,
            "vitals": {"systolic": "120", "diastolic": "80", "weight": "60"},
            "diagnostic_notes": "Baseline",
        },
    )
    assert vitals.status_code == 200, vitals.text

    pack = client.post(
        "/api/v1/history/referral-pack",
        headers=headers,
        json={
            "raw_identifier": raw_out,
            "note": "Please advise",
            "recipient_name": "Dr Outside",
            "patient_display_name": "Ref Pat",
        },
    )
    assert pack.status_code == 200, pack.text
    body = pack.json()
    assert body.get("download_url")
    pdf = base64.b64decode(body["pdf_base64"])
    assert pdf.startswith(b"%PDF")


def test_referral_pack_staff_forbidden(client: TestClient) -> None:
    headers = _session(client, "nurse1", "5678")
    raw = build_patient_raw_identifier("Staff Block", "9444444444")
    r = client.post(
        "/api/v1/history/referral-pack",
        headers=headers,
        json={"raw_identifier": raw},
    )
    assert r.status_code == 403


def test_referral_handoff_inbox_and_ack(client: TestClient) -> None:
    h1 = _session(client, "dr1", "1234")
    h2 = _session(client, "dr2", "2345")
    tok = client.post(
        "/api/v1/history/tokenize",
        headers=h1,
        json={"patient_name": "Hand Pat", "patient_phone": "9555555555"},
    )
    assert tok.status_code == 200, tok.text
    raw = f"mrn|{tok.json()['clinic_mrn']}"

    bad = client.post(
        "/api/v1/history/referral-handoff",
        headers=h1,
        json={"raw_identifier": raw, "to_user_id": "nurse1", "note": "nope"},
    )
    assert bad.status_code == 400

    ho = client.post(
        "/api/v1/history/referral-handoff",
        headers=h1,
        json={
            "raw_identifier": raw,
            "to_user_id": "dr2",
            "note": "Please review Hb",
            "patient_display_name": "Hand Pat",
        },
    )
    assert ho.status_code == 200, ho.text
    handoff_id = ho.json()["id"]

    inbox_self = client.get("/api/v1/history/referrals/inbox", headers=h1)
    assert inbox_self.status_code == 200
    assert all(i["id"] != handoff_id for i in inbox_self.json())

    inbox = client.get("/api/v1/history/referrals/inbox", headers=h2)
    assert inbox.status_code == 200
    items = inbox.json()
    assert any(i["id"] == handoff_id for i in items)
    match = next(i for i in items if i["id"] == handoff_id)
    assert match["from_display_name"]
    assert "Hb" in (match.get("note") or "")

    ack = client.post(
        f"/api/v1/history/referral-handoff/{handoff_id}/ack",
        headers=h2,
    )
    assert ack.status_code == 200, ack.text
    inbox2 = client.get("/api/v1/history/referrals/inbox", headers=h2)
    assert all(i["id"] != handoff_id for i in inbox2.json())
