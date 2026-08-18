"""Clinic keyword glossary, alias rewrite, and doctor-edit memory for STT/parse."""

from __future__ import annotations

import re
import threading
import time
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings

# Seed gynae formulary + Hindi transliterations for Whisper bias prompts.
_DEFAULT_GLOSSARY_TERMS_GYNAE: tuple[str, ...] = (
    "mefenamic acid",
    "मेफेनैमिक",
    "mefenamic",
    "tranexamic acid",
    "ट्रानेक्सामिक",
    "iron folic acid",
    "calcium",
    "labetalol",
    "metformin",
    "myo-inositol",
    "folic acid",
    "dydrogesterone",
    "progesterone",
    "isosxuprine",
    "albendazole",
    "ondansetron",
    "pantoprazole",
    "thyroxine",
    "levothyroxine",
    "aspirin",
    "nifedipine",
    "methyldopa",
    "dysmenorrhea",
    "menorrhagia",
    "antenatal",
    "anemia",
    "anaemia",
    "PCOS",
    "fundus",
    "fetal heart",
    "oligomenorrhea",
    "amenorrhea",
    "PID",
    "UTI",
)

_DEFAULT_GLOSSARY_TERMS_GP: tuple[str, ...] = (
    "paracetamol",
    "azithromycin",
    "amlodipine",
    "telmisartan",
    "metformin",
    "atorvastatin",
    "levothyroxine",
    "pantoprazole",
    "omeprazole",
    "salbutamol",
    "montelukast",
    "cetirizine",
    "hypertension",
    "diabetes",
    "HbA1c",
    "hypothyroidism",
    "URTI",
    "pneumonia",
    "asthma",
    "COPD",
    "fever",
    "cough",
    "diarrhea",
    "gastroenteritis",
)

# Built-in spoken/misspell → preferred (global, not clinic-specific).
_DEFAULT_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("mefthalamic", "mefenamic acid", "medication"),
    ("mefanamic", "mefenamic acid", "medication"),
    ("mefenamic acide", "mefenamic acid", "medication"),
    ("tranexmic", "tranexamic acid", "medication"),
    ("tranexamic acide", "tranexamic acid", "medication"),
    ("folic acide", "folic acid", "medication"),
    ("labetolol", "labetalol", "medication"),
    ("dysmenorrhoea", "dysmenorrhea", "diagnosis"),
    ("menorrhagia heavy flow", "menorrhagia", "diagnosis"),
)

# Short TTL: avoid 2–3 DB hits per note without serving stale clinic aliases for hours.
_ALIAS_CACHE_TTL_S = 30.0
_alias_cache: dict[str, tuple[float, dict[str, str]]] = {}
_alias_cache_lock = threading.Lock()


def _norm_key(term: str) -> str:
    return re.sub(r"\s+", " ", (term or "").strip().lower())


def env_glossary_terms() -> list[str]:
    raw = (settings.stt_glossary or "").strip()
    if not raw:
        return []
    parts = re.split(r"[,;\n]+", raw)
    return [p.strip() for p in parts if p.strip()]


def _default_glossary_terms(clinic_id: str | None = None) -> tuple[str, ...]:
    if not clinic_id:
        return _DEFAULT_GLOSSARY_TERMS_GYNAE
    try:
        from app.services.tenancy import get_clinic

        if "obstetric" in get_clinic(clinic_id).features:
            return _DEFAULT_GLOSSARY_TERMS_GYNAE
    except Exception:  # noqa: BLE001
        pass
    return _DEFAULT_GLOSSARY_TERMS_GP


def whisper_vocab_blob(
    *,
    clinic_id: str | None = None,
    clinic_aliases: list[str] | None = None,
) -> str:
    """Compact vocabulary string for Whisper initial_prompt / API prompt."""
    terms: list[str] = list(_default_glossary_terms(clinic_id))
    terms.extend(env_glossary_terms())
    if clinic_aliases:
        terms.extend(clinic_aliases)
    # De-dupe preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for t in terms:
        key = _norm_key(t)
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(t.strip())
    # Whisper prompts work best when not huge
    ordered = ordered[:80]
    meds = [t for t in ordered if not any("\u0900" <= c <= "\u097f" for c in t)]
    hindi = [t for t in ordered if any("\u0900" <= c <= "\u097f" for c in t)]
    parts = [
        "Medications and clinical terms: " + ", ".join(meds[:50]) + "."
    ]
    if hindi:
        parts.append("Hindi spellings: " + ", ".join(hindi[:20]) + ".")
    return " ".join(parts)


def load_clinic_alias_map(db: Session | None, clinic_id: str | None) -> dict[str, str]:
    """Merged default + clinic DB aliases (from_term → to_term). Cached briefly per clinic."""
    cache_key = clinic_id or ""
    now = time.monotonic()
    with _alias_cache_lock:
        hit = _alias_cache.get(cache_key)
        if hit is not None and now - hit[0] < _ALIAS_CACHE_TTL_S:
            return dict(hit[1])

    mapping: dict[str, str] = {
        _norm_key(src): dst for src, dst, _kind in _DEFAULT_ALIASES
    }
    if db is None or not clinic_id:
        with _alias_cache_lock:
            _alias_cache[cache_key] = (now, dict(mapping))
        return mapping
    try:
        from app.models.stt_memory import SttAlias

        rows = db.scalars(
            select(SttAlias).where(SttAlias.clinic_id == clinic_id)
        ).all()
        for row in rows:
            key = _norm_key(row.from_term)
            if key and row.to_term.strip():
                mapping[key] = row.to_term.strip()
    except Exception:  # noqa: BLE001
        pass
    with _alias_cache_lock:
        _alias_cache[cache_key] = (now, dict(mapping))
    return mapping


def clinic_alias_terms_for_prompt(db: Session | None, clinic_id: str | None) -> list[str]:
    mapping = load_clinic_alias_map(db, clinic_id)
    out: list[str] = []
    for src, dst in mapping.items():
        out.append(dst)
        out.append(src)
    return out


def apply_term_aliases(text: str, alias_map: dict[str, str] | None = None) -> str:
    """
    Rewrite known misspellings / spoken forms in a transcript.
    Longer keys applied first to avoid partial collisions.
    """
    if not text or not text.strip():
        return text
    mapping = alias_map if alias_map is not None else load_clinic_alias_map(None, None)
    if not mapping:
        return text
    result = text
    for src in sorted(mapping.keys(), key=len, reverse=True):
        dst = mapping[src]
        if not src or _norm_key(src) == _norm_key(dst):
            continue
        pattern = re.compile(re.escape(src), re.IGNORECASE)
        result = pattern.sub(dst, result)
    return result


def _med_names(clinical: dict[str, Any] | None) -> list[str]:
    if not isinstance(clinical, dict):
        return []
    names: list[str] = []
    for item in clinical.get("medications") or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.append(name)
    return names


def _dx_names(clinical: dict[str, Any] | None) -> list[str]:
    if not isinstance(clinical, dict):
        return []
    out: list[str] = []
    for item in clinical.get("diagnoses") or []:
        name = (
            str(item).strip()
            if not isinstance(item, dict)
            else str(item.get("name") or item.get("text") or "").strip()
        )
        if name:
            out.append(name)
    return out


def count_med_name_edits(
    parsed: dict[str, Any] | None, final: dict[str, Any] | None
) -> int:
    """Count medication names that changed between parse and signed draft."""
    parsed_names = [_norm_key(n) for n in _med_names(parsed)]
    final_names = [_norm_key(n) for n in _med_names(final)]
    if not parsed_names and not final_names:
        return 0
    # Pair by position when lengths match; else set-diff style
    edits = 0
    if len(parsed_names) == len(final_names):
        for a, b in zip(parsed_names, final_names, strict=True):
            if a != b:
                edits += 1
        return edits
    parsed_set = set(parsed_names)
    final_set = set(final_names)
    # Names removed or replaced
    return len(parsed_set - final_set) + len(final_set - parsed_set)


def extract_alias_candidates(
    parsed: dict[str, Any] | None, final: dict[str, Any] | None
) -> list[tuple[str, str, str]]:
    """
    Build (from, to, kind) candidates from positional med/dx renames.
    Skips pure additions (doctor knowledge, not STT errors).
    """
    pairs: list[tuple[str, str, str]] = []
    p_meds = _med_names(parsed)
    f_meds = _med_names(final)
    for i, src in enumerate(p_meds):
        if i >= len(f_meds):
            break
        dst = f_meds[i]
        if _norm_key(src) and _norm_key(src) != _norm_key(dst) and dst.strip():
            pairs.append((src.strip(), dst.strip(), "medication"))
    p_dx = _dx_names(parsed)
    f_dx = _dx_names(final)
    for i, src in enumerate(p_dx):
        if i >= len(f_dx):
            break
        dst = f_dx[i]
        if _norm_key(src) and _norm_key(src) != _norm_key(dst) and dst.strip():
            pairs.append((src.strip(), dst.strip(), "diagnosis"))
    return pairs


def upsert_aliases(
    db: Session,
    *,
    clinic_id: str,
    pairs: list[tuple[str, str, str]],
) -> int:
    from app.models.stt_memory import SttAlias

    updated = 0
    for src, dst, kind in pairs:
        key = _norm_key(src)
        if not key or not dst.strip():
            continue
        if len(key) > 120 or len(dst) > 120:
            continue
        existing = db.scalars(
            select(SttAlias).where(
                SttAlias.clinic_id == clinic_id,
                SttAlias.from_term == key,
            )
        ).first()
        if existing is None:
            db.add(
                SttAlias(
                    clinic_id=clinic_id,
                    from_term=key,
                    to_term=dst.strip(),
                    kind=kind,
                    hit_count=1,
                )
            )
            updated += 1
        else:
            existing.to_term = dst.strip()
            existing.kind = kind
            existing.hit_count = int(existing.hit_count or 0) + 1
            updated += 1
    return updated


def store_correction_feedback(
    db: Session,
    *,
    clinic_id: str,
    blind_patient_id: str,
    transcripts: list[str],
    parsed_clinical: dict[str, Any] | None,
    final_clinical: dict[str, Any] | None,
    source_language: str = "en",
) -> dict[str, Any]:
    """Persist feedback row and mine aliases. Safe no-op if nothing useful."""
    from app.models.stt_memory import SttCorrectionFeedback
    from app.services.lml_parser import _PHONE_PATTERN

    cleaned_transcripts = [
        _PHONE_PATTERN.sub("[phone]", t.strip())[:4000]
        for t in transcripts
        if isinstance(t, str) and t.strip()
    ]
    parsed = dict(parsed_clinical or {})
    final = dict(final_clinical or {})
    if not cleaned_transcripts and not parsed and not final:
        return {"stored": False, "aliases": 0, "med_name_edits": 0}

    med_edits = count_med_name_edits(parsed, final)
    row = SttCorrectionFeedback(
        clinic_id=clinic_id,
        blind_patient_id=(blind_patient_id or "")[:64],
        source_language=(source_language or "en")[:8],
        transcripts=cleaned_transcripts[:12],
        parsed_clinical=parsed,
        final_clinical=final,
        med_name_edits=med_edits,
    )
    db.add(row)
    pairs = extract_alias_candidates(parsed, final)
    alias_n = upsert_aliases(db, clinic_id=clinic_id, pairs=pairs)
    return {
        "stored": True,
        "aliases": alias_n,
        "med_name_edits": med_edits,
    }


def few_shot_pairs_from_feedback(
    db: Session | None,
    clinic_id: str | None,
    *,
    limit: int = 3,
) -> list[tuple[str, str]]:
    """
    Recent correction pairs as (user transcript snippet, assistant final JSON).
    Used as dynamic few-shots for the parse LLM.
    """
    if db is None or not clinic_id:
        return []
    try:
        import json

        from app.models.stt_memory import SttCorrectionFeedback

        rows = db.scalars(
            select(SttCorrectionFeedback)
            .where(
                SttCorrectionFeedback.clinic_id == clinic_id,
                SttCorrectionFeedback.med_name_edits > 0,
            )
            .order_by(SttCorrectionFeedback.created_at.desc())
            .limit(limit)
        ).all()
        pairs: list[tuple[str, str]] = []
        for row in rows:
            texts = row.transcripts if isinstance(row.transcripts, list) else []
            joined = "\n".join(str(t) for t in texts if t).strip()
            if not joined or not row.final_clinical:
                continue
            final = dict(row.final_clinical)
            # Compact assistant JSON matching parse schema
            payload = {
                "symptoms": final.get("symptoms") or [],
                "clinical_observations": final.get("clinical_observations") or [],
                "diagnoses": final.get("diagnoses") or [],
                "medications": final.get("medications") or [],
                "phi_detected": False,
                "phi_redaction_reason": None,
            }
            pairs.append(
                (
                    f"TRANSCRIPT:\n{joined[:1500]}",
                    json.dumps(payload, ensure_ascii=True),
                )
            )
        return pairs
    except Exception:  # noqa: BLE001
        return []


def stt_memory_metrics(db: Session, clinic_id: str) -> dict[str, Any]:
    """Clinic metrics: edit rate and top correction pairs."""
    from app.models.stt_memory import SttAlias, SttCorrectionFeedback

    rows = db.scalars(
        select(SttCorrectionFeedback).where(
            SttCorrectionFeedback.clinic_id == clinic_id
        )
    ).all()
    total = len(rows)
    with_edits = sum(1 for r in rows if int(r.med_name_edits or 0) > 0)
    edit_rate = round(with_edits / total, 4) if total else 0.0

    pair_counter: Counter[tuple[str, str]] = Counter()
    for r in rows:
        for src, dst, _kind in extract_alias_candidates(
            r.parsed_clinical if isinstance(r.parsed_clinical, dict) else {},
            r.final_clinical if isinstance(r.final_clinical, dict) else {},
        ):
            pair_counter[(_norm_key(src), dst.strip())] += 1

    top_pairs = [
        {"from": a, "to": b, "count": c}
        for (a, b), c in pair_counter.most_common(15)
    ]

    aliases = db.scalars(
        select(SttAlias)
        .where(SttAlias.clinic_id == clinic_id)
        .order_by(SttAlias.hit_count.desc())
        .limit(20)
    ).all()
    top_aliases = [
        {
            "from": a.from_term,
            "to": a.to_term,
            "kind": a.kind,
            "hit_count": int(a.hit_count or 0),
        }
        for a in aliases
    ]

    return {
        "feedback_count": total,
        "rx_with_med_name_edits": with_edits,
        "med_name_edit_rate": edit_rate,
        "top_correction_pairs": top_pairs,
        "top_aliases": top_aliases,
        "glossary_term_count": len(_default_glossary_terms(clinic_id))
        + len(env_glossary_terms()),
    }


def translate_glossary_hint(clinic_id: str | None = None) -> str:
    """Short hint appended to Hindi→English translation system prompt."""
    blob = whisper_vocab_blob(clinic_id=clinic_id)
    return (
        " Prefer these standard spellings when present in speech: "
        + blob
    )
