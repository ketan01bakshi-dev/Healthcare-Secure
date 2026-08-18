# ABHA/ABDM, SMS appointments, multi-tenant clinics

## Multi-tenant clinics

Define clinics and stamp users with a clinic id:

```env
CLINICS=default|Alpha Clinic|Shastri Nagar, Vidisha, Madhya Pradesh 464001|;east|East Branch|Sector 5|
CLINIC_USERS=default|dr1|Dr Main|doctor|1234;east|dr2|Dr East|doctor|1234;east|nurse1|Nurse East|staff|5678
```

- 4-field `CLINIC_USERS` rows still map to clinic `default` (backward compatible).
- Sessions carry `clinic_id`; clinical records, queue, appointments, and analytics are filtered by it.
- Existing DBs get `clinic_id` columns added on API startup (`schema_migrate`).

### Add a clinic (shared Hostinger platform)

No new domain, VPS, or APK. Full cloud runbook: [`CLOUD_DEPLOY.md`](CLOUD_DEPLOY.md).

1. On the VPS, edit `backend/.env`:
   - Append `newid|Display Name|Address|` to `CLINICS`
   - Append `newid|user_id|Name|role|pbkdf2$…` rows to `CLINIC_USERS` (hash with `scripts/hash_pin.py`)
2. Recreate/restart the API container so it reloads env:  
   `docker compose up -d --force-recreate api`
3. Give staff the **same** APK and **same** `https://api.<product>.in` URL plus their new PIN.
4. Isolation smoke test: Clinic N must not see other clinics’ patients or queue.

Demo seed for a second clinic (optional):

```cmd
scripts\seed_demo.cmd --clinic east
scripts\seed_demo.cmd --clinic east --wipe
```

### Cloud production template

Use [`backend/.env.cloud.example`](../backend/.env.cloud.example) on Hostinger (two sample clinics + Groq). Never commit real `.env`.

## ABHA / ABDM

| Mode | How |
|------|-----|
| Local HMAC | `POST /api/v1/integrations/abha/link` without OTP (consent required) |
| Demo OTP | `ABDM_MOCK=true` → Request OTP → confirm with `123456` → link with `txn_id` |
| Sandbox / prod | Set `ABDM_CLIENT_ID`, `ABDM_CLIENT_SECRET`, `ABDM_FACILITY_ID`; register callback URL |

Endpoints:

- `GET /integrations/abha/status`
- `POST /integrations/abha/otp/request`
- `POST /integrations/abha/otp/confirm`
- `POST /integrations/abha/link`
- `POST /integrations/abdm/callback/{path}` — gateway async callbacks

National ABDM still requires NHA sandbox/production approval, HIP registration, and a public HTTPS callback. This app implements the gateway session + MOBILE_OTP init/confirm shape used in Milestone-1 verify flows; care-context / HIU discovery is not included.

## SMS appointments

```env
SMS_PROVIDER=console   # or msg91 | twilio | none
```

- `POST /api/v1/appointments` books a slot and optionally sends confirmation SMS.
- `POST /appointments/{id}/remind` and `/cancel` (with notify).
- Phones are Fernet-encrypted at rest (`SECRET_KEY`); only last-4 is shown in the UI.

Use `console` in development (prints the SMS body). For India clinics, MSG91 is typical; Twilio also works.
