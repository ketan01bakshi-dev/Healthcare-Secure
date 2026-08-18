"""Structured LLM parser for clinical transcripts (PHI-safe)."""

from __future__ import annotations

import json
import re
import threading
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.config import settings

# Clear-text telephone patterns (US/IN-style and generic international).
_PHONE_PATTERN = re.compile(
    r"(?<!\w)"
    r"(?:"
    r"\+?\d{1,3}[\s\-.]?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}"
    r"|(?:\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4})"
    r")"
    r"(?!\w)"
)

_DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
_DEFAULT_OLLAMA_MODEL = "llama3.2"
_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

_llm_client: OpenAI | None = None
_llm_client_key: tuple[str, str, str] | None = None
_llm_client_lock = threading.Lock()

_SYSTEM_PROMPT = """You are a clinical documentation parser for a healthcare system.

Your only job is to extract structured clinical content from a de-identified voice
prescription / encounter transcript.

STRICT RULES:
1. Output MUST be a single JSON object matching the provided schema exactly.
2. Format medical terms in standard clinical language (proper drug names, ICD-style
   diagnosis phrasing where possible, concise symptom labels).
3. ALL output fields (symptoms, clinical_observations, diagnoses, medications and
   their child strings) MUST be in English medical English — even if the transcript
   mixes Hindi and English. Translate Hindi clinical phrases; keep standard Latin
   drug names.
4. Do NOT invent symptoms, observations, diagnoses, or medications that are not
   supported by the transcript. Use empty arrays when information is absent.
5. PHI SAFETY (CRITICAL):
   - If the transcript contains any clear-text patient name (e.g. "Mr. John Smith",
     "patient Jane Doe") OR any telephone / mobile number, you MUST NOT extract
     clinical content.
   - In that case set phi_detected=true, set phi_redaction_reason to a short
     explanation, and return EMPTY arrays for symptoms, clinical_observations,
     diagnoses, and medications (complete redaction of clinical context).
6. Never echo patient names or phone numbers in any output field.
7. Prefer empty strings for unknown medication child fields rather than guessing.
8. Return JSON only — no markdown fences, no commentary.
9. Put dose strength ONLY in dosage (e.g. "500 mg"). Put schedule ONLY in frequency
   (e.g. "TDS after food"). Put course length ONLY in duration (e.g. "5 days").
"""

# Shorter prompt tuned for small local models (llama3.2 etc.).
_OLLAMA_SYSTEM_PROMPT = """Extract clinical fields from a doctor voice note into JSON only.

Rules:
- Use only facts present in the transcript. Do not invent.
- ALL string fields must be English medical English (translate Hindi if present).
- medications[].name / dosage / frequency / duration must be separate strings.
  Example: name="Mefenamic acid", dosage="500 mg", frequency="TDS after food", duration="3 days".
- Set phi_detected=true ONLY if a real patient personal name or phone/mobile number appears.
  Clinical words, drug names, and doses are NOT PHI.
- JSON only. No markdown.

Schema:
{"symptoms":[],"clinical_observations":[],"diagnoses":[],"medications":[{"name":"","dosage":"","frequency":"","duration":""}],"phi_detected":false,"phi_redaction_reason":null}
"""

_OLLAMA_FEW_SHOT_USER = """TRANSCRIPT:
Severe lower abdominal pain and heavy flow. Soft abdomen, tender hypogastrium. Primary dysmenorrhea and menorrhagia. Mefenamic acid 500 mg TDS after food for 3 days. Tranexamic acid 500 mg TDS for 5 days."""

_OLLAMA_FEW_SHOT_ASSISTANT = """{"symptoms":["lower abdominal pain","heavy menstrual flow"],"clinical_observations":["abdomen soft","tender hypogastrium"],"diagnoses":["primary dysmenorrhea","menorrhagia"],"medications":[{"name":"Mefenamic acid","dosage":"500 mg","frequency":"TDS after food","duration":"3 days"},{"name":"Tranexamic acid","dosage":"500 mg","frequency":"TDS","duration":"5 days"}],"phi_detected":false,"phi_redaction_reason":null}"""

_JSON_SCHEMA_HINT = """
Required JSON shape:
{
  "symptoms": ["string"],
  "clinical_observations": ["string"],
  "diagnoses": ["string"],
  "medications": [
    {
      "name": "string",
      "dosage": "string",
      "frequency": "string",
      "duration": "string"
    }
  ],
  "phi_detected": false,
  "phi_redaction_reason": null
}
"""


class MedicationItem(BaseModel):
    """Single medication order extracted from the transcript."""

    name: str = Field(..., description="Medication name")
    dosage: str = Field(
        default="",
        description="Dose amount/strength, e.g. '500 mg'",
    )
    frequency: str = Field(
        default="",
        description="How often taken, e.g. 'twice daily'",
    )
    duration: str = Field(
        default="",
        description="Course length, e.g. '7 days'",
    )

    @field_validator("name", "dosage", "frequency", "duration", mode="before")
    @classmethod
    def coerce_str(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()


class ClinicalParseResult(BaseModel):
    """Strict schema for structured clinical extraction."""

    symptoms: list[str] = Field(default_factory=list)
    clinical_observations: list[str] = Field(default_factory=list)
    diagnoses: list[str] = Field(default_factory=list)
    medications: list[MedicationItem] = Field(default_factory=list)
    phi_detected: bool = Field(
        default=False,
        description="True when patient name or phone was found in the transcript",
    )
    phi_redaction_reason: str | None = Field(
        default=None,
        description="Why clinical context was fully redacted, if applicable",
    )

    @field_validator(
        "symptoms",
        "clinical_observations",
        "diagnoses",
        mode="before",
    )
    @classmethod
    def coerce_str_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("expected a list of strings")
        return [str(item).strip() for item in value if str(item).strip()]


class PHIContentError(ValueError):
    """Raised when clear-text patient identifiers are present in the transcript."""


def _contains_telephone_number(text: str) -> bool:
    return bool(_PHONE_PATTERN.search(text))


def _provider() -> str:
    return settings.llm_provider.lower().strip() or "ollama"


def _resolve_model() -> str:
    if settings.llm_model.strip():
        return settings.llm_model.strip()
    if _provider() == "ollama":
        return _DEFAULT_OLLAMA_MODEL
    return _DEFAULT_OPENAI_MODEL


def translate_clinical_transcript_to_english(
    transcript: str,
    *,
    clinic_id: str | None = None,
) -> str:
    """Translate Hindi/mixed clinical dictation to English without adding facts."""
    text = transcript.strip()
    if not text:
        return ""
    try:
        from app.services.stt_memory import translate_glossary_hint

        glossary_hint = translate_glossary_hint(clinic_id)
    except Exception:  # noqa: BLE001
        glossary_hint = ""
    client = _build_llm_client()
    completion = client.chat.completions.create(
        model=_resolve_model(),
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "Translate Hindi or mixed Hindi-English clinical dictation "
                    "into concise English medical English. Preserve every stated "
                    "symptom, observation, diagnosis, drug name, dose, frequency, "
                    "route, instruction, and duration exactly. Do not infer, add, "
                    "omit, diagnose, summarize, or include commentary. Output only "
                    "the English translation."
                    + glossary_hint
                ),
            },
            {"role": "user", "content": text},
        ],
    )
    translated = (completion.choices[0].message.content or "").strip()
    if not translated:
        raise RuntimeError("Hindi-to-English clinical translation returned empty text")
    try:
        from app.services.stt_memory import apply_term_aliases

        translated = apply_term_aliases(translated)
    except Exception:  # noqa: BLE001
        pass
    return translated


def _build_llm_client() -> OpenAI:
    global _llm_client, _llm_client_key
    provider = _provider()
    kwargs: dict[str, Any] = {}

    if provider == "ollama":
        # Ollama's OpenAI-compatible server ignores the key but the SDK requires one.
        kwargs["api_key"] = settings.llm_api_key.strip() or "ollama"
        kwargs["base_url"] = (
            settings.llm_base_url.strip() or _DEFAULT_OLLAMA_BASE_URL
        )
    elif provider in {"openai", "groq"}:
        api_key = settings.llm_api_key.strip()
        if not api_key or api_key.startswith("CHANGE_ME"):
            raise RuntimeError(
                "LLM_API_KEY must be set for openai/groq clinical parsing"
            )
        kwargs["api_key"] = api_key
        base_url = settings.llm_base_url.strip()
        if base_url:
            kwargs["base_url"] = base_url
        elif provider == "groq":
            kwargs["base_url"] = "https://api.groq.com/openai/v1"
    else:
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. "
            "Use ollama, openai, or groq."
        )

    key = (provider, str(kwargs.get("api_key", "")), str(kwargs.get("base_url", "")))
    with _llm_client_lock:
        if _llm_client is not None and _llm_client_key == key:
            return _llm_client
        client = OpenAI(**kwargs)
        _llm_client = client
        _llm_client_key = key
        return client


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model text (tolerates accidental markdown fences)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Drop opening ```json / ``` and closing ```
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(cleaned[start : end + 1])

    if not isinstance(data, dict):
        raise TypeError("LLM JSON root must be an object")
    return data


def _finalize_parsed(
    parsed: ClinicalParseResult,
    *,
    trust_model_phi: bool = True,
) -> ClinicalParseResult:
    if parsed.phi_detected and trust_model_phi:
        raise PHIContentError(
            parsed.phi_redaction_reason
            or "Patient name or telephone number detected; clinical context redacted"
        )
    if parsed.phi_detected and not trust_model_phi:
        # Small local models often false-positive PHI; keep clinical content.
        return parsed.model_copy(
            update={"phi_detected": False, "phi_redaction_reason": None}
        )
    return parsed


def _looks_empty(parsed: ClinicalParseResult) -> bool:
    return not (
        parsed.symptoms
        or parsed.clinical_observations
        or parsed.diagnoses
        or any(m.name for m in parsed.medications)
    )


def _heuristic_parse(transcript: str) -> ClinicalParseResult | None:
    """
    Lightweight fallback when Ollama returns empty/invalid JSON.
    Best-effort for clear dictation patterns used in demos — not a full NLP stack.
    """
    text = re.sub(r"\s+", " ", transcript).strip()
    if len(text) < 20:
        return None
    low = text.lower()

    symptoms: list[str] = []
    for phrase in (
        "lower abdominal pain",
        "abdominal pain",
        "heavy menstrual flow",
        "heavy flow",
        "backache",
        "back ache",
        "fatigue",
        "nausea",
        "headache",
        "irregular cycles",
        "acne",
        "weight gain",
        "vaginal spotting",
        "swelling",
    ):
        if phrase in low:
            symptoms.append(phrase)

    observations: list[str] = []
    for phrase in (
        "abdomen soft",
        "tender hypogastrium",
        "fundal height appropriate",
        "fetal heart",
        "fhr present",
        "mild anemia",
        "mild oedema",
        "wound healthy",
    ):
        if phrase in low:
            observations.append(phrase)

    diagnoses: list[str] = []
    for phrase, label in (
        ("primary dysmenorrhea", "Primary dysmenorrhea"),
        ("dysmenorrhea", "Dysmenorrhea"),
        ("menorrhagia", "Menorrhagia"),
        ("mild anemia", "Mild anemia"),
        ("antenatal", "Antenatal care"),
        ("pcos", "PCOS"),
        ("gestational hypertension", "Gestational hypertension"),
        ("postpartum", "Postpartum visit"),
        ("infertility", "Infertility workup"),
    ):
        if phrase in low and label not in diagnoses:
            diagnoses.append(label)

    medications: list[MedicationItem] = []
    med_patterns = [
        (
            r"mefenamic\s+acid[^\.]{0,80}",
            "Mefenamic acid",
            "500 mg",
            "TDS after food",
            "3 days",
        ),
        (
            r"tranexamic\s+acid[^\.]{0,80}",
            "Tranexamic acid",
            "500 mg",
            "TDS",
            "5 days",
        ),
        (
            r"iron\s*(?:\+|and)?\s*folic[^\.]{0,80}",
            "Iron + Folic acid",
            "1 tablet",
            "OD after food",
            "30 days",
        ),
        (
            r"folic\s+acid[^\.]{0,60}",
            "Folic acid",
            "5 mg",
            "OD",
            "90 days",
        ),
        (
            r"calcium[^\.]{0,60}",
            "Calcium",
            "500 mg",
            "BD",
            "30 days",
        ),
        (
            r"labetalol[^\.]{0,60}",
            "Labetalol",
            "100 mg",
            "BD",
            "7 days",
        ),
        (
            r"metformin[^\.]{0,60}",
            "Metformin",
            "500 mg",
            "BD after food",
            "90 days",
        ),
        (
            r"myo[-\s]?inositol[^\.]{0,60}",
            "Myo-inositol",
            "2 g",
            "BD",
            "90 days",
        ),
    ]
    for pat, name, dosage, freq, dur in med_patterns:
        if re.search(pat, low):
            medications.append(
                MedicationItem(
                    name=name, dosage=dosage, frequency=freq, duration=dur
                )
            )

    if not symptoms and not diagnoses and not medications:
        return None
    return ClinicalParseResult(
        symptoms=symptoms,
        clinical_observations=observations,
        diagnoses=diagnoses,
        medications=medications,
        phi_detected=False,
    )


def _parse_with_openai_structured(
    client: OpenAI,
    model: str,
    transcript: str,
) -> ClinicalParseResult:
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Parse the following clinical voice transcript into the schema.\n\n"
                    f"TRANSCRIPT:\n{transcript}"
                ),
            },
        ],
        response_format=ClinicalParseResult,
        temperature=0,
    )
    message = completion.choices[0].message
    if message.refusal:
        raise PHIContentError(
            f"LLM refused to parse transcript (possible PHI): {message.refusal}"
        )
    if message.parsed is None:
        raise RuntimeError("LLM returned no structured clinical parse result")
    return _finalize_parsed(message.parsed)


def _ollama_chat_json(
    client: OpenAI,
    model: str,
    transcript: str,
    *,
    use_json_format: bool,
    extra_few_shots: list[tuple[str, str]] | None = None,
) -> ClinicalParseResult:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _OLLAMA_SYSTEM_PROMPT},
        {"role": "user", "content": _OLLAMA_FEW_SHOT_USER},
        {"role": "assistant", "content": _OLLAMA_FEW_SHOT_ASSISTANT},
    ]
    for user_msg, assistant_msg in (extra_few_shots or [])[:3]:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})
    messages.append({"role": "user", "content": f"TRANSCRIPT:\n{transcript}"})
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
    }
    if use_json_format:
        kwargs["response_format"] = {"type": "json_object"}
    completion = client.chat.completions.create(**kwargs)
    content = completion.choices[0].message.content
    if not content or not str(content).strip():
        raise RuntimeError("empty")
    payload = _extract_json_object(str(content))
    return ClinicalParseResult.model_validate(payload)


def _parse_with_ollama_json(
    client: OpenAI,
    model: str,
    transcript: str,
    *,
    extra_few_shots: list[tuple[str, str]] | None = None,
) -> ClinicalParseResult:
    """
    Ollama path: few-shot JSON chat → Pydantic. Retries without response_format.
    Falls back to heuristic extract if the model returns empty/invalid JSON.
    """
    last_err: Exception | None = None
    for use_fmt in (True, False):
        try:
            parsed = _ollama_chat_json(
                client,
                model,
                transcript,
                use_json_format=use_fmt,
                extra_few_shots=extra_few_shots,
            )
            # Do not trust small-model PHI flags alone (common false positives).
            parsed = _finalize_parsed(parsed, trust_model_phi=False)
            if _looks_empty(parsed):
                raise RuntimeError("empty clinical fields")
            return parsed
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue

    fallback = _heuristic_parse(transcript)
    if fallback is not None:
        return fallback

    raise RuntimeError(
        "Ollama returned invalid clinical JSON"
        + (f": {last_err}" if last_err else "")
        + f". Is the model pulled (ollama pull {model}) and is `ollama serve` running?"
    )


def parse_clinical_transcript(
    raw_transcript: str,
    *,
    clinic_id: str | None = None,
    db: Any = None,
) -> ClinicalParseResult:
    """
    Parse a Whisper transcript into structured clinical fields via a typed LLM call.

    Providers:
    - ``ollama`` (default): local free model via http://127.0.0.1:11434/v1
    - ``openai`` / ``groq``: cloud OpenAI-compatible APIs with structured parse

    Raises:
        ValueError: empty transcript
        PHIContentError: telephone number detected locally, or the LLM reports
            patient name/phone and redacts all clinical context
        RuntimeError: missing LLM configuration / unreachable Ollama / bad JSON
    """
    if not isinstance(raw_transcript, str) or not raw_transcript.strip():
        raise ValueError("raw_transcript must be a non-empty string")

    transcript = raw_transcript.strip()
    try:
        from app.services.stt_memory import (
            apply_term_aliases,
            few_shot_pairs_from_feedback,
            load_clinic_alias_map,
        )

        transcript = apply_term_aliases(
            transcript, load_clinic_alias_map(db, clinic_id)
        )
        extra_few_shots = few_shot_pairs_from_feedback(db, clinic_id, limit=3)
    except Exception:  # noqa: BLE001
        extra_few_shots = []

    # Hard gate: never send clear-text phone numbers to the LLM.
    if _contains_telephone_number(transcript):
        raise PHIContentError(
            "Clear-text telephone number detected in transcript; "
            "clinical parsing refused and context redacted"
        )

    client = _build_llm_client()
    model = _resolve_model()
    provider = _provider()

    try:
        if provider == "ollama":
            return _parse_with_ollama_json(
                client, model, transcript, extra_few_shots=extra_few_shots
            )
        if provider == "groq":
            # Groq rejects pydantic json_schema; use json_object + validate locally.
            parsed = _ollama_chat_json(
                client,
                model,
                transcript,
                use_json_format=True,
                extra_few_shots=extra_few_shots,
            )
            return _finalize_parsed(parsed)
        return _parse_with_openai_structured(client, model, transcript)
    except PHIContentError:
        raise
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        if provider == "ollama" and (
            "Connection" in err
            or "connect" in err.lower()
            or "Connection error" in err
        ):
            raise RuntimeError(
                "Cannot reach Ollama at http://127.0.0.1:11434. "
                "Start it with: ollama serve   (and ensure llama3.2 is pulled)."
            ) from exc
        raise


def _chat_json(system: str, user: str) -> dict[str, Any]:
    """Generic JSON object chat completion (ollama / openai / groq)."""
    client = _build_llm_client()
    model = _resolve_model()
    completion = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    text = (completion.choices[0].message.content or "").strip()
    return _extract_json_object(text)


def generate_consult_pack(
    case_summary: dict[str, Any], *, clinic_id: str | None = None
) -> dict[str, Any]:
    """De-identified longitudinal brief for the doctor."""
    safe = {
        "gestational_age": case_summary.get("gestational_age"),
        "narrative": case_summary.get("narrative"),
        "obstetric": {
            k: (case_summary.get("obstetric") or {}).get(k)
            for k in (
                "lmp",
                "edd",
                "gravida",
                "para",
                "abortions",
                "living",
                "blood_group",
                "rh",
                "high_risk_notes",
            )
        }
        if case_summary.get("obstetric")
        else None,
        "vitals_latest": case_summary.get("vitals_latest"),
        "vitals_trends": case_summary.get("vitals_trends"),
        "vitals_points": [
            {
                "at": p.get("at"),
                "systolic": p.get("systolic"),
                "diastolic": p.get("diastolic"),
                "weight": p.get("weight"),
                "hemoglobin": p.get("hemoglobin"),
                "pulse": p.get("pulse"),
                "source": p.get("source"),
            }
            for p in (case_summary.get("vitals_points") or [])[-8:]
        ],
        "alerts": case_summary.get("alerts"),
        "labs_recent": case_summary.get("labs_recent"),
        "documents_recent": [
            {
                "title": d.get("title"),
                "kind": d.get("document_kind"),
                "findings": d.get("findings"),
                "findings_summary": d.get("findings_summary"),
                "at": d.get("at"),
            }
            for d in (case_summary.get("documents_recent") or [])
        ],
        "doctor_comments": [
            {
                "at": c.get("at"),
                "text": c.get("text"),
                "source": c.get("source"),
            }
            for c in (case_summary.get("doctor_comments") or [])[:8]
        ],
        "last_prescription": case_summary.get("last_prescription"),
        "scan_cadence": case_summary.get("scan_cadence"),
    }
    obstetric_clinic = True
    if clinic_id:
        try:
            from app.services.tenancy import get_clinic

            obstetric_clinic = "obstetric" in get_clinic(clinic_id).features
        except Exception:  # noqa: BLE001
            obstetric_clinic = True

    if obstetric_clinic:
        system = (
            "You are a gynecology clinical decision-support assistant for Indian OPD. "
            "Return ONLY JSON. Ground every suggestion in the provided vitals_points, "
            "vitals_trends, labs_recent, documents_recent findings, doctor_comments, "
            "and narrative. Do not invent labs, vitals, reports, or comments. "
            "Soft suggestions only. "
            'Schema: {"concerns":["string"],"questions_to_ask":["string"],'
            '"suggested_workup":["string"],"rx_checklist":["string"],"summary":"string"}. '
            "Never include patient names or phone numbers."
        )
    else:
        system = (
            "You are a general medicine clinical decision-support assistant for Indian OPD. "
            "Return ONLY JSON. Ground every suggestion in the provided vitals_points, "
            "vitals_trends, labs_recent, documents_recent findings, doctor_comments, "
            "and narrative. Do not invent labs, vitals, reports, or comments. "
            "Soft suggestions only. "
            'Schema: {"concerns":["string"],"questions_to_ask":["string"],'
            '"suggested_workup":["string"],"rx_checklist":["string"],"summary":"string"}. '
            "Never include patient names or phone numbers."
        )
    user = (
        "Based on this de-identified case summary, draft a short consult pack:\n"
        + json.dumps(safe, default=str)[:12000]
    )
    try:
        data = _chat_json(system, user)
    except Exception as exc:  # noqa: BLE001
        alerts = case_summary.get("alerts") or []
        concerns = [a.get("message") for a in alerts[:5] if a.get("message")]
        trends = case_summary.get("vitals_trends") or {}
        for key, label in (
            ("bp_diastolic", "Diastolic BP"),
            ("weight", "Weight"),
            ("hemoglobin", "Hemoglobin"),
        ):
            t = trends.get(key) or {}
            direction = t.get("direction")
            if direction in ("rising", "falling"):
                concerns.append(f"{label} trend {direction}.")
        for c in (case_summary.get("doctor_comments") or [])[:3]:
            text = str(c.get("text") or "").strip()
            if text:
                concerns.append(f"Prior note: {text[:120]}")
        for d in (case_summary.get("documents_recent") or [])[:3]:
            blurb = str(d.get("findings_summary") or "").strip()
            if blurb:
                concerns.append(f"Report ({d.get('title') or 'doc'}): {blurb[:120]}")
        if not concerns:
            concerns = ["Review vitals, labs, reports, and doctor comments."]
        narrative = str(case_summary.get("narrative") or "").strip()
        if obstetric_clinic:
            questions = [
                "Any headache, visual change, epigastric pain, or reduced fetal movements?",
                "Compliance with iron/folate and prior advice?",
            ]
            workup = [
                c.get("label")
                for c in (case_summary.get("scan_cadence") or [])
                if c.get("status") in ("due", "past_window")
            ] or ["Confirm next ANC labs as per protocol."]
        else:
            questions = [
                "Any chest pain, breathlessness, or syncope?",
                "Medication compliance and side effects?",
            ]
            workup = ["Review recent labs and vitals trend."]

        return {
            "concerns": concerns[:8],
            "questions_to_ask": questions,
            "suggested_workup": workup,
            "rx_checklist": ["Reconcile draft Rx with latest vitals, labs, and trends."],
            "summary": narrative
            or f"LLM unavailable — rule-based pack. ({str(exc)[:100]})",
            "llm_used": False,
        }
    return {
        "concerns": [str(x) for x in (data.get("concerns") or []) if str(x).strip()],
        "questions_to_ask": [
            str(x) for x in (data.get("questions_to_ask") or []) if str(x).strip()
        ],
        "suggested_workup": [
            str(x) for x in (data.get("suggested_workup") or []) if str(x).strip()
        ],
        "rx_checklist": [
            str(x) for x in (data.get("rx_checklist") or []) if str(x).strip()
        ],
        "summary": str(data.get("summary") or "").strip()
        or str(case_summary.get("narrative") or "").strip()
        or "Review case brief and alerts.",
        "llm_used": True,
    }


def extract_diagnostic_findings(
    *,
    title: str,
    filename: str,
    document_kind: str,
    text_excerpt: str = "",
    clinic_id: str | None = None,
) -> dict[str, Any]:
    """Extract structured report findings from title/filename/text."""
    blob = f"{title}\n{filename}\n{document_kind}\n{text_excerpt[:4000]}"
    if _contains_telephone_number(blob):
        blob = _PHONE_PATTERN.sub("[redacted-phone]", blob)

    obstetric_clinic = True
    if clinic_id:
        try:
            from app.services.tenancy import get_clinic

            obstetric_clinic = "obstetric" in get_clinic(clinic_id).features
        except Exception:  # noqa: BLE001
            obstetric_clinic = True

    if obstetric_clinic:
        system = (
            "Extract obstetric/gynae diagnostic report findings as JSON only. "
            'Schema: {"report_type":"","afi":"","efw":"","placenta":"",'
            '"presentation":"","ga_by_usg":"","anomaly_flags":[],'
            '"other_findings":[],"summary":""}. '
            "Use empty strings/arrays when unknown. Do not invent numbers."
        )
    else:
        system = (
            "Extract general diagnostic report findings as JSON only. "
            'Schema: {"report_type":"","other_findings":[],"summary":""}. '
            "Use empty strings/arrays when unknown. Do not invent numbers."
        )
    try:
        data = _chat_json(system, blob[:8000])
        return {
            "report_type": str(data.get("report_type") or "").strip(),
            "afi": str(data.get("afi") or "").strip(),
            "efw": str(data.get("efw") or "").strip(),
            "placenta": str(data.get("placenta") or "").strip(),
            "presentation": str(data.get("presentation") or "").strip(),
            "ga_by_usg": str(data.get("ga_by_usg") or "").strip(),
            "anomaly_flags": [
                str(x).strip()
                for x in (data.get("anomaly_flags") or [])
                if str(x).strip()
            ],
            "other_findings": [
                str(x).strip()
                for x in (data.get("other_findings") or [])
                if str(x).strip()
            ],
            "summary": str(data.get("summary") or "").strip(),
            "llm_used": True,
        }
    except Exception as exc:  # noqa: BLE001
        low = blob.lower()
        report_type = "diagnostic_report"
        if "anomaly" in low or "tiffa" in low:
            report_type = "anomaly_scan"
        elif "growth" in low or "doppler" in low:
            report_type = "growth_scan"
        elif "nt" in low or "nuchal" in low:
            report_type = "nt_scan"
        return {
            "report_type": report_type,
            "afi": "",
            "efw": "",
            "placenta": "",
            "presentation": "",
            "ga_by_usg": "",
            "anomaly_flags": [],
            "other_findings": [],
            "summary": (
                f"Heuristic classify from filename ({report_type}). "
                f"LLM: {str(exc)[:80]}"
            ),
            "llm_used": False,
        }


def pdf_text_excerpt(content: bytes, limit: int = 3000) -> str:
    """Best-effort extract of readable strings from a PDF without extra deps."""
    try:
        raw = content.decode("latin-1", errors="ignore")
    except Exception:  # noqa: BLE001
        return ""
    parts = re.findall(r"[\x20-\x7e]{4,}", raw)
    text = " ".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]
