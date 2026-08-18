"""
Seed gynecology clinic demo data for showcasing Aarogya One Connect.

Usage (from backend folder, with venv active):
  python scripts/seed_demo.py
  python scripts/seed_demo.py --wipe

Or from repo root:
  scripts\\seed_demo.cmd
  scripts\\seed_demo.cmd --wipe
  scripts\\seed_demo.cmd --clinic east
  scripts\\seed_demo.cmd --clinic east --wipe

Then unlock as Dr. Nirmala Tiwari (default clinic) or the east clinic doctor and lock a demo patient.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Ensure backend root is on path when run as scripts/seed_demo.py
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.api.v1.endpoints.queue import QueueEntry
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.models.appointment import Appointment
from app.models.record import ClinicalRecord
from app.services.attachment_store import save_attachment
from app.services.clinic_patients import upsert_clinic_patient
from app.services.phone_crypto import encrypt_phone
from app.services.security import (
    build_patient_raw_identifier,
    tokenize_patient_identifier,
)

IST = ZoneInfo("Asia/Kolkata")
CLINIC = "default"
DEMO_TAG = "demo:seed"
DOCTOR = {
    "user_id": "dr_nirmala",
    "display_name": "Dr. Nirmala Tiwari",
    "role": "doctor",
}
STAFF = {
    "user_id": "staff_dhanaraj",
    "display_name": "Staff",
    "role": "staff",
}
STAFF2 = {
    "user_id": "staff_priyanka",
    "display_name": "Priyanka",
    "role": "staff",
}
RECEPTION = {
    "user_id": "reception1",
    "display_name": "Front Desk",
    "role": "receptionist",
}
LAB = {
    "user_id": "lab1",
    "display_name": "Lab Desk",
    "role": "lab",
}

def _pdf_with_text(*lines: str) -> bytes:
    """Minimal PDF with extractable ASCII (for Analyze / cadence matching)."""
    text = "  ".join(lines)[:400]
    # Escape PDF string delimiters
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 10 Tf 40 720 Td ({safe}) Tj ET".encode("latin-1", errors="replace")
    return (
        b"%PDF-1.1\n1 0 obj<<>>endobj\n2 0 obj<< /Length "
        + str(len(stream)).encode()
        + b" >>stream\n"
        + stream
        + b"\nendstream\nendobj\n"
        b"3 0 obj<< /Type /Page /Parent 4 0 R /Contents 2 0 R >>endobj\n"
        b"4 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
        b"5 0 obj<< /Type /Catalog /Pages 4 0 R >>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \ntrailer<< /Size 6 /Root 5 0 R >>\n"
        b"startxref\n0\n%%EOF\n"
    )


_MINI_PDF = _pdf_with_text("Demo USG Report")


def _now_ist() -> datetime:
    return datetime.now(IST)


def _stamp(when: datetime) -> tuple[str, str]:
    iso = when.isoformat()
    display = when.strftime("%d %b %Y, %I:%M %p IST")
    return iso, display


def _rec(
    blind: str,
    data: dict[str, Any],
    when: datetime,
) -> ClinicalRecord:
    payload = dict(data)
    payload["demo"] = True
    payload["demo_tag"] = DEMO_TAG
    return ClinicalRecord(
        id=uuid.uuid4(),
        clinic_id=CLINIC,
        blind_patient_id=blind,
        created_at=when.astimezone(timezone.utc),
        encounter_data=payload,
    )


def _patient(
    name: str,
    phone: str,
    mrn: str | None = None,
) -> tuple[str, str, str]:
    raw = build_patient_raw_identifier(name, phone, clinic_mrn=mrn)
    blind = tokenize_patient_identifier(raw)
    return raw, blind, phone


def _billing(
    blind: str,
    *,
    kind: str,
    amount_inr: float,
    note: str,
    when: datetime,
    actor: dict[str, str],
) -> ClinicalRecord:
    iso, disp = _stamp(when)
    amount = round(float(amount_inr), 2)
    label = "Payment" if kind == "payment" else "Charge"
    summary = f"{label} ₹{amount:,.2f}"
    if note:
        summary += f" — {note[:120]}"
    return _rec(
        blind,
        {
            "type": "billing",
            "kind": kind,
            "amount_inr": amount,
            "currency": "INR",
            "note": note,
            "clinical_observations": [summary],
            "diagnoses": [],
            "medications": [],
            "symptoms": [],
            "entered_by": actor,
            "entered_at": iso,
            "entered_at_display": disp,
        },
        when,
    )


def wipe_demo(db, clinic_id: str | None = None) -> int:
    """Remove prior seed rows tagged demo:seed / demo flag.

    If clinic_id is set, only wipe that clinic's demo rows (for second-clinic re-seed).
    """
    removed = 0
    # Appointments
    appts = db.scalars(
        select(Appointment).where(Appointment.notes.contains(DEMO_TAG))
    ).all()
    for a in appts:
        if clinic_id is not None and getattr(a, "clinic_id", None) != clinic_id:
            continue
        db.delete(a)
        removed += 1
    # Queue
    qrows = db.scalars(
        select(QueueEntry).where(QueueEntry.note.contains(DEMO_TAG))
    ).all()
    for q in qrows:
        if clinic_id is not None and getattr(q, "clinic_id", None) != clinic_id:
            continue
        db.delete(q)
        removed += 1
    # Clinical records
    rows = db.scalars(select(ClinicalRecord)).all()
    for r in rows:
        if clinic_id is not None and r.clinic_id != clinic_id:
            continue
        data = r.encounter_data if isinstance(r.encounter_data, dict) else {}
        if data.get("demo") or data.get("demo_tag") == DEMO_TAG:
            db.delete(r)
            removed += 1
    db.commit()
    return removed


def seed(db) -> list[dict[str, str]]:
    get_settings.cache_clear()
    now = _now_ist()
    today = now.date()
    cheat: list[dict[str, str]] = []

    # --- Patients (each maps to a showcase path) ---
    patients = [
        {
            "key": "anc",
            "name": "Ananya Reddy",
            "phone": "9876501001",
            "mrn": "GYN-1001",
            "label": (
                "[STAR] Case brief, ANC alerts, GA charts, consult pack, "
                "billing (amount due), video consult timeline, Analyze USG"
            ),
        },
        {
            "key": "early",
            "name": "Priya Nair",
            "phone": "9876501007",
            "mrn": "GYN-1007",
            "label": "Early ANC ~12w - NT scan DUE on cadence checklist",
        },
        {
            "key": "pih",
            "name": "Rekha Sharma",
            "phone": "9876501008",
            "mrn": "GYN-1008",
            "label": (
                "PIH / high BP + low Hb - critical alerts; draft Rx without "
                "iron or with Methergine to demo Rx hints; billing charges"
            ),
        },
        {
            "key": "pcos",
            "name": "Kavita Mehta",
            "phone": "9876501002",
            "mrn": None,
            "label": "PCOS / infertility workup + pelvic USG + paid lab bill",
        },
        {
            "key": "dys",
            "name": "Sunita Devi",
            "phone": "9876501003",
            "mrn": None,
            "label": "Dysmenorrhea - voice-to-sign Rx + consult fee (part paid)",
        },
        {
            "key": "pp",
            "name": "Meera Joshi",
            "phone": "9876501004",
            "mrn": "GYN-1004",
            "label": "Postpartum + next appointment (Patient tab / ICS)",
        },
        {
            "key": "inf",
            "name": "Fatima Khan",
            "phone": "9876501005",
            "mrn": None,
            "label": "Infertility - tomorrow slot (day-before SMS) + video booking",
        },
        {
            "key": "pmb",
            "name": "Lakshmi Iyer",
            "phone": "9876501006",
            "mrn": None,
            "label": "PMB / menopause - waiting list Open + endometrium USG",
        },
        {
            "key": "sec",
            "name": "Neha Kapoor",
            "phone": "9876501009",
            "mrn": "GYN-1009",
            "label": (
                "[SECURITY] MRN-keyed identity + audit trail - history survives "
                "phone change; show blind-ID timeline"
            ),
        },
        {
            "key": "voice",
            "name": "Aisha Begum",
            "phone": "9876501010",
            "mrn": None,
            "label": (
                "[VOICE] Clean slate for live speech-to-Rx demo "
                "(or Visit -> Load demo transcript)"
            ),
        },
        {
            "key": "bill",
            "name": "Sonal Desai",
            "phone": "9876501011",
            "mrn": "GYN-1011",
            "label": (
                "[BILLING] Front-desk pitch: today's charges, prior payments, "
                "amount due — Show pay QR (receptionist PIN 1111)"
            ),
        },
    ]

    blinds: dict[str, tuple[str, str, str]] = {}
    for p in patients:
        raw, blind, phone = _patient(p["name"], p["phone"], p.get("mrn"))
        blinds[p["key"]] = (raw, blind, phone)
        cheat.append(
            {
                "name": p["name"],
                "phone": phone,
                "mrn": p.get("mrn") or "-",
                "raw": raw,
                "use": p["label"],
            }
        )

    # ========== Ananya Reddy — ANC continuity (full decision support) ==========
    _, blind_anc, _ = blinds["anc"]
    # LMP ~28 weeks before today → GA charts + obstetric card
    lmp_anc = (now - timedelta(weeks=28)).date()
    edd_anc = lmp_anc + timedelta(days=280)
    when = now - timedelta(days=20)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_anc,
            {
                "type": "obstetric_profile",
                "lmp": lmp_anc.isoformat(),
                "edd": edd_anc.isoformat(),
                "edd_source": "lmp",
                "gravida": "2",
                "para": "1",
                "abortions": "0",
                "living": "1",
                "blood_group": "B",
                "rh": "+",
                "high_risk_notes": "Previous LSCS; watch BP",
                "clinical_observations": [
                    f"LMP={lmp_anc.isoformat()}",
                    f"EDD={edd_anc.isoformat()}",
                    "G2P1A0L1",
                ],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
                "entered_by": DOCTOR,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    # Rising BP + falling Hb + weight jump → case-brief / chart alerts
    for i, (sys, dia, wt, hb, note) in enumerate(
        [
            (118, 76, "58.5", "11.8", "ANC booking — BP normal"),
            (120, 78, "59.2", "11.0", "ANC 20w — mild oedema"),
            (128, 84, "61.0", "10.4", "ANC 24w — BP rising"),
            (142, 94, "64.8", "9.6", "ANC 28w — hypertensive range + anemia"),
        ]
    ):
        when = now - timedelta(days=21 - i * 7, hours=2)
        iso, disp = _stamp(when)
        db.add(
            _rec(
                blind_anc,
                {
                    "type": "vitals",
                    "vitals": {
                        "blood_pressure": f"{sys}/{dia}",
                        "systolic": str(sys),
                        "diastolic": str(dia),
                        "pulse": str(78 + i * 2),
                        "temperature": "98.4",
                        "spo2": "98",
                        "weight": wt,
                        "height": "158",
                        "respiratory_rate": "16",
                        "hemoglobin": hb,
                    },
                    "diagnostic_notes": note,
                    "age_years": 28,
                    "clinical_observations": [
                        f"blood pressure={sys}/{dia}",
                        f"weight={wt}",
                        f"hemoglobin={hb}",
                        f"notes={note}",
                    ],
                    "diagnoses": [],
                    "medications": [],
                    "symptoms": [],
                    "entered_by": STAFF if i % 2 == 0 else STAFF2,
                    "entered_at": iso,
                    "entered_at_display": disp,
                },
                when,
            )
        )

    when = now - timedelta(days=2, hours=1)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_anc,
            {
                "type": "lab_result",
                "test_name": "Hemoglobin",
                "value": "9.8",
                "unit": "g/dL",
                "reference_range": "11–14 (pregnancy)",
                "collected_at": (now - timedelta(days=3)).date().isoformat(),
                "clinical_observations": ["Hb=9.8 g/dL"],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
                "entered_by": LAB,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    when = now - timedelta(days=2, hours=0)
    iso, disp = _stamp(when)
    for test, val, unit, ref in [
        ("TSH", "2.1", "mIU/L", "0.4–4.0"),
        ("Urine albumin", "Trace", "", "Nil"),
        ("FBS", "92", "mg/dL", "70–95 (ANC)"),
    ]:
        db.add(
            _rec(
                blind_anc,
                {
                    "type": "lab_result",
                    "test_name": test,
                    "value": val,
                    "unit": unit,
                    "reference_range": ref,
                    "collected_at": (now - timedelta(days=3)).date().isoformat(),
                    "clinical_observations": [f"{test}={val} {unit}".strip()],
                    "diagnoses": [],
                    "medications": [],
                    "symptoms": [],
                    "entered_by": LAB,
                    "entered_at": iso,
                    "entered_at_display": disp,
                },
                when,
            )
        )
        when = when + timedelta(minutes=3)
        iso, disp = _stamp(when)

    when = now - timedelta(hours=3)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_anc,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": get_settings().clinic_name,
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 0,
                "symptoms": ["mild backache", "fatigue", "headache"],
                "clinical_observations": [
                    "GA ~28 weeks",
                    "FHR present",
                    "Fundal height appropriate",
                    "BP elevated — review",
                ],
                "diagnoses": [
                    "Antenatal care — 28 weeks",
                    "Mild anemia",
                    "Gestational hypertension — monitor",
                ],
                "medications": [
                    {
                        "name": "Iron + Folic acid",
                        "dosage": "1 tablet",
                        "frequency": "OD after food",
                        "duration": "30 days",
                    },
                    {
                        "name": "Calcium",
                        "dosage": "500 mg",
                        "frequency": "BD",
                        "duration": "30 days",
                    },
                    {
                        "name": "Labetalol",
                        "dosage": "100 mg",
                        "frequency": "BD",
                        "duration": "7 days",
                    },
                ],
                "signed_by": DOCTOR,
            },
            when,
        )
    )

    def _add_doc(
        blind: str,
        *,
        title: str,
        filename: str,
        when: datetime,
        pdf: bytes,
        findings: dict[str, Any] | None = None,
        kind: str = "diagnostic_report",
    ) -> None:
        path = save_attachment(
            blind_patient_id=blind,
            filename=filename,
            content=pdf,
            content_type="application/pdf",
        )
        iso_d, disp_d = _stamp(when)
        payload: dict[str, Any] = {
            "type": "document",
            "document_kind": kind,
            "title": title,
            "filename": filename,
            "content_type": "application/pdf",
            "size_bytes": len(pdf),
            "content_path": path,
            "diagnoses": [],
            "clinical_observations": [f"Uploaded diagnostic report: {title}"],
            "medications": [],
            "symptoms": [],
            "entered_by": LAB,
            "entered_at": iso_d,
            "entered_at_display": disp_d,
        }
        if findings:
            payload["findings"] = findings
            payload["findings_at"] = iso_d
        db.add(_rec(blind, payload, when))

    # NT documented (past window) → cadence shows documented
    _add_doc(
        blind_anc,
        title="NT / nuchal translucency scan (12w)",
        filename="anc_nt_scan.pdf",
        when=now - timedelta(weeks=16, hours=3),
        pdf=_pdf_with_text(
            "NT nuchal translucency scan",
            "CRL 58mm",
            "NT 1.4mm",
            "low risk",
        ),
        findings={
            "report_type": "nt_scan",
            "afi": "",
            "efw": "",
            "placenta": "",
            "presentation": "",
            "ga_by_usg": "12w2d",
            "anomaly_flags": [],
            "other_findings": ["NT 1.4 mm", "low risk aneuploidy screen"],
            "summary": "NT 1.4 mm at 12w — low risk.",
            "llm_used": False,
        },
    )
    # Anomaly documented with structured findings (case brief)
    _add_doc(
        blind_anc,
        title="Anomaly / TIFFA scan (20w)",
        filename="anc_usg_anomaly_scan.pdf",
        when=now - timedelta(weeks=8, hours=4),
        pdf=_pdf_with_text(
            "Anomaly TIFFA Level II scan",
            "GA by USG 20w3d",
            "AFI 12 cm",
            "placenta anterior",
            "cephalic",
            "no major anomaly",
        ),
        findings={
            "report_type": "anomaly_scan",
            "afi": "12 cm",
            "efw": "",
            "placenta": "anterior, not low-lying",
            "presentation": "cephalic",
            "ga_by_usg": "20w3d",
            "anomaly_flags": [],
            "other_findings": ["cardiac 4-chamber view normal"],
            "summary": "TIFFA at 20w3d — no major anomaly; AFI 12 cm.",
            "llm_used": False,
        },
    )
    # Growth scan WITHOUT findings → use Records → Analyze
    _add_doc(
        blind_anc,
        title="Growth / Doppler USG (28w) — tap Analyze",
        filename="anc_growth_doppler.pdf",
        when=now - timedelta(days=1, hours=2),
        pdf=_pdf_with_text(
            "Growth Doppler third trimester USG",
            "EFW 1180 g",
            "AFI 11 cm",
            "UA PI normal",
            "placenta fundal",
            "cephalic presentation",
            "GA by USG 28w1d",
        ),
        findings=None,
    )

    # ========== Priya Nair — early ANC (~12w), NT due ==========
    _, blind_early, _ = blinds["early"]
    lmp_early = (now - timedelta(weeks=12, days=2)).date()
    edd_early = lmp_early + timedelta(days=280)
    when = now - timedelta(days=3)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_early,
            {
                "type": "obstetric_profile",
                "lmp": lmp_early.isoformat(),
                "edd": edd_early.isoformat(),
                "edd_source": "lmp",
                "gravida": "1",
                "para": "0",
                "abortions": "0",
                "living": "0",
                "blood_group": "O",
                "rh": "+",
                "high_risk_notes": "",
                "clinical_observations": ["G1P0A0L0", "booking visit"],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
                "entered_by": DOCTOR,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    when = now - timedelta(hours=6)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_early,
            {
                "type": "vitals",
                "vitals": {
                    "blood_pressure": "112/70",
                    "systolic": "112",
                    "diastolic": "70",
                    "pulse": "80",
                    "temperature": "98.2",
                    "spo2": "99",
                    "weight": "54",
                    "hemoglobin": "11.4",
                },
                "diagnostic_notes": "ANC booking ~12w",
                "age_years": 24,
                "clinical_observations": ["FHR +", "uterus 12 weeks size"],
                "diagnoses": [],
                "medications": [],
                "symptoms": ["nausea"],
                "entered_by": STAFF,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    when = now - timedelta(hours=5)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_early,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": get_settings().clinic_name,
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 0,
                "symptoms": ["nausea", "fatigue"],
                "clinical_observations": ["GA ~12 weeks"],
                "diagnoses": ["Antenatal care — first trimester"],
                "medications": [
                    {
                        "name": "Folic acid",
                        "dosage": "5 mg",
                        "frequency": "OD",
                        "duration": "90 days",
                    },
                    {
                        "name": "Doxylamine + Pyridoxine",
                        "dosage": "1 tablet",
                        "frequency": "HS",
                        "duration": "14 days",
                    },
                ],
                "signed_by": DOCTOR,
            },
            when,
        )
    )

    # ========== Rekha Sharma — PIH / critical alerts + Rx-hint target ==========
    _, blind_pih, _ = blinds["pih"]
    lmp_pih = (now - timedelta(weeks=34)).date()
    edd_pih = lmp_pih + timedelta(days=280)
    when = now - timedelta(days=5)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_pih,
            {
                "type": "obstetric_profile",
                "lmp": lmp_pih.isoformat(),
                "edd": edd_pih.isoformat(),
                "edd_source": "lmp",
                "gravida": "3",
                "para": "2",
                "abortions": "0",
                "living": "2",
                "blood_group": "A",
                "rh": "-",
                "high_risk_notes": "PIH; Rh negative; allergy to penicillin",
                "clinical_observations": ["G3P2A0L2", "Rh-"],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
                "entered_by": DOCTOR,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    for i, (sys, dia, wt, hb, note) in enumerate(
        [
            (132, 88, "68", "10.2", "ANC 30w — BP borderline"),
            (148, 96, "69", "9.8", "ANC 32w — rising BP"),
            (162, 112, "71", "8.9", "ANC 34w — severe diastolic range"),
        ]
    ):
        when = now - timedelta(days=14 - i * 5, hours=1)
        iso, disp = _stamp(when)
        db.add(
            _rec(
                blind_pih,
                {
                    "type": "vitals",
                    "vitals": {
                        "blood_pressure": f"{sys}/{dia}",
                        "systolic": str(sys),
                        "diastolic": str(dia),
                        "pulse": str(90 + i),
                        "temperature": "98.6",
                        "spo2": "97",
                        "weight": wt,
                        "hemoglobin": hb,
                    },
                    "diagnostic_notes": note,
                    "age_years": 32,
                    "clinical_observations": [
                        f"BP={sys}/{dia}",
                        f"Hb={hb}",
                        "proteinuria check advised",
                    ],
                    "diagnoses": [],
                    "medications": [],
                    "symptoms": ["headache"] if i == 2 else [],
                    "entered_by": STAFF2,
                    "entered_at": iso,
                    "entered_at_display": disp,
                },
                when,
            )
        )
    when = now - timedelta(days=1)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_pih,
            {
                "type": "lab_result",
                "test_name": "Hemoglobin",
                "value": "8.7",
                "unit": "g/dL",
                "reference_range": "11–14 (pregnancy)",
                "collected_at": (now - timedelta(days=1)).date().isoformat(),
                "clinical_observations": ["Hb=8.7 g/dL"],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
                "entered_by": LAB,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    # Last Rx intentionally WITHOUT iron → Rx-hint when drafting Calcium-only / Methergine
    when = now - timedelta(hours=8)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_pih,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": get_settings().clinic_name,
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 0,
                "symptoms": ["frontal headache", "swelling feet"],
                "clinical_observations": [
                    "BP 162/112",
                    "reflexes brisk",
                    "admit / urgent review advised",
                ],
                "diagnoses": ["Severe gestational hypertension", "Anemia in pregnancy"],
                "medications": [
                    {
                        "name": "Labetalol",
                        "dosage": "200 mg",
                        "frequency": "TDS",
                        "duration": "5 days",
                    },
                    {
                        "name": "Aspirin",
                        "dosage": "75 mg",
                        "frequency": "OD",
                        "duration": "until 36w",
                    },
                ],
                "signed_by": DOCTOR,
            },
            when,
        )
    )
    _add_doc(
        blind_pih,
        title="Growth Doppler USG (34w)",
        filename="pih_growth_doppler.pdf",
        when=now - timedelta(days=2),
        pdf=_pdf_with_text(
            "Growth Doppler third trimester",
            "EFW 2100 g",
            "AFI 8 cm",
            "UA PI elevated",
        ),
        findings={
            "report_type": "growth_scan",
            "afi": "8 cm",
            "efw": "2100 g",
            "placenta": "posterior",
            "presentation": "cephalic",
            "ga_by_usg": "33w5d",
            "anomaly_flags": ["oligohydramnios borderline"],
            "other_findings": ["UA PI elevated — correlate clinically"],
            "summary": "Growth scan: EFW 2100 g, AFI 8 cm, UA PI elevated.",
            "llm_used": False,
        },
    )

    # ========== Kavita Mehta — PCOS ==========
    _, blind_pcos, _ = blinds["pcos"]
    when = now - timedelta(days=5)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_pcos,
            {
                "type": "vitals",
                "vitals": {
                    "blood_pressure": "128/84",
                    "systolic": "128",
                    "diastolic": "84",
                    "pulse": "82",
                    "temperature": "98.2",
                    "spo2": "99",
                    "weight": "72",
                    "height": "162",
                },
                "diagnostic_notes": "PCOS follow-up",
                "age_years": 26,
                "clinical_observations": ["BMI elevated"],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
                "entered_by": STAFF2,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    when = now - timedelta(days=4)
    iso, disp = _stamp(when)
    for test, val, unit, ref in [
        ("AMH", "4.8", "ng/mL", "1.0–3.5"),
        ("FSH", "6.2", "mIU/mL", "3–10 follicular"),
        ("LH", "11.5", "mIU/mL", "2–10 follicular"),
        ("TSH", "3.4", "mIU/L", "0.4–4.0"),
    ]:
        db.add(
            _rec(
                blind_pcos,
                {
                    "type": "lab_result",
                    "test_name": test,
                    "value": val,
                    "unit": unit,
                    "reference_range": ref,
                    "collected_at": (now - timedelta(days=5)).date().isoformat(),
                    "clinical_observations": [f"{test}={val} {unit}"],
                    "diagnoses": [],
                    "medications": [],
                    "symptoms": [],
                    "entered_by": LAB,
                    "entered_at": iso,
                    "entered_at_display": disp,
                },
                when,
            )
        )
        when = when + timedelta(minutes=5)

    when = now - timedelta(days=1, hours=2)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_pcos,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": get_settings().clinic_name,
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 0,
                "symptoms": ["irregular cycles", "acne", "weight gain"],
                "clinical_observations": ["PCO morphology on USG", "LH:FSH elevated"],
                "diagnoses": ["PCOS", "Infertility workup"],
                "medications": [
                    {
                        "name": "Metformin",
                        "dosage": "500 mg",
                        "frequency": "BD after food",
                        "duration": "90 days",
                    },
                    {
                        "name": "Myo-inositol",
                        "dosage": "2 g",
                        "frequency": "BD",
                        "duration": "90 days",
                    },
                ],
                "signed_by": DOCTOR,
            },
            when,
        )
    )
    _add_doc(
        blind_pcos,
        title="Pelvic USG — PCOS morphology",
        filename="pcos_pelvic_usg.pdf",
        when=now - timedelta(days=6),
        pdf=_pdf_with_text(
            "Pelvic USG",
            "bilateral polycystic ovaries",
            "endometrium 8 mm",
        ),
        findings={
            "report_type": "pelvic_usg",
            "afi": "",
            "efw": "",
            "placenta": "",
            "presentation": "",
            "ga_by_usg": "",
            "anomaly_flags": [],
            "other_findings": ["bilateral PCO morphology", "ET 8 mm"],
            "summary": "Pelvic USG consistent with polycystic ovarian morphology.",
            "llm_used": False,
        },
    )

    # ========== Sunita Devi — dysmenorrhea ==========
    _, blind_dys, _ = blinds["dys"]
    when = now - timedelta(hours=5)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_dys,
            {
                "type": "vitals",
                "vitals": {
                    "blood_pressure": "110/70",
                    "systolic": "110",
                    "diastolic": "70",
                    "pulse": "88",
                    "temperature": "98.6",
                    "spo2": "98",
                    "weight": "55",
                },
                "diagnostic_notes": "Acute dysmenorrhea",
                "age_years": 22,
                "clinical_observations": [],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
                "entered_by": STAFF,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    when = now - timedelta(hours=4)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_dys,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": get_settings().clinic_name,
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 0,
                "symptoms": ["severe lower abdominal pain", "heavy flow"],
                "clinical_observations": ["P/A soft, tender hypogastrium"],
                "diagnoses": ["Primary dysmenorrhea", "Menorrhagia"],
                "medications": [
                    {
                        "name": "Mefenamic acid",
                        "dosage": "500 mg",
                        "frequency": "TID after food",
                        "duration": "3 days",
                    },
                    {
                        "name": "Tranexamic acid",
                        "dosage": "500 mg",
                        "frequency": "TID",
                        "duration": "5 days",
                    },
                ],
                "signed_by": DOCTOR,
            },
            when,
        )
    )

    # ========== Meera Joshi — postpartum ==========
    _, blind_pp, _ = blinds["pp"]
    when = now - timedelta(days=10)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_pp,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": get_settings().clinic_name,
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 0,
                "symptoms": ["postpartum check"],
                "clinical_observations": ["LSCS day 42", "Wound healthy"],
                "diagnoses": ["Postpartum visit", "Contraception counselling"],
                "medications": [
                    {
                        "name": "Iron + Folic acid",
                        "dosage": "1 tablet",
                        "frequency": "OD",
                        "duration": "30 days",
                    }
                ],
                "signed_by": DOCTOR,
            },
            when,
        )
    )

    # ========== Fatima — infertility labs ==========
    _, blind_inf, _ = blinds["inf"]
    when = now - timedelta(days=7)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_inf,
            {
                "type": "lab_result",
                "test_name": "AMH",
                "value": "1.2",
                "unit": "ng/mL",
                "reference_range": "1.0–3.5",
                "collected_at": (now - timedelta(days=8)).date().isoformat(),
                "clinical_observations": ["AMH=1.2 ng/mL"],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
                "entered_by": LAB,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )

    # ========== Lakshmi Iyer — PMB ==========
    _, blind_pmb, _ = blinds["pmb"]
    when = now - timedelta(hours=2)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_pmb,
            {
                "type": "vitals",
                "vitals": {
                    "blood_pressure": "138/86",
                    "systolic": "138",
                    "diastolic": "86",
                    "pulse": "76",
                    "temperature": "98.4",
                    "spo2": "98",
                    "weight": "64",
                },
                "diagnostic_notes": "PMB evaluation",
                "age_years": 54,
                "clinical_observations": ["postmenopausal bleeding × 10 days"],
                "diagnoses": [],
                "medications": [],
                "symptoms": ["vaginal spotting"],
                "entered_by": STAFF,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    _add_doc(
        blind_pmb,
        title="TVS endometrium — PMB workup",
        filename="pmb_tvs.pdf",
        when=now - timedelta(hours=1),
        pdf=_pdf_with_text(
            "Transvaginal USG",
            "endometrial thickness 11 mm",
            "no adnexal mass",
        ),
        findings={
            "report_type": "tvs",
            "afi": "",
            "efw": "",
            "placenta": "",
            "presentation": "",
            "ga_by_usg": "",
            "anomaly_flags": ["endometrium thickened"],
            "other_findings": ["ET 11 mm"],
            "summary": "TVS: endometrial thickness 11 mm — biopsy consideration.",
            "llm_used": False,
        },
    )

    # ========== Neha Kapoor — security / MRN + audit showcase ==========
    _, blind_sec, _ = blinds["sec"]
    when = now - timedelta(days=12)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_sec,
            {
                "type": "audit",
                "action": "patient_locked",
                "summary": "Staff locked patient via MRN GYN-1009 (demo)",
                "clinical_observations": [
                    "identity_key=mrn",
                    "raw phone never written to clinical_records columns",
                ],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
                "entered_by": STAFF,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    when = now - timedelta(days=11)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_sec,
            {
                "type": "vitals",
                "vitals": {
                    "blood_pressure": "118/74",
                    "systolic": "118",
                    "diastolic": "74",
                    "pulse": "76",
                    "weight": "60",
                    "hemoglobin": "12.1",
                },
                "diagnostic_notes": "Pre-op clearance",
                "age_years": 30,
                "clinical_observations": ["BP normal"],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
                "entered_by": STAFF2,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    when = now - timedelta(days=10)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_sec,
            {
                "type": "audit",
                "action": "phone_change_note",
                "summary": (
                    "Demo note: MRN-keyed patients keep history if mobile changes "
                    "(change-phone remap applies to name|phone keys only)."
                ),
                "clinical_observations": ["mrn=GYN-1009"],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
                "entered_by": DOCTOR,
                "entered_at": iso,
                "entered_at_display": disp,
            },
            when,
        )
    )
    when = now - timedelta(days=9)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_sec,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": get_settings().clinic_name,
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 2,
                "symptoms": ["pre-op anxiety"],
                "clinical_observations": ["signed after voice parse review"],
                "diagnoses": ["Elective procedure counselling"],
                "medications": [
                    {
                        "name": "Alprazolam",
                        "dosage": "0.25 mg",
                        "frequency": "HS",
                        "duration": "3 days",
                    }
                ],
                "signed_by": DOCTOR,
            },
            when,
        )
    )

    # ========== Analytics volume — extra signed Rx over the last week ==========
    analytics_rx = [
        (
            "dys",
            6,
            ["cramps"],
            ["Primary dysmenorrhea"],
            [{"name": "Mefenamic acid", "dosage": "500 mg", "frequency": "TDS", "duration": "3 days"}],
        ),
        (
            "pcos",
            5,
            ["irregular cycles"],
            ["PCOS"],
            [{"name": "Metformin", "dosage": "500 mg", "frequency": "BD", "duration": "90 days"}],
        ),
        (
            "anc",
            4,
            ["fatigue"],
            ["Antenatal care", "Mild anemia"],
            [
                {
                    "name": "Iron + Folic acid",
                    "dosage": "1 tablet",
                    "frequency": "OD",
                    "duration": "30 days",
                }
            ],
        ),
        (
            "pp",
            3,
            ["postpartum check"],
            ["Postpartum visit"],
            [
                {
                    "name": "Iron + Folic acid",
                    "dosage": "1 tablet",
                    "frequency": "OD",
                    "duration": "30 days",
                }
            ],
        ),
        (
            "pmb",
            2,
            ["spotting"],
            ["Postmenopausal bleeding — evaluation"],
            [],
        ),
        (
            "inf",
            1,
            ["trying to conceive"],
            ["Infertility counselling"],
            [
                {
                    "name": "Folic acid",
                    "dosage": "5 mg",
                    "frequency": "OD",
                    "duration": "90 days",
                }
            ],
        ),
    ]
    for key, days_ago, symptoms, diagnoses, meds in analytics_rx:
        _, blind, _ = blinds[key]
        when = now - timedelta(days=days_ago, hours=3)
        iso, disp = _stamp(when)
        db.add(
            _rec(
                blind,
                {
                    "type": "prescription",
                    "doctor_name": DOCTOR["display_name"],
                    "clinic_name": get_settings().clinic_name,
                    "issued_at": iso,
                    "issued_at_display": disp,
                    "transcript_count": 1,
                    "symptoms": symptoms,
                    "clinical_observations": ["demo analytics volume"],
                    "diagnoses": diagnoses,
                    "medications": meds,
                    "signed_by": DOCTOR,
                },
                when,
            )
        )
        # Spread vitals for analytics "today/week" charts
        when_v = when - timedelta(hours=1)
        iso_v, disp_v = _stamp(when_v)
        db.add(
            _rec(
                blind,
                {
                    "type": "vitals",
                    "vitals": {
                        "blood_pressure": "120/78",
                        "systolic": "120",
                        "diastolic": "78",
                        "pulse": "80",
                        "weight": "58",
                    },
                    "diagnostic_notes": "analytics seed vitals",
                    "clinical_observations": [],
                    "diagnoses": [],
                    "medications": [],
                    "symptoms": [],
                    "entered_by": STAFF,
                    "entered_at": iso_v,
                    "entered_at_display": disp_v,
                },
                when_v,
            )
        )

    # ========== Appointments (Waiting List = today's booked) ==========
    def add_appt(
        *,
        key: str,
        display: str,
        when: datetime,
        reason: str,
        status: str = "booked",
        notes: str = DEMO_TAG,
        created_by: str = DOCTOR["display_name"],
        duration: str = "15",
        sms: str = "skipped:console",
        modality: str = "in_person",
    ) -> None:
        raw, blind, phone = blinds[key]
        digits = "".join(c for c in phone if c.isdigit())
        db.add(
            Appointment(
                id=uuid.uuid4(),
                clinic_id=CLINIC,
                blind_patient_id=blind,
                display_name=display,
                phone_encrypted=encrypt_phone(digits),
                phone_last4=digits[-4:],
                scheduled_at=when.astimezone(timezone.utc),
                duration_minutes=duration,
                reason=reason,
                modality=modality,
                status=status,
                sms_status=sms,
                created_by=created_by,
                notes=notes,
            )
        )

    # Today — waiting list showcase
    add_appt(
        key="anc",
        display="Ananya Reddy",
        when=now.replace(hour=10, minute=0, second=0, microsecond=0),
        reason="ANC 28w follow-up",
        created_by=STAFF["display_name"],
    )
    add_appt(
        key="early",
        display="Priya Nair",
        when=now.replace(hour=10, minute=20, second=0, microsecond=0),
        reason="ANC booking / NT counselling",
        created_by=STAFF["display_name"],
    )
    add_appt(
        key="pih",
        display="Rekha Sharma",
        when=now.replace(hour=10, minute=45, second=0, microsecond=0),
        reason="PIH review — urgent",
        created_by=DOCTOR["display_name"],
    )
    add_appt(
        key="dys",
        display="Sunita Devi",
        when=now.replace(hour=11, minute=0, second=0, microsecond=0),
        reason="Dysmenorrhea",
        created_by=STAFF2["display_name"],
    )
    add_appt(
        key="pmb",
        display="Lakshmi Iyer",
        when=now.replace(hour=11, minute=30, second=0, microsecond=0),
        reason="PMB evaluation",
        created_by=STAFF["display_name"],
    )
    add_appt(
        key="pcos",
        display="Kavita Mehta",
        when=now.replace(hour=12, minute=0, second=0, microsecond=0),
        reason="PCOS review + USG",
        created_by=DOCTOR["display_name"],
    )
    add_appt(
        key="voice",
        display="Aisha Begum",
        when=now.replace(hour=12, minute=30, second=0, microsecond=0),
        reason="Voice-to-Rx live demo slot",
        created_by=STAFF["display_name"],
    )
    add_appt(
        key="sec",
        display="Neha Kapoor",
        when=now.replace(hour=13, minute=0, second=0, microsecond=0),
        reason="Security / MRN identity demo",
        created_by=DOCTOR["display_name"],
    )
    # Future follow-ups (case brief next appointment)
    add_appt(
        key="anc",
        display="Ananya Reddy",
        when=(now + timedelta(days=7)).replace(
            hour=10, minute=30, second=0, microsecond=0
        ),
        reason="ANC BP / Hb review",
        notes=f"{DEMO_TAG};source:follow_up",
        created_by=DOCTOR["display_name"],
    )
    next_pp = (now + timedelta(days=14)).replace(
        hour=11, minute=0, second=0, microsecond=0
    )
    add_appt(
        key="pp",
        display="Meera Joshi",
        when=next_pp,
        reason="Next appointment",
        notes=f"{DEMO_TAG};source:patient_tab",
        created_by=DOCTOR["display_name"],
    )
    add_appt(
        key="early",
        display="Priya Nair",
        when=(now + timedelta(days=10)).replace(
            hour=9, minute=30, second=0, microsecond=0
        ),
        reason="NT scan slot",
        created_by=STAFF2["display_name"],
    )
    # Tomorrow — day-before reminder demo
    tomorrow = (now + timedelta(days=1)).replace(
        hour=10, minute=30, second=0, microsecond=0
    )
    add_appt(
        key="inf",
        display="Fatima Khan",
        when=tomorrow,
        reason="Infertility counselling (video)",
        created_by=DOCTOR["display_name"],
        sms="",
        modality="video",
    )

    # ========== Billing ledger (Patient Info pitch) ==========
    def add_bill(
        key: str,
        kind: str,
        amount: float,
        note: str,
        days_ago: float,
        actor: dict[str, str],
    ) -> None:
        _, blind, _ = blinds[key]
        when_b = now - timedelta(days=days_ago)
        db.add(
            _billing(
                blind,
                kind=kind,
                amount_inr=amount,
                note=note,
                when=when_b,
                actor=actor,
            )
        )

    # Ananya — prior ANC package partly paid; today's consult still due
    add_bill("anc", "charge", 2500, "ANC package (28w visit)", 14, RECEPTION)
    add_bill("anc", "payment", 1500, "UPI part payment", 13, RECEPTION)
    add_bill("anc", "charge", 800, "Today's consult + NST", 0.05, RECEPTION)
    # Rekha — urgent PIH review unpaid
    add_bill("pih", "charge", 1200, "Urgent PIH review", 0.1, RECEPTION)
    add_bill("pih", "charge", 450, "Lab: CBC + urine protein", 0.08, STAFF)
    # Kavita — labs paid in full
    add_bill("pcos", "charge", 1800, "Hormonal panel + pelvic USG", 3, RECEPTION)
    add_bill("pcos", "payment", 1800, "Cash settled", 3, RECEPTION)
    # Sunita — consult fee partially paid
    add_bill("dys", "charge", 600, "OPD consult", 0.02, RECEPTION)
    add_bill("dys", "payment", 200, "Cash advance", 0.01, RECEPTION)
    # Sonal — dedicated billing showcase (amount due ≈ ₹2,150)
    add_bill("bill", "charge", 1500, "New patient registration + consult", 2, RECEPTION)
    add_bill("bill", "charge", 900, "USG pelvis", 1, RECEPTION)
    add_bill("bill", "payment", 500, "Partial UPI", 1, RECEPTION)
    add_bill("bill", "charge", 250, "Today's medicine dispensing fee", 0.03, RECEPTION)
    # Lakshmi — small walk-in charge
    add_bill("pmb", "charge", 700, "PMB evaluation consult", 0.04, RECEPTION)

    # ========== Video consult timeline (Ananya) ==========
    _, blind_anc_v, _ = blinds["anc"]
    when_vid = now - timedelta(days=5, hours=2)
    iso_vid, disp_vid = _stamp(when_vid)
    room = f"demo-{CLINIC}-anc-{when_vid.strftime('%Y%m%d')}"
    db.add(
        _rec(
            blind_anc_v,
            {
                "type": "video_consult",
                "room_name": room,
                "join_url": f"https://meet.jit.si/{room}",
                "provider": "jitsi",
                "appointment_id": None,
                "started_at": iso_vid,
                "started_by": DOCTOR,
                "clinical_observations": [
                    f"Video consult started ({room})",
                    f"Demo timeline entry @ {disp_vid}",
                ],
                "diagnoses": [],
                "medications": [],
                "symptoms": [],
            },
            when_vid,
        )
    )
    # Future video slot today for Fatima pitch (already booked tomorrow as video)
    add_appt(
        key="anc",
        display="Ananya Reddy",
        when=(now + timedelta(days=3)).replace(
            hour=16, minute=0, second=0, microsecond=0
        ),
        reason="Tele-ANC follow-up",
        created_by=DOCTOR["display_name"],
        modality="video",
        notes=f"{DEMO_TAG};source:video_follow_up",
    )

    # ========== All-patients roster (Patient Info directory) ==========
    name_by_key = {p["key"]: p["name"] for p in patients}
    for p in patients:
        raw, blind, phone = blinds[p["key"]]
        upsert_clinic_patient(
            db,
            clinic_id=CLINIC,
            blind_patient_id=blind,
            display_name=p["name"],
            phone_digits=phone,
            clinic_mrn=p.get("mrn") or "",
            bump_visit=False,
            seen_at=(now - timedelta(days=1)).astimezone(timezone.utc),
        )

    # Queue walk-ins (API exists; Waiting List UI uses appointments)
    for key, note, hour in [
        ("anc", "ANC — already booked also", 9),
        ("pih", "PIH walk-in priority", 9),
        ("pmb", "Walk-in PMB", 9),
        ("dys", "Pain — priority", 9),
        ("bill", "Billing / pay QR demo", 9),
    ]:
        _, blind, _ = blinds[key]
        db.add(
            QueueEntry(
                id=uuid.uuid4(),
                clinic_id=CLINIC,
                queue_date=today.isoformat(),
                display_name=name_by_key[key],
                blind_patient_id=blind,
                note=f"{note} [{DEMO_TAG}]",
                status="waiting",
                created_by=STAFF["display_name"],
                created_at=now.replace(hour=hour, minute=0).astimezone(timezone.utc),
            )
        )

    db.commit()
    return cheat


def main() -> int:
    global CLINIC
    parser = argparse.ArgumentParser(description="Seed gynae clinic demo data")
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Remove previous demo:seed rows before inserting",
    )
    parser.add_argument(
        "--clinic",
        default="default",
        help="clinic_id to stamp on seeded rows (default: default). "
        "Use a second id (e.g. east) to verify multi-clinic isolation.",
    )
    args = parser.parse_args()
    CLINIC = (args.clinic or "default").strip() or "default"

    # Refresh settings from .env
    get_settings.cache_clear()

    Base.metadata.create_all(bind=engine)
    # Import models so tables exist
    import app.api.v1.endpoints.queue  # noqa: F401
    import app.models.appointment  # noqa: F401
    import app.models.clinic_patient  # noqa: F401
    import app.models.record  # noqa: F401

    Base.metadata.create_all(bind=engine)
    from app.services.schema_migrate import ensure_schema_columns

    ensure_schema_columns(engine)

    db = SessionLocal()
    try:
        if args.wipe:
            n = wipe_demo(db, clinic_id=CLINIC)
            print(f"Wiped {n} previous demo row(s) for clinic_id={CLINIC}.")
        cheat = seed(db)
    finally:
        db.close()

    print()
    print("=" * 72)
    print("Demo data seeded - full clinic showcase")
    print("=" * 72)
    print(f"Clinic: {CLINIC}")
    print(f"Doctor letterhead: {get_settings().doctor_name}")
    print()
    if CLINIC == "default":
        print("Sign in as (default clinic users from CLINIC_USERS):")
        print("  Dr. Nirmala Tiwari  (doctor)         PIN 1234")
        print("  Staff               (staff)          PIN 5678")
        print("  Priyanka            (staff)          PIN 5678")
        print("  Front Desk          (receptionist)   PIN 1111")
        print("  Lab Desk            (lab)            PIN 9999")
    else:
        print(f"Sign in as a user whose CLINIC_USERS row has clinic_id={CLINIC}")
        print("  (cloud example: east|dr_east|Dr East|doctor|…)")
        print("  Ensure CLINICS includes this id; restart API after .env edits.")
    print()
    print("Suggested tour (lock patient on Patient Info / All patients, then Visit / Records):")
    print("-" * 72)
    for row in cheat:
        print(f"  {row['name']}")
        print(f"    Mobile: {row['phone']}   MRN: {row['mrn']}")
        print(f"    Showcase: {row['use']}")
        print()
    print("Quick demos:")
    print("  * Pitch script     -> docs\\DEMO_CLIENT.md")
    print("  * Sonal Desai      -> Patient Info billing + Show pay QR (receptionist 1111)")
    print("  * Ananya Reddy     -> Visit case brief / alerts / video timeline; billing due")
    print("  * Aisha / Sunita   -> Visit: Load demo transcript -> Prepare -> Sign")
    print("  * Priya Nair       -> Case brief scan cadence shows NT scan DUE")
    print("  * Rekha Sharma     -> Critical BP/Hb; Rx hints; unpaid charges")
    print("  * Neha Kapoor      -> Records audit + MRN identity (security)")
    print("  * More tab         -> Clinic analytics (today / week / top meds)")
    print("  * Patient Info     -> Waiting List Open, All patients, Billing")
    print("  * Fatima Khan      -> tomorrow VIDEO slot - remind_day_before.cmd")
    print("  * Meera Joshi      -> next appointment / Google Calendar")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
