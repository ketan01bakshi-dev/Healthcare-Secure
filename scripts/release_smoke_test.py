#!/usr/bin/env python3
"""Pre-release API smoke tests against production or local backend."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

API = sys.argv[1] if len(sys.argv) > 1 else "https://api.aarogyaoneconnect.in"
CLINIC = "Alpha Clinic"
CLINIC_PW = "ClinicShare2026"
DOCTOR = "dr_main"
PIN = "4829"


def req(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict | str]:
    url = f"{API.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", **(headers or {})}
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))

    # 1. Health / auth status (no secrets)
    code, body = req("GET", "/api/v1/auth/status")
    check("auth/status reachable", code == 200, f"HTTP {code}")
    if isinstance(body, dict):
        check("auth_required=true", body.get("auth_required") is True)
        check("no clinic roster leak", "clinics" not in body and "users" not in body)
        check("HTTPS enforced", API.startswith("https://"))

    # 2. Clinic unlock
    code, body = req("POST", "/api/v1/auth/clinic-unlock", {"clinic_name": CLINIC, "password": CLINIC_PW})
    check("clinic unlock", code == 200, f"HTTP {code}")
    ticket = body.get("clinic_ticket") if isinstance(body, dict) else None
    check("clinic ticket issued", bool(ticket), f"len={len(ticket or '')}")

    # 3. PIN unlock
    code, body = req(
        "POST",
        "/api/v1/auth/unlock",
        {
            "user_id": DOCTOR,
            "pin": PIN,
            "clinic_id": body.get("clinic_id") if isinstance(body, dict) else None,
            "clinic_ticket": ticket,
        },
    )
    check("doctor PIN unlock", code == 200, f"HTTP {code}")
    token = body.get("session_token") if isinstance(body, dict) else None
    check("session token issued", bool(token))
    clinic_id = body.get("clinic_id") if isinstance(body, dict) else None
    auth = {"X-Doctor-Session": token or ""}

    # 4. Patient list
    code, body = req("GET", "/api/v1/history/patients", headers=auth)
    check("patient list", code == 200, f"HTTP {code}, count={len(body) if isinstance(body, list) else '?'}")

    # 5. Unauthorized blocked
    code, _ = req("GET", "/api/v1/history/patients")
    check("unauthenticated blocked", code in (401, 403), f"HTTP {code}")

    # 6. Clinical search (doctor)
    code, body = req("GET", "/api/v1/history/clinical-search?q=pat", headers=auth)
    check("clinical search", code == 200, f"HTTP {code}")

    # 7. Lab role isolation smoke
    code_l, body_l = req(
        "POST",
        "/api/v1/auth/unlock",
        {"user_id": "lab1", "pin": "7391", "clinic_id": clinic_id, "clinic_ticket": ticket},
    )
    if code_l == 200 and isinstance(body_l, dict) and body_l.get("session_token"):
        lab_auth = {"X-Doctor-Session": body_l["session_token"]}
        code_v, _ = req("POST", "/api/v1/history/vitals", headers=lab_auth, body={"blind_patient_id": "x", "vitals": {}})
        check("lab cannot write vitals", code_v in (403, 422), f"HTTP {code_v}")
        code_cs, cs = req("GET", "/api/v1/history/clinical-search?q=test", headers=lab_auth)
        check("lab clinical search allowed", code_cs == 200, f"HTTP {code_cs}")
    else:
        check("lab PIN unlock", False, f"HTTP {code_l}")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\nSummary: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
