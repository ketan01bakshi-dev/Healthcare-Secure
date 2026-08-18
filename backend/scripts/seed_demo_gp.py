"""
Seed general physician clinic demo data for showcasing Aarogya One Connect.

Usage (from backend folder, with venv active):
  python scripts/seed_demo_gp.py
  python scripts/seed_demo_gp.py --wipe

Or from repo root:
  scripts\\seed_demo_gp.cmd
  scripts\\seed_demo_gp.cmd --wipe

Then unlock City General Clinic as Dr Rajesh Kumar and lock a demo patient.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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
CLINIC = "gp"
DEMO_TAG = "demo:seed-gp"
DOCTOR = {
    "user_id": "dr_gp",
    "display_name": "Dr Rajesh Kumar",
    "role": "doctor",
}
STAFF = {
    "user_id": "staff_gp",
    "display_name": "Priya Sharma",
    "role": "staff",
}
RECEPTION = {
    "user_id": "reception_gp",
    "display_name": "Front Desk",
    "role": "receptionist",
}
LAB = {
    "user_id": "lab_gp",
    "display_name": "Lab Desk",
    "role": "lab",
}


def _pdf_with_text(*lines: str) -> bytes:
    text = "  ".join(lines)[:400]
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


def _now_ist() -> datetime:
    return datetime.now(IST)


def _stamp(when: datetime) -> tuple[str, str]:
    iso = when.isoformat()
    display = when.strftime("%d %b %Y, %I:%M %p IST")
    return iso, display


def _rec(blind: str, data: dict[str, Any], when: datetime) -> ClinicalRecord:
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


def _patient(name: str, phone: str, mrn: str | None = None) -> tuple[str, str, str]:
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
    removed = 0
    appts = db.scalars(
        select(Appointment).where(Appointment.notes.contains(DEMO_TAG))
    ).all()
    for a in appts:
        if clinic_id is not None and getattr(a, "clinic_id", None) != clinic_id:
            continue
        db.delete(a)
        removed += 1
    qrows = db.scalars(
        select(QueueEntry).where(QueueEntry.note.contains(DEMO_TAG))
    ).all()
    for q in qrows:
        if clinic_id is not None and getattr(q, "clinic_id", None) != clinic_id:
            continue
        db.delete(q)
        removed += 1
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

    patients = [
        {
            "key": "dm",
            "name": "Ramesh Kumar",
            "phone": "9876512001",
            "mrn": "GP-2001",
            "label": "[STAR] Type 2 DM follow-up — HbA1c trend, metformin Rx, vitals charts",
        },
        {
            "key": "htn",
            "name": "Sita Patel",
            "phone": "9876512002",
            "mrn": "GP-2002",
            "label": "Hypertension — elevated BP alerts, amlodipine review",
        },
        {
            "key": "urti",
            "name": "Arjun Mehta",
            "phone": "9876512003",
            "mrn": "GP-2003",
            "label": "[VOICE] URTI — hero voice-to-Rx demo (or Load demo script)",
        },
        {
            "key": "ger",
            "name": "Kamala Devi",
            "phone": "9876512004",
            "mrn": "GP-2004",
            "label": "Geriatric review — polypharmacy, chronic conditions",
        },
        {
            "key": "thy",
            "name": "Vikram Singh",
            "phone": "9876512005",
            "mrn": "GP-2005",
            "label": "Thyroid disorder — TSH trend, levothyroxine",
        },
        {
            "key": "sec",
            "name": "Neha Shah",
            "phone": "9876512006",
            "mrn": "GP-2006",
            "label": "[SECURITY] MRN identity + audit trail demo",
        },
        {
            "key": "voice",
            "name": "Rohit Jain",
            "phone": "9876512007",
            "mrn": None,
            "label": "[VOICE] Clean slate for live speech-to-Rx",
        },
        {
            "key": "bill",
            "name": "Anjali Rao",
            "phone": "9876512008",
            "mrn": "GP-2008",
            "label": "[BILLING] Amount due ~INR 1,850 — Show pay QR (receptionist 1111)",
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

    # --- Ramesh Kumar — Type 2 DM ---
    _, blind_dm, _ = blinds["dm"]
    for i, (fbs, hba1c, wt, note) in enumerate(
        [
            ("142", "8.2", "78.0", "DM review — suboptimal control"),
            ("128", "7.6", "77.2", "Improved fasting glucose"),
            ("118", "7.1", "76.5", "Better control on metformin"),
            ("112", "6.9", "76.0", "Target range approaching"),
        ]
    ):
        when = now - timedelta(days=90 - i * 30, hours=2)
        iso, disp = _stamp(when)
        db.add(
            _rec(
                blind_dm,
                {
                    "type": "vitals",
                    "vitals": {
                        "blood_pressure": "130/82",
                        "systolic": "130",
                        "diastolic": "82",
                        "pulse": "78",
                        "temperature": "98.4",
                        "spo2": "98",
                        "weight": wt,
                        "height": "170",
                        "respiratory_rate": "16",
                    },
                    "diagnostic_notes": note,
                    "age_years": 52,
                    "clinical_observations": [
                        f"FBS={fbs} mg/dL",
                        f"HbA1c={hba1c}%",
                        f"weight={wt}",
                        f"notes={note}",
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
        when_lab = when + timedelta(hours=1)
        iso_l, disp_l = _stamp(when_lab)
        db.add(
            _rec(
                blind_dm,
                {
                    "type": "lab_result",
                    "test_name": "HbA1c",
                    "value": hba1c,
                    "unit": "%",
                    "reference_range": "<7.0 (DM target)",
                    "collected_at": when.date().isoformat(),
                    "clinical_observations": [f"HbA1c={hba1c}%"],
                    "diagnoses": [],
                    "medications": [],
                    "symptoms": [],
                    "entered_by": LAB,
                    "entered_at": iso_l,
                    "entered_at_display": disp_l,
                },
                when_lab,
            )
        )

    when = now - timedelta(days=14)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_dm,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": "City General Clinic",
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 0,
                "symptoms": ["fatigue", "polyuria"],
                "clinical_observations": ["FBS 112", "HbA1c 6.9%"],
                "diagnoses": ["Type 2 diabetes mellitus — follow-up"],
                "medications": [
                    {
                        "name": "Metformin",
                        "dosage": "500 mg",
                        "frequency": "BD after food",
                        "duration": "90 days",
                    },
                    {
                        "name": "Atorvastatin",
                        "dosage": "10 mg",
                        "frequency": "OD at night",
                        "duration": "90 days",
                    },
                ],
                "signed_by": DOCTOR,
            },
            when,
        )
    )

    # --- Sita Patel — Hypertension / BP alerts ---
    _, blind_htn, _ = blinds["htn"]
    for i, (sys, dia, note) in enumerate(
        [
            (128, 82, "HTN follow-up — controlled"),
            (134, 88, "Mild elevation"),
            (148, 96, "Stage 1 hypertension"),
            (162, 104, "Uncontrolled — review meds"),
        ]
    ):
        when = now - timedelta(days=21 - i * 7, hours=3)
        iso, disp = _stamp(when)
        db.add(
            _rec(
                blind_htn,
                {
                    "type": "vitals",
                    "vitals": {
                        "blood_pressure": f"{sys}/{dia}",
                        "systolic": str(sys),
                        "diastolic": str(dia),
                        "pulse": str(82 + i),
                        "temperature": "98.2",
                        "spo2": "99",
                        "weight": "62",
                        "height": "158",
                    },
                    "diagnostic_notes": note,
                    "age_years": 58,
                    "clinical_observations": [f"BP={sys}/{dia}", note],
                    "diagnoses": [],
                    "medications": [],
                    "symptoms": ["headache"] if i >= 2 else [],
                    "entered_by": STAFF,
                    "entered_at": iso,
                    "entered_at_display": disp,
                },
                when,
            )
        )
    when = now - timedelta(days=7)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_htn,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": "City General Clinic",
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 0,
                "symptoms": ["headache", "dizziness"],
                "clinical_observations": ["BP 162/104 on repeat"],
                "diagnoses": ["Essential hypertension — uncontrolled"],
                "medications": [
                    {
                        "name": "Amlodipine",
                        "dosage": "5 mg",
                        "frequency": "OD",
                        "duration": "30 days",
                    },
                    {
                        "name": "Telmisartan",
                        "dosage": "40 mg",
                        "frequency": "OD",
                        "duration": "30 days",
                    },
                ],
                "signed_by": DOCTOR,
            },
            when,
        )
    )

    # --- Arjun Mehta — URTI (signed Rx for timeline) ---
    _, blind_urti, _ = blinds["urti"]
    when = now - timedelta(hours=8)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_urti,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": "City General Clinic",
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 1,
                "symptoms": ["cough", "fever", "sore throat"],
                "clinical_observations": ["Throat congested", "Chest clear"],
                "diagnoses": ["Acute upper respiratory tract infection"],
                "medications": [
                    {
                        "name": "Paracetamol",
                        "dosage": "500 mg",
                        "frequency": "TDS after food",
                        "duration": "3 days",
                    },
                    {
                        "name": "Azithromycin",
                        "dosage": "500 mg",
                        "frequency": "OD",
                        "duration": "3 days",
                    },
                ],
                "signed_by": DOCTOR,
            },
            when,
        )
    )

    # --- Kamala Devi — Geriatric ---
    _, blind_ger, _ = blinds["ger"]
    when = now - timedelta(days=30)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_ger,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": "City General Clinic",
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 0,
                "symptoms": ["joint pain", "fatigue"],
                "clinical_observations": ["Multiple chronic meds", "Stable vitals"],
                "diagnoses": [
                    "Osteoarthritis",
                    "Hypertension",
                    "Type 2 diabetes mellitus",
                ],
                "medications": [
                    {
                        "name": "Amlodipine",
                        "dosage": "5 mg",
                        "frequency": "OD",
                        "duration": "30 days",
                    },
                    {
                        "name": "Metformin",
                        "dosage": "500 mg",
                        "frequency": "BD",
                        "duration": "30 days",
                    },
                    {
                        "name": "Paracetamol",
                        "dosage": "650 mg",
                        "frequency": "SOS",
                        "duration": "15 days",
                    },
                ],
                "signed_by": DOCTOR,
            },
            when,
        )
    )

    # --- Vikram Singh — Thyroid ---
    _, blind_thy, _ = blinds["thy"]
    for tsh, when_days in [("8.4", 60), ("5.2", 30), ("3.1", 7)]:
        when = now - timedelta(days=when_days)
        iso, disp = _stamp(when)
        db.add(
            _rec(
                blind_thy,
                {
                    "type": "lab_result",
                    "test_name": "TSH",
                    "value": tsh,
                    "unit": "mIU/L",
                    "reference_range": "0.4–4.0",
                    "collected_at": when.date().isoformat(),
                    "clinical_observations": [f"TSH={tsh} mIU/L"],
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
    when = now - timedelta(days=14)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_thy,
            {
                "type": "prescription",
                "doctor_name": DOCTOR["display_name"],
                "clinic_name": "City General Clinic",
                "issued_at": iso,
                "issued_at_display": disp,
                "transcript_count": 0,
                "symptoms": ["fatigue", "weight gain"],
                "clinical_observations": ["TSH improving on thyroxine"],
                "diagnoses": ["Hypothyroidism"],
                "medications": [
                    {
                        "name": "Levothyroxine",
                        "dosage": "50 mcg",
                        "frequency": "OD empty stomach",
                        "duration": "90 days",
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
            "document_kind": "diagnostic_report",
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

    _add_doc(
        blind_thy,
        title="Thyroid ultrasound",
        filename="thyroid_us.pdf",
        when=now - timedelta(days=45),
        pdf=_pdf_with_text("Thyroid ultrasound", "Normal size", "No nodules"),
        findings={
            "report_type": "thyroid_ultrasound",
            "summary": "Thyroid normal in size. No dominant nodule.",
            "other_findings": ["Isthmus normal"],
        },
    )

    # --- Neha Shah — MRN security ---
    _, blind_sec, _ = blinds["sec"]
    when = now - timedelta(days=3)
    iso, disp = _stamp(when)
    db.add(
        _rec(
            blind_sec,
            {
                "type": "audit",
                "event": "mrn_identity",
                "clinical_observations": [
                    "Patient registered with MRN GP-2006",
                    "Phone updated by staff — history preserved under blind ID",
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

    # --- Analytics volume ---
    analytics_rx = [
        (
            "urti",
            5,
            ["cough", "fever"],
            ["Acute URTI"],
            [{"name": "Paracetamol", "dosage": "500 mg", "frequency": "TDS", "duration": "3 days"}],
        ),
        (
            "htn",
            4,
            ["headache"],
            ["Essential hypertension"],
            [{"name": "Amlodipine", "dosage": "5 mg", "frequency": "OD", "duration": "30 days"}],
        ),
        (
            "dm",
            3,
            ["fatigue"],
            ["Type 2 diabetes mellitus"],
            [{"name": "Metformin", "dosage": "500 mg", "frequency": "BD", "duration": "90 days"}],
        ),
        (
            "thy",
            2,
            ["fatigue"],
            ["Hypothyroidism"],
            [{"name": "Levothyroxine", "dosage": "50 mcg", "frequency": "OD", "duration": "90 days"}],
        ),
        (
            "ger",
            1,
            ["joint pain"],
            ["Osteoarthritis"],
            [],
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
                    "clinic_name": "City General Clinic",
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

    # --- Appointments ---
    def add_appt(
        *,
        key: str,
        display: str,
        when: datetime,
        reason: str,
        status: str = "booked",
        notes: str = DEMO_TAG,
        created_by: str = DOCTOR["display_name"],
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
                duration_minutes="15",
                reason=reason,
                modality=modality,
                status=status,
                sms_status="skipped:console",
                created_by=created_by,
                notes=notes,
            )
        )

    add_appt(
        key="dm",
        display="Ramesh Kumar",
        when=now.replace(hour=10, minute=0, second=0, microsecond=0),
        reason="DM follow-up — HbA1c review",
        created_by=STAFF["display_name"],
    )
    add_appt(
        key="htn",
        display="Sita Patel",
        when=now.replace(hour=10, minute=30, second=0, microsecond=0),
        reason="Hypertension — BP review",
        created_by=STAFF["display_name"],
    )
    add_appt(
        key="urti",
        display="Arjun Mehta",
        when=now.replace(hour=11, minute=0, second=0, microsecond=0),
        reason="Cough and fever",
        created_by=STAFF["display_name"],
    )
    add_appt(
        key="ger",
        display="Kamala Devi",
        when=now.replace(hour=11, minute=30, second=0, microsecond=0),
        reason="Geriatric review",
        created_by=DOCTOR["display_name"],
    )
    add_appt(
        key="bill",
        display="Anjali Rao",
        when=now.replace(hour=12, minute=0, second=0, microsecond=0),
        reason="Billing / pay QR demo",
        created_by=RECEPTION["display_name"],
    )
    add_appt(
        key="voice",
        display="Rohit Jain",
        when=now.replace(hour=12, minute=30, second=0, microsecond=0),
        reason="Voice-to-Rx live demo",
        created_by=STAFF["display_name"],
    )
    add_appt(
        key="thy",
        display="Vikram Singh",
        when=(now + timedelta(days=7)).replace(
            hour=10, minute=0, second=0, microsecond=0
        ),
        reason="Thyroid follow-up",
        created_by=DOCTOR["display_name"],
        notes=f"{DEMO_TAG};source:follow_up",
    )

    # --- Billing ---
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

    add_bill("dm", "charge", 800, "DM review consult", 0.05, RECEPTION)
    add_bill("htn", "charge", 600, "HTN review", 0.08, RECEPTION)
    add_bill("htn", "charge", 350, "ECG", 0.07, STAFF)
    add_bill("bill", "charge", 500, "New patient registration", 2, RECEPTION)
    add_bill("bill", "charge", 900, "Chest X-ray", 1, RECEPTION)
    add_bill("bill", "charge", 600, "Lab panel", 1, RECEPTION)
    add_bill("bill", "payment", 550, "Partial UPI", 0.5, RECEPTION)
    add_bill("bill", "charge", 400, "Today's consult", 0.03, RECEPTION)

    # --- Roster + queue ---
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

    for key, note, hour in [
        ("dm", "DM follow-up", 9),
        ("htn", "HTN priority", 9),
        ("urti", "URTI walk-in", 9),
        ("bill", "Billing demo", 9),
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
    parser = argparse.ArgumentParser(description="Seed GP clinic demo data")
    parser.add_argument("--wipe", action="store_true")
    parser.add_argument(
        "--clinic",
        default="gp",
        help="clinic_id to stamp (default: gp)",
    )
    args = parser.parse_args()
    CLINIC = (args.clinic or "gp").strip() or "gp"

    get_settings.cache_clear()
    Base.metadata.create_all(bind=engine)
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
            print(f"Wiped {n} previous GP demo row(s) for clinic_id={CLINIC}.")
        cheat = seed(db)
    finally:
        db.close()

    print()
    print("=" * 72)
    print("GP demo data seeded — City General Clinic")
    print("=" * 72)
    print(f"Clinic: {CLINIC}")
    print()
    print("Sign in as (City General Clinic):")
    print("  Dr Rajesh Kumar     (doctor)         PIN 2468")
    print("  Priya Sharma        (staff)          PIN 1357")
    print("  Front Desk          (receptionist)   PIN 1111")
    print("  Lab Desk            (lab)            PIN 9999")
    print()
    print("Clinic unlock: City General Clinic / clinicpass")
    print()
    for row in cheat:
        print(f"  {row['name']}")
        print(f"    Mobile: {row['phone']}   MRN: {row['mrn']}")
        print(f"    Showcase: {row['use']}")
        print()
    print("Pitch script: docs\\DEMO_GP.md")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
