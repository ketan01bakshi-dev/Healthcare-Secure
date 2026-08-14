"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    """Central settings for a healthcare API (env-driven, no secrets in code)."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Aarogya One Connect API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Security — set SECRET_KEY / SECRET_SALT in .env; never commit real values
    secret_key: str = "CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_HEX_32"
    secret_salt: str = "CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_HEX_32"
    # NoDecode: pydantic-settings must not json.loads CSV values before validators
    allowed_hosts: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1"]
    )
    cors_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # Database
    database_url: str = "sqlite:///./healthcare.db"

    # Whisper transcription: local (CPU POC) | openai | groq
    # English may use base.en; Hindi→English needs multilingual (base, not *.en).
    whisper_provider: str = "local"
    whisper_api_key: str = "CHANGE_ME_SET_OPENAI_OR_GROQ_KEY"
    whisper_base_url: str = ""  # optional; Groq auto-set when provider=groq
    # local: base.en (English) or base (multilingual / Hindi). Empty → language-aware default.
    # openai: whisper-1; groq: whisper-large-v3-turbo (en) / whisper-large-v3 (hi) when empty
    whisper_model: str = ""
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_preload: bool = False  # warm local model after startup (prefer false)

    # Extra STT glossary terms (comma/semicolon separated) merged into Whisper prompts
    stt_glossary: str = ""

    # Structured clinical LLM parser: ollama (local $0) | openai | groq
    llm_provider: str = "ollama"
    llm_api_key: str = "ollama"  # ignored by Ollama; required for openai/groq
    llm_model: str = "llama3.2"  # ollama pull llama3.2
    llm_base_url: str = ""  # empty → http://127.0.0.1:11434/v1 when provider=ollama

    # Prescription PDF clinic branding / letterhead template
    clinic_name: str = "Aarogya One Connect"
    clinic_subtitle: str = (
        "Secure Clinical Prescription - De-identified Patient Record"
    )
    clinic_address: str = ""
    doctor_name: str = "Dr. Attending Clinician"
    doctor_credentials: str = "MBBS"
    # IANA timezone for auto-stamped prescription date/time (e.g. Asia/Kolkata)
    prescription_timezone: str = "Asia/Kolkata"
    # Optional absolute/relative paths; defaults: app/assets/doctor_seal.png, letterhead.png
    doctor_seal_path: str = ""
    prescription_letterhead_path: str = ""

    # Public base used when minting shareable prescription download links
    public_api_base_url: str = "http://127.0.0.1:8000"

    # Clinic users: user_id|Display Name|doctor|pin;...|staff|...;...|lab|pin
    # PIN may be plaintext or pbkdf2$salt$hex (see scripts/hash_pin.py)
    clinic_users: str = ""
    doctor_pin: str = ""
    # When true (or APP_ENV=production), refuse open local-doctor mode without users
    require_clinic_users: bool = False
    # Optional override for document files (default: backend/data/attachments)
    attachments_dir: str = ""

    # Multi-clinic: clinic_id|Name|Address|Subtitle;...
    # Empty → single "default" clinic from CLINIC_NAME / ADDRESS / SUBTITLE
    clinics: str = ""

    # ABDM / ABHA (sandbox: https://dev.abdm.gov.in/gateway)
    abdm_client_id: str = ""
    abdm_client_secret: str = ""
    abdm_gateway_url: str = "https://dev.abdm.gov.in/gateway"
    abdm_cm_id: str = "sbx"  # sbx sandbox | abdm production
    abdm_facility_id: str = ""  # HIP / facility id
    abdm_callback_base_url: str = ""  # public HTTPS for gateway callbacks
    abdm_mock: bool = False  # OTP demo without NHA (use OTP 123456)

    # SMS appointments: none | console | msg91 | twilio
    # Default console logs SMS on the API host; use msg91/twilio for carrier delivery.
    sms_provider: str = "console"
    sms_api_key: str = ""  # MSG91 authkey
    sms_sender_id: str = "CLINIC"
    sms_msg91_template_id: str = ""
    sms_msg91_url: str = ""
    sms_account_sid: str = ""  # Twilio
    sms_auth_token: str = ""
    sms_from_number: str = ""
    # Optional shared secret for scripts/remind_day_before.cmd (header X-Reminder-Token)
    appointment_reminder_token: str = ""

    # Video consult (Jitsi) — no call recording stored on this API
    video_consult_provider: str = "jitsi"
    jitsi_base_url: str = "https://meet.jit.si"

    # Razorpay UPI QR (leave keys empty to disable)
    payments_enabled: bool = True
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    # When true, create QR without calling Razorpay (local/demo tests)
    razorpay_mock: bool = False

    @field_validator("cors_origins", "allowed_hosts", mode="before")
    @classmethod
    def parse_csv_or_json_list(cls, value: object) -> object:
        """Accept JSON arrays or comma-separated strings from .env."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return value
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


class _SettingsProxy:
    """Always read the current get_settings() cache (survives cache_clear in tests)."""

    def __getattr__(self, name: str):
        return getattr(get_settings(), name)

    def __repr__(self) -> str:
        return repr(get_settings())


settings = _SettingsProxy()  # type: ignore[assignment]
