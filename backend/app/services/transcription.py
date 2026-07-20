"""In-memory Whisper transcription — audio never touches disk."""

from __future__ import annotations

import io
import threading
from typing import Any

from app.core.config import settings

_local_model: Any | None = None
_local_model_lock = threading.Lock()


def _default_cloud_model() -> str:
    if settings.whisper_model.strip():
        return settings.whisper_model.strip()
    if settings.whisper_provider.lower() == "groq":
        return "whisper-large-v3"
    return "whisper-1"


def _default_local_model_name() -> str:
    return settings.whisper_model.strip() or "base.en"


def _build_cloud_client():
    """Return an OpenAI-compatible client (OpenAI or Groq)."""
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

    return OpenAI(**kwargs)


def get_local_whisper_model():
    """
    Lazy-load a singleton faster-whisper model on CPU for the laptop POC.

    Model weights are cached on disk by the library (not patient audio).
    """
    global _local_model
    if _local_model is not None:
        return _local_model

    with _local_model_lock:
        if _local_model is not None:
            return _local_model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Run: .\\.venv\\Scripts\\pip install faster-whisper"
            ) from exc

        _local_model = WhisperModel(
            _default_local_model_name(),
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        return _local_model


def preload_local_whisper_model() -> None:
    """Warm the local model at startup when provider=local."""
    if settings.whisper_provider.lower() == "local":
        get_local_whisper_model()


def _transcribe_local(buffer: io.BytesIO) -> str:
    """Decode audio from BytesIO in memory and run faster-whisper on CPU."""
    from faster_whisper.audio import decode_audio

    buffer.seek(0)
    # PyAV decodes from the file-like object — no temp file for patient audio.
    audio = decode_audio(buffer, sampling_rate=16000)
    model = get_local_whisper_model()
    segments, _info = model.transcribe(
        audio,
        language="en",
        beam_size=1,  # faster for CPU POC
        vad_filter=True,
    )
    transcript = "".join(segment.text for segment in segments).strip()
    del audio
    return transcript


def _transcribe_cloud(buffer: io.BytesIO) -> str:
    client = _build_cloud_client()
    buffer.seek(0)
    result = client.audio.transcriptions.create(
        model=_default_cloud_model(),
        file=buffer,
    )
    return (result.text or "").strip()


def transcribe_audio_buffer(buffer: io.BytesIO) -> str:
    """
    Transcribe audio from an in-memory ``BytesIO`` via Whisper.

    Providers:
    - ``local``: faster-whisper on CPU (POC / self-hosted, $0)
    - ``openai`` / ``groq``: remote OpenAI-compatible API

    Patient audio is never written to disk. The buffer is cleared in ``finally``.
    """
    if buffer.getbuffer().nbytes == 0:
        raise ValueError("audio payload is empty")

    provider = settings.whisper_provider.lower().strip()
    buffer.seek(0)
    try:
        if provider == "local":
            return _transcribe_local(buffer)
        if provider in {"openai", "groq"}:
            return _transcribe_cloud(buffer)
        raise RuntimeError(
            f"Unsupported WHISPER_PROVIDER '{settings.whisper_provider}'. "
            "Use local, openai, or groq."
        )
    finally:
        buffer.seek(0)
        buffer.truncate(0)
        buffer.close()
