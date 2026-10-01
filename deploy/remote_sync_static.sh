#!/usr/bin/env bash
# Sync a static directory on the VPS with one-step rollback tarball.
# Usage: bash deploy/remote_sync_static.sh <remote-root> <subdir> <local-tar-stream-already-extracted>
# Typically called after rsync; this only manages .prev snapshots + nginx reload.
set -euo pipefail

ROOT="${1:-/root/Healthcare-Secure}"
SUBDIR="${2:?subdir required e.g. deploy/www or deploy/web}"
cd "$ROOT"

TARGET="$ROOT/$SUBDIR"
mkdir -p "$TARGET"
mkdir -p "$ROOT/deploy/.static-prev"

SAFE_NAME="${SUBDIR//\//_}"
PREV_TAR="$ROOT/deploy/.static-prev/${SAFE_NAME}.tar.gz"

if [[ -d "$TARGET" ]] && [[ -n "$(ls -A "$TARGET" 2>/dev/null || true)" ]]; then
  tar -czf "$PREV_TAR" -C "$TARGET" .
  echo "==> Saved previous static snapshot: $PREV_TAR"
fi

bash "$ROOT/deploy/remote_reload_nginx.sh" "$ROOT"
