#!/usr/bin/env bash
set -euo pipefail
cd /root/Healthcare-Secure
python3 <<'PY'
from pathlib import Path
path = Path("backend/.env")
lines = []
seen = False
for line in path.read_text(encoding="utf-8").splitlines():
    if line.startswith("CLINIC_NAME="):
        lines.append("CLINIC_NAME=Aarogya One Connect")
        seen = True
    else:
        lines.append(line)
if not seen:
    lines.append("CLINIC_NAME=Aarogya One Connect")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print([line for line in lines if line.startswith("CLINIC_NAME=")])
PY
set -a
. ./.compose.env
set +a
docker compose up -d --build api
docker compose up -d nginx
curl -fsS https://api.aarogyaoneconnect.in/health
echo
