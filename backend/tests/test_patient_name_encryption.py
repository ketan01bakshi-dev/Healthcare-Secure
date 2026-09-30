"""Patient names are Fernet-encrypted at rest, readable in the app, and searchable."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.encrypted_type import is_encrypted
from app.main import app
from app.models.clinic_patient import ClinicPatient
from app.services.clinic_patients import list_clinic_patients, upsert_clinic_patient
from app.services.schema_migrate import encrypt_patient_names
from tests.auth_helpers import session_headers


@pytest.fixture(scope="module")
def client() -> TestClient:
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c


def _raw_name(blind_id: str) -> str:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT display_name FROM clinic_patients WHERE blind_patient_id = :b"),
            {"b": blind_id},
        ).scalar_one()


def test_name_encrypted_at_rest_and_searchable(client: TestClient) -> None:
    name = f"Encrypt Pat {uuid.uuid4().hex[:6]}"
    blind_id = f"test-{uuid.uuid4().hex}"
    with SessionLocal() as db:
        upsert_clinic_patient(
            db, clinic_id="default", blind_patient_id=blind_id, display_name=name
        )
        db.commit()

    stored = _raw_name(blind_id)
    assert stored != name
    assert is_encrypted(stored)

    with SessionLocal() as db:
        assert db.get(ClinicPatient, ("default", blind_id)).display_name == name
        hits = list_clinic_patients(db, "default", q=name.split()[-1].upper())
        assert [r.blind_patient_id for r in hits] == [blind_id]

    doctor = session_headers(client, "dr1", "1234")
    res = client.get(
        "/api/v1/history/patients", headers=doctor, params={"q": name.split()[-1]}
    )
    assert res.status_code == 200, res.text
    assert [p["display_name"] for p in res.json()] == [name]


def test_legacy_plaintext_names_are_backfilled(client: TestClient) -> None:
    name = f"Legacy Pat {uuid.uuid4().hex[:6]}"
    blind_id = f"legacy-{uuid.uuid4().hex}"
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO clinic_patients "
                "(clinic_id, blind_patient_id, display_name, phone_last4, "
                "phone_encrypted, clinic_mrn, visit_count, first_seen_at, last_seen_at) "
                "VALUES ('default', :b, :n, '', '', '', 1, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"b": blind_id, "n": name},
        )

    # Old rows stay readable before the backfill runs.
    with SessionLocal() as db:
        assert db.get(ClinicPatient, ("default", blind_id)).display_name == name

    assert encrypt_patient_names(engine) >= 1
    assert is_encrypted(_raw_name(blind_id))
    assert encrypt_patient_names(engine) == 0  # idempotent

    with SessionLocal() as db:
        assert db.get(ClinicPatient, ("default", blind_id)).display_name == name
