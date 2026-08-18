"""Outbound SMS — MSG91 (India), Twilio, or console log (dev)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger("healthcare.sms")


def sms_configured() -> bool:
    provider = (settings.sms_provider or "none").strip().lower()
    if provider in ("", "none", "console"):
        return provider == "console"
    if provider == "msg91":
        return bool((settings.sms_api_key or "").strip()) and not settings.sms_api_key.startswith(
            "CHANGE_ME"
        )
    if provider == "twilio":
        return bool(
            (settings.sms_account_sid or "").strip()
            and (settings.sms_auth_token or "").strip()
            and (settings.sms_from_number or "").strip()
        )
    return False


def send_sms(*, to_phone: str, message: str) -> dict[str, Any]:
    """
    Send an SMS. Returns ``{status, provider, detail}``.
    Phone should be digits; India numbers may be 10-digit (prefix +91).
    """
    digits = "".join(c for c in (to_phone or "") if c.isdigit())
    if len(digits) < 10:
        raise ValueError("Phone number too short for SMS")
    if len(digits) == 10:
        e164 = f"91{digits}"
    else:
        e164 = digits

    text = (message or "").strip()
    if not text:
        raise ValueError("Empty SMS body")

    provider = (settings.sms_provider or "none").strip().lower()
    if provider in ("", "none"):
        return {
            "status": "skipped",
            "provider": "none",
            "detail": "SMS_PROVIDER not set — configure msg91, twilio, or console.",
        }

    if provider == "console":
        logger.info("[sms:console] to=+%s body=%s", e164, text)
        print(f"[sms:console] to=+{e164} | {text}")
        return {"status": "sent", "provider": "console", "detail": "Logged to console"}

    if provider == "msg91":
        # Flow API / sendhttp — simple transactional send
        url = (settings.sms_msg91_url or "").strip() or (
            "https://control.msg91.com/api/v5/flow/"
        )
        headers = {
            "authkey": settings.sms_api_key.strip(),
            "Content-Type": "application/json",
        }
        # Prefer template flow when template id set; else raw sendhttp
        template_id = (settings.sms_msg91_template_id or "").strip()
        if template_id:
            payload: dict[str, Any] = {
                "template_id": template_id,
                "short_url": "0",
                "recipients": [
                    {
                        "mobiles": e164,
                        "VAR1": text[:100],
                    }
                ],
            }
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                ok = resp.status_code < 400
                return {
                    "status": "sent" if ok else "error",
                    "provider": "msg91",
                    "detail": resp.text[:300],
                }
        send_url = (
            "https://control.msg91.com/api/sendhttp.php"
            f"?authkey={quote(settings.sms_api_key.strip())}"
            f"&mobiles={e164}"
            f"&message={quote(text)}"
            f"&sender={(settings.sms_sender_id or 'CLINIC').strip()}"
            f"&route=4"
            f"&country=91"
        )
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(send_url)
            ok = resp.status_code < 400
            return {
                "status": "sent" if ok else "error",
                "provider": "msg91",
                "detail": resp.text[:300],
            }

    if provider == "twilio":
        sid = settings.sms_account_sid.strip()
        token = settings.sms_auth_token.strip()
        from_num = settings.sms_from_number.strip()
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        data = {
            "To": f"+{e164}",
            "From": from_num,
            "Body": text,
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, data=data, auth=(sid, token))
            ok = resp.status_code < 300
            return {
                "status": "sent" if ok else "error",
                "provider": "twilio",
                "detail": resp.text[:300],
            }

    raise ValueError(f"Unsupported SMS_PROVIDER: {provider}")
