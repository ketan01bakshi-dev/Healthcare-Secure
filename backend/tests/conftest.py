"""Pytest defaults — isolate tenancy from developer backend/.env."""

from __future__ import annotations

import os

import pytest

# Must run before app imports. Keep a full roster so any collected module
# can unlock dr1/dr2/nurse1/lab1/desk1 without depending on import order.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_healthcare.db")
os.environ.setdefault(
    "SECRET_SALT", "test_salt_not_for_production_0123456789abcdef"
)
os.environ.setdefault(
    "SECRET_KEY", "test_secret_key_not_for_production_01234567"
)

TEST_CLINICS = (
    "default|Test Clinic|||testpass|"
    "voice_rx,labs,queue,appointments,analytics,obstetric,video_consult"
)
TEST_CLINIC_USERS = (
    "dr1|Dr Test|doctor|1234;"
    "dr2|Dr Two|doctor|2345;"
    "nurse1|Nurse Test|staff|5678;"
    "lab1|Lab Test|lab|9999;"
    "desk1|Front Desk|receptionist|1111"
)

os.environ["CLINICS"] = TEST_CLINICS
os.environ["CLINIC_USERS"] = TEST_CLINIC_USERS
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("REQUIRE_CLINIC_USERS", "false")
os.environ.setdefault("WHISPER_PRELOAD", "false")
os.environ.setdefault("PAYMENTS_ENABLED", "true")
os.environ.setdefault("RAZORPAY_MOCK", "true")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "whsec_test")


@pytest.fixture(autouse=True)
def _isolate_clinic_env() -> None:
    """Re-apply roster after other test modules overwrite os.environ at import."""
    os.environ["CLINICS"] = TEST_CLINICS
    os.environ["CLINIC_USERS"] = TEST_CLINIC_USERS
    try:
        from app.core.config import get_settings

        get_settings.cache_clear()
    except Exception:
        pass
    yield
    try:
        from app.core.config import get_settings

        get_settings.cache_clear()
    except Exception:
        pass
