#!/usr/bin/env python3
"""Thorough live API verification after demo seed refresh."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import date
from typing import Any
from urllib.parse import quote

API = sys.argv[1] if len(sys.argv) > 1 else "https://api.aarogyaoneconnect.in"

# name -> (phone, mrn or "")
ALPHA_ROSTER = {
    "Ananya Reddy": ("9876501001", "GYN-1001"),
    "Priya Nair": ("9876501007", "GYN-1007"),
    "Rekha Sharma": ("9876501008", "GYN-1008"),
    "Kavita Mehta": ("9876501002", ""),
    "Sunita Devi": ("9876501003", ""),
    "Meera Joshi": ("9876501004", "GYN-1004"),
    "Fatima Khan": ("9876501005", ""),
    "Lakshmi Iyer": ("9876501006", ""),
    "Neha Kapoor": ("9876501009", "GYN-1009"),
    "Aisha Begum": ("9876501010", ""),
    "Sonal Desai": ("9876501011", "GYN-1011"),
    "Deepa Verma": ("9876501012", "GYN-1012"),
    "Jyoti Malhotra": ("9876501013", "GYN-1013"),
    "Pooja Sinha": ("9876501014", "GYN-1014"),
    "Isha Gupta": ("9876501015", "GYN-1015"),
    "Nandini Rao": ("9876501016", "GYN-1016"),
}

GP_ROSTER = {
    "Ramesh Kumar": ("9876512001", "GP-2001"),
    "Sita Patel": ("9876512002", "GP-2002"),
    "Arjun Mehta": ("9876512003", "GP-2003"),
    "Kamala Devi": ("9876512004", "GP-2004"),
    "Vikram Singh": ("9876512005", "GP-2005"),
    "Neha Shah": ("9876512006", "GP-2006"),
    "Rohit Jain": ("9876512007", ""),
    "Anjali Rao": ("9876512008", "GP-2008"),
    "Aarav Sharma": ("9876512009", "GP-2009"),
    "Deepak Nair": ("9876512010", "GP-2010"),
    "Mohan Lal": ("9876512011", "GP-2011"),
    "Harish Gupta": ("9876512012", "GP-2012"),
    "Geeta Joshi": ("9876512013", "GP-2013"),
    "Shalini Menon": ("9876512014", "GP-2014"),
}

ALPHA = {
    "clinic_name": "Alpha Clinic",
    "password": "ClinicShare2026",
    "doctor": ("dr_main", "4829"),
    "staff": ("staff_main", "5738"),
    "reception": ("reception1", "6142"),
    "lab": ("lab1", "7391"),
    "roster": ALPHA_ROSTER,
    "star": "Ananya Reddy",
    "billing_due": "Sonal Desai",
    "billing_paid": "Pooja Sinha",
    "obstetric": True,
}

GP = {
    "clinic_name": "City General Clinic",
    "password": "ClinicShare2026",
    "doctor": ("dr_gp", "3641"),
    "staff": ("staff_gp", "4582"),
    "reception": ("reception_gp", "5193"),
    "lab": ("lab_gp", "6827"),
    "roster": GP_ROSTER,
    "star": "Ramesh Kumar",
    "billing_due": "Anjali Rao",
    "billing_paid": "Geeta Joshi",
    "obstetric": False,
}


def raw_id(name: str, phone: str, mrn: str) -> str:
    if mrn.strip():
        return f"mrn|{mrn.strip().upper()}"
    return f"{name.strip()}|{phone.strip()}"


def req(
    method: str,
    path: str,
    body: dict | None = None,
    headers: dict | None = None,
) -> tuple[int, Any]:
    url = f"{API.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", **(headers or {})}
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=45) as resp:
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
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def unlock_clinic(cfg: dict) -> tuple[str | None, str | None]:
    code, body = req(
        "POST",
        "/api/v1/auth/clinic-unlock",
        {"clinic_name": cfg["clinic_name"], "password": cfg["password"]},
    )
    check(f"{cfg['clinic_name']} unlock", code == 200, f"HTTP {code}")
    if not isinstance(body, dict):
        return None, None
    return body.get("clinic_ticket"), body.get("clinic_id")


def unlock_user(
    label: str,
    user_id: str,
    pin: str,
    clinic_id: str | None,
    ticket: str | None,
) -> str | None:
    code, body = req(
        "POST",
        "/api/v1/auth/unlock",
        {
            "user_id": user_id,
            "pin": pin,
            "clinic_id": clinic_id,
            "clinic_ticket": ticket,
        },
    )
    ok = code == 200 and isinstance(body, dict) and bool(body.get("session_token"))
    check(f"{label} PIN ({user_id})", ok, f"HTTP {code}")
    return body.get("session_token") if isinstance(body, dict) else None


def verify_clinic(cfg: dict) -> tuple[str | None, list[str]] | None:
    print("\n" + "=" * 72)
    print(f"Clinic: {cfg['clinic_name']}")
    print("=" * 72)

    ticket, clinic_id = unlock_clinic(cfg)
    if not ticket:
        return None

    doc_token = unlock_user(
        "doctor", cfg["doctor"][0], cfg["doctor"][1], clinic_id, ticket
    )
    if not doc_token:
        return None
    auth = {"X-Doctor-Session": doc_token}

    code, body = req("GET", "/api/v1/history/patients", headers=auth)
    check("patient list", code == 200 and isinstance(body, list), f"HTTP {code}")
    names = [
        r.get("display_name", "")
        for r in (body if isinstance(body, list) else [])
        if isinstance(r, dict)
    ]
    expected = list(cfg["roster"].keys())
    check(
        f"patient count >= {len(expected)}",
        len(names) >= len(expected),
        f"got {len(names)}",
    )
    missing = [n for n in expected if n not in names]
    check(
        "all seeded patients present",
        not missing,
        f"missing={missing}" if missing else f"{len(expected)}/{len(expected)}",
    )

    # Clinical search
    q = cfg["star"].split()[0]
    code, cs = req(
        "GET", f"/api/v1/history/clinical-search?q={quote(q)}", headers=auth
    )
    check(f"clinical search '{q}'", code == 200, f"HTTP {code}")
    if isinstance(cs, list):
        check(f"clinical search non-empty for {q}", len(cs) > 0, f"rows={len(cs)}")

    # History + billing for star / billing patients
    for label, pname in [
        ("star", cfg["star"]),
        ("billing_due", cfg["billing_due"]),
        ("billing_paid", cfg["billing_paid"]),
    ]:
        phone, mrn = cfg["roster"][pname]
        rid = raw_id(pname, phone, mrn)
        code, hist = req(
            "POST",
            "/api/v1/history/search",
            {"raw_identifier": rid},
            headers=auth,
        )
        check(f"{pname} history search", code == 200, f"HTTP {code}")
        if isinstance(hist, list):
            types = set()
            for r in hist:
                if not isinstance(r, dict):
                    continue
                data = r.get("encounter_data") if isinstance(r.get("encounter_data"), dict) else r
                t = data.get("type") if isinstance(data, dict) else None
                if t:
                    types.add(str(t))
            check(
                f"{pname} has records",
                len(hist) > 0,
                f"n={len(hist)} types={sorted(types)[:10]}",
            )

        code, bill = req(
            "POST",
            "/api/v1/history/billing-summary",
            {"raw_identifier": rid},
            headers=auth,
        )
        check(f"{pname} billing-summary", code == 200, f"HTTP {code}")
        if code == 200 and isinstance(bill, dict):
            due = bill.get("amount_due_inr", bill.get("amount_due"))
            charged = bill.get("total_charges_inr", bill.get("total_charges") or 0)
            paid = bill.get("total_paid_inr", bill.get("total_paid") or 0)
            if label == "billing_due":
                check(
                    f"{pname} has amount due > 0",
                    float(due or 0) > 0 or float(charged) > float(paid),
                    f"due={due} charged={charged} paid={paid}",
                )
            if label == "billing_paid":
                check(
                    f"{pname} settled (due ~0)",
                    float(due or 0) <= 0.01,
                    f"due={due} charged={charged} paid={paid}",
                )
            if label == "star" and cfg["obstetric"]:
                # case summary
                code2, case = req(
                    "GET",
                    f"/api/v1/history/case-summary?raw_identifier={quote(rid)}",
                    headers=auth,
                )
                check(f"{pname} case-summary", code2 == 200, f"HTTP {code2}")
                code3, obst = req(
                    "GET",
                    f"/api/v1/history/obstetric-profile?raw_identifier={quote(rid)}",
                    headers=auth,
                )
                check(
                    f"{pname} obstetric-profile",
                    code3 == 200 and obst is not None,
                    f"HTTP {code3}",
                )

    # Appointments — list booked without a same-day midnight trap
    code, appts = req(
        "GET",
        "/api/v1/appointments?status=booked",
        headers=auth,
    )
    check("appointments list", code == 200, f"HTTP {code}")
    if isinstance(appts, list):
        check(
            "appointments non-empty",
            len(appts) > 0,
            f"count={len(appts)}",
        )
        # Prefer IST today window (matches Waiting List UI)
        today = date.today().isoformat()
        code2, today_appts = req(
            "GET",
            f"/api/v1/appointments?status=booked&from_date={today}T00:00:00%2B05:30&to_date={today}T23:59:59%2B05:30",
            headers=auth,
        )
        check(
            "appointments IST today window",
            code2 == 200 and isinstance(today_appts, list) and len(today_appts) > 0,
            f"HTTP {code2} count={len(today_appts) if isinstance(today_appts, list) else '?'}",
        )

    # Analytics
    code, today_a = req("GET", "/api/v1/analytics/today", headers=auth)
    check("analytics/today", code == 200, f"HTTP {code}")
    code, overview = req("GET", "/api/v1/analytics/overview?limit=10", headers=auth)
    check("analytics/overview", code == 200, f"HTTP {code}")

    # Roles
    for role, key in [
        ("staff", "staff"),
        ("reception", "reception"),
        ("lab", "lab"),
    ]:
        uid, pin = cfg[key]
        tok = unlock_user(role, uid, pin, clinic_id, ticket)
        if not tok:
            continue
        rauth = {"X-Doctor-Session": tok}
        code, _ = req("GET", "/api/v1/history/patients", headers=rauth)
        check(f"{role} list patients", code == 200, f"HTTP {code}")
        if role == "lab":
            code, _ = req(
                "POST",
                "/api/v1/history/vitals",
                {"blind_patient_id": "x", "vitals": {}},
                headers=rauth,
            )
            check("lab blocked from vitals write", code in (403, 422), f"HTTP {code}")

    return clinic_id, names


def main() -> int:
    print(f"API: {API}")
    code, body = req("GET", "/api/v1/auth/status")
    check("auth/status", code == 200, f"HTTP {code}")
    check("HTTPS", API.startswith("https://"))
    if isinstance(body, dict):
        check("auth_required", body.get("auth_required") is True)
        check("no roster leak", "clinics" not in body and "users" not in body)

    alpha = verify_clinic(ALPHA)
    gp = verify_clinic(GP)

    print("\n" + "=" * 72)
    print("Cross-clinic isolation")
    print("=" * 72)
    if alpha and gp:
        _, alpha_names = alpha
        _, gp_names = gp
        gp_only = ["Ramesh Kumar", "Arjun Mehta", "Aarav Sharma", "Harish Gupta", "Shalini Menon"]
        alpha_only = ["Ananya Reddy", "Deepa Verma", "Sonal Desai", "Isha Gupta"]
        leaked_gp = [n for n in gp_only if n in alpha_names]
        leaked_alpha = [n for n in alpha_only if n in gp_names]
        check("Alpha isolated from GP patients", not leaked_gp, f"leaked={leaked_gp}" if leaked_gp else "ok")
        check("GP isolated from Alpha patients", not leaked_alpha, f"leaked={leaked_alpha}" if leaked_alpha else "ok")

    code, _ = req(
        "POST",
        "/api/v1/auth/clinic-unlock",
        {"clinic_name": "Alpha Clinic", "password": "WrongPassword"},
    )
    check("wrong password rejected", code in (401, 403), f"HTTP {code}")

    code, _ = req("GET", "/api/v1/history/patients")
    check("unauthenticated blocked", code in (401, 403), f"HTTP {code}")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'=' * 72}")
    print(f"Summary: {passed}/{total} checks passed")
    fails = [n for n, ok, d in results if not ok]
    if fails:
        print("FAILED:")
        for n, ok, d in results:
            if not ok:
                print(f"  - {n}: {d}")
    print("=" * 72)
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
