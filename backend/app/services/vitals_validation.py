"""Physiological range checks for clinic vitals (adult + pediatric). Empty = OK."""

from __future__ import annotations

import re
from typing import Callable

_BP_RE = re.compile(r"^(\d{2,3})\s*/\s*(\d{2,3})$")
_NOTES_MAX = 2000


def _parse_number(raw: str) -> float | None:
    cleaned = raw.strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _pulse_bounds(age_years: float | None) -> tuple[int, int]:
    if age_years is None or age_years >= 18:
        return 30, 220
    # Neonate ~0–28 days ≈ age < 0.08 years
    if age_years < 0.08:
        return 100, 205
    if age_years < 1:
        return 80, 180
    if age_years < 3:
        return 70, 150
    if age_years < 6:
        return 65, 140
    if age_years < 12:
        return 60, 130
    return 50, 120


def _rr_bounds(age_years: float | None) -> tuple[int, int]:
    if age_years is None or age_years >= 18:
        return 5, 60
    if age_years < 0.08:
        return 30, 60
    if age_years < 1:
        return 20, 60
    if age_years < 3:
        return 18, 40
    if age_years < 6:
        return 16, 35
    if age_years < 12:
        return 14, 30
    return 12, 25


def _bp_bounds(age_years: float | None) -> tuple[int, int, int, int]:
    """systolic_min, systolic_max, diastolic_min, diastolic_max."""
    if age_years is None or age_years >= 18:
        return 70, 250, 40, 150
    if age_years < 0.08:
        return 50, 100, 25, 70
    if age_years < 1:
        return 60, 120, 30, 80
    if age_years < 6:
        return 70, 140, 35, 90
    if age_years < 12:
        return 80, 160, 40, 100
    return 85, 180, 40, 110


def validate_blood_pressure(
    raw: str,
    *,
    age_years: float | None = None,
) -> str | None:
    value = raw.strip()
    if not value:
        return None
    match = _BP_RE.match(value)
    if not match:
        return "Enter BP as 120/80 (mmHg)"
    systolic = int(match.group(1))
    diastolic = int(match.group(2))
    smin, smax, dmin, dmax = _bp_bounds(age_years)
    if not (smin <= systolic <= smax and dmin <= diastolic <= dmax):
        return f"Blood pressure must be between {smin}/{dmin} and {smax}/{dmax}"
    if systolic <= diastolic:
        return "Systolic must be higher than diastolic"
    return None


def validate_pulse(raw: str, *, age_years: float | None = None) -> str | None:
    value = raw.strip()
    if not value:
        return None
    n = _parse_number(value)
    if n is None or not float(n).is_integer():
        return "Pulse must be a whole number (bpm)"
    lo, hi = _pulse_bounds(age_years)
    if not lo <= int(n) <= hi:
        return f"Pulse must be {lo}–{hi}"
    return None


def validate_temperature(
    raw: str,
    *,
    unit: str = "F",
) -> str | None:
    value = raw.strip()
    if not value:
        return None
    n = _parse_number(value)
    if n is None:
        return "Enter temperature as a number"
    u = (unit or "F").strip().upper()
    if u == "C":
        if not 34.0 <= n <= 42.5:
            return "Temperature must be 34–42.5 °C"
        return None
    if not 93 <= n <= 108:
        return "Temperature must be 93–108 °F"
    return None


def temperature_to_f(raw: str, unit: str) -> str:
    """Normalize stored vitals temperature to °F string for consistent history."""
    n = _parse_number(raw)
    if n is None:
        return raw.strip()
    if (unit or "F").strip().upper() == "C":
        return f"{(n * 9 / 5) + 32:.1f}"
    return str(n).rstrip("0").rstrip(".") if "." in str(n) else str(int(n) if float(n).is_integer() else n)


def validate_spo2(raw: str) -> str | None:
    value = raw.strip().rstrip("%")
    if not value.strip():
        return None
    n = _parse_number(value)
    if n is None:
        return "Enter SpO₂ as a number"
    if not 50 <= n <= 100:
        return "SpO₂ must be 50–100"
    return None


def validate_weight(raw: str, *, age_years: float | None = None) -> str | None:
    value = raw.strip()
    if not value:
        return None
    n = _parse_number(value)
    if n is None:
        return "Enter weight in kg"
    hi = 300 if age_years is None or age_years >= 12 else 120
    lo = 0.5 if age_years is not None and age_years < 2 else 1
    if not lo <= n <= hi:
        return f"Weight must be {lo}–{hi} kg"
    return None


def validate_height(raw: str, *, age_years: float | None = None) -> str | None:
    value = raw.strip()
    if not value:
        return None
    n = _parse_number(value)
    if n is None:
        return "Enter height in cm"
    lo, hi = (30, 150) if age_years is not None and age_years < 12 else (40, 250)
    if not lo <= n <= hi:
        return f"Height must be {lo}–{hi} cm"
    return None


def validate_respiratory_rate(
    raw: str,
    *,
    age_years: float | None = None,
) -> str | None:
    value = raw.strip()
    if not value:
        return None
    n = _parse_number(value)
    if n is None or not float(n).is_integer():
        return "Respiratory rate must be a whole number"
    lo, hi = _rr_bounds(age_years)
    if not lo <= int(n) <= hi:
        return f"Respiratory rate must be {lo}–{hi}"
    return None


def validate_hemoglobin(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    n = _parse_number(value)
    if n is None:
        return "Enter hemoglobin in g/dL"
    if not 3.0 <= n <= 22.0:
        return "Hemoglobin must be 3–22 g/dL"
    return None


def validate_notes(raw: str) -> str | None:
    if len(raw) > _NOTES_MAX:
        return "Notes are too long"
    return None


def validate_vitals_dict(
    vitals: dict[str, str],
    *,
    age_years: float | None = None,
    temperature_unit: str = "F",
) -> str | None:
    """Return the first validation error message, or None if all OK."""
    checks: list[tuple[str, Callable[..., str | None]]] = [
        ("blood_pressure", lambda v: validate_blood_pressure(v, age_years=age_years)),
        ("pulse", lambda v: validate_pulse(v, age_years=age_years)),
        (
            "temperature",
            lambda v: validate_temperature(v, unit=temperature_unit),
        ),
        ("spo2", validate_spo2),
        ("weight", lambda v: validate_weight(v, age_years=age_years)),
        ("height", lambda v: validate_height(v, age_years=age_years)),
        (
            "respiratory_rate",
            lambda v: validate_respiratory_rate(v, age_years=age_years),
        ),
        ("hemoglobin", validate_hemoglobin),
    ]
    for key, validator in checks:
        err = validator(str(vitals.get(key, "") or ""))
        if err:
            return err
    return None
