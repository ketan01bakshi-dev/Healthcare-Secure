#!/usr/bin/env bash
# Dump Postgres from Docker Compose into backend/backups/ (whole platform / all clinics).
#
# Usage (from repo root on the VPS):
#   bash deploy/backup_pg.sh
#   bash deploy/backup_pg.sh /var/backups/healthcare
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTDIR="${1:-${ROOT}/backend/backups}"
mkdir -p "${OUTDIR}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUTFILE="${OUTDIR}/pg_${STAMP}.sql"

cd "${ROOT}"
echo "Writing ${OUTFILE}"
docker compose exec -T db pg_dump -U healthcare healthcare > "${OUTFILE}"
gzip -f "${OUTFILE}"
echo "Done: ${OUTFILE}.gz"
# Keep last 14 dumps in OUTDIR
ls -1t "${OUTDIR}"/pg_*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
