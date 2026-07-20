"""Cryptographically expiring prescription download links with durable disk store."""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from hashlib import sha256
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlencode

from app.core.config import settings

PRESIGNED_TTL_SECONDS = 24 * 60 * 60

_STORE_DIR = Path(__file__).resolve().parents[2] / "data" / "presigned_pdfs"
_lock = threading.Lock()


class _EphemeralPdf(NamedTuple):
    data: bytes
    expires_at: int


# In-process cache (optional hot path); disk is source of truth across restarts.
_PDF_CACHE: dict[str, _EphemeralPdf] = {}


def _signing_key() -> bytes:
    secret = settings.secret_key.strip()
    if not secret or secret.startswith("CHANGE_ME"):
        raise RuntimeError("SECRET_KEY must be set to sign prescription download URLs")
    return secret.encode("utf-8")


def _sign(resource_id: str, expires_at: int) -> str:
    message = f"{resource_id}.{expires_at}".encode("utf-8")
    return hmac.new(_signing_key(), message, sha256).hexdigest()


def _public_api_base() -> str:
    base = (settings.public_api_base_url or "").strip().rstrip("/")
    if not base:
        base = "http://127.0.0.1:8000"
    return base


def _ensure_store() -> Path:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    return _STORE_DIR


def _pdf_path(resource_id: str) -> Path:
    # resource_id is url-safe; still sanitize path segments.
    safe = "".join(c for c in resource_id if c.isalnum() or c in "-_")
    if not safe:
        raise ValueError("Invalid resource id")
    return _ensure_store() / f"{safe}.pdf"


def _meta_path(resource_id: str) -> Path:
    safe = "".join(c for c in resource_id if c.isalnum() or c in "-_")
    return _ensure_store() / f"{safe}.expires"


def _purge_expired(now: int | None = None) -> None:
    ts = int(time.time()) if now is None else now
    expired_keys = [key for key, item in _PDF_CACHE.items() if item.expires_at <= ts]
    for key in expired_keys:
        _PDF_CACHE.pop(key, None)
        _delete_disk(key)

    store = _ensure_store()
    for meta in store.glob("*.expires"):
        try:
            expires_at = int(meta.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        if expires_at <= ts:
            resource_id = meta.stem
            _delete_disk(resource_id)


def _delete_disk(resource_id: str) -> None:
    for path in (_pdf_path(resource_id), _meta_path(resource_id)):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _write_disk(resource_id: str, pdf_bytes: bytes, expires_at: int) -> None:
    pdf_path = _pdf_path(resource_id)
    meta_path = _meta_path(resource_id)
    pdf_path.write_bytes(pdf_bytes)
    meta_path.write_text(str(expires_at), encoding="utf-8")


def _read_disk(resource_id: str) -> _EphemeralPdf | None:
    pdf_path = _pdf_path(resource_id)
    meta_path = _meta_path(resource_id)
    if not pdf_path.is_file() or not meta_path.is_file():
        return None
    try:
        expires_at = int(meta_path.read_text(encoding="utf-8").strip())
        data = pdf_path.read_bytes()
    except (OSError, ValueError):
        return None
    if not data:
        return None
    return _EphemeralPdf(data=data, expires_at=expires_at)


def mint_presigned_prescription_url(pdf_bytes: bytes) -> tuple[str, int]:
    """
    Persist PDF bytes on disk and return a URL that cryptographically expires
    exactly 24 hours after creation.

    Token format: ``{resource_id}.{expires_at}.{hmac_sha256}``
    """
    if not pdf_bytes:
        raise ValueError("pdf_bytes must be non-empty")

    now = int(time.time())
    expires_at = now + PRESIGNED_TTL_SECONDS
    resource_id = secrets.token_urlsafe(16)
    signature = _sign(resource_id, expires_at)
    token = f"{resource_id}.{expires_at}.{signature}"

    with _lock:
        _purge_expired(now)
        _write_disk(resource_id, pdf_bytes, expires_at)
        _PDF_CACHE[resource_id] = _EphemeralPdf(data=pdf_bytes, expires_at=expires_at)

    query = urlencode({"token": token})
    prefix = settings.api_v1_prefix.rstrip("/")
    url = f"{_public_api_base()}{prefix}/prescription/download?{query}"
    return url, expires_at


def resolve_presigned_prescription(token: str) -> bytes:
    """
    Verify HMAC + expiry, then return PDF bytes from disk (or memory cache).

    Raises ValueError when the token is invalid, tampered, expired, or unknown.
    """
    parts = (token or "").split(".")
    if len(parts) != 3:
        raise ValueError("Malformed download token")

    resource_id, expires_raw, signature = parts
    try:
        expires_at = int(expires_raw)
    except ValueError as exc:
        raise ValueError("Malformed download token expiry") from exc

    expected = _sign(resource_id, expires_at)
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Invalid download token signature")

    now = int(time.time())
    if now >= expires_at:
        with _lock:
            _PDF_CACHE.pop(resource_id, None)
            _delete_disk(resource_id)
        raise ValueError("Download link has expired")

    with _lock:
        _purge_expired(now)
        entry = _PDF_CACHE.get(resource_id)
        if entry is None:
            entry = _read_disk(resource_id)
            if entry is not None:
                _PDF_CACHE[resource_id] = entry

    if entry is None:
        raise ValueError("Download link is unknown or already purged")
    if entry.expires_at != expires_at:
        raise ValueError("Download link expiry mismatch")

    return entry.data


def revoke_presigned_prescription(token: str) -> None:
    """Best-effort purge of ephemeral PDF bytes for a token."""
    parts = (token or "").split(".")
    if len(parts) != 3:
        return
    resource_id = parts[0]
    with _lock:
        _PDF_CACHE.pop(resource_id, None)
        _delete_disk(resource_id)
