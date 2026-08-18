"""Encrypt small PHI fields (appointment phones) at rest."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    # Derive a stable 32-byte key from SECRET_KEY
    digest = hashlib.sha256((settings.secret_key or "dev").encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_phone(phone: str) -> str:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if not digits:
        return ""
    return _fernet().encrypt(digits.encode("utf-8")).decode("utf-8")


def decrypt_phone(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
