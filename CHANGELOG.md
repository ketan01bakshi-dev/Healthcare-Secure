# Changelog

All notable changes to Aarogya One Connect are documented here.
Versions follow [SemVer](https://semver.org/) (`MAJOR.MINOR.PATCH`).
Git tags and GitHub Releases use a `v` prefix (e.g. `v0.1.0`).

## [Unreleased]

### Added

- Patient billing ledger on **Patient Info** (`POST /history/billing`, `billing-summary`); roles doctor/staff/receptionist
- Razorpay UPI QR pay (`/api/v1/payments/*`, webhook → ledger payment); see [`docs/CLOUD_DEPLOY.md`](docs/CLOUD_DEPLOY.md)
- Video consult (Jitsi) behind clinic feature `video_consult`
- Receptionist role (Patient Info + More); nav labels Patient Info / Vitals
- Share HTTPS APK helper [`scripts/build_share_apk.cmd`](scripts/build_share_apk.cmd); More page **UI build** stamp
- Hostinger multi-clinic cloud runbook ([`docs/CLOUD_DEPLOY.md`](docs/CLOUD_DEPLOY.md)): shared Mumbai VPS, DNS `api` A(+AAAA) record, Let’s Encrypt scripts, add-clinic ops, mobile-data smoke test
- [`backend/.env.cloud.example`](backend/.env.cloud.example) — two-clinic production template (Groq STT/LLM)
- Deploy helpers: `deploy/install_docker.sh`, `deploy/init_letsencrypt.sh`, `deploy/backup_pg.sh`
- Demo seed `--clinic <id>` for second-tenant isolation checks (`scripts/seed_demo.cmd --clinic east`)
- Clinic server URL: bare public hostnames default to `https://` (`apiBase.ts`)
- Browser clinic desk at `https://app.aarogyaoneconnect.in` (static Next export on nginx; same UI as APK)
- Today-only patient pick (All patients / waiting list); Vitals has no Select form
- Persisted Visit lab orders (`GET`/`PUT /history/lab-orders`) + ~15s directory/chart poll
- Role routing after lock: doctor → Visit, staff → Vitals, lab → Labs, receptionist stays Patient Info
- `scripts/deploy_web.cmd` to publish the browser desk

### Changed

- Doctor PIN / app home lands on **Patient Info** (pick first); lock then opens Visit (including video)
- Lab nav is Today / Labs / More only; lab never sees billing
- Handbook edition 15 Aug 2026 (Era O, RCA-23 Lab Desk 403, RCA-24 CORS Failed-to-fetch)
- Visit: sections default collapsed; order vitals trend → case brief → video → prescription
- Docker Compose: `restart: unless-stopped`; Postgres not published publicly; API bound to `127.0.0.1:8000`
- After `force-recreate api`, also restart **nginx** (stale upstream IP → 502)
- README: Hostinger multi-clinic cloud is the primary production path; LAN Wi‑Fi is fallback
- Handbook edition 4 Aug 2026 (Eras M/N, RCA-18…22)

### Fixed

- Dual-stack DNS: add AAAA when some ISPs black-hole VPS IPv4
- Lab Desk 403 on patient lock: tokenize/directory use `DoctorSession`; `bump_visit` skipped for lab (RCA-23)
- Browser desk Continue → Failed to fetch: add `https://app.*` to `CORS_ORIGINS` and publish `deploy/web` (RCA-24)
- Compose `$$` escaping for `pbkdf2$` hashes in `CLINIC_USERS` / `CLINICS`
- Phone missing latest UI: Capacitor embeds `out/` — rebuild/reinstall APK after frontend changes (not API-only deploy)
- Offline banner stuck after empty vitals 400: only queue network/5xx; drop 400/422 on flush; require a vital/note before save
- `VitalsTrendCharts` Python-style `*` keyword-only args broke `npm run mobile:build`

### Added (prior)

- OPD multi-tab shell: Today / Patient / Visit / Records / Labs / More + ClinicNav
- Obstetric profile (LMP/EDD/GPLA/Rh/high-risk) + gestational age on patient chip
- Hemoglobin on vitals; pregnancy-aware weight/BP/Hb trend charts (GA X-axis when LMP set)
- Patient case brief + `GET /history/case-summary` (deltas, labs, docs, ANC alerts, scan cadence)
- ANC rule alerts (`anc_alerts.py`) on vitals-trend and case brief; lab Hb merged into trends
- `POST /history/consult-pack` (LLM + rule fallback); `POST /history/rx-hints` pre-sign soft warnings
- `POST /history/documents/{id}/analyze` — USG/report findings; Analyze on attachments
- Waiting List Open → lock patient; Google Calendar / `.ics`; day-before SMS (`scripts/remind_day_before.cmd`)
- Demo seed showcase: `scripts/seed_demo.cmd` (--wipe) with ten gynae patients + analytics volume
- Client demo cue cards: [`docs/DEMO_CLIENT.md`](docs/DEMO_CLIENT.md); Visit → Load demo transcript
- Ollama clinical parse: few-shot prompt, JSON retry, heuristic fallback; Whisper medical initial_prompt + `base.en`
- Ops: `scripts/watch_api.cmd` health watchdog; Whisper preload default off; phone first-run clinic URL setup; `docs/CLOUD_DEPLOY.md`
- Analytics: `/api/v1/analytics/today`, `/week`, `/frequency`, vitals-trend, de-identified CSV + Clinic Analytics UI
- Hardening: TrustedHostMiddleware from ALLOWED_HOSTS; rate-limit on `/auth/unlock`; `scripts/backup_pg.cmd` / `restore_pg.cmd`
- Attachments stored on disk (`content_path`) instead of base64-in-DB; legacy base64 still readable
- °C/°F temperature preference; expanded neonatal pediatric vitals bands; HL7 ORU MSA ACK response
- Multi-tenant clinics (`CLINICS` + optional `clinic_id|…` in `CLINIC_USERS`); records/queue/appointments scoped by clinic
- ABDM/ABHA: gateway OTP verify + link (`ABDM_*` / `ABDM_MOCK`), callback route; local HMAC link retained
- Appointments API + SMS (`SMS_PROVIDER=console|msg91|twilio`) with encrypted phone storage
- See [`docs/ABDM_SMS_MULTI_TENANT.md`](docs/ABDM_SMS_MULTI_TENANT.md)
- Clinic MRN identity (`mrn|{id}`) so history survives phone/name changes
- Structured lab results + HL7 ORU ingest + ABHA local link (HMAC only)
- Print-first prescription CTA; today's waiting queue
- Hindi/English UI toggle; offline queue for vitals/lab when API is down
- Docker Compose (Postgres + API + nginx TLS); Play Store AAB docs
- Pediatric vitals ranges when age is provided
- Runtime clinic server URL on sign-in (saved on device; no APK rebuild for IP changes)
- Durable clinic sessions in SQLite (survive API restart; 7-day expiry)
- PIN hashing helper (`scripts/hash_pin.py`), lockout after failed attempts
- `REQUIRE_CLINIC_USERS` / production mode blocks open local-doctor access
- Patient activity log (who changed what)
- SQLite backup/restore scripts; GitHub Actions pytest CI

## [0.1.0] - 2026-07-20

### Added

- Dual-root clinic app: FastAPI backend + Next.js / Capacitor frontend
- Patient lock by name + 10-digit phone (HMAC-blinded history)
- Doctor / staff roles, vitals entry, voice dictation, sign & seal PDF
- Document upload, timeline, and free native share (no Twilio)
- Simplified clinic UI copy for non-technical staff
