"""Shared auth helpers for API tests (clinic ticket + PIN unlock)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.models.clinic_credential import ClinicCredential
from app.services.rate_limit import clear_rate_limits


def _clear_clinic_password_overrides() -> None:
    db = SessionLocal()
    try:
        for row in db.query(ClinicCredential).all():
            db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def clinic_ticket(
    client: TestClient,
    *,
    clinic_name: str | None = None,
    password: str | None = None,
) -> str:
    """Unlock clinic gate; try common local/cloud passwords when not specified."""
    import os

    from app.core.config import get_settings

    # Force pytest roster (other test modules may overwrite at import).
    os.environ["CLINICS"] = (
        "default|Test Clinic|||testpass|"
        "voice_rx,labs,queue,appointments,analytics,obstetric,video_consult"
    )
    os.environ["CLINIC_USERS"] = (
        "dr1|Dr Test|doctor|1234;"
        "dr2|Dr Two|doctor|2345;"
        "nurse1|Nurse Test|staff|5678;"
        "lab1|Lab Test|lab|9999;"
        "desk1|Front Desk|receptionist|1111"
    )
    get_settings.cache_clear()
    clear_rate_limits()
    _clear_clinic_password_overrides()
    attempts: list[tuple[str, str]] = []
    if clinic_name and password:
        attempts.append((clinic_name, password))
    attempts.extend(
        [
            ("Test Clinic", "testpass"),
            ("default", "testpass"),
        ]
    )
    last = ""
    seen: set[tuple[str, str]] = set()
    for name, pw in attempts:
        key = (name, pw)
        if key in seen:
            continue
        seen.add(key)
        clear_rate_limits()
        r = client.post(
            "/api/v1/auth/clinic-unlock",
            json={"clinic_name": name, "password": pw},
        )
        if r.status_code == 200:
            ticket = r.json().get("clinic_ticket")
            assert ticket, r.text
            return str(ticket)
        last = r.text
    raise AssertionError(f"clinic-unlock failed: {last}")


def session_headers(
    client: TestClient,
    user_id: str,
    pin: str,
    *,
    clinic_name: str | None = None,
    password: str | None = None,
    clinic_id: str | None = None,
) -> dict[str, str]:
    ticket = clinic_ticket(
        client, clinic_name=clinic_name, password=password
    )
    body: dict[str, str] = {
        "user_id": user_id,
        "pin": pin,
        "clinic_ticket": ticket,
    }
    if clinic_id:
        body["clinic_id"] = clinic_id
    r = client.post("/api/v1/auth/unlock", json=body)
    assert r.status_code == 200, r.text
    token = r.json()["session_token"]
    return {"X-Doctor-Session": token}
