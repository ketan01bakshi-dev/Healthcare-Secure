# Multi-clinic cloud deploy (Hostinger)

Use this when **many clinics** share one platform and staff phones must work on **mobile data** with **no clinic PC**.

## Platform shape

| Item | Choice |
|------|--------|
| Model | **One shared deployment**, multi-tenant by `clinic_id` |
| Registrar + DNS | **Hostinger** hPanel |
| Domain | **`.in`** product domain (e.g. `healthcaresecure.in`) |
| Host | **Hostinger VPS**, **Mumbai** |
| Start size | **KVM 2** (2 vCPU / 8 GB); upgrade when CPU/RAM/disk pressure appears |
| Stack | Docker Compose: Postgres + API + nginx TLS ([`docker-compose.yml`](../docker-compose.yml)) |
| TLS | Let’s Encrypt → [`deploy/certs/clinic.crt`](../deploy/certs) + `clinic.key` |
| Voice / LLM | Cloud **Groq** (or OpenAI) — stock API image has **no** Whisper/Ollama |
| Phone URL | **Same for all clinics:** `https://api.<product>.in` |

Do **not** put live patient data on free PaaS with sleeping instances. Do **not** use Hostinger shared web hosting or paid SSL for this stack. Do **not** open ports **5432** or **8000** to the public internet.

Related: [`ABDM_SMS_MULTI_TENANT.md`](ABDM_SMS_MULTI_TENANT.md) · [`backend/.env.cloud.example`](../backend/.env.cloud.example) · [`PLAY_STORE.md`](PLAY_STORE.md)

---

## How multi-clinic works

- Staff install the **same Android APK** and point at **one** API host.
- Sign-in PIN maps to a user row that includes `clinic_id`.
- Records, queue, appointments, and analytics are filtered by that `clinic_id`.
- Adding Clinic N does **not** require a new domain, VPS, or APK rebuild.

```env
CLINICS=default|Alpha Clinic|Shastri Nagar, Vidisha, Madhya Pradesh 464001|;east|East Branch|Sector 5|
CLINIC_USERS=default|dr_main|Dr Main|doctor|pbkdf2$...;east|dr_east|Dr East|doctor|pbkdf2$...
```

---

## Phase 1 — Hostinger purchases (once)

1. Create a Hostinger account.
2. **Domains →** buy `yourproduct.in` (1 year, auto-renew on). Decline hosting / email / paid SSL add-ons.
3. **VPS →** order **KVM 2**, datacenter **Mumbai (India)**, OS **Ubuntu 24.04**.
4. From VPS → Manage, save: **public IP**, root password or SSH key.
5. Firewall: allow **22**, **80**, **443**. Do **not** allow public **5432** or **8000**. Prefer SSH keys; restrict SSH if possible.

---

## Phase 2 — DNS (once)

1. Domains → Domain Portfolio → Manage your `.in` domain → **DNS / Nameservers**.
2. Remove conflicting default A/AAAA/CNAME records that park `@` / `www` on shared hosting if they conflict with your intent (root website is optional; the API only needs `api`).
3. Add:

| Type | Name | Points to | TTL |
|------|------|-----------|-----|
| A | `api` | VPS public IP | 300 |
| A | `app` | VPS public IP | 300 |
| A | `www` | VPS public IP | 300 |

4. Wait until `api.yourproduct.in` (and `app.yourproduct.in` for the browser desk) resolve to the VPS IP (minutes to a few hours; up to 24h worst case).

All clinics use `https://api.yourproduct.in`. Staff/receptionist can also open **`https://app.yourproduct.in`** in a desktop browser (same clinic UI as the APK). Per-clinic vanity subdomains are optional later and should still proxy to the same API.

---

## Phase 3 — Server software

SSH as root to the VPS:

```bash
# 1. Docker
curl -fsSL https://raw.githubusercontent.com/ketan01bakshi-dev/Healthcare-Secure/main/deploy/install_docker.sh | bash
# Or clone first, then: bash deploy/install_docker.sh

# 2. App (no secrets in git)
git clone https://github.com/ketan01bakshi-dev/Healthcare-Secure.git
cd Healthcare-Secure

# 3. Env (edit on the server only)
cp backend/.env.cloud.example backend/.env
nano backend/.env   # secrets, CLINICS, CLINIC_USERS, Groq keys, domain hostnames

# 4. Postgres password: set POSTGRES_PASSWORD in .env and pass via compose override
#    See docker-compose.yml comments / POSTGRES_PASSWORD below.

# 5. TLS (writes deploy/certs/clinic.crt + clinic.key)
bash deploy/init_letsencrypt.sh api.yourproduct.in

# 6. Start
export POSTGRES_PASSWORD='your-strong-password'   # must match backend/.env DATABASE_URL user/pass if overridden
docker compose up -d --build

# 7. Health
curl -fsS https://api.yourproduct.in/health
# also: https://api.yourproduct.in/api/v1/health
```

### Required `backend/.env` (production)

Copy from [`backend/.env.cloud.example`](../backend/.env.cloud.example). At minimum:

- Strong `SECRET_KEY` / `SECRET_SALT` (`openssl rand -hex 32`)
- `APP_ENV=production`, `REQUIRE_CLINIC_USERS=true`
- `CLINICS` with **at least two** clinics for day-one isolation checks
- `CLINIC_USERS` with `pbkdf2$…` PINs from `scripts/hash_pin.py`
- `WHISPER_PROVIDER=groq`, `LLM_PROVIDER=groq` + API keys
- `PUBLIC_API_BASE_URL=https://api.yourproduct.in`
- `ALLOWED_HOSTS=api.yourproduct.in`
- `CORS_ORIGINS=capacitor://localhost,https://localhost,https://api.yourproduct.in`
- Strong Postgres password (never leave Compose default `healthcare` in production)

Hash PINs on a trusted machine:

```cmd
cd backend
.\.venv\Scripts\python ..\scripts\hash_pin.py 1234
```

### Voice / LLM on the VPS

```env
WHISPER_PROVIDER=groq
WHISPER_API_KEY=your_key_here
WHISPER_MODEL=whisper-large-v3-turbo
WHISPER_PRELOAD=false
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
LLM_API_KEY=your_key_here
```

Or `openai` for both. Local Whisper/Ollama needs a larger box and a custom image.

---

## Phase 4b — Browser desk (receptionist / staff)

Same Next.js UI as the APK, served at **`https://app.yourproduct.in`**.

1. DNS: A record `app` → VPS IP (see Phase 2).
2. TLS: include both names when issuing certs:
   `bash deploy/init_letsencrypt.sh api.yourproduct.in app.yourproduct.in`
3. `CORS_ORIGINS` on the VPS must include `https://app.yourproduct.in` (see `.env.cloud.example`).
4. nginx serves `deploy/web` for the `app` host (see `deploy/nginx/nginx.conf` + `docker-compose.yml`).
5. From Windows after frontend changes:

```cmd
scripts\deploy_web.cmd
```

Sign in with clinic name + password, then receptionist or staff profile + PIN — same as the phone app.

Public **product / marketing** site (no PHI, no PINs): **`https://www.yourproduct.in`** — nginx root `deploy/www`. Publish with `scripts\deploy_www.cmd`. Include `www` on the Let’s Encrypt SAN list.

---

## Phase 4 — One APK for every clinic

On the Windows build machine:

```cmd
cd frontend
set CAPACITOR_HTTPS=true
set NEXT_PUBLIC_API_BASE_URL=https://api.yourproduct.in
npm run mobile:build
npm run cap:open:android
```

Install the same APK on all staff phones. **Clinic server address** = `https://api.yourproduct.in` (saved on device if not baked in).

### Multi-clinic mobile-data smoke test

1. Turn **Wi‑Fi off**; use mobile data only.
2. Open `https://api.yourproduct.in/health` in the phone browser.
3. Sign in as Clinic A doctor → lock a patient → confirm queue/timeline.
4. Sign out; sign in as Clinic B doctor → confirm Clinic A patients/queue are **not** visible.
5. Complete one voice Rx path on Clinic A to confirm Groq STT/LLM.

See also [Add a clinic](#add-a-clinic) and [`ABDM_SMS_MULTI_TENANT.md`](ABDM_SMS_MULTI_TENANT.md).

---

## Razorpay UPI QR (patient pay)

Staff can show a scannable UPI QR from **Patient Info → Billing** (amount due or typed amount). When Razorpay confirms payment, the API appends a `kind: payment` ledger row automatically.

1. Create a Razorpay account (use **test mode** first).
2. On the VPS `backend/.env`:

```env
PAYMENTS_ENABLED=true
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

3. Razorpay Dashboard → Webhooks → add:

`https://api.yourproduct.in/api/v1/payments/webhook/razorpay`

Subscribe at least to `payment.captured` and `qr_code.credited`. Use the webhook secret as `RAZORPAY_WEBHOOK_SECRET`.

4. Recreate API: `docker compose up -d --force-recreate api`.

5. Smoke-test: lock a patient → add charge → **Show pay QR** → pay with UPI (or test tools) → amount due drops.

Local demo without Razorpay: `RAZORPAY_MOCK=true` (then `POST /api/v1/payments/{id}/mock-pay` or wait for UI poll after calling mock-pay from tests). Never enable mock in production.

Key secret stays **server-only** — never put it in the APK or frontend env.

---

## Phase 5 — First clinic data migration

If a clinic already ran on a laptop (SQLite):

1. Stop local uvicorn.
2. Backup: `scripts\backup_db.cmd` and copy `backend/data/attachments`.
3. On the VPS, restore/migrate into Postgres under that clinic’s `clinic_id` (usually `default`). Place attachments where the API expects them (`ATTACHMENTS_DIR` / default data path).
4. Smoke-test that clinic’s PIN on mobile data.
5. **Retire the clinic PC API** so phones are not split between LAN and cloud.

---

## Add a clinic

No new DNS, VPS, or APK.

1. On the VPS, edit `backend/.env`:
   - Append to `CLINICS`: `newid|Display Name|Address|`
   - Append staff to `CLINIC_USERS`: `newid|user_id|Display Name|role|pbkdf2$…`
2. Restart API: `docker compose up -d --force-recreate api` (or `docker compose restart api` if env is re-read; prefer recreate after `.env` edits).
3. Issue PINs to staff; same APK + same `https://api.yourproduct.in`.
4. Isolation check: Clinic N must not see other clinics’ patients/queue.

Optional demo data for a second clinic (from backend venv):

```cmd
scripts\seed_demo.cmd --clinic east
scripts\seed_demo_gp.cmd --wipe
```

Ensure `CLINICS` / `CLINIC_USERS` already include `east` or `gp` before staff sign-in.

---

## Phase 6 — Ongoing ops

| Task | Action |
|------|--------|
| Nightly DB backup | On VPS: cron `deploy/backup_pg.sh`; copy dumps off-box weekly |
| Cert renewal | `certbot renew` then reload nginx (see `init_letsencrypt.sh` install notes) |
| App updates | `git pull` → `docker compose up -d --build` (all clinics upgrade together) |
| Restart API only | Step-by-step: [`RESTART_PRODUCTION_API.md`](RESTART_PRODUCTION_API.md) (`--force-recreate api` after `.env` edits) |
| Video consult | Enable `video_consult` in clinic `CLINICS` features; set `VIDEO_CONSULT_PROVIDER=jitsi` and `JITSI_BASE_URL` (default `https://meet.jit.si`). Doctor Visit panel mints a room + SMS join link — **no call recording** on the VPS. |
| Capacity | Watch Hostinger CPU/RAM/disk; upgrade VPS tier before many high-volume clinics |
| New phone | Same HTTPS APK + same API URL + that user’s PIN |

```bash
# Example cron (root): nightly 02:15 IST-ish — adjust TZ
# 15 2 * * * cd /root/Healthcare-Secure && bash deploy/backup_pg.sh
```

---

## Known gaps (early multi-clinic pilots)

- Prescription PDF letterhead still leans on global `CLINIC_*` more than per-clinic branding.
- Onboarding is **env-edit + restart**, not an admin “Create clinic” UI.
- Attachments share one disk volume — plan Hostinger disk growth and whole-platform backups.
- Live ABDM needs this public HTTPS base; per-clinic facility IDs may come later.

---

## Local LAN still works (single-clinic Wi‑Fi fallback)

For clinic Wi‑Fi only (no cloud), keep uvicorn on `0.0.0.0:8000` and use `scripts\watch_api.cmd`. Production multi-clinic path is this Hostinger guide.
