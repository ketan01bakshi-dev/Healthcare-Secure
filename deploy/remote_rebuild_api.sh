#!/usr/bin/env bash
# Deploy API on VPS from a GHCR image tag (preferred) or local build (emergency).
# Usage:
#   bash deploy/remote_rebuild_api.sh /root/Healthcare-Secure
#   bash deploy/remote_rebuild_api.sh /root/Healthcare-Secure <image-tag-or-ref>
# Never touches the Postgres volume. Never deletes .env or certs.
set -euo pipefail

ROOT="${1:-/root/Healthcare-Secure}"
TAG_OR_IMAGE="${2:-${API_IMAGE_TAG:-}}"
cd "$ROOT"

if [[ ! -f docker-compose.yml ]]; then
  echo "ERROR: docker-compose.yml missing in $ROOT" >&2
  exit 1
fi

ENV_FILE="${ENV_FILE:-backend/.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE missing — refuse to deploy without runtime secrets." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
[[ -f .compose.env ]] && . ./.compose.env
set +a

HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
COMPOSE=( docker compose -f docker-compose.yml )
if [[ -n "$TAG_OR_IMAGE" && -f docker-compose.image.yml ]]; then
  COMPOSE+=( -f docker-compose.image.yml )
fi
if [[ -n "${COMPOSE_PROJECT_NAME:-}" ]]; then
  COMPOSE=( env COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" "${COMPOSE[@]}" )
fi

if [[ -n "$TAG_OR_IMAGE" ]]; then
  if [[ "$TAG_OR_IMAGE" == *\/* ]]; then
    export API_IMAGE="$TAG_OR_IMAGE"
  else
    OWNER="${GHCR_OWNER:-ketan01bakshi-dev}"
    export API_IMAGE="ghcr.io/${OWNER}/healthcare-api:${TAG_OR_IMAGE}"
  fi
  echo "==> Pulling and recreating api from ${API_IMAGE} (db volume untouched)..."
  "${COMPOSE[@]}" pull api
  "${COMPOSE[@]}" up -d --no-build --force-recreate api
else
  echo "==> Building and recreating api from local Dockerfile (db volume untouched)..."
  unset API_IMAGE || true
  docker compose -f docker-compose.yml up -d --build --force-recreate api
fi

echo "==> Restarting nginx so upstream IP refresh does not 502..."
docker compose -f docker-compose.yml restart nginx 2>/dev/null || true

echo "==> Waiting for local health at ${HEALTH_URL}..."
ok=0
for _ in $(seq 1 45); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done

if [[ "$ok" -ne 1 ]]; then
  echo "ERROR: API health did not become ready in time." >&2
  "${COMPOSE[@]}" ps || docker compose ps
  "${COMPOSE[@]}" logs --tail=80 api || true
  exit 1
fi

if [[ -n "${API_IMAGE:-}" ]]; then
  if [[ -f .release-tag ]]; then
    cp .release-tag .release-tag.prev
  fi
  printf '%s\n' "$API_IMAGE" > .release-tag
  echo "==> Recorded release tag: $API_IMAGE"
fi

"${COMPOSE[@]}" ps || docker compose ps
echo "==> API deploy complete."
