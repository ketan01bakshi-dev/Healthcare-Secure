"""ABDM / ABHA gateway client (sandbox + production URLs).

Implements gateway session + M1-style MOBILE_OTP verify/link flow.
When credentials are missing, callers should use local HMAC link only.
Set ABDM_MOCK=true to exercise OTP without calling NHA (tests / offline demo).
"""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

# In-memory txn store for OTP flows + async callback correlation
_TXNS: dict[str, dict[str, Any]] = {}
_TOKEN_CACHE: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


@dataclass
class AbdmStatus:
    enabled: bool
    mode: str
    gateway_url: str
    cm_id: str
    facility_id: str
    message: str
    mock: bool = False


def abdm_configured() -> bool:
    if getattr(settings, "abdm_mock", False):
        return True
    client_id = (settings.abdm_client_id or "").strip()
    secret = (settings.abdm_client_secret or "").strip()
    return bool(
        client_id
        and secret
        and not client_id.startswith("CHANGE_ME")
        and not secret.startswith("CHANGE_ME")
    )


def get_status() -> AbdmStatus:
    gateway = (settings.abdm_gateway_url or "").rstrip("/")
    cm = (settings.abdm_cm_id or "sbx").strip() or "sbx"
    facility = (settings.abdm_facility_id or "").strip()
    mock = bool(getattr(settings, "abdm_mock", False))
    if mock:
        return AbdmStatus(
            enabled=True,
            mode="mock",
            gateway_url=gateway or "mock://abdm",
            cm_id=cm,
            facility_id=facility or "MOCK-HIP",
            message="ABDM_MOCK=true — OTP demo without NHA network calls.",
            mock=True,
        )
    if not abdm_configured():
        return AbdmStatus(
            enabled=False,
            mode="local_hash_only",
            gateway_url=gateway,
            cm_id=cm,
            facility_id=facility,
            message=(
                "Set ABDM_CLIENT_ID / ABDM_CLIENT_SECRET (sandbox approval) "
                "to enable national ABHA verification."
            ),
        )
    return AbdmStatus(
        enabled=True,
        mode="abdm_gateway",
        gateway_url=gateway,
        cm_id=cm,
        facility_id=facility,
        message="ABDM credentials configured — OTP verify/link available.",
    )


def _gateway_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-CM-ID": (settings.abdm_cm_id or "sbx").strip() or "sbx",
    }


def fetch_gateway_token(*, force: bool = False) -> str:
    """POST /v0.5/sessions — client credentials."""
    if getattr(settings, "abdm_mock", False):
        return "mock-gateway-token"
    now = time.time()
    cached = _TOKEN_CACHE.get("access_token")
    expires = float(_TOKEN_CACHE.get("expires_at") or 0)
    if cached and not force and expires > now + 60:
        return str(cached)

    gateway = (settings.abdm_gateway_url or "").rstrip("/")
    url = f"{gateway}/v0.5/sessions"
    payload = {
        "clientId": settings.abdm_client_id.strip(),
        "clientSecret": settings.abdm_client_secret.strip(),
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    token = data.get("accessToken") or data.get("access_token")
    if not token:
        raise RuntimeError("ABDM sessions response missing accessToken")
    # Default ~20 min; refresh early
    _TOKEN_CACHE["access_token"] = token
    _TOKEN_CACHE["expires_at"] = now + 15 * 60
    return str(token)


def request_mobile_otp(
    *,
    abha_address_or_number: str,
    clinic_id: str,
) -> dict[str, Any]:
    """
    Start MOBILE_OTP auth for an ABHA address/number.

    Real ABDM is async (on-init callback). We also keep a local txn so the
    clinic UI can proceed; callbacks update the same txn when registered.
    """
    identity = (abha_address_or_number or "").strip()
    if not identity:
        raise ValueError("ABHA address or number is required")

    txn_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    entry: dict[str, Any] = {
        "txn_id": txn_id,
        "request_id": request_id,
        "clinic_id": clinic_id,
        "abha": identity,
        "status": "otp_requested",
        "created_at": time.time(),
        "auth_token": None,
        "profile": None,
    }

    if getattr(settings, "abdm_mock", False):
        entry["mock_otp"] = "123456"
        entry["status"] = "otp_sent"
        _TXNS[txn_id] = entry
        return {
            "txn_id": txn_id,
            "request_id": request_id,
            "status": "otp_sent",
            "message": "Mock OTP sent. Use 123456 to confirm.",
            "mock": True,
        }

    token = fetch_gateway_token()
    gateway = (settings.abdm_gateway_url or "").rstrip("/")
    # Gateway auth init (M1 verify by OTP)
    url = f"{gateway}/v0.5/users/auth/init"
    body = {
        "requestId": request_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "query": {
            "id": identity,
            "purpose": "KYC_AND_LINK",
            "authMode": "MOBILE_OTP",
            "requester": {
                "type": "HIP",
                "id": (settings.abdm_facility_id or settings.abdm_client_id).strip(),
            },
        },
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=body, headers=_gateway_headers(token))
        if resp.status_code >= 400:
            raise RuntimeError(f"ABDM auth/init failed: {resp.status_code} {resp.text[:300]}")
    entry["status"] = "otp_pending_callback"
    _TXNS[txn_id] = entry
    _TXNS[request_id] = entry  # also index by requestId for callbacks
    return {
        "txn_id": txn_id,
        "request_id": request_id,
        "status": "otp_pending_callback",
        "message": (
            "Auth init sent to ABDM. Patient should receive OTP. "
            "Confirm with txn_id once OTP is collected (ensure callback URL is registered)."
        ),
        "mock": False,
    }


def confirm_otp(*, txn_id: str, otp: str) -> dict[str, Any]:
    """Confirm MOBILE_OTP and return linking token + profile fields when available."""
    entry = _TXNS.get((txn_id or "").strip())
    if not entry or "abha" not in entry:
        raise ValueError("Unknown or expired ABDM transaction")
    code = (otp or "").strip()
    if len(code) < 4:
        raise ValueError("OTP looks too short")

    if getattr(settings, "abdm_mock", False):
        expected = str(entry.get("mock_otp") or "123456")
        if code != expected:
            raise ValueError("Invalid mock OTP (use 123456)")
        link_token = secrets.token_urlsafe(24)
        entry["status"] = "confirmed"
        entry["auth_token"] = link_token
        entry["profile"] = {
            "abha": entry["abha"],
            "name": "Mock Patient",
            "gender": "U",
        }
        return {
            "txn_id": txn_id,
            "status": "confirmed",
            "linking_token": link_token,
            "profile": entry["profile"],
            "mock": True,
        }

    token = fetch_gateway_token()
    gateway = (settings.abdm_gateway_url or "").rstrip("/")
    request_id = str(uuid.uuid4())
    transaction_id = entry.get("gateway_transaction_id") or entry.get("txn_id")
    url = f"{gateway}/v0.5/users/auth/confirm"
    body = {
        "requestId": request_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "transactionId": transaction_id,
        "credential": {"authCode": code},
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=body, headers=_gateway_headers(token))
        if resp.status_code >= 400:
            raise RuntimeError(
                f"ABDM auth/confirm failed: {resp.status_code} {resp.text[:300]}"
            )
    entry["status"] = "confirm_pending_callback"
    entry["confirm_request_id"] = request_id
    _TXNS[request_id] = entry
    # If on-confirm already arrived, surface it
    if entry.get("auth_token"):
        return {
            "txn_id": txn_id,
            "status": "confirmed",
            "linking_token": entry["auth_token"],
            "profile": entry.get("profile") or {},
            "mock": False,
        }
    return {
        "txn_id": txn_id,
        "status": "confirm_pending_callback",
        "linking_token": None,
        "profile": entry.get("profile"),
        "message": "Confirm sent; waiting for ABDM on-confirm callback.",
        "mock": False,
    }


def handle_callback(path: str, payload: dict[str, Any]) -> dict[str, str]:
    """Merge async ABDM gateway callbacks into the txn store."""
    resp = payload.get("resp") or payload.get("auth") or payload
    request_id = (
        (payload.get("response") or {}).get("requestId")
        or payload.get("requestId")
        or ""
    )
    entry = _TXNS.get(str(request_id)) if request_id else None
    # Also try nested transactionId
    txn = (
        payload.get("auth", {}).get("transactionId")
        if isinstance(payload.get("auth"), dict)
        else None
    ) or payload.get("transactionId")
    if entry is None and txn:
        for v in _TXNS.values():
            if isinstance(v, dict) and (
                v.get("gateway_transaction_id") == txn or v.get("txn_id") == txn
            ):
                entry = v
                break
    if entry is None:
        # Store orphan callback briefly for debugging
        orphan_id = f"orphan:{uuid.uuid4()}"
        _TXNS[orphan_id] = {"raw": payload, "path": path, "created_at": time.time()}
        return {"status": "stored_orphan"}

    if "on-init" in path or path.endswith("on-init"):
        auth = payload.get("auth") or {}
        entry["gateway_transaction_id"] = auth.get("transactionId") or txn
        entry["status"] = "otp_sent"
    if "on-confirm" in path or path.endswith("on-confirm"):
        auth = payload.get("auth") or {}
        entry["auth_token"] = (auth.get("accessToken") or {}).get("token") or auth.get(
            "accessToken"
        )
        entry["profile"] = auth.get("patient") or auth.get("profile") or {}
        entry["status"] = "confirmed"
    return {"status": "ok", "txn_id": str(entry.get("txn_id") or "")}


def get_txn(txn_id: str) -> dict[str, Any] | None:
    entry = _TXNS.get((txn_id or "").strip())
    if not entry or "abha" not in entry:
        return None
    # Never expose mock_otp in public poll except mock mode already told user
    safe = {k: v for k, v in entry.items() if k != "mock_otp"}
    return safe


def purge_old_txns(max_age_seconds: float = 3600) -> int:
    now = time.time()
    dead = [
        k
        for k, v in _TXNS.items()
        if isinstance(v, dict) and now - float(v.get("created_at") or now) > max_age_seconds
    ]
    for k in dead:
        _TXNS.pop(k, None)
    return len(dead)
