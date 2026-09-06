"""Lab clinical-search scoping — lab users see only their own uploads."""

from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_healthcare.db")
os.environ.setdefault(
    "SECRET_SALT", "test_salt_not_for_production_0123456789abcdef"
)
os.environ.setdefault(
    "SECRET_KEY", "test_secret_key_not_for_production_01234567"
)
os.environ["CLINICS"] = (
    "default|Test Clinic|||testpass|"
    "voice_rx,labs,queue,appointments,analytics,obstetric,video_consult"
)
os.environ["CLINIC_USERS"] = (
    "dr1|Dr Test|doctor|1234;"
    "lab1|Lab Test|lab|9999"
)

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.security import build_patient_raw_identifier
from tests.auth_helpers import session_headers


@pytest.fixture(scope="module")
def client() -> TestClient:
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c


def test_lab_clinical_search_own_uploads_only(client: TestClient) -> None:
    doctor = session_headers(client, "dr1", "1234")
    lab = session_headers(client, "lab1", "9999")

    phone = "9" + f"{uuid.uuid4().int % 10**9:09d}"
    tokenize = client.post(
        "/api/v1/history/tokenize",
        headers=doctor,
        json={"patient_name": "Lab Search Pat", "patient_phone": phone},
    )
    assert tokenize.status_code == 200, tokenize.text
    body = tokenize.json()
    raw = f"mrn|{body['clinic_mrn']}"

    dr_marker = f"DrMarker{uuid.uuid4().hex[:6]}"
    lab_marker = f"LabMarker{uuid.uuid4().hex[:6]}"

    dr_lab = client.post(
        "/api/v1/history/lab-results",
        headers=doctor,
        json={
            "raw_identifier": raw,
            "test_name": dr_marker,
            "value": "12",
            "unit": "mg/dL",
        },
    )
    assert dr_lab.status_code == 200, dr_lab.text

    lab_lab = client.post(
        "/api/v1/history/lab-results",
        headers=lab,
        json={
            "raw_identifier": raw,
            "test_name": lab_marker,
            "value": "8",
            "unit": "mg/dL",
        },
    )
    assert lab_lab.status_code == 200, lab_lab.text

    own_hits = client.get(
        f"/api/v1/history/clinical-search?q={lab_marker.lower()}",
        headers=lab,
    )
    assert own_hits.status_code == 200, own_hits.text
    own_types = {row["match_type"] for row in own_hits.json()}
    assert "lab_result" in own_types

    foreign_hits = client.get(
        f"/api/v1/history/clinical-search?q={dr_marker.lower()}",
        headers=lab,
    )
    assert foreign_hits.status_code == 200, foreign_hits.text
    foreign_lab = [
        row
        for row in foreign_hits.json()
        if row.get("match_type") == "lab_result"
    ]
    assert foreign_lab == []
