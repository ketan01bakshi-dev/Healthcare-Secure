# Aarogya One Connect

**Single source of truth (student handbook):**  
[docs/Healthcare_Secure_Handbook.docx](docs/Healthcare_Secure_Handbook.docx) — complete guide from first scaffold to current clinic app (architecture, Android/Capacitor, analytics, ABDM/SMS/multi-tenant, gynae decision support, Hostinger cloud ops, patient billing / Razorpay UPI QR, video consult, browser desk at `app.*`, Today-only patient pick, persisted lab orders, dual-stack DNS + nginx upstream RCA, Capacitor stale-UI RCA, Lab Desk 403 RCA, CORS Failed-to-fetch RCA, secrets, paid India VPS). Edition **15 Aug 2026**. Rebuild with `python docs/build_handbook_docx.py` (diagrams: `python docs/build_handbook_diagrams.py`).

Annexes: [CLOUD_DEPLOY.md](docs/CLOUD_DEPLOY.md) · [RESTART_PRODUCTION_API.md](docs/RESTART_PRODUCTION_API.md) · [PLAY_STORE.md](docs/PLAY_STORE.md) · [PRIVACY_POLICY.md](docs/PRIVACY_POLICY.md) · [ABDM_SMS_MULTI_TENANT.md](docs/ABDM_SMS_MULTI_TENANT.md) · [DEMO_CLIENT.md](docs/DEMO_CLIENT.md) · [CHANGELOG.md](CHANGELOG.md) · [AGENTS.md](AGENTS.md) (Android / Cloud Agents)

Production-oriented dual-root layout for a secure healthcare web app.

```
Healthcare/
├── backend/          # Python FastAPI API
├── frontend/         # Next.js App Router + Tailwind + TypeScript
└── docs/             # Handbook (.docx), Play Store notes, diagrams
```

## Backend

```cmd
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Default transcription is **local CPU Whisper** (`faster-whisper`, `tiny.en`) — no API key. Keep clips short (5–15 s).

Clinical parsing defaults to **Ollama** (fully free, local):

```cmd
winget install Ollama.Ollama
ollama pull llama3.2
ollama serve
```

```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
LLM_API_KEY=ollama
```

Optional cloud: `LLM_PROVIDER=openai` or `groq` with `LLM_API_KEY`. Optional cloud Whisper via `WHISPER_PROVIDER=openai`.

## Frontend

```cmd
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

CORS allows `http://localhost:3000` and `http://127.0.0.1:3000` by default.

### Clinical workflow (dashboard)

1. **Lock patient** — enter patient name → HMAC-encoded blind ID (name never stored in DB).
2. **Record** one or more voice segments → session transcript list.
3. **Write prescription** — consolidates transcripts → LLM parse → PDF → saves history → share sheet / copy link.
4. **Upload** scanned prescriptions or diagnostic reports against the same patient.
5. **Timeline** auto-loads for the locked patient (visits + documents).

Requires Ollama (`LLM_PROVIDER=ollama`) for structured parse when writing a prescription.

Prescription PDFs use a clinic letterhead template (clinic name + doctor seal) and auto-stamp local date/time (`PRESCRIPTION_TIMEZONE`, default `Asia/Kolkata`). Optional images: `backend/app/assets/doctor_seal.png`, `letterhead.png`.


### Production (multi-clinic, phones everywhere)

**Primary path:** one Hostinger Mumbai VPS + `.in` domain + shared HTTPS API for **all** clinics (no clinic PC). Same Android APK; PIN selects `clinic_id`.

Full checklist: [docs/CLOUD_DEPLOY.md](docs/CLOUD_DEPLOY.md) (DNS `api` A record, Let’s Encrypt, Groq STT/LLM, add-clinic ops, backups). Env template: [`backend/.env.cloud.example`](backend/.env.cloud.example).

### Phone setup (LAN Wi‑Fi fallback — single clinic)

Your laptop LAN IP is used so the phone can reach the API. Example: `192.168.1.19`. Use this only for local Wi‑Fi demos; production multi-clinic is cloud ([CLOUD_DEPLOY.md](docs/CLOUD_DEPLOY.md)).

**1. Backend — bind to all interfaces + restart**

```cmd
cd backend
.\.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In `backend/.env` (already set for `192.168.1.19` on this machine):

- `ALLOWED_HOSTS` includes your LAN IP
- `CORS_ORIGINS` includes `http://YOUR_LAN_IP:3000` and Capacitor origins
- `PUBLIC_API_BASE_URL=http://YOUR_LAN_IP:8000`

Allow Windows Firewall inbound TCP **8000** (and **3000** if using the phone browser).

**2a. Quick test — phone browser**

```cmd
cd frontend
REM .env.local → NEXT_PUBLIC_API_BASE_URL=http://YOUR_LAN_IP:8000
npm run dev -- -H 0.0.0.0 -p 3000
```

On the phone open `http://YOUR_LAN_IP:3000`.

**2b. Capacitor Android app**

```cmd
cd frontend
npm run mobile:build
npm run cap:open:android
```

In Android Studio: Run on a USB device or emulator. Allow microphone when prompted.

`NEXT_PUBLIC_API_BASE_URL` is baked in at **build** time — change `.env.local`, then `npm run mobile:build` again after IP changes.

| Script | What it does |
|--------|----------------|
| `mobile:build` | `next build` → `out/` then `cap sync` |
| `cap:open:android` | Open the Android project (prefers registry Studio path) |
| `mobile:android` | Build + sync + open IDE |

Prescription delivery uses the **Web Share API** (native share sheet / SMS) — no Twilio. Desktop falls back to copy-to-clipboard.

### Native mic

- **Android:** `RECORD_AUDIO` + cleartext HTTP for the LAN API (dev)
- **iOS:** needs a Mac; set `NSMicrophoneUsageDescription` in `Info.plist`

## Releases (GitHub-style)

Versions are maintained on GitHub:
[ketan01bakshi-dev/Healthcare-Secure](https://github.com/ketan01bakshi-dev/Healthcare-Secure)
([Releases](https://github.com/ketan01bakshi-dev/Healthcare-Secure/releases)).

Tag a commit → publish a Release with notes. Keep the same SemVer in two places:

| File | Field |
|------|--------|
| `frontend/package.json` | `"version"` |
| `backend/app/__init__.py` | `__version__` |

Check the running API: `GET http://127.0.0.1:8000/api/v1/health` → `{ "status": "healthy", "version": "0.1.0" }`.

### SemVer

| Change | Bump |
|--------|------|
| Bug fix / copy | patch (`0.1.0` → `0.1.1`) |
| New feature | minor (`0.1.1` → `0.2.0`) |
| Breaking clinic change | major (`0.2.0` → `1.0.0`) |

Tag format: `v` + SemVer (`v0.2.0`).

### Publish a release

1. Finish work on `main` (or merge your PR).
2. Move notes from `[Unreleased]` in `CHANGELOG.md` into a new `## [X.Y.Z] - YYYY-MM-DD` section.
3. Set `X.Y.Z` in `frontend/package.json` and `backend/app/__init__.py`.
4. Commit: `chore: release X.Y.Z`
5. Tag and push (from repo root, PowerShell or cmd):

```cmd
git tag v0.2.0
git push origin main --tags
```

6. Create the GitHub Release (pick one):

**GitHub UI (recommended if `gh` is not installed)**

Open [New release](https://github.com/ketan01bakshi-dev/Healthcare-Secure/releases/new), choose tag `v0.2.0`, paste the changelog section, and publish.

**CLI** (requires [GitHub CLI](https://cli.github.com/))

```cmd
gh release create v0.2.0 --repo ketan01bakshi-dev/Healthcare-Secure --title "v0.2.0" --notes "See CHANGELOG.md section [0.2.0]."
```

7. Deploy that build to the clinic: restart the API, then `cd frontend` → `npm run mobile:build` and install the APK. Optionally set Android Studio `versionName` to the same SemVer by hand.

### First release (`v0.1.0`)

Publish the baseline on [Healthcare-Secure](https://github.com/ketan01bakshi-dev/Healthcare-Secure):

```cmd
git tag v0.1.0
git push origin main --tags
```

Then open [New release](https://github.com/ketan01bakshi-dev/Healthcare-Secure/releases/new), select tag `v0.1.0`, title `v0.1.0`, and paste the `[0.1.0]` section from `CHANGELOG.md`.

Or with GitHub CLI:

```cmd
gh release create v0.1.0 --repo ketan01bakshi-dev/Healthcare-Secure --title "v0.1.0" --notes "Initial clinic release. See CHANGELOG.md."
```

No CI is required for a release tag, but GitHub Actions runs pytest on push (see `.github/workflows/ci.yml`).

## Database backup

SQLite file is typically `backend/healthcare.db` (or path in `DATABASE_URL`).

```cmd
scripts\backup_db.cmd
scripts\restore_db.cmd backend\backups\healthcare_YYYYMMDD_HHMMSS.db
```

Stop the API before restore. Sessions survive API restarts (stored in `clinic_sessions` table, 7-day expiry).

**Postgres (Docker Compose):**

```cmd
scripts\backup_pg.cmd
scripts\restore_pg.cmd backend\backups\pg_YYYYMMDD_HHMMSS.sql
```

## Clinic server URL on the phone

On the sign-in screen, set **Clinic server address** (e.g. `http://192.168.1.19:8000`) and tap **Save & reconnect**. The value is stored on the device — no APK rebuild when the LAN/hotspot IP changes.

## Hashing PINs

```cmd
cd backend
.\.venv\Scripts\python ..\scripts\hash_pin.py 1234
```

Put the printed `pbkdf2$...` value in `CLINIC_USERS` instead of the plaintext PIN. After 5 wrong PINs, that user is locked for 5 minutes.

Set `REQUIRE_CLINIC_USERS=true` or `APP_ENV=production` to disable open “local doctor” mode when no users are configured.

## Keep the API alive (watchdog)

If uvicorn hangs (port open but `/health` never answers), phones show “no profiles”. Leave this running during clinic hours:

```cmd
scripts\watch_api.cmd
scripts\watch_api.cmd http://127.0.0.1:8000 15
```

It polls `/health` and restarts the API after repeated failures (`WHISPER_PRELOAD=false`).

### Quick troubleshooting (phone / API)

| Symptom | Check / fix |
|---------|-------------|
| Phone “Loading…” or “no profiles” | `curl -m 3 http://127.0.0.1:8000/health` must succeed; restart API with `WHISPER_PRELOAD=false`; set clinic URL to `http://LAN:8000` (**not** localhost) |
| Empty users on unlock | Real accounts are in `backend/.env` (`CLINIC_USERS`), not blank `.env.example` |
| Port 8000 listening but no HTTP | Kill stuck uvicorn; run `scripts\watch_api.cmd` |
| AGP ProGuard build error | `npm run mobile:build` runs `fix-agp-proguard.mjs` (optimize ProGuard file) |
| Browser Continue → Failed to fetch | CORS must include `https://app.aarogyaoneconnect.in`; publish `scripts\deploy_web.cmd`; hard-refresh (RCA-24) |
| Lab Desk cannot lock a patient (403) | Tokenize uses `DoctorSession`; lab does not bump visit (RCA-23) |

Full write-ups: handbook **Part V, RCA-11–RCA-24**.

## Docker / Postgres / TLS

```cmd
deploy\gen_self_signed_cert.cmd
docker compose up --build
```

- API: container port 8000 bound to **localhost only** on the host (`127.0.0.1:8000`); phones use **nginx :443**
- Postgres: internal Docker network only (not published publicly). Override password with `POSTGRES_PASSWORD` / `backend/.env`
- HTTPS: nginx on **443** with `deploy/certs/clinic.crt`

Point the app **Clinic server address** to `https://YOUR_LAN_IP` after trusting the cert (LAN), or `https://api.yourproduct.in` (Hostinger — [CLOUD_DEPLOY.md](docs/CLOUD_DEPLOY.md)).

For **phones on 4G / multi-clinic platform (no clinic PC)**, follow [docs/CLOUD_DEPLOY.md](docs/CLOUD_DEPLOY.md) (Hostinger Mumbai VPS + Let’s Encrypt + Groq + `CLINICS`).

Receptionist / staff **browser desk** (same UI as the APK): [https://app.aarogyaoneconnect.in](https://app.aarogyaoneconnect.in). After frontend changes: `scripts\deploy_web.cmd` (does not update phones — still rebuild the APK).

In **production**, set `ALLOWED_HOSTS` to your real hostname (e.g. `api.yourproduct.in`) — TrustedHost is enforced when `APP_ENV=production`. Do not publish Postgres `5432` publicly.

## Build from Android (Cloud Agents)

There is no native Cursor Android app. On the phone, open [cursor.com/agents](https://cursor.com/agents) in Chrome → **Install app**, sign in with the same account, and pick this GitHub repo. Feature work uses a Cloud machine (opens a PR). Live debugging of this PC / VPS uses the **healthcare-pc** My Machines worker. Full steps: [AGENTS.md](AGENTS.md).

## Play Store AAB

See [docs/PLAY_STORE.md](docs/PLAY_STORE.md) and `scripts\build_aab.cmd`. Host or paste [docs/PRIVACY_POLICY.md](docs/PRIVACY_POLICY.md) for the store listing. For cloud HTTPS APK builds: `set CAPACITOR_HTTPS=true` then `npm run mobile:build`.

## ABHA / HL7 / SMS / multi-clinic

See [docs/ABDM_SMS_MULTI_TENANT.md](docs/ABDM_SMS_MULTI_TENANT.md).

- **Link ABHA** supports local HMAC or ABDM MOBILE_OTP (`ABDM_MOCK=true` for demo OTP `123456`).
- `POST /api/v1/integrations/hl7/oru` imports OBX rows and returns an MSA-style `hl7_ack`.
- **Appointments** with SMS via `SMS_PROVIDER` (console / msg91 / twilio).
- **Multi-clinic:** `CLINICS` + `clinic_id|user|…` in `CLINIC_USERS`.
