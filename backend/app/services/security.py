"""Identity tokenization — raw patient identifiers never leave process memory as stored data."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any, Mapping, MutableMapping

from app.core.config import settings

# Keys that must never be persisted or carried into session/login context.
_RAW_IDENTIFIER_KEYS = frozenset(
    {
        "mobile",
        "mobile_number",
        "phone",
        "phone_number",
        "national_id",
        "national_id_number",
        "ssn",
        "social_security_number",
        "raw_identifier",
        "patient_identifier",
        "patient_id_raw",
        "mrn_raw",
        "clinic_mrn",
        "abha_id",
        "abha_number",
        "patient_name",
        "patient_phone",
    }
)


def normalize_phone_digits(phone: str) -> str:
    """Keep digits only; normalize Indian +91 / leading 0 to 10-digit mobile."""
    p = re.sub(r"\D+", "", (phone or "").strip())
    if len(p) >= 12 and p.startswith("91"):
        p = p[-10:]
    elif len(p) == 11 and p.startswith("0"):
        p = p[1:]
    return p


def normalize_mrn(mrn: str) -> str:
    """Clinic MRN: strip spaces, uppercase alphanumerics and dashes."""
    return re.sub(r"[^A-Za-z0-9\-]", "", (mrn or "").strip()).upper()


def normalize_abha_id(abha: str) -> str:
    """ABHA number: digits only (14-digit form common)."""
    return re.sub(r"\D+", "", (abha or "").strip())


def build_patient_raw_identifier(
    name: str,
    phone: str,
    *,
    clinic_mrn: str | None = None,
) -> str:
    """
    Stable composite key for history linkage.

    Prefer clinic MRN when present (``mrn|{MRN}``) so name/phone changes
    do not orphan history. Otherwise ``name|10digits``.
    Clear-text is HMAC input only — never stored on ClinicalRecord.
    """
    mrn = normalize_mrn(clinic_mrn or "")
    if mrn:
        if len(mrn) < 2:
            raise ValueError("clinic MRN is too short")
        return f"mrn|{mrn}"

    n = (name or "").strip()
    p = normalize_phone_digits(phone)
    if not n:
        raise ValueError("patient name is required")
    if not p:
        raise ValueError("patient phone number is required")
    if len(p) != 10:
        raise ValueError("patient phone number must be exactly 10 digits")
    return f"{n}|{p}"


def tokenize_patient_identifier(
    raw_identifier: str,
    *,
    secret_salt: str | None = None,
) -> str:
    """
    Return an irreversible blind-patient-ID via HMAC-SHA256.

    The raw identifier is used only as the HMAC message and is not returned or
    written by this function. Callers must discard their own copy after use and
    must never assign the raw value to ORM fields or logs.
    """
    if not isinstance(raw_identifier, str) or not raw_identifier.strip():
        raise ValueError("raw_identifier must be a non-empty string")

    salt = secret_salt if secret_salt is not None else settings.secret_salt
    if not salt or salt.startswith("CHANGE_ME"):
        raise ValueError("SECRET_SALT must be set to a strong non-default value")

    key = salt.encode("utf-8")
    # Normalize lightly for stable tokens; do not retain a separate normalized copy.
    message = raw_identifier.strip().encode("utf-8")
    digest = hmac.new(key, message, hashlib.sha256).hexdigest()
    # Drop references to plaintext material as soon as the digest exists.
    del key, message, raw_identifier, salt
    return digest


def strip_raw_identifiers(
    payload: Mapping[str, Any] | MutableMapping[str, Any],
) -> dict[str, Any]:
    """
    Return a shallow copy of ``payload`` with raw identity fields removed.

    Use this before any internal application login, session creation, or
    persistence so only ``blind_patient_id`` (or non-identifying fields) remain.
    """
    return {
        key: value
        for key, value in payload.items()
        if key.lower() not in _RAW_IDENTIFIER_KEYS
    }


def tokenize_and_strip(
    payload: Mapping[str, Any] | MutableMapping[str, Any],
    *,
    identifier_key: str = "raw_identifier",
    blind_key: str = "blind_patient_id",
    secret_salt: str | None = None,
) -> dict[str, Any]:
    """
    Tokenize a raw identifier from ``payload``, then strip all raw ID fields.

    The raw value is read once, hashed in memory, and never placed on the
    returned dict. Suitable as a gate before login or clinical write paths.
    """
    if identifier_key not in payload:
        raise KeyError(f"payload missing required key '{identifier_key}'")

    raw = payload[identifier_key]
    if not isinstance(raw, str):
        raise TypeError(f"'{identifier_key}' must be a string")

    blind_id = tokenize_patient_identifier(raw, secret_salt=secret_salt)
    del raw

    cleaned = strip_raw_identifiers(payload)
    cleaned[blind_key] = blind_id
    return cleaned
