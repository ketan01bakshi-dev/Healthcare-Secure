"""Rule-based ANC / vitals alerts for doctor decision support (not diagnosis)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Alert:
    code: str
    severity: str  # info | warn | critical
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }


def _f(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def evaluate_vitals_alerts(
    points: list[dict[str, Any]],
    *,
    high_risk_notes: str = "",
) -> list[Alert]:
    """
    points: chronological dicts with systolic, diastolic, weight, hemoglobin,
    gestational_weeks (optional).
    """
    alerts: list[Alert] = []
    if not points:
        return alerts

    dias = [(p, _f(p.get("diastolic"))) for p in points]
    dias_ok = [(p, d) for p, d in dias if d is not None]
    if dias_ok:
        last_p, last_d = dias_ok[-1]
        if last_d >= 110:
            alerts.append(
                Alert(
                    "bp_severe",
                    "critical",
                    f"Diastolic {int(last_d)} mmHg — severe range; urgent clinical review.",
                )
            )
        elif last_d >= 90:
            alerts.append(
                Alert(
                    "bp_high",
                    "warn",
                    f"Diastolic {int(last_d)} mmHg (≥90) — check for hypertensive disorder of pregnancy.",
                )
            )
        if len(dias_ok) >= 2:
            prev_d = dias_ok[-2][1]
            if prev_d is not None and last_d - prev_d >= 15:
                alerts.append(
                    Alert(
                        "bp_rising",
                        "warn",
                        f"Diastolic rose {int(last_d - prev_d)} mmHg since last visit.",
                    )
                )

    hbs = [(p, _f(p.get("hemoglobin"))) for p in points]
    hbs_ok = [(p, h) for p, h in hbs if h is not None]
    if hbs_ok:
        _, last_hb = hbs_ok[-1]
        gw = _f(hbs_ok[-1][0].get("gestational_weeks"))
        # Trimester-ish cutoffs (simplified): <11 g/dL anemia in pregnancy
        cutoff = 10.5 if gw is not None and gw >= 28 else 11.0
        if last_hb < 7:
            alerts.append(
                Alert(
                    "hb_severe",
                    "critical",
                    f"Hemoglobin {last_hb:.1f} g/dL — severe anemia range.",
                )
            )
        elif last_hb < cutoff:
            alerts.append(
                Alert(
                    "hb_low",
                    "warn",
                    f"Hemoglobin {last_hb:.1f} g/dL below antenatal target (~{cutoff:g} g/dL).",
                )
            )
        if len(hbs_ok) >= 2:
            prev_h = hbs_ok[-2][1]
            if prev_h is not None and prev_h - last_hb >= 1.5:
                alerts.append(
                    Alert(
                        "hb_drop",
                        "warn",
                        f"Hemoglobin dropped {prev_h - last_hb:.1f} g/dL since last recorded value.",
                    )
                )

    wts = [(p, _f(p.get("weight"))) for p in points]
    wts_ok = [(p, w) for p, w in wts if w is not None]
    if len(wts_ok) >= 2:
        prev_w = wts_ok[-2][1]
        last_w = wts_ok[-1][1]
        if prev_w and last_w and last_w - prev_w >= 3:
            alerts.append(
                Alert(
                    "weight_jump",
                    "info",
                    f"Weight rose {last_w - prev_w:.1f} kg between visits — correlate clinically.",
                )
            )

    notes = (high_risk_notes or "").lower()
    if notes and any(
        k in notes for k in ("pih", "preeclamp", "gdm", "lscs", "prev lscs", "ivf")
    ):
        alerts.append(
            Alert(
                "high_risk_card",
                "info",
                "High-risk notes on obstetric card — review before treatment changes.",
            )
        )

    return alerts


def anc_scan_cadence(lmp_ymd: str | None, ga_weeks: float | None) -> list[dict[str, Any]]:
    """Expected ANC imaging windows vs current GA."""
    if not lmp_ymd and ga_weeks is None:
        return []
    gw = ga_weeks
    checks = [
        ("nt_scan", "NT / early anomaly (11–14w)", 11.0, 14.0),
        ("anomaly_scan", "Anomaly / TIFFA (18–22w)", 18.0, 22.0),
        ("growth_scan", "Growth / third-trimester USG (28–36w)", 28.0, 36.0),
    ]
    out: list[dict[str, Any]] = []
    for code, label, start, end in checks:
        if gw is None:
            status = "unknown"
        elif gw < start:
            status = "upcoming"
        elif start <= gw <= end:
            status = "due"
        else:
            status = "past_window"
        out.append(
            {
                "code": code,
                "label": label,
                "window_weeks": f"{int(start)}–{int(end)}",
                "status": status,
            }
        )
    return out
