#!/usr/bin/env bash
# Reload nginx after static site sync (www / web). Safe: no DB touch.
set -euo pipefail

ROOT="${1:-/root/Healthcare-Secure}"
cd "$ROOT"

set -a
# shellcheck disable=SC1091
[[ -f .compose.env ]] && . ./.compose.env
set +a

if docker compose exec -T nginx nginx -t; then
  docker compose exec -T nginx nginx -s reload
else
  echo "nginx -t failed — recreating nginx container..."
  docker compose up -d nginx
  docker compose restart nginx
fi

echo "==> nginx reload complete."
