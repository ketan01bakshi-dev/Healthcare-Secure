"""Route helpers for prescription PDF minting (client shares via native sheet)."""

from __future__ import annotations

import io
from typing import Any

from app.services.presigned_url import (
    PRESIGNED_TTL_SECONDS,
    mint_presigned_prescription_url,
)


def build_expiring_prescription_download_url(pdf: bytes | io.BytesIO) -> dict[str, Any]:
    """
    Mint a cryptographically signed download URL that expires in exactly 24 hours.

    The mobile / web client shares this URL via the device share sheet or clipboard.
    No carrier SMS gateway is used.
    """
    if isinstance(pdf, io.BytesIO):
        pdf_bytes = pdf.getvalue()
    else:
        pdf_bytes = pdf

    url, expires_at = mint_presigned_prescription_url(pdf_bytes)
    return {
        "download_url": url,
        "expires_at": expires_at,
        "expires_in_seconds": PRESIGNED_TTL_SECONDS,
        "expires_in_hours": PRESIGNED_TTL_SECONDS // 3600,
    }
