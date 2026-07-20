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
    app_name: str = "Healthcare Secure API"
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
    whisper_provider: str = "local"
    whisper_api_key: str = "CHANGE_ME_SET_OPENAI_OR_GROQ_KEY"
    whisper_base_url: str = ""  # optional; Groq auto-set when provider=groq
    # local default base.en; openai whisper-1; groq whisper-large-v3 when empty
    whisper_model: str = ""
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_preload: bool = True  # warm local model on API startup

    # Structured clinical LLM parser: ollama (local $0) | openai | groq
    llm_provider: str = "ollama"
    llm_api_key: str = "ollama"  # ignored by Ollama; required for openai/groq
    llm_model: str = "llama3.2"  # ollama pull llama3.2
    llm_base_url: str = ""  # empty → http://127.0.0.1:11434/v1 when provider=ollama

    # Prescription PDF clinic branding / letterhead template
    clinic_name: str = "Healthcare Secure Clinic"
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

    # Clinic users: user_id|Display Name|doctor|pin;nurse1|Nurse One|staff|pin2
    # If empty, falls back to single doctor via DOCTOR_PIN (legacy).
    clinic_users: str = ""
    # Legacy single-doctor PIN when CLINIC_USERS is empty
    doctor_pin: str = ""

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


settings = get_settings()
