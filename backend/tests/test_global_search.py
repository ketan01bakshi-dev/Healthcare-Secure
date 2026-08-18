"""Focused tests for clinic universal search helpers."""

from __future__ import annotations

import os
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_healthcare.db")
os.environ.setdefault("SECRET_SALT", "test_salt_not_for_production_0123456789abcdef")
os.environ.setdefault("SECRET_KEY", "test_secret_key_not_for_production_01234567")

from app.core.database import Base
from app.models.record import ClinicalRecord
from app.services.clinical_search import remember_patient_identity, search_clinic_records
from app.services.security import build_patient_raw_identifier, tokenize_patient_identifier


def _build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def test_global_search_matches_patients_and_record_text() -> None:
    db = _build_session()
    suffix = uuid.uuid4().hex[:6]
    alice_name = f"Alice Search {suffix}"
    bob_name = f"Bob Search {suffix}"
    alice_phone = f"91{int(suffix, 16) % 10_000_000:08d}"[:10]
    bob_phone = f"92{int(suffix, 16) % 10_000_000:08d}"[:10]
    alice_raw = build_patient_raw_identifier(alice_name, alice_phone)
    bob_raw = build_patient_raw_identifier(bob_name, bob_phone)
    alice_blind = tokenize_patient_identifier(alice_raw)
    bob_blind = tokenize_patient_identifier(bob_raw)

    remember_patient_identity(
        blind_patient_id=alice_blind,
        patient_name=alice_name,
        patient_phone=alice_phone,
    )
    remember_patient_identity(
        blind_patient_id=bob_blind,
        patient_name=bob_name,
        patient_phone=bob_phone,
    )

    db.add_all(
        [
            ClinicalRecord(
                blind_patient_id=alice_blind,
                encounter_data={
                    "type": "prescription",
                    "diagnoses": ["Asthma"],
                    "clinical_observations": ["Dry cough follow-up and wheeze review"],
                    "medications": [
                        {
                            "name": "Amoxicillin",
                            "dosage": "500 mg",
                            "frequency": "twice daily",
                            "duration": "5 days",
                        }
                    ],
                },
            ),
            ClinicalRecord(
                blind_patient_id=bob_blind,
                encounter_data={
                    "type": "document",
                    "document_kind": "diagnostic_report",
                    "title": "Acme Labs CBC",
                    "clinical_observations": ["Dry cough improving after antibiotics"],
                },
            ),
        ]
    )
    db.commit()

    patient_results = search_clinic_records(db, query="Alice Search")
    assert any(
        item.kind == "patient" and item.patient_name == alice_name
        for item in patient_results
    )

    diagnosis_results = search_clinic_records(db, query="asthma")
    assert any(
        item.kind == "record"
        and item.patient_name == alice_name
        and item.match_source == "diagnosis"
        for item in diagnosis_results
    )

    medication_results = search_clinic_records(db, query="amoxicillin")
    assert any(
        item.patient_name == alice_name and item.match_source == "medication"
        for item in medication_results
    )

    lab_results = search_clinic_records(db, query="acme")
    assert any(
        item.patient_name == bob_name and item.match_source in {"lab", "document"}
        for item in lab_results
    )

    phone_results = search_clinic_records(db, query=alice_phone)
    assert any(
        item.kind == "patient" and item.patient_phone == alice_phone
        for item in phone_results
    )

    locked_results = search_clinic_records(
        db,
        query="cough",
        locked_blind_patient_id=bob_blind,
    )
    assert locked_results
    assert locked_results[0].patient_name == bob_name
    assert locked_results[0].locked_patient_priority is True
