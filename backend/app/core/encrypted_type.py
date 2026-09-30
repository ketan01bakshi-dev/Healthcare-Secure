"""Column type that stores small PHI strings (patient names) Fernet-encrypted at rest."""

from __future__ import annotations

from cryptography.fernet import InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.services.phone_crypto import _fernet


def is_encrypted(value: str) -> bool:
    """True when ``value`` is a Fernet token this deployment can decrypt."""
    try:
        _fernet().decrypt(value.encode("utf-8"))
    except (InvalidToken, ValueError):
        return False
    return True


def encrypt_text(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


class EncryptedText(TypeDecorator[str]):
    """
    Encrypt on write, decrypt on read; the ORM attribute stays plaintext.

    Fernet is randomised, so SQL equality / LIKE on this column never matches:
    filter in Python after loading rows. Legacy plaintext rows are returned
    as-is until ``encrypt_patient_names`` backfills them at startup.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if not value or is_encrypted(value):
            return value
        return encrypt_text(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if not value:
            return value
        try:
            return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError):
            return value
