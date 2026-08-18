"""Case brief enrichment from vitals, reports, and doctor comments."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.services.case_summary import summarize_encounter_rows
from app.services import lml_parser


def _row(at: datetime, encounter: dict) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), created_at=at, encounter_data=encounter)


def test_case_summary_includes_comments_trends_and_narrative(
    monkeypatch,
) -> None:
    now = datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)
    rows = [
        _row(
            now - timedelta(days=60),
            {
                "type": "obstetric_profile",
                "lmp": "2025-12-01",
                "edd": "2026-09-07",
                "gravida": "2",
                "para": "1",
                "abortions": "0",
                "living": "1",
                "high_risk_notes": "Prior PIH",
            },
        ),
        _row(
            now - timedelta(days=21),
            {
                "type": "vitals",
                "vitals": {
                    "systolic": "118",
                    "diastolic": "76",
                    "weight": "62",
                    "hemoglobin": "11.2",
                    "pulse": "78",
                },
                "diagnostic_notes": "ANC booking, mild fatigue",
                "entered_by": {"display_name": "Staff Main", "role": "staff"},
            },
        ),
        _row(
            now - timedelta(days=7),
            {
                "type": "vitals",
                "vitals": {
                    "systolic": "132",
                    "diastolic": "92",
                    "weight": "64.5",
                    "hemoglobin": "10.4",
                    "pulse": "84",
                },
                "diagnostic_notes": "BP rising; counsel rest",
                "entered_by": {"display_name": "Dr Main", "role": "doctor"},
            },
        ),
        _row(
            now - timedelta(days=5),
            {
                "type": "document",
                "title": "Growth scan",
                "filename": "growth_usg.pdf",
                "document_kind": "ultrasound",
                "findings": {
                    "summary": "EFW on track; AFI normal",
                    "efw": "1800g",
                    "afi": "12",
                },
            },
        ),
        _row(
            now - timedelta(days=2),
            {
                "type": "prescription",
                "symptoms": ["headache"],
                "diagnoses": ["Gestational hypertension suspect"],
                "medications": [{"name": "Labetalol"}],
                "clinical_notes": ["Review BP diary"],
                "signed_by": {"display_name": "Dr Main", "role": "doctor"},
            },
        ),
    ]

    summary = summarize_encounter_rows(
        rows,
        clinic_id="default",
        blind_patient_id="blind-patient-demo-001",
    )

    assert summary["doctor_comments"], "expected doctor comments from notes/symptoms"
    assert any("BP rising" in (c.get("text") or "") for c in summary["doctor_comments"])
    assert any(
        "headache" in (c.get("text") or "").lower() for c in summary["doctor_comments"]
    )

    trends = summary["vitals_trends"]
    assert trends["bp_diastolic"]["direction"] == "rising"
    assert trends["weight"]["direction"] == "rising"
    assert trends["hemoglobin"]["direction"] == "falling"

    narrative = summary["narrative"] or ""
    assert narrative
    assert "BP" in narrative or "vitals" in narrative.lower()
    assert "Doctor comments" in narrative or "comment" in narrative.lower()
    assert any(
        "EFW" in (d.get("findings_summary") or "")
        or "AFI" in (d.get("findings_summary") or "")
        for d in summary["documents_recent"]
    )

    def _boom(_system: str, _user: str) -> dict:
        raise RuntimeError("llm disabled in test")

    monkeypatch.setattr(lml_parser, "_chat_json", _boom)
    pack = lml_parser.generate_consult_pack(summary)
    assert pack["llm_used"] is False
    assert pack["concerns"]
    assert pack.get("summary")
    assert any(
        "Prior note" in c or "trend" in c.lower() or len(c) > 5 for c in pack["concerns"]
    )
