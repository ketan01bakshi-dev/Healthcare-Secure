@echo off
REM Create a self-signed TLS cert for clinic LAN HTTPS (nginx).
setlocal
cd /d "%~dp0"
if not exist "certs" mkdir certs
where openssl >nul 2>&1
if errorlevel 1 (
  echo OpenSSL not found. Install OpenSSL or use Git Bash openssl.
  exit /b 1
)
openssl req -x509 -nodes -newkey rsa:2048 -days 825 ^
  -keyout certs\clinic.key -out certs\clinic.crt ^
  -subj "/CN=Aarogya One Connect/O=Clinic/C=IN"
echo Wrote deploy\certs\clinic.crt and clinic.key
echo Point phones at https://YOUR_LAN_IP (trust the cert on the device for lab use).
endlocal
