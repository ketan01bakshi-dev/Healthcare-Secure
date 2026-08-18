"""Multi-clinic tenancy — clinic registry, branding, features, and record scoping."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Select

from app.core.config import settings

DEFAULT_CLINIC_ID = "default"

ALL_FEATURES: frozenset[str] = frozenset(
    {
        "voice_rx",
        "labs",
        "queue",
        "appointments",
        "analytics",
        "obstetric",
        "video_consult",
    }
)


@dataclass(frozen=True)
class ClinicInfo:
    clinic_id: str
    name: str
    address: str = ""
    subtitle: str = ""
    password: str = ""  # server-only; never expose in public APIs
    features: frozenset[str] = field(default_factory=lambda: ALL_FEATURES)


def _parse_features(raw: str) -> frozenset[str]:
    cleaned = (raw or "").strip()
    if not cleaned:
        return ALL_FEATURES
    flags = {
        part.strip().lower()
        for part in cleaned.split(",")
        if part.strip()
    }
    return frozenset(f for f in flags if f in ALL_FEATURES) or ALL_FEATURES


def _parse_clinics() -> dict[str, ClinicInfo]:
    """
    CLINICS format (semicolon-separated)::
        clinic_id|Display Name|Address|Subtitle
        clinic_id|Display Name|Address|Subtitle|password_or_pbkdf2|features
    """
    raw = (getattr(settings, "clinics", None) or "").strip()
    out: dict[str, ClinicInfo] = {}
    if raw:
        for chunk in raw.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = [p.strip() for p in chunk.split("|")]
            if len(parts) < 2 or not parts[0]:
                continue
            cid = parts[0]
            out[cid] = ClinicInfo(
                clinic_id=cid,
                name=parts[1] or cid,
                address=parts[2] if len(parts) > 2 else "",
                subtitle=parts[3] if len(parts) > 3 else "",
                password=parts[4] if len(parts) > 4 else "",
                features=_parse_features(parts[5] if len(parts) > 5 else ""),
            )
    if not out:
        out[DEFAULT_CLINIC_ID] = ClinicInfo(
            clinic_id=DEFAULT_CLINIC_ID,
            name=(settings.clinic_name or "Clinic").strip() or "Clinic",
            address=(settings.clinic_address or "").strip(),
            subtitle=(settings.clinic_subtitle or "").strip(),
            password="",
            features=ALL_FEATURES,
        )
    return out


def list_clinics() -> list[ClinicInfo]:
    return list(_parse_clinics().values())


def get_clinic(clinic_id: str | None) -> ClinicInfo:
    clinics = _parse_clinics()
    cid = (clinic_id or DEFAULT_CLINIC_ID).strip() or DEFAULT_CLINIC_ID
    if cid in clinics:
        return clinics[cid]
    return clinics.get(DEFAULT_CLINIC_ID) or next(iter(clinics.values()))


def find_clinic_by_name_or_id(clinic_name: str) -> ClinicInfo | None:
    """Match by clinic_id or display name (case-insensitive trim)."""
    needle = (clinic_name or "").strip().lower()
    if not needle:
        return None
    clinics = _parse_clinics()
    if needle in clinics:
        return clinics[needle]
    for clinic in clinics.values():
        if clinic.name.strip().lower() == needle:
            return clinic
        if clinic.clinic_id.strip().lower() == needle:
            return clinic
    return None


def public_clinic_dict(clinic: ClinicInfo) -> dict[str, object]:
    """Safe clinic payload — never includes password."""
    return {
        "clinic_id": clinic.clinic_id,
        "name": clinic.name,
        "address": clinic.address,
        "subtitle": clinic.subtitle,
        "features": sorted(clinic.features),
    }


def branding_for(clinic_id: str | None) -> dict[str, str]:
    clinic = get_clinic(clinic_id)
    return {
        "clinic_id": clinic.clinic_id,
        "clinic_name": clinic.name or settings.clinic_name,
        "clinic_subtitle": clinic.subtitle or settings.clinic_subtitle,
        "clinic_address": clinic.address or settings.clinic_address,
        "doctor_name": settings.doctor_name,
        "doctor_credentials": settings.doctor_credentials,
    }


def normalize_clinic_id(clinic_id: str | None) -> str:
    cid = (clinic_id or DEFAULT_CLINIC_ID).strip() or DEFAULT_CLINIC_ID
    clinics = _parse_clinics()
    if cid not in clinics and DEFAULT_CLINIC_ID in clinics:
        # Unknown id still accepted for user assignment; branding falls back
        return cid
    return cid if cid in clinics else DEFAULT_CLINIC_ID


def scope_by_clinic(stmt: Select, model: type, clinic_id: str) -> Select:
    """Restrict a SQLAlchemy select to one clinic."""
    return stmt.where(model.clinic_id == clinic_id)
