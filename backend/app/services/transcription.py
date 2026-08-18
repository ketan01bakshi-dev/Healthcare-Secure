"""In-memory Whisper transcription — audio never touches disk.

Supports English transcription and Hindi→English translation for voice Rx.
"""

from __future__ import annotations

import io
import re
import threading
from typing import Any, Literal

from app.core.config import settings

SpeakLanguage = Literal["en", "hi"]

_local_models: dict[str, Any] = {}
_local_model_lock = threading.Lock()

_cloud_client: Any = None
_cloud_client_key: tuple[str, str] | None = None
_cloud_client_lock = threading.Lock()

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


_MED_VOCAB_GYNAE = (
    "Medications: mefenamic acid, tranexamic acid, iron folic acid, calcium, "
    "labetalol, metformin, myo-inositol, folic acid. "
    "Terms: dysmenorrhea, menorrhagia, antenatal, anemia, PCOS, fundus, fetal heart."
)

_MED_VOCAB_GP = (
    "Medications: paracetamol, azithromycin, amlodipine, telmisartan, metformin, "
    "atorvastatin, levothyroxine, pantoprazole, omeprazole, salbutamol. "
    "Terms: hypertension, diabetes, URTI, cough, fever, HbA1c, hypothyroidism."
)


def _is_obstetric_clinic(clinic_id: str | None) -> bool:
    if not clinic_id:
        return True
    try:
        from app.services.tenancy import get_clinic

        return "obstetric" in get_clinic(clinic_id).features
    except Exception:  # noqa: BLE001
        return True


def _med_vocab(
    *,
    clinic_id: str | None = None,
    db: Any = None,
    clinic_aliases: list[str] | None = None,
) -> str:
    """Clinic-aware Whisper vocabulary (defaults + env + mined aliases)."""
    try:
        from app.services.stt_memory import (
            clinic_alias_terms_for_prompt,
            whisper_vocab_blob,
        )

        aliases = clinic_aliases
        if aliases is None:
            aliases = clinic_alias_terms_for_prompt(db, clinic_id)
        return whisper_vocab_blob(
            clinic_id=clinic_id,
            clinic_aliases=aliases,
        )
    except Exception:  # noqa: BLE001
        return _MED_VOCAB_GYNAE if _is_obstetric_clinic(clinic_id) else _MED_VOCAB_GP


def _default_cloud_model(*, source_language: SpeakLanguage) -> str:
    if settings.whisper_model.strip():
        return settings.whisper_model.strip()
    if settings.whisper_provider.lower() == "groq":
        return "whisper-large-v3-turbo"
    return "whisper-1"


def _local_model_name(source_language: SpeakLanguage) -> str:
    """English may use *.en; Hindi requires a multilingual checkpoint."""
    configured = settings.whisper_model.strip()
    if source_language == "hi":
        if not configured or configured.endswith(".en"):
            return "base"
        return configured
    return configured or "base.en"


def _build_cloud_client():
    """Return a reused OpenAI-compatible client (OpenAI or Groq)."""
    global _cloud_client, _cloud_client_key
    from openai import OpenAI

    api_key = settings.whisper_api_key.strip()
    if not api_key or api_key.startswith("CHANGE_ME"):
        raise RuntimeError(
            "WHISPER_API_KEY must be set to a valid OpenAI or Groq API key"
        )

    kwargs: dict[str, str] = {"api_key": api_key}
    base_url = settings.whisper_base_url.strip()
    if base_url:
        kwargs["base_url"] = base_url
    elif settings.whisper_provider.lower() == "groq":
        kwargs["base_url"] = "https://api.groq.com/openai/v1"

    key = (api_key, kwargs.get("base_url", ""))
    with _cloud_client_lock:
        if _cloud_client is not None and _cloud_client_key == key:
            return _cloud_client
        client = OpenAI(**kwargs)
        _cloud_client = client
        _cloud_client_key = key
        return client


def get_local_whisper_model(source_language: SpeakLanguage = "en"):
    """
    Lazy-load a faster-whisper model on CPU for the laptop POC.

    Models are cached by name so English (*.en) and multilingual Hindi
    checkpoints can coexist. Weights are cached on disk by the library
    (not patient audio).
    """
    name = _local_model_name(source_language)
    cached = _local_models.get(name)
    if cached is not None:
        return cached

    with _local_model_lock:
        cached = _local_models.get(name)
        if cached is not None:
            return cached
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Run: .\\.venv\\Scripts\\pip install faster-whisper"
            ) from exc

        model = WhisperModel(
            name,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        _local_models[name] = model
        return model


def preload_local_whisper_model() -> None:
    """Warm the local English model at startup when provider=local."""
    if settings.whisper_provider.lower() == "local":
        get_local_whisper_model("en")


def _initial_prompt(
    source_language: SpeakLanguage,
    *,
    clinic_id: str | None = None,
    db: Any = None,
    clinic_aliases: list[str] | None = None,
) -> str:
    vocab = _med_vocab(
        clinic_id=clinic_id, db=db, clinic_aliases=clinic_aliases
    )
    if _is_obstetric_clinic(clinic_id):
        if source_language == "hi":
            return (
                "Hindi gynecology clinic prescription dictation. "
                "Translate clinical content into clear English medical English. "
                + vocab
            )
        return "Gynecology clinic prescription dictation in English. " + vocab
    if source_language == "hi":
        return (
            "Hindi general medicine clinic prescription dictation. "
            "Translate clinical content into clear English medical English. "
            + vocab
        )
    return "General medicine clinic prescription dictation in English. " + vocab


def _transcribe_local(
    buffer: io.BytesIO,
    source_language: SpeakLanguage,
    *,
    clinic_id: str | None = None,
    db: Any = None,
    clinic_aliases: list[str] | None = None,
) -> str:
    """Decode audio from BytesIO in memory and run faster-whisper on CPU."""
    from faster_whisper.audio import decode_audio

    buffer.seek(0)
    # PyAV decodes from the file-like object — no temp file for patient audio.
    audio = decode_audio(buffer, sampling_rate=16000)
    model = get_local_whisper_model(source_language)
    kwargs: dict[str, Any] = {
        "beam_size": 3,
        "best_of": 3,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 400},
        "condition_on_previous_text": False,
        "initial_prompt": _initial_prompt(
            source_language,
            clinic_id=clinic_id,
            db=db,
            clinic_aliases=clinic_aliases,
        ),
    }
    if source_language == "hi":
        kwargs["language"] = "hi"
        kwargs["task"] = "translate"
    else:
        kwargs["language"] = "en"
        kwargs["task"] = "transcribe"

    segments, _info = model.transcribe(audio, **kwargs)
    transcript = "".join(segment.text for segment in segments).strip()
    del audio
    return transcript


def _prepare_upload_file(buffer: io.BytesIO):
    buffer.seek(0)
    # OpenAI SDK expects a file-like with a name for multipart.
    if not getattr(buffer, "name", None):
        buffer.name = "prescription.wav"  # type: ignore[attr-defined]
    return buffer


def transcript_needs_english_translation(text: str) -> bool:
    """True when Whisper Hindi output still contains Devanagari (must LLM-translate)."""
    return bool(_DEVANAGARI_RE.search(text or ""))


def _alias_terms(alias_map: dict[str, str] | None) -> list[str] | None:
    if not alias_map:
        return None
    out: list[str] = []
    for src, dst in alias_map.items():
        out.append(dst)
        out.append(src)
    return out


def _transcribe_cloud(
    buffer: io.BytesIO,
    source_language: SpeakLanguage,
    *,
    clinic_id: str | None = None,
    db: Any = None,
    alias_map: dict[str, str] | None = None,
) -> str:
    client = _build_cloud_client()
    model = _default_cloud_model(source_language=source_language)
    upload = _prepare_upload_file(buffer)
    clinic_aliases = _alias_terms(alias_map)
    prompt = _initial_prompt(
        source_language,
        clinic_id=clinic_id,
        db=db,
        clinic_aliases=clinic_aliases,
    )

    if source_language == "hi" and settings.whisper_provider.lower() == "groq":
        # Groq turbo cannot use /translations, while large-v3 may be disabled
        # at the organization level. Transcribe Hindi, then translate through
        # the already-configured clinical LLM when Devanagari remains.
        result = client.audio.transcriptions.create(
            model=model,
            file=upload,
            language="hi",
            prompt=prompt,
        )
        hindi_text = (result.text or "").strip()
        if not hindi_text:
            return ""
        if not transcript_needs_english_translation(hindi_text):
            return hindi_text
        from app.services.lml_parser import (
            translate_clinical_transcript_to_english,
        )

        return translate_clinical_transcript_to_english(
            hindi_text, clinic_id=clinic_id
        )
    if source_language == "hi":
        # OpenAI/Groq translations endpoint: source audio → English text.
        result = client.audio.translations.create(
            model=model,
            file=upload,
            prompt=prompt,
        )
    else:
        result = client.audio.transcriptions.create(
            model=model,
            file=upload,
            language="en",
            prompt=prompt,
        )
    return (result.text or "").strip()


def normalize_speak_language(value: str | None) -> SpeakLanguage:
    lang = (value or "en").strip().lower()
    if lang in {"en", "english"}:
        return "en"
    if lang in {"hi", "hindi", "hin"}:
        return "hi"
    raise ValueError("language must be en or hi")


def transcribe_audio_buffer(
    buffer: io.BytesIO,
    *,
    source_language: SpeakLanguage | str = "en",
    clinic_id: str | None = None,
    db: Any = None,
    alias_map: dict[str, str] | None = None,
) -> str:
    """
    Transcribe audio from an in-memory ``BytesIO`` via Whisper.

    - ``en``: English transcription (output English)
    - ``hi``: Hindi speech translated to English for doctor review

    Providers:
    - ``local``: faster-whisper on CPU (POC / self-hosted, $0)
    - ``openai`` / ``groq``: remote OpenAI-compatible API

    Patient audio is never written to disk. The buffer is cleared in ``finally``.
    """
    if buffer.getbuffer().nbytes == 0:
        raise ValueError("audio payload is empty")

    lang = normalize_speak_language(str(source_language))
    provider = settings.whisper_provider.lower().strip()
    resolved_aliases = alias_map
    if resolved_aliases is None:
        try:
            from app.services.stt_memory import load_clinic_alias_map

            resolved_aliases = load_clinic_alias_map(db, clinic_id)
        except Exception:  # noqa: BLE001
            resolved_aliases = {}
    clinic_aliases = _alias_terms(resolved_aliases)
    buffer.seek(0)
    try:
        if provider == "local":
            transcript = _transcribe_local(
                buffer,
                lang,
                clinic_id=clinic_id,
                db=db,
                clinic_aliases=clinic_aliases,
            )
        elif provider in {"openai", "groq"}:
            transcript = _transcribe_cloud(
                buffer,
                lang,
                clinic_id=clinic_id,
                db=db,
                alias_map=resolved_aliases,
            )
        else:
            raise RuntimeError(
                f"Unsupported WHISPER_PROVIDER '{settings.whisper_provider}'. "
                "Use local, openai, or groq."
            )
        try:
            from app.services.stt_memory import apply_term_aliases

            transcript = apply_term_aliases(transcript, resolved_aliases)
        except Exception:  # noqa: BLE001
            pass
        return transcript
    finally:
        buffer.seek(0)
        buffer.truncate(0)
        buffer.close()
