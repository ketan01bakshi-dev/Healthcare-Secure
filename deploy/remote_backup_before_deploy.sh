#!/usr/bin/env bash
# Optional pre-deploy Postgres snapshot. Never blocks www-only deploys (caller decides).
set -euo pipefail

ROOT="${1:-/root/Healthcare-Secure}"
cd "$ROOT"

if [[ -x deploy/backup_pg.sh ]]; then
  bash deploy/backup_pg.sh
elif [[ -f deploy/backup_pg.sh ]]; then
  bash deploy/backup_pg.sh
else
  echo "WARN: deploy/backup_pg.sh missing — skipping backup."
fi
