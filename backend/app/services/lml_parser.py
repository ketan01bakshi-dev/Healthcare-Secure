"""Structured LLM parser for clinical transcripts (PHI-safe)."""

from __future__ import annotations

import json
import re
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

_SYSTEM_PROMPT = """You are a clinical documentation parser for a healthcare system.

Your only job is to extract structured clinical content from a de-identified voice
prescription / encounter transcript.

STRICT RULES:
1. Output MUST be a single JSON object matching the provided schema exactly.
2. Format medical terms in standard clinical language (proper drug names, ICD-style
   diagnosis phrasing where possible, concise symptom labels).
3. Do NOT invent symptoms, observations, diagnoses, or medications that are not
   supported by the transcript. Use empty arrays when information is absent.
4. PHI SAFETY (CRITICAL):
   - If the transcript contains any clear-text patient name (e.g. "Mr. John Smith",
     "patient Jane Doe") OR any telephone / mobile number, you MUST NOT extract
     clinical content.
   - In that case set phi_detected=true, set phi_redaction_reason to a short
     explanation, and return EMPTY arrays for symptoms, clinical_observations,
     diagnoses, and medications (complete redaction of clinical context).
5. Never echo patient names or phone numbers in any output field.
6. Prefer empty strings for unknown medication child fields rather than guessing.
7. Return JSON only — no markdown fences, no commentary.
"""

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


def _build_llm_client() -> OpenAI:
    provider = _provider()
    kwargs: dict[str, Any] = {}

    if provider == "ollama":
        # Ollama's OpenAI-compatible server ignores the key but the SDK requires one.
        kwargs["api_key"] = settings.llm_api_key.strip() or "ollama"
        kwargs["base_url"] = (
            settings.llm_base_url.strip() or _DEFAULT_OLLAMA_BASE_URL
        )
        return OpenAI(**kwargs)

    if provider in {"openai", "groq"}:
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
        return OpenAI(**kwargs)

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. "
        "Use ollama, openai, or groq."
    )


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


def _finalize_parsed(parsed: ClinicalParseResult) -> ClinicalParseResult:
    if parsed.phi_detected:
        raise PHIContentError(
            parsed.phi_redaction_reason
            or "Patient name or telephone number detected; clinical context redacted"
        )
    return parsed


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


def _parse_with_ollama_json(
    client: OpenAI,
    model: str,
    transcript: str,
) -> ClinicalParseResult:
    """
    Ollama path: OpenAI-compatible chat API + local JSON → Pydantic validation.

    Does not use OpenAI `.parse()` (unsupported by Ollama). Still $0 / fully local.
    """
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT + "\n" + _JSON_SCHEMA_HINT},
            {
                "role": "user",
                "content": (
                    "Parse the following clinical voice transcript into the JSON schema.\n\n"
                    f"TRANSCRIPT:\n{transcript}"
                ),
            },
        ],
        temperature=0,
        # Ollama honors this via the OpenAI-compatible shim when supported.
        response_format={"type": "json_object"},
    )
    content = completion.choices[0].message.content
    if not content or not str(content).strip():
        raise RuntimeError(
            "Ollama returned an empty response. Is the model pulled "
            f"(ollama pull {model}) and is `ollama serve` running?"
        )

    try:
        payload = _extract_json_object(str(content))
        parsed = ClinicalParseResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise RuntimeError(
            f"Ollama returned invalid clinical JSON: {exc}"
        ) from exc

    return _finalize_parsed(parsed)


def parse_clinical_transcript(raw_transcript: str) -> ClinicalParseResult:
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
            return _parse_with_ollama_json(client, model, transcript)
        return _parse_with_openai_structured(client, model, transcript)
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
