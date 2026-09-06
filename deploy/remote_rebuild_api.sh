#!/usr/bin/env bash
# Run on the VPS after code has been synced. Rebuilds/recreates API only.
# Never touches the Postgres volume. Never deletes .env or certs.
set -euo pipefail

ROOT="${1:-/root/Healthcare-Secure}"
cd "$ROOT"

if [[ ! -f docker-compose.yml ]]; then
  echo "ERROR: docker-compose.yml missing in $ROOT" >&2
  exit 1
fi

if [[ ! -f backend/.env ]]; then
  echo "ERROR: backend/.env missing — refuse to deploy without runtime secrets." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
[[ -f .compose.env ]] && . ./.compose.env
set +a

echo "==> Building and recreating api (db volume untouched)..."
docker compose up -d --build --force-recreate api

echo "==> Restarting nginx so upstream IP refresh does not 502..."
docker compose restart nginx

echo "==> Waiting for local health..."
ok=0
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done

if [[ "$ok" -ne 1 ]]; then
  echo "ERROR: API health did not become ready in time." >&2
  docker compose ps
  docker compose logs --tail=80 api || true
  exit 1
fi

docker compose ps
echo "==> API rebuild complete."
