#!/usr/bin/env bash
# Obtain Let's Encrypt certs and write deploy/certs/clinic.crt + clinic.key
# (names expected by deploy/nginx/nginx.conf).
#
# Usage (as root, from repo root, DNS A record already pointing here):
#   bash deploy/init_letsencrypt.sh api.yourproduct.in
#   bash deploy/init_letsencrypt.sh api.yourproduct.in app.yourproduct.in
#   bash deploy/init_letsencrypt.sh api.yourproduct.in app.yourproduct.in you@example.com
set -euo pipefail

# First arg is primary domain (cert folder name). Extra args are more -d names.
PRIMARY="${1:-}"
shift || true

if [[ -z "${PRIMARY}" ]]; then
  echo "Usage: bash deploy/init_letsencrypt.sh <primary-domain> [extra-domain ...] [email]"
  exit 1
fi

EMAIL=""
DOMAINS=("-d" "${PRIMARY}")
for arg in "$@"; do
  if [[ "${arg}" == *@* ]]; then
    EMAIL="${arg}"
  else
    DOMAINS+=("-d" "${arg}")
  fi
done
EMAIL="${EMAIL:-admin@${PRIMARY}}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (certbot + binding :80)."
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="${ROOT}/deploy/certs"
mkdir -p "${CERT_DIR}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y certbot

# Stop anything on 80/443 so standalone can bind (safe if compose not up yet).
if command -v docker >/dev/null 2>&1; then
  (cd "${ROOT}" && docker compose stop nginx 2>/dev/null) || true
fi
fuser -k 80/tcp 2>/dev/null || true

certbot certonly --standalone \
  --non-interactive --agree-tos --expand \
  -m "${EMAIL}" \
  --cert-name "${PRIMARY}" \
  "${DOMAINS[@]}"

LIVE="/etc/letsencrypt/live/${PRIMARY}"
cp -f "${LIVE}/fullchain.pem" "${CERT_DIR}/clinic.crt"
cp -f "${LIVE}/privkey.pem" "${CERT_DIR}/clinic.key"
chmod 644 "${CERT_DIR}/clinic.crt"
chmod 600 "${CERT_DIR}/clinic.key"

# Renew hook: recopy + reload nginx container
HOOK="/etc/letsencrypt/renewal-hooks/deploy/healthcare-secure-certs.sh"
mkdir -p "$(dirname "${HOOK}")"
cat > "${HOOK}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cp -f "${LIVE}/fullchain.pem" "${CERT_DIR}/clinic.crt"
cp -f "${LIVE}/privkey.pem" "${CERT_DIR}/clinic.key"
cd "${ROOT}" && docker compose exec -T nginx nginx -s reload || docker compose restart nginx
EOF
chmod +x "${HOOK}"

echo "Wrote ${CERT_DIR}/clinic.crt and clinic.key for ${PRIMARY} (+ extras)"
echo "Start stack: cd ${ROOT} && docker compose up -d --build"
echo "Renewal: certbot renew (hook recopies certs and reloads nginx)"
