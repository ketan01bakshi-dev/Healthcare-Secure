# Production-grade CI / CD / CT — Aarogya One Connect

This document is the operator runbook for the autonomous pipeline.

## Autonomy model

| Stage | Behavior |
|-------|----------|
| **CI** | Every PR: backend pytest + frontend lint/tsc/build + compose config |
| **CD staging** | Every `main` push that touches API: build GHCR image → auto-deploy staging → smoke |
| **CD production** | After staging smoke: waits for GitHub Environment **`production`** approval → backup → deploy same image → smoke |
| **CT rollback** | If prod smoke fails: auto-rollback to `.release-tag.prev` → re-smoke |
| **Nightly CT** | Schedule (~06:00 IST): live health + smoke (no deploy) |
| **Manual** | `Deploy + smoke (manual)` and Pipeline `workflow_dispatch` for hotfix/rollback |

Production is **never** auto-deployed without the Environment approval click.

```text
PR ──► CI (gating)
main push (API) ──► CI ──► GHCR image ──► staging deploy+smoke
                                      └──► [approve production] ──► backup ──► prod deploy+smoke
                                                                              └── fail ──► rollback
```

## Workflows

| File | Trigger | Purpose |
|------|---------|---------|
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | PR (+ reusable) | Classroom CI |
| [`.github/workflows/pipeline.yml`](../.github/workflows/pipeline.yml) | `main` push + dispatch | Full CD/CT |
| [`.github/workflows/nightly-ct.yml`](../.github/workflows/nightly-ct.yml) | Cron + dispatch | Live CT |
| [`.github/workflows/deploy-production.yml`](../.github/workflows/deploy-production.yml) | Dispatch only | Emergency lever |

## One-time GitHub setup

### 1. Environments

**Settings → Environments**

1. **`staging`** — no required reviewers (auto).
2. **`production`** — enable **Required reviewers** (add yourself). Optional wait timer 5 minutes.

### 2. Branch protection (`main`)

**Settings → Branches → Add rule** for `main`:

- Require a pull request before merging
- Require status checks: **`CI / gating`** (from the CI workflow on PRs)
- Require linear history (optional)
- Do not allow force pushes

### 3. Repository / environment secrets

Add under **Settings → Secrets and variables → Actions** (prefer Environment secrets for prod/staging where possible):

| Secret | Where | Notes |
|--------|-------|-------|
| `DEPLOY_SSH_KEY` | repo or both envs | PEM private key (`healthcare_hostinger`) |
| `DEPLOY_HOST` | repo | e.g. `187.127.170.45` |
| `DEPLOY_USER` | repo | `root` |
| `DEPLOY_PATH` | production | `/root/Healthcare-Secure` |
| `STAGING_DEPLOY_PATH` | staging | `/root/Healthcare-Secure-Staging` |
| `GHCR_READ_TOKEN` | both | PAT with `read:packages` for VPS `docker login` (or rely on `GITHUB_TOKEN` if package is visible to the deploy identity) |
| `SMOKE_CLINIC_PASSWORD` | production | **Required** — no fallback in Actions |
| `SMOKE_DOCTOR_PIN` | production | **Required** |
| `SMOKE_LAB_PIN` | production | **Required** |
| `SMOKE_API_BASE` | production | optional, default live API URL |
| `SMOKE_CLINIC_NAME` / `SMOKE_DOCTOR_USER` / `SMOKE_LAB_USER` | production | optional |
| `STAGING_SMOKE_*` | staging | same shape as SMOKE_* for staging-api |
| `NOTIFY_WEBHOOK_URL` | production | optional Slack/Discord/Telegram webhook |

### 4. GHCR package

After the first image push, open the `healthcare-api` package → Package settings → ensure the Actions identity / deploy token can pull. Prefer **private**.

## One-time VPS setup

```bash
# Staging directory (separate Compose project; wipeable DB)
mkdir -p /root/Healthcare-Secure-Staging/backend /root/Healthcare-Secure-Staging/deploy
# Copy backend/.env.staging.example → backend/.env.staging and edit secrets
# Ensure POSTGRES password matches staging compose / DATABASE_URL

mkdir -p /root/Healthcare-Secure/deploy/web-staging
# First pipeline deploy syncs compose files; or scp them once.

# Docker login for pulls (use GHCR_READ_TOKEN)
echo "$GHCR_READ_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
```

### DNS + TLS (Hostinger)

| Type | Name | Points to |
|------|------|-----------|
| A | `staging-api` | VPS IP |
| A | `staging-app` | VPS IP |

Re-issue Let’s Encrypt with SANs including:

`api`, `app`, `www`, `staging-api`, `staging-app`

Then reload production nginx (config already has staging server blocks proxying to `host.docker.internal:8001`).

### Seed staging demos

Actions → **Pipeline** → Run workflow → `action=seed-staging`  
or on VPS: `bash deploy/remote_seed_staging.sh /root/Healthcare-Secure-Staging`

## Day-to-day usage

### Normal release (API)

1. Open PR → wait for **CI / gating** green → merge to `main`.
2. Pipeline builds image, deploys staging, runs staging smoke.
3. Open the Actions run → **Review deployments** → Approve **production**.
4. Watch prod deploy + smoke. On failure, rollback runs automatically.

### Website-only / app-only

Path filters deploy `www` or `app` after CI + production approval (same Environment). API image is skipped when those paths change without backend.

### Emergency

- **Deploy + smoke (manual)** with `confirm=deploy-production`
- Pipeline dispatch: `rollback-api`, optional `image_tag`
- Never run `docker compose down -v` on production

### Nightly / deep verify

- Automatic: Nightly CT workflow
- Manual deep: Nightly CT → `deep_verify=true` (demo clinics only)

## Scripts reference

| Script | Role |
|--------|------|
| `deploy/remote_rebuild_api.sh` | Pull/recreate API; records `.release-tag` |
| `deploy/remote_rollback_api.sh` | Recreate from `.release-tag.prev` |
| `deploy/remote_backup_before_deploy.sh` | Calls `backup_pg.sh` |
| `deploy/remote_reload_nginx.sh` | nginx -t + reload |
| `deploy/remote_sync_static.sh` | Snapshot static dir before replace |
| `deploy/remote_rollback_static.sh` | Restore static snapshot |
| `deploy/remote_seed_staging.sh` | Wipe+seed staging demos |
| `scripts/release_smoke_test.py` | CT smoke (`SMOKE_REQUIRE_SECRETS=1` in Actions) |
| `scripts/verify_live_demo.py` | Deep demo verify |

## Compose overlays

- [`docker-compose.yml`](../docker-compose.yml) — production `db`+`api`+`nginx`
- [`docker-compose.image.yml`](../docker-compose.image.yml) — sets `api.image` from `API_IMAGE`
- [`docker-compose.staging.yml`](../docker-compose.staging.yml) — staging project on `:8001`

## Safety rules

- Never sync `backend/.env`, `.compose.env`, or `deploy/certs/` from CI
- Never wipe production `pgdata`
- Prod smoke **fail-closed** without secrets
- Staging DB is disposable; production is not
- Keep `Deploy + smoke (manual)` until Pipeline is proven on a few releases

## Merge note

PR #4 (manual deploy+smoke) is included in this branch. Merge this feature branch to `main` after secrets/environments exist, then run **Pipeline → smoke-only** once before the first real API deploy.
