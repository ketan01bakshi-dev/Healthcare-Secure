# Manual Deploy + Smoke (CD + CT)

This repo’s **CI** (`.github/workflows/ci.yml`) still runs pytest on every push/PR.

**Deploy to production does not run on push.** Use the manual workflow:

**Actions → Deploy + smoke (manual) → Run workflow**

## What it does

| Input `target` | Effect |
|----------------|--------|
| `api` | Sync code → rebuild/recreate Docker `api` → restart nginx → smoke |
| `www` | Sync `deploy/www` → reload nginx → smoke |
| `api+www` | Both of the above → smoke |
| `smoke-only` | No deploy; only hit live API with `release_smoke_test.py` |

You must type **`deploy-production`** in the `confirm` box or the run aborts.

Safety:

- Never auto-deploys on commit
- Never syncs `backend/.env`, `.compose.env`, or `deploy/certs/`
- Never runs `docker compose down -v` (Postgres volume stays)
- Uses GitHub Environment **`production`** (optional required reviewers)
- One deploy at a time (`concurrency` group)

## One-time GitHub setup

### 1. Create Environment

Repo → **Settings → Environments → New environment** → name: `production`.

Optional but recommended: enable **Required reviewers** (yourself) so the deploy job waits for a click even after `workflow_dispatch`.

### 2. Add repository secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Example / notes |
|--------|-----------------|
| `DEPLOY_SSH_KEY` | Full private key PEM for the VPS (`healthcare_hostinger` contents) |
| `DEPLOY_HOST` | `187.127.170.45` |
| `DEPLOY_USER` | `root` |
| `DEPLOY_PATH` | `/root/Healthcare-Secure` (optional; this is the default) |
| `SMOKE_CLINIC_PASSWORD` | Demo clinic password (recommended over relying on script default) |
| `SMOKE_DOCTOR_PIN` | Doctor PIN for smoke |
| `SMOKE_LAB_PIN` | Lab PIN for smoke |

Optional overrides: `SMOKE_API_BASE`, `SMOKE_CLINIC_NAME`, `SMOKE_DOCTOR_USER`, `SMOKE_LAB_USER`.

### 3. VPS authorized_keys

The public half of `DEPLOY_SSH_KEY` must already be in `/root/.ssh/authorized_keys` on the VPS (same key you use from Windows).

## How to run

1. Merge / push the commit you want on `main` (CI must be green).
2. Actions → **Deploy + smoke (manual)** → **Run workflow**.
3. Branch: `main`.
4. `target`: usually `api`.
5. `confirm`: `deploy-production`.
6. Run → wait for deploy + smoke jobs.

CLI equivalent:

```bash
gh workflow run "Deploy + smoke (manual)" \
  -f target=api \
  -f confirm=deploy-production \
  -f ref_note="release after CI green"
gh run watch
```

Smoke-only (no SSH deploy):

```bash
gh workflow run "Deploy + smoke (manual)" \
  -f target=smoke-only \
  -f confirm=deploy-production
```

## Local scripts used by the workflow

| File | Role |
|------|------|
| `deploy/remote_rebuild_api.sh` | On VPS: `compose up --build --force-recreate api` + nginx restart + health wait |
| `deploy/remote_reload_nginx.sh` | On VPS: nginx reload after static sync |
| `scripts/release_smoke_test.py` | CT against live API (env-overridable credentials) |

## Out of scope (for now)

- Auto-deploy on every `main` push
- Browser desk (`app`) build/publish — still `scripts/deploy_web.cmd`
- APK / Play Store CD
- Nightly scheduled CT (easy follow-up: new workflow `on: schedule` calling smoke-only)

Related: [`CLOUD_DEPLOY.md`](CLOUD_DEPLOY.md) · [`RESTART_PRODUCTION_API.md`](RESTART_PRODUCTION_API.md)
