@echo off
REM Build static clinic UI and publish to VPS at https://app.aarogyaoneconnect.in
REM Requires: SSH key %USERPROFILE%\.ssh\healthcare_hostinger
setlocal
cd /d "%~dp0..\frontend"
if not defined NEXT_PUBLIC_API_BASE_URL set NEXT_PUBLIC_API_BASE_URL=https://api.aarogyaoneconnect.in
call npm run build
if errorlevel 1 exit /b 1

set HOST=root@187.127.170.45
set KEY=%USERPROFILE%\.ssh\healthcare_hostinger
set REMOTE=/root/Healthcare-Secure

echo.
echo Syncing frontend\out → VPS deploy\web ...
ssh -i "%KEY%" -o BatchMode=yes %HOST% "mkdir -p %REMOTE%/deploy/web && find %REMOTE%/deploy/web -mindepth 1 -delete"
pushd out
tar -cf - . | ssh -i "%KEY%" -o BatchMode=yes %HOST% "cd %REMOTE%/deploy/web && tar -xf -"
if errorlevel 1 (
  popd
  exit /b 1
)
popd

echo Reloading nginx...
ssh -i "%KEY%" -o BatchMode=yes %HOST% "cd %REMOTE% && docker compose exec -T nginx nginx -t && docker compose exec -T nginx nginx -s reload"
if errorlevel 1 (
  echo nginx reload failed — recreating nginx...
  ssh -i "%KEY%" -o BatchMode=yes %HOST% "cd %REMOTE% && docker compose up -d nginx && docker compose restart nginx"
)

echo.
echo Web desk: https://app.aarogyaoneconnect.in
echo API:      https://api.aarogyaoneconnect.in
endlocal
