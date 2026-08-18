"""Build a de-identified patient case summary for doctor decision support."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.record import ClinicalRecord
from app.services.anc_alerts import anc_scan_cadence, evaluate_vitals_alerts


def _as_dict(data: Any) -> dict[str, Any]:
    return dict(data) if isinstance(data, dict) else {}


def _etype(data: dict[str, Any]) -> str:
    t = data.get("type")
    if isinstance(t, str) and t.strip():
        return t.strip()
    if data.get("document_kind"):
        return "document"
    return "visit"


def _f(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


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


def _parse_bp(v: dict[str, Any]) -> tuple[str | None, str | None]:
    sys = str(v.get("systolic") or v.get("bp_systolic") or "").strip() or None
    dia = str(v.get("diastolic") or v.get("bp_diastolic") or "").strip() or None
    if not sys or not dia:
        bp = str(v.get("blood_pressure") or "").strip()
        m = re.match(r"^(\d{2,3})\s*/\s*(\d{2,3})$", bp)
        if m:
            sys = sys or m.group(1)
            dia = dia or m.group(2)
    return sys, dia


def _as_string_list(raw: Any) -> list[str]:
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def _entered_by_name(data: dict[str, Any]) -> str | None:
    actor = data.get("entered_by") or data.get("signed_by")
    if isinstance(actor, dict):
        name = str(actor.get("display_name") or "").strip()
        return name or None
    return None


def _trend_direction(delta: float | None, *, epsilon: float = 0.05) -> str:
    if delta is None:
        return "unknown"
    if abs(delta) <= epsilon:
        return "stable"
    return "rising" if delta > 0 else "falling"


def _delta_field(
    vitals_points: list[dict[str, Any]], field: str
) -> dict[str, Any] | None:
    vals = [
        (p.get("at"), _f(p.get(field)))
        for p in vitals_points
        if _f(p.get(field)) is not None
    ]
    if len(vals) < 2:
        if len(vals) == 1:
            return {
                "latest": vals[-1][1],
                "previous": None,
                "delta": None,
                "direction": "unknown",
            }
        return None
    latest = vals[-1][1]
    prev = vals[-2][1]
    delta = (latest - prev) if latest is not None and prev is not None else None
    return {
        "latest": latest,
        "previous": prev,
        "delta": delta,
        "direction": _trend_direction(delta, epsilon=0.15 if field == "weight" else 0.05),
    }


def _delta_bp(points: list[dict[str, Any]]) -> dict[str, Any] | None:
    bps = [p for p in points if p.get("systolic") and p.get("diastolic")]
    if not bps:
        return None
    last = bps[-1]
    out: dict[str, Any] = {
        "latest": f"{last['systolic']}/{last['diastolic']}",
        "previous": None,
        "delta_diastolic": None,
        "direction": "unknown",
    }
    if len(bps) >= 2:
        prev = bps[-2]
        out["previous"] = f"{prev['systolic']}/{prev['diastolic']}"
        ld = _f(last.get("diastolic"))
        pd = _f(prev.get("diastolic"))
        if ld is not None and pd is not None:
            delta = ld - pd
            out["delta_diastolic"] = delta
            out["direction"] = _trend_direction(delta, epsilon=2.0)
    return out


def _findings_blurb(findings: dict[str, Any] | None) -> str | None:
    if not findings:
        return None
    summary = str(findings.get("summary") or "").strip()
    if summary:
        return summary
    parts: list[str] = []
    for key in ("report_type", "afi", "efw", "placenta", "presentation", "ga_by_usg"):
        val = str(findings.get(key) or "").strip()
        if val:
            parts.append(f"{key.replace('_', ' ')}: {val}")
    flags = findings.get("anomaly_flags")
    if isinstance(flags, list) and flags:
        parts.append("flags: " + ", ".join(str(x) for x in flags if str(x).strip()))
    other = findings.get("other_findings")
    if isinstance(other, list) and other:
        parts.append(", ".join(str(x) for x in other if str(x).strip())[:160])
    return "; ".join(parts) if parts else None


def _build_narrative(
    *,
    gestational_age: str | None,
    obstetric: dict[str, Any] | None,
    vitals_latest: dict[str, Any],
    vitals_trends: dict[str, Any],
    alerts: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    doctor_comments: list[dict[str, Any]],
    last_rx: dict[str, Any] | None,
) -> str:
    bits: list[str] = []
    if gestational_age:
        gpla = ""
        if obstetric:
            g = str(obstetric.get("gravida") or "").strip()
            p = str(obstetric.get("para") or "").strip()
            if g or p:
                gpla = f" (G{g or '?'}P{p or '?'})"
        bits.append(f"Gestational age {gestational_age}{gpla}.")
    risk = str((obstetric or {}).get("high_risk_notes") or "").strip()
    if risk:
        bits.append(f"High-risk notes: {risk}.")

    vparts: list[str] = []
    bp = vitals_latest.get("bp") or {}
    if bp.get("latest"):
        d = vitals_trends.get("bp_diastolic") or {}
        dir_ = d.get("direction")
        extra = f", diastolic {dir_}" if dir_ and dir_ != "unknown" else ""
        vparts.append(f"BP {bp['latest']}{extra}")
    wt = vitals_latest.get("weight") or {}
    if wt.get("latest") is not None:
        d = vitals_trends.get("weight") or {}
        dir_ = d.get("direction")
        extra = f", {dir_}" if dir_ and dir_ != "unknown" else ""
        vparts.append(f"weight {wt['latest']} kg{extra}")
    hb = vitals_latest.get("hemoglobin") or {}
    if hb.get("latest") is not None:
        d = vitals_trends.get("hemoglobin") or {}
        dir_ = d.get("direction")
        extra = f", {dir_}" if dir_ and dir_ != "unknown" else ""
        vparts.append(f"Hb {hb['latest']} g/dL{extra}")
    pulse = vitals_latest.get("pulse") or {}
    if pulse.get("latest") is not None:
        vparts.append(f"pulse {pulse['latest']}")
    if vparts:
        bits.append("Latest vitals: " + "; ".join(vparts) + ".")

    if alerts:
        bits.append(
            "Alerts: " + "; ".join(str(a.get("message") or "") for a in alerts[:4] if a.get("message")) + "."
        )

    doc_blurbs = []
    for d in documents[:3]:
        blurb = _findings_blurb(
            d.get("findings") if isinstance(d.get("findings"), dict) else None
        )
        title = str(d.get("title") or "Report")
        if blurb:
            doc_blurbs.append(f"{title}: {blurb}")
        else:
            doc_blurbs.append(title)
    if doc_blurbs:
        bits.append("Reports: " + " | ".join(doc_blurbs) + ".")

    if doctor_comments:
        recent = [str(c.get("text") or "").strip() for c in doctor_comments[:3]]
        recent = [t for t in recent if t]
        if recent:
            bits.append("Doctor comments: " + " | ".join(recent) + ".")

    if last_rx and (last_rx.get("diagnoses") or last_rx.get("symptoms")):
        dx = [
            str(x).strip()
            for x in (last_rx.get("diagnoses") or [])
            if str(x).strip()
        ]
        sx = [
            str(x).strip()
            for x in (last_rx.get("symptoms") or [])
            if str(x).strip()
        ]
        if dx:
            bits.append("Last diagnoses: " + "; ".join(dx[:5]) + ".")
        if sx:
            bits.append("Last symptoms: " + "; ".join(sx[:5]) + ".")

    return " ".join(bits).strip()


def summarize_encounter_rows(
    rows: list[Any],
    *,
    clinic_id: str,
    blind_patient_id: str,
    next_appointment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Core case-summary builder from ClinicalRecord-like rows (for API + tests)."""
    obstetric: dict[str, Any] | None = None
    lmp_ymd: str | None = None
    for r in reversed(rows):
        data = _as_dict(getattr(r, "encounter_data", None))
        if data.get("type") == "obstetric_profile":
            obstetric = {
                "lmp": data.get("lmp") or None,
                "edd": data.get("edd") or None,
                "edd_source": data.get("edd_source") or "",
                "gravida": data.get("gravida") or "",
                "para": data.get("para") or "",
                "abortions": data.get("abortions") or "",
                "living": data.get("living") or "",
                "blood_group": data.get("blood_group") or "",
                "rh": data.get("rh") or "",
                "high_risk_notes": data.get("high_risk_notes") or "",
            }
            raw = str(data.get("lmp") or "").strip()
            if len(raw) >= 10:
                lmp_ymd = raw[:10]
            break

    vitals_points: list[dict[str, Any]] = []
    labs: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    doctor_comments: list[dict[str, Any]] = []
    last_rx: dict[str, Any] | None = None

    for r in rows:
        data = _as_dict(getattr(r, "encounter_data", None))
        et = _etype(data)
        at = getattr(r, "created_at", None)
        at_iso = at.isoformat() if at else None
        ga_w, ga_l = (
            _ga_from_lmp(lmp_ymd, at) if lmp_ymd and at else (None, None)
        )
        by_name = _entered_by_name(data)

        if et == "vitals":
            v = data.get("vitals") if isinstance(data.get("vitals"), dict) else data
            if not isinstance(v, dict):
                continue
            sys, dia = _parse_bp(v)
            vitals_points.append(
                {
                    "at": at_iso,
                    "systolic": sys,
                    "diastolic": dia,
                    "weight": str(v.get("weight") or "").strip() or None,
                    "hemoglobin": str(
                        v.get("hemoglobin") or v.get("hb") or ""
                    ).strip()
                    or None,
                    "pulse": str(v.get("pulse") or "").strip() or None,
                    "gestational_weeks": ga_w,
                    "gestational_label": ga_l,
                    "source": "vitals",
                }
            )
            notes = str(data.get("diagnostic_notes") or "").strip()
            if notes:
                doctor_comments.append(
                    {
                        "at": at_iso,
                        "text": notes[:500],
                        "source": "vitals",
                        "entered_by": by_name,
                    }
                )
        elif et == "lab_result":
            name = str(data.get("test_name") or "").strip()
            val = str(data.get("value") or "").strip()
            unit = str(data.get("unit") or "").strip()
            labs.append(
                {
                    "at": at_iso,
                    "test_name": name,
                    "value": val,
                    "unit": unit,
                    "reference_range": str(data.get("reference_range") or ""),
                    "gestational_label": ga_l,
                }
            )
            low = name.lower()
            if any(k in low for k in ("hemoglobin", "haemoglobin", "hb ")) or low in (
                "hb",
                "hgb",
            ):
                vitals_points.append(
                    {
                        "at": at_iso,
                        "systolic": None,
                        "diastolic": None,
                        "weight": None,
                        "hemoglobin": val,
                        "pulse": None,
                        "gestational_weeks": ga_w,
                        "gestational_label": ga_l,
                        "source": "lab",
                    }
                )
        elif et == "document":
            findings = (
                data.get("findings")
                if isinstance(data.get("findings"), dict)
                else None
            )
            documents.append(
                {
                    "id": str(getattr(r, "id", "") or ""),
                    "at": at_iso,
                    "title": str(
                        data.get("title") or data.get("filename") or "Document"
                    ),
                    "document_kind": str(data.get("document_kind") or "other"),
                    "filename": str(data.get("filename") or ""),
                    "findings": findings,
                    "findings_summary": _findings_blurb(findings),
                    "gestational_label": ga_l,
                }
            )
        elif et in ("prescription", "visit"):
            comment_parts: list[str] = []
            symptoms = _as_string_list(data.get("symptoms"))
            if symptoms:
                comment_parts.append("Symptoms: " + ", ".join(symptoms[:8]))
            for key in ("clinical_notes", "notes"):
                comment_parts.extend(_as_string_list(data.get(key))[:4])
            obs = _as_string_list(data.get("clinical_observations"))
            # Prefer short free-text observations that look like notes, not vital dumps
            for o in obs[:4]:
                if o.lower().startswith("notes=") or (
                    "=" not in o and len(o) > 12
                ):
                    comment_parts.append(
                        o[6:].strip() if o.lower().startswith("notes=") else o
                    )
            if comment_parts:
                doctor_comments.append(
                    {
                        "at": at_iso,
                        "text": " · ".join(comment_parts)[:500],
                        "source": et,
                        "entered_by": by_name,
                    }
                )
            if data.get("medications") or data.get("diagnoses") or data.get("signed_by"):
                last_rx = {
                    "at": at_iso,
                    "diagnoses": data.get("diagnoses") or [],
                    "medications": data.get("medications") or [],
                    "symptoms": data.get("symptoms") or [],
                }

    vitals_points.sort(key=lambda p: p.get("at") or "")
    # Newest comments first
    doctor_comments.sort(key=lambda c: c.get("at") or "", reverse=True)
    doctor_comments = doctor_comments[:10]

    weight_d = _delta_field(vitals_points, "weight")
    hb_d = _delta_field(vitals_points, "hemoglobin")
    pulse_d = _delta_field(vitals_points, "pulse")
    bp_d = _delta_bp(vitals_points)

    vitals_latest = {
        "bp": bp_d,
        "weight": weight_d,
        "hemoglobin": hb_d,
        "pulse": pulse_d,
    }
    vitals_trends = {
        "bp_diastolic": {
            "latest": bp_d.get("latest") if bp_d else None,
            "previous": bp_d.get("previous") if bp_d else None,
            "delta": bp_d.get("delta_diastolic") if bp_d else None,
            "direction": (bp_d or {}).get("direction") or "unknown",
        }
        if bp_d
        else None,
        "weight": weight_d,
        "hemoglobin": hb_d,
        "pulse": pulse_d,
    }

    ga_now, ga_label_now = (
        _ga_from_lmp(lmp_ymd, datetime.now(timezone.utc)) if lmp_ymd else (None, None)
    )
    high_risk = str((obstetric or {}).get("high_risk_notes") or "")
    alerts = [
        a.as_dict()
        for a in evaluate_vitals_alerts(vitals_points, high_risk_notes=high_risk)
    ]

    cadence = anc_scan_cadence(lmp_ymd, ga_now)
    doc_titles = " ".join(
        (d.get("title") or "") + " " + (d.get("filename") or "") for d in documents
    ).lower()
    for item in cadence:
        code = item["code"]
        keywords = {
            "nt_scan": ("nt", "nuchal", "11-14", "first trimester"),
            "anomaly_scan": ("anomaly", "tiffa", "level ii", "level 2", "18-22"),
            "growth_scan": ("growth", "third trimester", "doppler", "efw"),
        }.get(code, ())
        found = any(k in doc_titles for k in keywords)
        item["matched_document"] = found
        if found and item["status"] in ("due", "past_window", "upcoming"):
            item["status"] = "documented"

    docs_recent = documents[-6:][::-1]
    narrative = _build_narrative(
        gestational_age=ga_label_now,
        obstetric=obstetric,
        vitals_latest=vitals_latest,
        vitals_trends=vitals_trends,
        alerts=alerts,
        documents=docs_recent,
        doctor_comments=doctor_comments,
        last_rx=last_rx,
    )

    return {
        "blind_patient_id_prefix": blind_patient_id[:8],
        "clinic_id": clinic_id,
        "obstetric": obstetric,
        "gestational_age": ga_label_now,
        "gestational_weeks": ga_now,
        "vitals_latest": vitals_latest,
        "vitals_trends": vitals_trends,
        "vitals_points": vitals_points[-12:],
        "labs_recent": labs[-8:][::-1],
        "documents_recent": docs_recent,
        "doctor_comments": doctor_comments,
        "narrative": narrative,
        "last_prescription": last_rx,
        "alerts": alerts,
        "scan_cadence": cadence,
        "next_appointment": next_appointment,
        "disclaimer": (
            "Decision support only — not a diagnosis. Confirm with clinical judgment."
        ),
    }


def build_case_summary(
    db: Session,
    *,
    clinic_id: str,
    blind_patient_id: str,
) -> dict[str, Any]:
    rows = db.scalars(
        select(ClinicalRecord)
        .where(
            ClinicalRecord.blind_patient_id == blind_patient_id,
            ClinicalRecord.clinic_id == clinic_id,
        )
        .order_by(ClinicalRecord.created_at.asc())
    ).all()

    next_appt = None
    now = datetime.now(timezone.utc)
    appt = db.scalars(
        select(Appointment)
        .where(
            Appointment.clinic_id == clinic_id,
            Appointment.blind_patient_id == blind_patient_id,
            Appointment.status == "booked",
            Appointment.scheduled_at >= now,
        )
        .order_by(Appointment.scheduled_at.asc())
        .limit(1)
    ).first()
    if appt is not None:
        next_appt = {
            "scheduled_at": appt.scheduled_at.isoformat() if appt.scheduled_at else None,
            "reason": appt.reason,
        }

    return summarize_encounter_rows(
        list(rows),
        clinic_id=clinic_id,
        blind_patient_id=blind_patient_id,
        next_appointment=next_appt,
    )


def rx_conflict_hints(
    summary: dict[str, Any],
    medications: list[dict[str, Any]] | list[str],
) -> list[dict[str, str]]:
    """Soft pre-sign hints from latest labs/vitals vs draft meds."""
    hints: list[dict[str, str]] = []
    med_names = []
    for m in medications or []:
        if isinstance(m, dict):
            med_names.append(str(m.get("name") or "").lower())
        else:
            med_names.append(str(m).lower())
    joined = " ".join(med_names)

    hb = (summary.get("vitals_latest") or {}).get("hemoglobin") or {}
    latest_hb = hb.get("latest")
    if isinstance(latest_hb, (int, float)) and latest_hb < 11:
        if not any(k in joined for k in ("iron", "ferrous", "folic", "haematinic")):
            hints.append(
                {
                    "severity": "warn",
                    "message": (
                        f"Hb {latest_hb:.1f} g/dL is low and draft Rx has no iron/folate — "
                        "consider haematinics if clinically appropriate."
                    ),
                }
            )

    bp = (summary.get("vitals_latest") or {}).get("bp") or {}
    latest_bp = str(bp.get("latest") or "")
    m = re.match(r"^(\d+)/(\d+)$", latest_bp)
    if m and int(m.group(2)) >= 90:
        if any(k in joined for k in ("ergometrine", "methylergometrine", "methergine")):
            hints.append(
                {
                    "severity": "critical",
                    "message": (
                        "Elevated diastolic BP with uterotonic (ergometrine-class) in draft — "
                        "review contraindications."
                    ),
                }
            )

    risk = str(((summary.get("obstetric") or {}).get("high_risk_notes") or "")).lower()
    if "allerg" in risk and med_names:
        hints.append(
            {
                "severity": "info",
                "message": "High-risk notes mention allergy — double-check draft medications.",
            }
        )

    for a in summary.get("alerts") or []:
        if a.get("severity") == "critical":
            hints.append(
                {
                    "severity": "critical",
                    "message": f"Open alert: {a.get('message')}",
                }
            )
    return hints
