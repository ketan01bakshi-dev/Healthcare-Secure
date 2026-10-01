#!/usr/bin/env bash
# Roll API back to the previous GHCR image recorded in .release-tag.prev.
# Never touches the Postgres volume.
set -euo pipefail

ROOT="${1:-/root/Healthcare-Secure}"
cd "$ROOT"

if [[ ! -f .release-tag.prev ]]; then
  echo "ERROR: .release-tag.prev missing — nothing to roll back to." >&2
  exit 1
fi

PREV="$(tr -d '[:space:]' < .release-tag.prev)"
if [[ -z "$PREV" ]]; then
  echo "ERROR: .release-tag.prev is empty." >&2
  exit 1
fi

echo "==> Rolling back api to ${PREV}"
bash "$(dirname "$0")/remote_rebuild_api.sh" "$ROOT" "$PREV"

# After a successful rollback, swap tags so a second rollback can return forward if needed.
if [[ -f .release-tag ]]; then
  # remote_rebuild_api already rotated .release-tag → .release-tag.prev to PREV's predecessor.
  # Force current to PREV and keep the failed tag as .release-tag.failed for forensics.
  if [[ -f .release-tag.prev ]]; then
    cp .release-tag .release-tag.failed 2>/dev/null || true
  fi
  printf '%s\n' "$PREV" > .release-tag
fi

echo "==> Rollback complete."
