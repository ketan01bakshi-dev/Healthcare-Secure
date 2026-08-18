#!/usr/bin/env bash
# Update Groq STT/LLM keys on the VPS after rotating in console.groq.com.
# Usage (on VPS, from /root/Healthcare-Secure):
#   bash deploy/set_groq_key.sh gsk_YOUR_NEW_KEY
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY="${1:-}"
if [[ -z "$KEY" || "$KEY" == CHANGE* ]]; then
  echo "Usage: bash deploy/set_groq_key.sh <new_groq_api_key>"
  exit 1
fi

ENV_FILE="$ROOT/backend/.env"
python3 - <<PY
from pathlib import Path
path = Path("$ENV_FILE")
key = """$KEY"""
lines = []
seen_w = seen_l = False
for line in path.read_text(encoding="utf-8").splitlines():
    if line.startswith("WHISPER_API_KEY="):
        lines.append("WHISPER_API_KEY=" + key)
        seen_w = True
    elif line.startswith("LLM_API_KEY="):
        lines.append("LLM_API_KEY=" + key)
        seen_l = True
    else:
        lines.append(line)
if not seen_w:
    lines.append("WHISPER_API_KEY=" + key)
if not seen_l:
    lines.append("LLM_API_KEY=" + key)
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Updated WHISPER_API_KEY and LLM_API_KEY in backend/.env")
PY

cd "$ROOT"
set -a
# shellcheck disable=SC1091
. ./.compose.env
set +a
docker compose up -d --force-recreate api
docker compose up -d nginx
curl -fsS https://api.aarogyaoneconnect.in/health
echo
echo "Done. Revoke the old key in the Groq console if you have not already."
