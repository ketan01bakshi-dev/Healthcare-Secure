@echo off
REM Publish public marketing site to https://www.aarogyaoneconnect.in
setlocal
set KEY=%USERPROFILE%\.ssh\healthcare_hostinger
set TARGET=root@187.127.170.45
set REMOTE=/root/Healthcare-Secure

ssh -i "%KEY%" -o BatchMode=yes %TARGET% "mkdir -p %REMOTE%/deploy/www && find %REMOTE%/deploy/www -mindepth 1 -delete"
pushd "%~dp0..\deploy\www"
tar -cf - . | ssh -i "%KEY%" -o BatchMode=yes %TARGET% "cd %REMOTE%/deploy/www && tar -xf -"
if errorlevel 1 (
  popd
  exit /b 1
)
popd

ssh -i "%KEY%" -o BatchMode=yes %TARGET% "cd %REMOTE% && docker compose exec -T nginx nginx -t && docker compose exec -T nginx nginx -s reload"
if errorlevel 1 (
  ssh -i "%KEY%" -o BatchMode=yes %TARGET% "cd %REMOTE% && docker compose up -d nginx && docker compose restart nginx"
)

echo.
echo Marketing: https://www.aarogyaoneconnect.in
endlocal
