"""Persist Visit diagnostic ticks on the clinic patient roster."""

from __future__ import annotations

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

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c


def _session(client: TestClient, user_id: str = "dr1", pin: str = "1234") -> dict[str, str]:
    from tests.auth_helpers import session_headers

    return session_headers(client, user_id, pin)


def test_lab_orders_persist_across_roles(client: TestClient) -> None:
    doctor = _session(client, "dr1", "1234")
    name = f"Lab Order Pat {uuid.uuid4().hex[:8]}"
    phone = f"9{uuid.uuid4().int % 10**9:09d}"
    created = client.post(
        "/api/v1/history/tokenize",
        headers=doctor,
        json={"patient_name": name, "patient_phone": phone},
    )
    assert created.status_code == 200, created.text
    mrn = created.json()["clinic_mrn"]
    assert mrn
    raw = f"mrn|{mrn}"

    empty = client.get(
        "/api/v1/history/lab-orders",
        headers=doctor,
        params={"raw_identifier": raw},
    )
    assert empty.status_code == 200, empty.text
    assert empty.json() == {"selected": [], "dismissed": []}

    saved = client.put(
        "/api/v1/history/lab-orders",
        headers=doctor,
        json={
            "raw_identifier": raw,
            "selected": ["cbc", "hba1c"],
            "dismissed": ["widal"],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["selected"] == ["cbc", "hba1c"]
    assert saved.json()["dismissed"] == ["widal"]

    lab = _session(client, "lab1", "9999")
    from_lab = client.get(
        "/api/v1/history/lab-orders",
        headers=lab,
        params={"raw_identifier": raw},
    )
    assert from_lab.status_code == 200, from_lab.text
    assert from_lab.json()["selected"] == ["cbc", "hba1c"]
    assert from_lab.json()["dismissed"] == ["widal"]

    desk = _session(client, "desk1", "1111")
    blocked = client.get(
        "/api/v1/history/lab-orders",
        headers=desk,
        params={"raw_identifier": raw},
    )
    assert blocked.status_code == 403


def test_identity_allows_mrn_without_phone(client: TestClient) -> None:
    doctor = _session(client, "dr1", "1234")
    name = f"Mrn Only {uuid.uuid4().hex[:8]}"
    mrn = f"TEST-{uuid.uuid4().hex[:6].upper()}"
    created = client.post(
        "/api/v1/history/tokenize",
        headers=doctor,
        json={"patient_name": name, "clinic_mrn": mrn},
    )
    assert created.status_code == 200, created.text
    blind_id = created.json()["blind_patient_id"]
    assert created.json()["clinic_mrn"] == mrn

    identity = client.get(
        f"/api/v1/history/patients/{blind_id}/identity",
        headers=doctor,
    )
    assert identity.status_code == 200, identity.text
    body = identity.json()
    assert body["display_name"] == name
    assert body["clinic_mrn"] == mrn
    assert body.get("phone") in ("", None)
