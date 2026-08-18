# Restart the production API (Aarogya One Connect)

Step-by-step runbook for restarting the **backend API** on the Hostinger Mumbai VPS. Use this when you change `backend/.env` (users, clinics, keys), after a hang, or when you need env to reload without rebuilding the image.

Related: [`CLOUD_DEPLOY.md`](CLOUD_DEPLOY.md) · [`share/ROTATE_GROQ.md`](../share/ROTATE_GROQ.md)

---

## What you are restarting

| Item | Value |
|------|--------|
| Public API | `https://api.aarogyaoneconnect.in` |
| VPS (SSH) | `root@187.127.170.45` |
| SSH key (local) | `~/.ssh/healthcare_hostinger` (Windows: `%USERPROFILE%\.ssh\healthcare_hostinger`) |
| App directory on VPS | `/root/Healthcare-Secure` |
| Compose service name | `api` (container `healthcare-secure-api-1`) |
| Stack | Docker Compose: `db` + `api` + `nginx` |

Do **not** restart Postgres (`db`) unless you intend a DB outage. Nginx can stay up; it will briefly fail upstream until the API is healthy again.

---

## Choose the right command

| Situation | Command |
|-----------|---------|
| Changed `backend/.env` (users, clinics, Groq keys, CORS, etc.) | `docker compose up -d --force-recreate api` |
| API hung / process crash; no env change | `docker compose restart api` |
| Pulled new code that needs a new image | `git pull` then `docker compose up -d --build` |

**Prefer force-recreate after any `.env` edit.** Plain `restart` may keep an old env snapshot depending on how the container was created.

**Always restart nginx after `force-recreate api`.** The API container can get a new Docker network IP; nginx may keep proxying to the old upstream and return **502** while `http://127.0.0.1:8000/health` still looks fine:

```bash
docker compose up -d --force-recreate api
docker compose restart nginx
```

See handbook RCA-18.

---

## From your Windows PC (recommended)

### 1. Confirm SSH key exists

In PowerShell:

```powershell
Test-Path "$env:USERPROFILE\.ssh\healthcare_hostinger"
```

Must print `True`. If missing, recover the key from your secure backup or Hostinger panel / previous machine before continuing.

### 2. Check current health (optional)

```powershell
curl.exe -fsS https://api.aarogyaoneconnect.in/health
```

Expected JSON includes `"status":"ok"`.

### 3. SSH and recreate the API container

One-shot from PowerShell:

```powershell
ssh -i "$env:USERPROFILE\.ssh\healthcare_hostinger" -o BatchMode=yes root@187.127.170.45 "cd /root/Healthcare-Secure && set -a && [ -f .compose.env ] && . ./.compose.env; set +a && docker compose up -d --force-recreate api && docker compose ps"
```

What this does:

1. Loads optional Compose secrets from `.compose.env` (e.g. `POSTGRES_PASSWORD`) if present.
2. Recreates **only** the `api` service from the existing image, re-reading `backend/.env`.
3. Waits for Postgres health, then starts the new API container.
4. Prints `docker compose ps` so you can see `api` as `Up`.

Interactive equivalent:

```powershell
ssh -i "$env:USERPROFILE\.ssh\healthcare_hostinger" root@187.127.170.45
```

Then on the VPS:

```bash
cd /root/Healthcare-Secure
set -a && [ -f .compose.env ] && . ./.compose.env; set +a
docker compose up -d --force-recreate api
docker compose ps
```

### 4. Wait a few seconds, then verify

Uvicorn may take ~5–15 seconds after “Started” before it accepts connections. If you curl immediately you may see connection reset — wait and retry.

From Windows:

```powershell
Start-Sleep -Seconds 8
curl.exe -fsS https://api.aarogyaoneconnect.in/health
```

From the VPS (localhost, bypasses nginx):

```bash
curl -fsS http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok","service":"Aarogya One Connect API","version":"0.1.0","whisper_provider":"groq"}
```

### 5. Confirm clinic sign-in still works

On a phone (or browser hitting the API): unlock with clinic password + a known PIN. If you added a new role/user in `CLINIC_USERS`, that profile should appear in the unlock roster **after** this recreate.

---

## From the VPS shell only

If you are already logged in via Hostinger console / SSH:

```bash
cd /root/Healthcare-Secure
set -a && [ -f .compose.env ] && . ./.compose.env; set +a

# After .env edits — preferred
docker compose up -d --force-recreate api

# Or quick bounce with no env change
# docker compose restart api

sleep 8
curl -fsS http://127.0.0.1:8000/health
curl -fsS https://api.aarogyaoneconnect.in/health
docker compose ps
docker compose logs --tail=80 api
```

---

## After editing `backend/.env` on the VPS

Typical flow when adding a clinic user or receptionist:

1. SSH in (see above).
2. Backup the env file first:

   ```bash
   cp backend/.env backend/.env.bak.$(date +%Y%m%d%H%M)
   ```

3. Edit carefully:

   ```bash
   nano backend/.env
   ```

   Append users to `CLINIC_USERS` (role `doctor` | `staff` | `receptionist` | `lab`). Do not commit this file; it stays only on the VPS.

4. Force-recreate API (step 3 above).
5. Health-check (step 4).
6. Sign in with the new profile on the app.

Hashed PINs use `pbkdf2$…` in cloud; plain PINs in env are only for local/dev. Production usually stores hashed values — see `deploy/set_clinic_passwords.sh` and `SHARE_PACK.md`.

---

## After deploying new code

```bash
cd /root/Healthcare-Secure
git pull
set -a && [ -f .compose.env ] && . ./.compose.env; set +a
docker compose up -d --build
sleep 10
curl -fsS https://api.aarogyaoneconnect.in/health
```

`--build` rebuilds the API image; all clinics share the upgrade. Nginx and DB stay as defined in `docker-compose.yml`.

---

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| `Permission denied (publickey)` | Wrong key path; use `-i` with `healthcare_hostinger`. Ensure `BatchMode` isn’t required if you use a passphrase-protected key interactively. |
| Health curl fails for ~10s after recreate | Normal cold start — wait and retry. |
| Health still failing after 30s | `docker compose logs --tail=100 api` — look for env parse errors, DB connection, or crash loops. |
| `db` unhealthy | Do **not** force-recreate blindly; check `docker compose logs db` and disk space (`df -h`). |
| Sign-in roster missing new user | Env edit not saved, typo in `CLINIC_USERS`, or you used `restart` instead of `--force-recreate`. Recreate again. |
| HTTPS works but localhost:8000 fails | API down; nginx may still answer with 502. Fix `api` first. |
| 502 from public URL | `docker compose ps` — is `api` Up? Is nginx Up? `docker compose logs nginx --tail=50`. |

Useful inspection commands:

```bash
docker compose ps
docker compose logs --tail=100 api
docker inspect healthcare-secure-api-1 --format '{{.State.Status}} {{.State.StartedAt}}'
df -h
free -h
```

---

## What not to do

- Do **not** open Postgres `5432` or API `8000` on the public internet (API is bound to `127.0.0.1:8000` on purpose).
- Do **not** commit `backend/.env` or paste live PINs/API keys into git or chat.
- Do **not** run `docker compose down -v` — that can destroy the Postgres volume.
- Do **not** `docker compose restart` as a substitute for recreate when you need new env vars loaded.

---

## Quick copy-paste (Windows → production recreate)

```powershell
ssh -i "$env:USERPROFILE\.ssh\healthcare_hostinger" -o BatchMode=yes root@187.127.170.45 "cd /root/Healthcare-Secure && set -a && [ -f .compose.env ] && . ./.compose.env; set +a && docker compose up -d --force-recreate api"
Start-Sleep -Seconds 8
curl.exe -fsS https://api.aarogyaoneconnect.in/health
```
