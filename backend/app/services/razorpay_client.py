"""Razorpay UPI QR client (orders/QR create + webhook verify).

Live path: prefer Razorpay QR Codes API; if that product is not enabled on the
merchant account (common 400 "URL was not found"), fall back to Payment Links
and render a scannable QR PNG from the short URL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import time
from typing import Any

import httpx

from app.core.config import settings

_API_BASE = "https://api.razorpay.com/v1"


class RazorpayError(RuntimeError):
    """Raised when Razorpay API or configuration fails."""


def payments_configured() -> bool:
    if not settings.payments_enabled:
        return False
    if settings.razorpay_mock:
        return True
    return bool(settings.razorpay_key_id.strip() and settings.razorpay_key_secret.strip())


def _auth() -> tuple[str, str]:
    return (settings.razorpay_key_id.strip(), settings.razorpay_key_secret.strip())


def _qr_png_base64(payload: str) -> str:
    """Best-effort QR PNG as base64 (empty string if encoder unavailable)."""
    text = (payload or "").strip()
    if not text:
        return ""
    try:
        import qrcode  # type: ignore[import-untyped]

        img = qrcode.make(text)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:  # noqa: BLE001
        return ""


def _mock_qr(
    *,
    amount_inr: float,
    description: str,
    close_by_unix: int,
) -> dict[str, Any]:
    qr_id = f"qr_mock_{int(time.time())}"
    qr_string = (
        f"upi://pay?pa=mock@razorpay&pn=Clinic&am={amount_inr:.2f}"
        f"&cu=INR&tn={description[:40]}"
    )
    image_b64 = _qr_png_base64(qr_string)
    if not image_b64:
        # 1x1 PNG fallback
        image_b64 = base64.b64encode(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        ).decode("ascii")
    return {
        "provider_qr_id": qr_id,
        "provider_order_id": f"order_mock_{qr_id}",
        "qr_string": qr_string,
        "qr_image_url": "",
        "qr_image_base64": image_b64,
        "expires_at_unix": close_by_unix,
        "raw": {"id": qr_id, "mock": True},
    }


def _create_via_qr_codes(
    *,
    amount_paise: int,
    description: str,
    notes: dict[str, str],
    close_by_unix: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "upi_qr",
        "name": (settings.clinic_name or "Clinic")[:20],
        "usage": "single_use",
        "fixed_amount": True,
        "payment_amount": amount_paise,
        "description": (description or "Clinic payment")[:255],
        "close_by": close_by_unix,
        "notes": {str(k)[:256]: str(v)[:256] for k, v in (notes or {}).items()},
    }
    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            f"{_API_BASE}/payments/qr_codes",
            json=payload,
            auth=_auth(),
        )
        if res.status_code >= 400:
            raise RazorpayError(
                f"Razorpay QR create failed: {res.status_code} {res.text[:300]}"
            )
        data = res.json()

    qr_id = str(data.get("id") or "")
    image_url = str(data.get("image_url") or "")
    qr_string = str(data.get("qr_string") or data.get("qr_code") or "")
    image_b64 = ""
    if image_url:
        try:
            with httpx.Client(timeout=20.0) as client:
                img = client.get(image_url)
                if img.status_code == 200 and img.content:
                    image_b64 = base64.b64encode(img.content).decode("ascii")
        except Exception:  # noqa: BLE001
            image_b64 = ""
    if not image_b64 and qr_string:
        image_b64 = _qr_png_base64(qr_string)

    return {
        "provider_qr_id": qr_id,
        "provider_order_id": "",
        "qr_string": qr_string,
        "qr_image_url": image_url,
        "qr_image_base64": image_b64,
        "expires_at_unix": int(data.get("close_by") or close_by_unix),
        "raw": data,
    }


def _create_via_payment_link(
    *,
    amount_paise: int,
    description: str,
    notes: dict[str, str],
    close_by_unix: int,
) -> dict[str, Any]:
    """Fallback when QR Codes product is not enabled on the Razorpay account."""
    payload: dict[str, Any] = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": (description or "Clinic payment")[:255],
        "expire_by": close_by_unix,
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "notes": {str(k)[:256]: str(v)[:256] for k, v in (notes or {}).items()},
    }
    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            f"{_API_BASE}/payment_links",
            json=payload,
            auth=_auth(),
        )
        if res.status_code >= 400:
            raise RazorpayError(
                f"Razorpay payment link failed: {res.status_code} {res.text[:300]}"
            )
        data = res.json()

    link_id = str(data.get("id") or "")
    short_url = str(data.get("short_url") or "")
    if not short_url:
        raise RazorpayError("Razorpay payment link missing short_url")
    image_b64 = _qr_png_base64(short_url)
    return {
        "provider_qr_id": link_id,
        "provider_order_id": link_id,
        "qr_string": short_url,
        "qr_image_url": short_url,
        "qr_image_base64": image_b64,
        "expires_at_unix": int(data.get("expire_by") or close_by_unix),
        "raw": {**data, "fallback": "payment_link"},
    }


def create_upi_qr(
    *,
    amount_inr: float,
    description: str,
    notes: dict[str, str],
    close_by_unix: int | None = None,
) -> dict[str, Any]:
    """
    Create a single-use fixed-amount UPI QR (or payment-link QR fallback).

    Returns dict with provider_qr_id, provider_order_id, qr_string, qr_image_url,
    qr_image_base64 (best-effort), expires_at_unix.
    """
    # #region agent log
    try:
        import json as _json
        from pathlib import Path as _Path

        _Path("/tmp/debug-bbdc54.log").open("a", encoding="utf-8").write(
            _json.dumps(
                {
                    "sessionId": "bbdc54",
                    "runId": "qr-server",
                    "hypothesisId": "H1_H2",
                    "location": "razorpay_client.create_upi_qr:entry",
                    "message": "create_upi_qr entry",
                    "data": {
                        "amount_inr": amount_inr,
                        "payments_enabled": settings.payments_enabled,
                        "razorpay_mock": settings.razorpay_mock,
                        "key_id_set": bool(settings.razorpay_key_id.strip()),
                        "key_secret_set": bool(settings.razorpay_key_secret.strip()),
                        "configured": payments_configured(),
                    },
                    "timestamp": int(time.time() * 1000),
                }
            )
            + "\n"
        )
    except Exception:
        pass
    # #endregion

    amount_paise = int(round(float(amount_inr) * 100))
    if amount_paise < 100:
        raise RazorpayError("Minimum amount is ₹1.00")
    if close_by_unix is None:
        # Payment links / QR close_by must be >= ~15 minutes ahead
        close_by_unix = int(time.time()) + 20 * 60

    if settings.razorpay_mock:
        return _mock_qr(
            amount_inr=amount_inr,
            description=description,
            close_by_unix=close_by_unix,
        )

    if not payments_configured():
        raise RazorpayError("Razorpay is not configured")

    try:
        result = _create_via_qr_codes(
            amount_paise=amount_paise,
            description=description,
            notes=notes,
            close_by_unix=close_by_unix,
        )
        # #region agent log
        try:
            import json as _json
            from pathlib import Path as _Path

            _Path("/tmp/debug-bbdc54.log").open("a", encoding="utf-8").write(
                _json.dumps(
                    {
                        "sessionId": "bbdc54",
                        "runId": "qr-server",
                        "hypothesisId": "H3",
                        "location": "razorpay_client.create_upi_qr:qr_codes_ok",
                        "message": "QR Codes API succeeded",
                        "data": {
                            "qr_string_len": len(result.get("qr_string") or ""),
                            "qr_b64_len": len(result.get("qr_image_base64") or ""),
                        },
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
        except Exception:
            pass
        # #endregion
        return result
    except RazorpayError as qr_exc:
        # #region agent log
        try:
            import json as _json
            from pathlib import Path as _Path

            _Path("/tmp/debug-bbdc54.log").open("a", encoding="utf-8").write(
                _json.dumps(
                    {
                        "sessionId": "bbdc54",
                        "runId": "qr-server",
                        "hypothesisId": "H3",
                        "location": "razorpay_client.create_upi_qr:fallback",
                        "message": "QR Codes failed; trying payment_links",
                        "data": {"qr_err": str(qr_exc)[:300]},
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
        except Exception:
            pass
        # #endregion
        result = _create_via_payment_link(
            amount_paise=amount_paise,
            description=description,
            notes=notes,
            close_by_unix=close_by_unix,
        )
        # #region agent log
        try:
            import json as _json
            from pathlib import Path as _Path

            _Path("/tmp/debug-bbdc54.log").open("a", encoding="utf-8").write(
                _json.dumps(
                    {
                        "sessionId": "bbdc54",
                        "runId": "qr-server",
                        "hypothesisId": "H3",
                        "location": "razorpay_client.create_upi_qr:payment_link_ok",
                        "message": "Payment link fallback succeeded",
                        "data": {
                            "qr_string_len": len(result.get("qr_string") or ""),
                            "qr_b64_len": len(result.get("qr_image_base64") or ""),
                        },
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
        except Exception:
            pass
        # #endregion
        return result


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    secret = (settings.razorpay_webhook_secret or "").strip()
    if settings.razorpay_mock and not secret:
        return True
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature.strip())
