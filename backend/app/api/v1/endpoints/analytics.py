"""Clinic analytics — de-identified counts and vitals trends (no raw phone/name columns)."""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.record import ClinicalRecord
from app.services.doctor_auth import ClinicalSession, DoctorSession
from app.services.security import tokenize_patient_identifier

router = APIRouter(prefix="/analytics")


def _as_dict(data: Any) -> dict[str, Any]:
    return dict(data) if isinstance(data, dict) else {}


def _encounter_type(data: dict[str, Any]) -> str:
    t = data.get("type")
    if isinstance(t, str) and t.strip():
        return t.strip()
    if data.get("document_kind"):
        return "document"
    if data.get("medications") or data.get("prescription"):
        return "prescription"
    return "visit"


def _clinic_tz():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Asia/Kolkata")
    except Exception:  # noqa: BLE001
        return timezone.utc


def _day_start_utc(d: date) -> datetime:
    """Start of calendar day in Asia/Kolkata, as UTC."""
    tz = _clinic_tz()
    local_midnight = datetime(d.year, d.month, d.day, tzinfo=tz)
    return local_midnight.astimezone(timezone.utc)


def _clinic_today() -> date:
    return datetime.now(_clinic_tz()).date()


class TodaySummary(BaseModel):
    date: str
    encounters_today: int
    unique_patients_today: int
    prescriptions_signed_today: int
    vitals_today: int
    lab_results_today: int
    queue_waiting: int
    by_type: dict[str, int]


class WeekSummary(BaseModel):
    start_date: str
    end_date: str
    encounters: int
    unique_patients: int
    prescriptions_signed: int
    by_day: dict[str, int]


class FrequencyItem(BaseModel):
    name: str
    count: int


class FrequencyOut(BaseModel):
    days: int
    medications: list[FrequencyItem]
    diagnoses: list[FrequencyItem]


class PeriodBilling(BaseModel):
    total_inr: float
    billed_patients: int
    per_patient_inr: float
    bill_count: int


class PeriodOverview(BaseModel):
    key: str
    label: str
    start_date: str
    end_date: str
    patients_visited: int
    encounters: int
    medications: list[FrequencyItem]
    diagnoses: list[FrequencyItem]
    billing: PeriodBilling


class ClinicOverviewOut(BaseModel):
    periods: list[PeriodOverview]


class SttMemoryMetricsOut(BaseModel):
    feedback_count: int
    rx_with_med_name_edits: int
    med_name_edit_rate: float
    top_correction_pairs: list[dict[str, Any]]
    top_aliases: list[dict[str, Any]]
    glossary_term_count: int


class VitalsPoint(BaseModel):
    at: datetime
    pulse: str | None = None
    systolic: str | None = None
    diastolic: str | None = None
    spo2: str | None = None
    temperature_f: str | None = None
    weight: str | None = None
    hemoglobin: str | None = None
    gestational_weeks: float | None = None
    gestational_label: str | None = None


class VitalsTrendOut(BaseModel):
    blind_patient_id_prefix: str
    points: list[VitalsPoint]
    alerts: list[dict[str, str]] = []
    gestational_age: str | None = None


class VitalsTrendRequest(BaseModel):
    raw_identifier: str = Field(..., min_length=1)


@router.get("/today", response_model=TodaySummary)
def today_summary(
    auth: DoctorSession,
    db: Session = Depends(get_db),
) -> TodaySummary:
    """Clinic-day counts. Lab role: limited to lab_results + documents only."""
    today = _clinic_today()
    start = _day_start_utc(today)
    rows = db.scalars(
        select(ClinicalRecord).where(
            ClinicalRecord.created_at >= start,
            ClinicalRecord.clinic_id == auth.clinic_id,
        )
    ).all()

    by_type: Counter[str] = Counter()
    patients: set[str] = set()
    rx = 0
    vitals = 0
    labs = 0
    for r in rows:
        data = _as_dict(r.encounter_data)
        et = _encounter_type(data)
        if auth.role == "lab" and et not in ("lab_result", "document"):
            continue
        by_type[et] += 1
        patients.add(r.blind_patient_id)
        if et in ("prescription", "visit") and (
            data.get("signed") or data.get("signed_by") or data.get("medications")
        ):
            if et == "prescription" or data.get("signed_by"):
                rx += 1
        if et == "vitals":
            vitals += 1
        if et == "lab_result":
            labs += 1

    queue_waiting = 0
    if auth.role != "lab":
        try:
            from app.models.appointment import Appointment

            # Count today's booked appointments (Waiting List source, IST)
            start = _day_start_utc(_clinic_today())
            end = start + timedelta(days=1)
            queue_waiting = len(
                db.scalars(
                    select(Appointment).where(
                        Appointment.clinic_id == auth.clinic_id,
                        Appointment.status == "booked",
                        Appointment.scheduled_at >= start,
                        Appointment.scheduled_at < end,
                    )
                ).all()
            )
        except Exception:  # noqa: BLE001
            queue_waiting = 0

    return TodaySummary(
        date=today.isoformat(),
        encounters_today=sum(by_type.values()),
        unique_patients_today=len(patients),
        prescriptions_signed_today=rx,
        vitals_today=vitals,
        lab_results_today=labs,
        queue_waiting=queue_waiting,
        by_type=dict(by_type),
    )


@router.get("/week", response_model=WeekSummary)
def week_summary(
    auth: DoctorSession,
    db: Session = Depends(get_db),
) -> WeekSummary:
    """Last 7 calendar days of encounter counts (de-identified)."""
    if auth.role == "lab":
        raise HTTPException(status_code=403, detail="Lab cannot view week summary")
    end = _clinic_today()
    start = end - timedelta(days=6)
    start_dt = _day_start_utc(start)
    tz = _clinic_tz()
    rows = db.scalars(
        select(ClinicalRecord).where(
            ClinicalRecord.created_at >= start_dt,
            ClinicalRecord.clinic_id == auth.clinic_id,
        )
    ).all()
    by_day: Counter[str] = Counter()
    patients: set[str] = set()
    rx = 0
    for r in rows:
        data = _as_dict(r.encounter_data)
        et = _encounter_type(data)
        day_key = (
            r.created_at.astimezone(tz).date().isoformat()
            if r.created_at
            else end.isoformat()
        )
        by_day[day_key] += 1
        patients.add(r.blind_patient_id)
        if et == "prescription" or data.get("signed_by"):
            rx += 1
    return WeekSummary(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        encounters=sum(by_day.values()),
        unique_patients=len(patients),
        prescriptions_signed=rx,
        by_day=dict(sorted(by_day.items())),
    )


def _billing_amount(data: dict[str, Any]) -> float | None:
    """Charge amounts only — payments must not inflate clinic billing totals."""
    if _encounter_type(data) != "billing":
        return None
    kind = str(data.get("kind") or "charge").strip().lower()
    if kind == "payment":
        return None
    raw = data.get("amount_inr", data.get("amount"))
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        return None
    if amount < 0 or amount > 10_000_000:
        return None
    return round(amount, 2)


def _collect_meds_dx(
    rows: list[ClinicalRecord],
    *,
    limit: int,
) -> tuple[list[FrequencyItem], list[FrequencyItem]]:
    meds: Counter[str] = Counter()
    dx: Counter[str] = Counter()
    for r in rows:
        data = _as_dict(r.encounter_data)
        et = _encounter_type(data)
        if et not in ("prescription", "visit"):
            continue
        for item in data.get("medications") or []:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
            else:
                name = str(item).strip()
            if name:
                meds[name[:80]] += 1
        for item in data.get("diagnoses") or []:
            name = (
                str(item).strip()
                if not isinstance(item, dict)
                else str(item.get("name") or item.get("text") or "").strip()
            )
            if name:
                dx[name[:80]] += 1
    return (
        [FrequencyItem(name=n, count=c) for n, c in meds.most_common(limit)],
        [FrequencyItem(name=n, count=c) for n, c in dx.most_common(limit)],
    )


def _period_stats(
    rows: list[ClinicalRecord],
    *,
    key: str,
    label: str,
    start: date,
    end: date,
    limit: int,
) -> PeriodOverview:
    patients: set[str] = set()
    billed_patients: set[str] = set()
    total = 0.0
    bill_count = 0
    for r in rows:
        patients.add(r.blind_patient_id)
        data = _as_dict(r.encounter_data)
        amount = _billing_amount(data)
        if amount is not None:
            total += amount
            bill_count += 1
            billed_patients.add(r.blind_patient_id)
    per_patient = (
        round(total / len(billed_patients), 2) if billed_patients else 0.0
    )
    meds, diagnoses = _collect_meds_dx(rows, limit=limit)
    return PeriodOverview(
        key=key,
        label=label,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        patients_visited=len(patients),
        encounters=len(rows),
        medications=meds,
        diagnoses=diagnoses,
        billing=PeriodBilling(
            total_inr=round(total, 2),
            billed_patients=len(billed_patients),
            per_patient_inr=per_patient,
            bill_count=bill_count,
        ),
    )


@router.get("/overview", response_model=ClinicOverviewOut)
def clinic_overview(
    auth: DoctorSession,
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
) -> ClinicOverviewOut:
    """Patients visited, top meds/diagnoses, and billing for today / week / year."""
    if auth.role == "lab":
        raise HTTPException(status_code=403, detail="Lab cannot view clinic overview")

    today = _clinic_today()
    week_start = today - timedelta(days=today.weekday())
    year_start = date(today.year, 1, 1)
    year_start_dt = _day_start_utc(year_start)
    end_exclusive = _day_start_utc(today + timedelta(days=1))

    rows = db.scalars(
        select(ClinicalRecord).where(
            ClinicalRecord.created_at >= year_start_dt,
            ClinicalRecord.created_at < end_exclusive,
            ClinicalRecord.clinic_id == auth.clinic_id,
        )
    ).all()

    tz = _clinic_tz()
    today_rows: list[ClinicalRecord] = []
    week_rows: list[ClinicalRecord] = []
    year_rows: list[ClinicalRecord] = []
    for r in rows:
        if not r.created_at:
            continue
        local_day = r.created_at.astimezone(tz).date()
        if local_day > today:
            continue
        year_rows.append(r)
        if local_day >= week_start:
            week_rows.append(r)
        if local_day == today:
            today_rows.append(r)

    return ClinicOverviewOut(
        periods=[
            _period_stats(
                today_rows,
                key="today",
                label="Today",
                start=today,
                end=today,
                limit=limit,
            ),
            _period_stats(
                week_rows,
                key="week",
                label="This week",
                start=week_start,
                end=today,
                limit=limit,
            ),
            _period_stats(
                year_rows,
                key="year",
                label="This year",
                start=year_start,
                end=today,
                limit=limit,
            ),
        ]
    )


@router.get("/stt-memory", response_model=SttMemoryMetricsOut)
def stt_memory_summary(
    auth: DoctorSession,
    db: Session = Depends(get_db),
) -> SttMemoryMetricsOut:
    """Med-name edit rate and top correction pairs from doctor review memory."""
    if auth.role == "lab":
        raise HTTPException(status_code=403, detail="Lab cannot view STT memory")
    from app.services.stt_memory import stt_memory_metrics

    return SttMemoryMetricsOut(**stt_memory_metrics(db, auth.clinic_id))


@router.get("/frequency", response_model=FrequencyOut)
def drug_diagnosis_frequency(
    auth: DoctorSession,
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=15, ge=1, le=50),
) -> FrequencyOut:
    """Top medication names and diagnoses from signed Rx / visits (no PHI)."""
    if auth.role == "lab":
        raise HTTPException(status_code=403, detail="Lab cannot view drug frequency")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.scalars(
        select(ClinicalRecord).where(
            ClinicalRecord.created_at >= since,
            ClinicalRecord.clinic_id == auth.clinic_id,
        )
    ).all()
    medications, diagnoses = _collect_meds_dx(rows, limit=limit)
    return FrequencyOut(
        days=days,
        medications=medications,
        diagnoses=diagnoses,
    )


@router.post("/vitals-trend", response_model=VitalsTrendOut)
def vitals_trend(
    body: VitalsTrendRequest,
    _auth: ClinicalSession,
    db: Session = Depends(get_db),
) -> VitalsTrendOut:
    blind = tokenize_patient_identifier(body.raw_identifier)
    rows = db.scalars(
        select(ClinicalRecord)
        .where(
            ClinicalRecord.blind_patient_id == blind,
            ClinicalRecord.clinic_id == _auth.clinic_id,
        )
        .order_by(ClinicalRecord.created_at.asc())
    ).all()
    points: list[VitalsPoint] = []
    # Latest obstetric profile LMP for gestational dating on charts
    lmp_ymd: str | None = None
    for r in reversed(rows):
        data = _as_dict(r.encounter_data)
        if data.get("type") == "obstetric_profile":
            raw_lmp = str(data.get("lmp") or "").strip()
            if len(raw_lmp) >= 10:
                lmp_ymd = raw_lmp[:10]
                break

    for r in rows:
        data = _as_dict(r.encounter_data)
        et = _encounter_type(data)
        if et == "vitals":
            v = data.get("vitals") if isinstance(data.get("vitals"), dict) else data
            if not isinstance(v, dict):
                continue
            sys = _str_or_none(v.get("systolic") or v.get("bp_systolic"))
            dia = _str_or_none(v.get("diastolic") or v.get("bp_diastolic"))
            if not sys or not dia:
                bp = str(v.get("blood_pressure") or "").strip()
                m = re.match(r"^(\d{2,3})\s*/\s*(\d{2,3})$", bp)
                if m:
                    sys = sys or m.group(1)
                    dia = dia or m.group(2)
            ga_weeks = None
            ga_label = None
            if lmp_ymd and r.created_at:
                ga_weeks, ga_label = _ga_from_lmp(lmp_ymd, r.created_at)
            points.append(
                VitalsPoint(
                    at=r.created_at,
                    pulse=_str_or_none(v.get("pulse") or v.get("pulse_bpm")),
                    systolic=sys,
                    diastolic=dia,
                    spo2=_str_or_none(v.get("spo2") or v.get("oxygen_saturation")),
                    temperature_f=_str_or_none(
                        v.get("temperature_f")
                        or v.get("temperature")
                        or v.get("temp_f")
                    ),
                    weight=_str_or_none(v.get("weight") or v.get("weight_kg")),
                    hemoglobin=_str_or_none(
                        v.get("hemoglobin") or v.get("hb") or v.get("haemoglobin")
                    ),
                    gestational_weeks=ga_weeks,
                    gestational_label=ga_label,
                )
            )
        elif et == "lab_result":
            name = str(data.get("test_name") or "").lower()
            if not any(
                k in name for k in ("hemoglobin", "haemoglobin", "hgb")
            ) and name not in ("hb",):
                continue
            ga_weeks = None
            ga_label = None
            if lmp_ymd and r.created_at:
                ga_weeks, ga_label = _ga_from_lmp(lmp_ymd, r.created_at)
            points.append(
                VitalsPoint(
                    at=r.created_at,
                    hemoglobin=_str_or_none(data.get("value")),
                    gestational_weeks=ga_weeks,
                    gestational_label=ga_label,
                )
            )

    points.sort(key=lambda p: p.at or datetime.min.replace(tzinfo=timezone.utc))
    ga_now = None
    if lmp_ymd:
        _, ga_now = _ga_from_lmp(lmp_ymd, datetime.now(timezone.utc))

    from app.services.anc_alerts import evaluate_vitals_alerts

    high_risk = ""
    for r in reversed(rows):
        data = _as_dict(r.encounter_data)
        if data.get("type") == "obstetric_profile":
            high_risk = str(data.get("high_risk_notes") or "")
            break
    alert_points = [
        {
            "systolic": p.systolic,
            "diastolic": p.diastolic,
            "weight": p.weight,
            "hemoglobin": p.hemoglobin,
            "gestational_weeks": p.gestational_weeks,
        }
        for p in points
    ]
    alerts = [
        a.as_dict()
        for a in evaluate_vitals_alerts(alert_points, high_risk_notes=high_risk)
    ]

    return VitalsTrendOut(
        blind_patient_id_prefix=blind[:8],
        points=points,
        alerts=alerts,
        gestational_age=ga_now,
    )


def _ga_from_lmp(lmp_ymd: str, at: datetime) -> tuple[float | None, str | None]:
    try:
        y, m, d = (int(x) for x in lmp_ymd.split("-")[:3])
        lmp = datetime(y, m, d, tzinfo=timezone.utc)
        when = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
        days = int((when.astimezone(timezone.utc) - lmp).total_seconds() // 86400)
        if days < 0 or days > 314:
            return None, None
        weeks, rem = divmod(days, 7)
        return days / 7.0, f"{weeks}w{rem}d"
    except Exception:  # noqa: BLE001
        return None, None


def _str_or_none(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


@router.get("/export.csv")
def export_csv(
    auth: DoctorSession,
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365),
) -> StreamingResponse:
    """De-identified CSV: date, blind_id prefix, encounter type — no phone/name."""
    if auth.role == "lab":
        raise HTTPException(status_code=403, detail="Lab cannot export clinic CSV")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.scalars(
        select(ClinicalRecord)
        .where(
            ClinicalRecord.created_at >= since,
            ClinicalRecord.clinic_id == auth.clinic_id,
        )
        .order_by(ClinicalRecord.created_at.desc())
    ).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["created_at_utc", "blind_patient_id_prefix", "encounter_type"]
    )
    for r in rows:
        data = _as_dict(r.encounter_data)
        writer.writerow(
            [
                r.created_at.isoformat() if r.created_at else "",
                r.blind_patient_id[:8],
                _encounter_type(data),
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="clinic_export_{days}d.csv"'
        },
    )
