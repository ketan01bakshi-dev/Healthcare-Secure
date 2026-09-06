#!/usr/bin/env bash
# Restore previous static snapshot for www or web.
# Usage: bash deploy/remote_rollback_static.sh /root/Healthcare-Secure deploy/www
set -euo pipefail

ROOT="${1:-/root/Healthcare-Secure}"
SUBDIR="${2:?subdir required}"
cd "$ROOT"

SAFE_NAME="${SUBDIR//\//_}"
PREV_TAR="$ROOT/deploy/.static-prev/${SAFE_NAME}.tar.gz"
TARGET="$ROOT/$SUBDIR"

if [[ ! -f "$PREV_TAR" ]]; then
  echo "ERROR: no previous snapshot at $PREV_TAR" >&2
  exit 1
fi

mkdir -p "$TARGET"
find "$TARGET" -mindepth 1 -delete
tar -xzf "$PREV_TAR" -C "$TARGET"
bash "$ROOT/deploy/remote_reload_nginx.sh" "$ROOT"
echo "==> Restored $SUBDIR from $PREV_TAR"
