"""Tests for English/Hindi voice prescription transcription routing."""

from __future__ import annotations

import io
import os
from unittest.mock import MagicMock, patch

# Isolated DB / secrets before app imports (same pattern as test_p1_reliability).
os.environ["DATABASE_URL"] = "sqlite:///./test_healthcare.db"
os.environ["SECRET_SALT"] = "test_salt_not_for_production_0123456789abcdef"
os.environ["SECRET_KEY"] = "test_secret_key_not_for_production_01234567"
os.environ["CLINICS"] = (
    "default|Test Clinic|||testpass|"
    "voice_rx,labs,queue,appointments,analytics,obstetric,video_consult"
)
os.environ["CLINIC_USERS"] = (
    "dr1|Dr Test|doctor|1234;"
    "nurse1|Nurse Test|staff|5678;"
    "lab1|Lab Test|lab|9999"
)
os.environ["APP_ENV"] = "development"
os.environ["REQUIRE_CLINIC_USERS"] = "false"
os.environ["WHISPER_PRELOAD"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.transcription import (
    _default_cloud_model,
    _local_model_name,
    normalize_speak_language,
    transcribe_audio_buffer,
    transcript_needs_english_translation,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _session(client: TestClient, user_id: str, pin: str) -> dict[str, str]:
    from tests.auth_helpers import session_headers

    return session_headers(client, user_id, pin)


def test_normalize_speak_language_accepts_en_hi() -> None:
    assert normalize_speak_language("en") == "en"
    assert normalize_speak_language("EN") == "en"
    assert normalize_speak_language("english") == "en"
    assert normalize_speak_language("hi") == "hi"
    assert normalize_speak_language("Hindi") == "hi"
    assert normalize_speak_language(None) == "en"


def test_normalize_speak_language_rejects_other() -> None:
    with pytest.raises(ValueError, match="en or hi"):
        normalize_speak_language("fr")
    with pytest.raises(ValueError, match="en or hi"):
        normalize_speak_language("ta")


def test_local_model_name_hindi_avoids_english_only() -> None:
    with patch("app.services.transcription.settings") as settings:
        settings.whisper_model = "base.en"
        assert _local_model_name("en") == "base.en"
        assert _local_model_name("hi") == "base"

        settings.whisper_model = "tiny.en"
        assert _local_model_name("hi") == "base"

        settings.whisper_model = "medium"
        assert _local_model_name("hi") == "medium"


def test_groq_uses_enabled_turbo_for_english_and_hindi() -> None:
    with patch("app.services.transcription.settings") as settings:
        settings.whisper_provider = "groq"
        settings.whisper_model = ""
        assert _default_cloud_model(source_language="en") == "whisper-large-v3-turbo"
        assert _default_cloud_model(source_language="hi") == "whisper-large-v3-turbo"

        settings.whisper_model = "whisper-large-v3-turbo"
        assert _default_cloud_model(source_language="hi") == "whisper-large-v3-turbo"


def test_transcribe_english_routes_to_local_transcribe() -> None:
    buffer = io.BytesIO(b"RIFF" + b"\x00" * 44)
    buffer.name = "t.wav"  # type: ignore[attr-defined]

    with (
        patch("app.services.transcription.settings") as settings,
        patch("app.services.transcription._transcribe_local") as local_fn,
    ):
        settings.whisper_provider = "local"
        local_fn.return_value = "severe pain"
        text = transcribe_audio_buffer(buffer, source_language="en")
        assert text == "severe pain"
        local_fn.assert_called_once()
        assert local_fn.call_args.args[1] == "en"


def test_transcribe_hindi_routes_to_local_translate() -> None:
    buffer = io.BytesIO(b"RIFF" + b"\x00" * 44)
    buffer.name = "t.wav"  # type: ignore[attr-defined]

    with (
        patch("app.services.transcription.settings") as settings,
        patch("app.services.transcription._transcribe_local") as local_fn,
    ):
        settings.whisper_provider = "local"
        local_fn.return_value = "severe lower abdominal pain"
        text = transcribe_audio_buffer(buffer, source_language="hi")
        assert text == "severe lower abdominal pain"
        local_fn.assert_called_once()
        assert local_fn.call_args.args[1] == "hi"


def test_cloud_hindi_uses_translations_endpoint() -> None:
    buffer = io.BytesIO(b"RIFF" + b"\x00" * 44)
    buffer.name = "t.wav"  # type: ignore[attr-defined]

    client = MagicMock()
    client.audio.translations.create.return_value = MagicMock(
        text="iron folic acid once daily",
    )

    with (
        patch("app.services.transcription.settings") as settings,
        patch("app.services.transcription._build_cloud_client", return_value=client),
    ):
        settings.whisper_provider = "openai"
        settings.whisper_model = "whisper-1"
        text = transcribe_audio_buffer(buffer, source_language="hi")
        assert text == "iron folic acid once daily"
        client.audio.translations.create.assert_called_once()
        client.audio.transcriptions.create.assert_not_called()


def test_groq_hindi_transcribes_then_translates_with_llm() -> None:
    buffer = io.BytesIO(b"RIFF" + b"\x00" * 44)
    buffer.name = "t.wav"  # type: ignore[attr-defined]

    client = MagicMock()
    client.audio.transcriptions.create.return_value = MagicMock(
        text="तीन दिन से पेट दर्द",
    )

    with (
        patch("app.services.transcription.settings") as settings,
        patch("app.services.transcription._build_cloud_client", return_value=client),
        patch(
            "app.services.lml_parser.translate_clinical_transcript_to_english",
            return_value="Abdominal pain for three days",
        ) as translate_fn,
    ):
        settings.whisper_provider = "groq"
        settings.whisper_model = "whisper-large-v3-turbo"
        text = transcribe_audio_buffer(buffer, source_language="hi")
        assert text == "Abdominal pain for three days"
        kwargs = client.audio.transcriptions.create.call_args.kwargs
        assert kwargs["language"] == "hi"
        client.audio.translations.create.assert_not_called()
        translate_fn.assert_called_once_with("तीन दिन से पेट दर्द", clinic_id=None)


def test_groq_hindi_skips_llm_when_whisper_already_english() -> None:
    buffer = io.BytesIO(b"RIFF" + b"\x00" * 44)
    buffer.name = "t.wav"  # type: ignore[attr-defined]

    client = MagicMock()
    client.audio.transcriptions.create.return_value = MagicMock(
        text="Mefenamic acid 500 mg TDS for 3 days",
    )

    with (
        patch("app.services.transcription.settings") as settings,
        patch("app.services.transcription._build_cloud_client", return_value=client),
        patch(
            "app.services.lml_parser.translate_clinical_transcript_to_english",
        ) as translate_fn,
    ):
        settings.whisper_provider = "groq"
        settings.whisper_model = "whisper-large-v3-turbo"
        text = transcribe_audio_buffer(buffer, source_language="hi")
        assert text == "Mefenamic acid 500 mg TDS for 3 days"
        translate_fn.assert_not_called()


def test_transcript_needs_english_translation_devanagari_only() -> None:
    assert transcript_needs_english_translation("तीन दिन से पेट दर्द") is True
    assert transcript_needs_english_translation("Abdominal pain for 3 days") is False
    assert transcript_needs_english_translation("") is False


def test_cloud_english_uses_transcriptions_endpoint() -> None:
    buffer = io.BytesIO(b"RIFF" + b"\x00" * 44)
    buffer.name = "t.wav"  # type: ignore[attr-defined]

    client = MagicMock()
    client.audio.transcriptions.create.return_value = MagicMock(
        text="dysmenorrhea",
    )

    with (
        patch("app.services.transcription.settings") as settings,
        patch("app.services.transcription._build_cloud_client", return_value=client),
    ):
        settings.whisper_provider = "groq"
        settings.whisper_model = ""
        text = transcribe_audio_buffer(buffer, source_language="en")
        assert text == "dysmenorrhea"
        kwargs = client.audio.transcriptions.create.call_args.kwargs
        assert kwargs["language"] == "en"
        client.audio.translations.create.assert_not_called()


def test_api_rejects_unsupported_language(client: TestClient) -> None:
    headers = _session(client, "dr1", "1234")
    files = {"audio": ("note.wav", b"RIFF" + b"\x00" * 44, "audio/wav")}
    data = {"language": "fr"}
    r = client.post(
        "/api/v1/prescription/transcribe",
        headers=headers,
        files=files,
        data=data,
    )
    assert r.status_code == 400
    assert "en or hi" in r.text.lower() or "language" in r.text.lower()


def test_api_defaults_language_en_when_omitted(client: TestClient) -> None:
    headers = _session(client, "dr1", "1234")
    files = {"audio": ("note.wav", b"RIFF" + b"\x00" * 44, "audio/wav")}
    with patch(
        "app.api.v1.endpoints.prescription.transcribe_audio_buffer",
        return_value="ok",
    ) as mock_tx:
        r = client.post(
            "/api/v1/prescription/transcribe",
            headers=headers,
            files=files,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_language"] == "en"
    assert body["output_language"] == "en"
    assert body["transcript"] == "ok"
    assert mock_tx.call_args.kwargs.get("source_language") == "en"


def test_api_passes_hindi_language(client: TestClient) -> None:
    headers = _session(client, "dr1", "1234")
    files = {"audio": ("note.wav", b"RIFF" + b"\x00" * 44, "audio/wav")}
    data = {"language": "hi"}
    with patch(
        "app.api.v1.endpoints.prescription.transcribe_audio_buffer",
        return_value="translated english",
    ) as mock_tx:
        r = client.post(
            "/api/v1/prescription/transcribe",
            headers=headers,
            files=files,
            data=data,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_language"] == "hi"
    assert body["output_language"] == "en"
    assert body["transcript"] == "translated english"
    assert mock_tx.call_args.kwargs.get("source_language") == "hi"
