"""Unit tests for STT glossary, aliases, and correction memory."""

from __future__ import annotations

import os

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
os.environ.setdefault(
    "CLINIC_USERS",
    "dr1|Dr Test|doctor|1234;nurse1|Nurse Test|staff|5678;lab1|Lab Test|lab|9999",
)
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("REQUIRE_CLINIC_USERS", "false")
os.environ.setdefault("WHISPER_PRELOAD", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.services.stt_memory import (
    apply_term_aliases,
    count_med_name_edits,
    extract_alias_candidates,
    load_clinic_alias_map,
    store_correction_feedback,
    stt_memory_metrics,
    whisper_vocab_blob,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_whisper_vocab_includes_seed_and_env(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.stt_memory.settings.stt_glossary",
        "dydrogesterone, customdrug",
    )
    blob = whisper_vocab_blob()
    assert "mefenamic" in blob.lower()
    assert "dydrogesterone" in blob.lower()
    assert "customdrug" in blob.lower()


def test_apply_default_aliases() -> None:
    mapping = load_clinic_alias_map(None, None)
    out = apply_term_aliases(
        "Start mefthalamic acid 500 mg TDS", mapping
    )
    assert "mefenamic acid" in out.lower()
    assert "mefthalamic" not in out.lower()


def test_alias_map_cache_returns_same_terms() -> None:
    first = load_clinic_alias_map(None, "default")
    second = load_clinic_alias_map(None, "default")
    assert first == second
    assert "mefthalamic" in first


def test_med_name_edit_count_and_alias_extract() -> None:
    parsed = {
        "medications": [{"name": "Mefthalamic", "dosage": "500 mg"}],
        "diagnoses": ["Dysmenorrhoea"],
    }
    final = {
        "medications": [{"name": "Mefenamic acid", "dosage": "500 mg"}],
        "diagnoses": ["Dysmenorrhea"],
    }
    assert count_med_name_edits(parsed, final) == 1
    pairs = extract_alias_candidates(parsed, final)
    assert any(p[1].lower().startswith("mefenamic") for p in pairs)
    assert any(p[2] == "diagnosis" for p in pairs)


def test_store_feedback_mines_aliases(client: TestClient) -> None:
    # Ensure lifespan create_all has run (client fixture).
    _ = client
    db: Session = SessionLocal()
    try:
        result = store_correction_feedback(
            db,
            clinic_id="default",
            blind_patient_id="abc123",
            transcripts=["Give mefthalamic acid 500 mg"],
            parsed_clinical={
                "medications": [{"name": "Mefthalamic", "dosage": "500 mg"}],
                "diagnoses": [],
                "symptoms": [],
                "clinical_observations": [],
            },
            final_clinical={
                "medications": [
                    {"name": "Mefenamic acid", "dosage": "500 mg"}
                ],
                "diagnoses": [],
                "symptoms": [],
                "clinical_observations": [],
            },
            source_language="en",
        )
        db.commit()
        assert result["stored"] is True
        assert result["med_name_edits"] >= 1
        metrics = stt_memory_metrics(db, "default")
        assert metrics["feedback_count"] >= 1
        assert metrics["glossary_term_count"] > 0
        assert metrics["med_name_edit_rate"] >= 0
    finally:
        db.close()


def test_stt_memory_analytics_endpoint(client: TestClient) -> None:
    from tests.auth_helpers import session_headers

    headers = session_headers(client, "dr1", "1234")
    res = client.get(
        "/api/v1/analytics/stt-memory",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "med_name_edit_rate" in body
    assert "top_correction_pairs" in body
    assert "glossary_term_count" in body
