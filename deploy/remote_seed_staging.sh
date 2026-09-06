#!/usr/bin/env bash
# First-boot / refresh demo seed inside the staging API container.
# Safe: staging volume only. Never point this at production.
set -euo pipefail

ROOT="${1:-/root/Healthcare-Secure-Staging}"
cd "$ROOT"

COMPOSE=( docker compose -p healthcare-secure-staging -f docker-compose.staging.yml )

echo "==> Ensuring staging stack is up..."
"${COMPOSE[@]}" up -d db api

echo "==> Waiting for staging API on 127.0.0.1:8001..."
ok=0
for _ in $(seq 1 45); do
  if curl -fsS "http://127.0.0.1:8001/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done
if [[ "$ok" -ne 1 ]]; then
  echo "ERROR: staging API not healthy" >&2
  "${COMPOSE[@]}" logs --tail=80 api || true
  exit 1
fi

echo "==> Copying seed scripts into api container..."
"${COMPOSE[@]}" exec -T api mkdir -p /app/scripts
"${COMPOSE[@]}" cp backend/scripts/seed_demo.py api:/app/scripts/seed_demo.py
"${COMPOSE[@]}" cp backend/scripts/seed_demo_gp.py api:/app/scripts/seed_demo_gp.py

echo "==> Seeding Alpha + GP demo data (wipe tagged demo rows only)..."
"${COMPOSE[@]}" exec -T -e PYTHONIOENCODING=utf-8 api python scripts/seed_demo.py --wipe
"${COMPOSE[@]}" exec -T -e PYTHONIOENCODING=utf-8 api python scripts/seed_demo_gp.py --wipe

echo "==> Staging seed complete."
