#!/usr/bin/env bash
set -euo pipefail
cd /root/Healthcare-Secure
rm -f /etc/apt/sources.list.d/docker.list || true

SK="$(openssl rand -hex 32)"
SS="$(openssl rand -hex 32)"
PG="$(openssl rand -hex 16)"

cat > backend/.env <<EOF
APP_ENV=production
DEBUG=false
SECRET_KEY=${SK}
SECRET_SALT=${SS}
DATABASE_URL=postgresql+psycopg2://healthcare:${PG}@db:5432/healthcare
POSTGRES_PASSWORD=${PG}
PUBLIC_API_BASE_URL=https://api.aarogyaoneconnect.in
ALLOWED_HOSTS=api.aarogyaoneconnect.in
CORS_ORIGINS=capacitor://localhost,https://localhost,https://api.aarogyaoneconnect.in
REQUIRE_CLINIC_USERS=true
WHISPER_PRELOAD=false
WHISPER_PROVIDER=groq
WHISPER_API_KEY=CHANGE_ME_GROQ_KEY
WHISPER_MODEL=whisper-large-v3-turbo
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
LLM_API_KEY=CHANGE_ME_GROQ_KEY
CLINIC_NAME=Aarogya One Connect
CLINIC_SUBTITLE=Secure Clinical Prescription - De-identified Patient Record
CLINIC_ADDRESS=
DOCTOR_NAME=Dr. Nirmala Tiwari
DOCTOR_CREDENTIALS=MBBS
PRESCRIPTION_TIMEZONE=Asia/Kolkata
CLINICS=default|Alpha Clinic|Shastri Nagar, Vidisha, Madhya Pradesh 464001|;east|East Branch|Branch|
CLINIC_USERS=default|dr_nirmala|Dr. Nirmala Tiwari|doctor|1234;default|staff_dhanaraj|Staff|staff|5678;default|staff_priyanka|Priyanka|staff|5678;default|lab1|Lab Desk|lab|9999;east|dr_east|Dr East|doctor|1234;east|staff_east|Staff East|staff|5678
ABDM_MOCK=false
ABDM_CALLBACK_BASE_URL=https://api.aarogyaoneconnect.in
SMS_PROVIDER=console
SMS_SENDER_ID=CLINIC
EOF
chmod 600 backend/.env
echo "POSTGRES_PASSWORD=${PG}" > /root/Healthcare-Secure/.compose.env
chmod 600 /root/Healthcare-Secure/.compose.env

if command -v ufw >/dev/null; then
  ufw allow 22/tcp || true
  ufw allow 80/tcp || true
  ufw allow 443/tcp || true
fi

echo ENV_READY
