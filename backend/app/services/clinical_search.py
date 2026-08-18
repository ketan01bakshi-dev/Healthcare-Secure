"""Clinic-wide patient and record search helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.record import ClinicalRecord
from app.services.security import normalize_phone_digits, tokenize_patient_identifier


@dataclass
class SearchPatientIdentity:
    blind_patient_id: str
    patient_name: str
    patient_phone: str
    blind_name_id: str
    blind_phone_id: str
    updated_at: datetime


@dataclass
class SearchResultItem:
    kind: str
    blind_patient_id: str
    patient_name: str | None
    patient_phone: str | None
    record_id: str | None
    created_at: datetime | None
    title: str
    subtitle: str
    match_source: str
    locked_patient_priority: bool = False


_PATIENT_INDEX: dict[str, SearchPatientIdentity] = {}


def remember_patient_identity(
    *,
    blind_patient_id: str,
    patient_name: str,
    patient_phone: str,
) -> SearchPatientIdentity:
    """Cache clinic-local patient identity for universal search results."""
    clean_name = patient_name.strip()
    clean_phone = normalize_phone_digits(patient_phone)
    identity = SearchPatientIdentity(
        blind_patient_id=blind_patient_id,
        patient_name=clean_name,
        patient_phone=clean_phone,
        blind_name_id=tokenize_patient_identifier(clean_name),
        blind_phone_id=tokenize_patient_identifier(clean_phone),
        updated_at=datetime.now(timezone.utc),
    )
    _PATIENT_INDEX[blind_patient_id] = identity
    return identity


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                items.append(text)
    return items


def _medication_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        parts = [
            str(item.get("name") or "").strip(),
            str(item.get("dosage") or "").strip(),
            str(item.get("frequency") or "").strip(),
            str(item.get("duration") or "").strip(),
        ]
        text = " ".join(part for part in parts if part)
        if text:
            items.append(text)
    return items


def _record_search_fields(record: ClinicalRecord) -> list[tuple[str, str]]:
    data = record.encounter_data or {}
    fields: list[tuple[str, str]] = []
    mapping = {
        "diagnosis": _string_list(data.get("diagnoses")) + _string_list(data.get("diagnosis")),
        "medication": _medication_strings(data.get("medications")),
        "note": _string_list(data.get("clinical_observations"))
        + _string_list(data.get("clinical_notes"))
        + _string_list(data.get("notes"))
        + _string_list(data.get("symptoms")),
        "document": [
            str(data.get("title") or "").strip(),
            str(data.get("filename") or "").strip(),
            str(data.get("document_kind") or "").replace("_", " ").strip(),
        ],
        "lab": [str(data.get("title") or "").strip()],
    }
    diagnostic_notes = str(data.get("diagnostic_notes") or "").strip()
    if diagnostic_notes:
        mapping["note"].append(diagnostic_notes)
    for source, values in mapping.items():
        for value in values:
            if value:
                fields.append((source, value))
    return fields


def search_clinic_records(
    db: Session,
    *,
    query: str,
    locked_blind_patient_id: str | None = None,
    limit: int = 12,
) -> list[SearchResultItem]:
    """Search cached patients and clinical record text for the current clinic."""
    needle = query.strip().lower()
    if len(needle) < 2:
        return []

    exact_token_matches: set[str] = set()
    normalized_digits = normalize_phone_digits(query)
    if normalized_digits:
        try:
            exact_token_matches.add(tokenize_patient_identifier(normalized_digits))
        except ValueError:
            pass
    try:
        exact_token_matches.add(tokenize_patient_identifier(query.strip()))
    except ValueError:
        pass

    results: list[SearchResultItem] = []
    seen_patients: set[str] = set()
    for blind_patient_id, identity in _PATIENT_INDEX.items():
        name_match = needle in identity.patient_name.lower()
        phone_match = normalized_digits and normalized_digits in identity.patient_phone
        exact_match = (
            identity.blind_name_id in exact_token_matches
            or identity.blind_phone_id in exact_token_matches
        )
        if not (name_match or phone_match or exact_match):
            continue
        seen_patients.add(blind_patient_id)
        results.append(
            SearchResultItem(
                kind="patient",
                blind_patient_id=blind_patient_id,
                patient_name=identity.patient_name,
                patient_phone=identity.patient_phone,
                record_id=None,
                created_at=None,
                title=identity.patient_name,
                subtitle=f"Mobile {identity.patient_phone}",
                match_source="patient",
                locked_patient_priority=blind_patient_id == locked_blind_patient_id,
            )
        )

    stmt = select(ClinicalRecord).order_by(ClinicalRecord.created_at.desc())
    for record in db.scalars(stmt):
        identity = _PATIENT_INDEX.get(record.blind_patient_id)
        for match_source, text in _record_search_fields(record):
            if needle not in text.lower():
                continue
            patient_name = identity.patient_name if identity else None
            patient_phone = identity.patient_phone if identity else None
            patient_label = patient_name or "Patient"
            subtitle = text if len(text) <= 120 else f"{text[:117]}..."
            if patient_phone:
                subtitle = f"{patient_label} · {subtitle}"
            results.append(
                SearchResultItem(
                    kind="record",
                    blind_patient_id=record.blind_patient_id,
                    patient_name=patient_name,
                    patient_phone=patient_phone,
                    record_id=str(record.id),
                    created_at=record.created_at,
                    title=patient_label,
                    subtitle=subtitle,
                    match_source=match_source,
                    locked_patient_priority=record.blind_patient_id == locked_blind_patient_id,
                )
            )
            if identity:
                seen_patients.add(record.blind_patient_id)
            break

    results.sort(
        key=lambda item: (
            0 if item.locked_patient_priority else 1,
            0 if item.kind == "patient" else 1,
            -(item.created_at.timestamp() if item.created_at else 0),
            item.title.lower(),
        )
    )

    deduped: list[SearchResultItem] = []
    seen_keys: set[tuple[str, str | None, str]] = set()
    for item in results:
        key = (item.kind, item.record_id, item.blind_patient_id)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped
