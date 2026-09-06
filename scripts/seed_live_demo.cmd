@echo off
setlocal
set KEY=%USERPROFILE%\.ssh\healthcare_hostinger
set TARGET=root@187.127.170.45
set REMOTE=/root/Healthcare-Secure

echo === Upload seed scripts to VPS ===
scp -i "%KEY%" -o BatchMode=yes "%~dp0..\backend\scripts\seed_demo.py" %TARGET%:%REMOTE%/backend/scripts/seed_demo.py
if errorlevel 1 exit /b 1
scp -i "%KEY%" -o BatchMode=yes "%~dp0..\backend\scripts\seed_demo_gp.py" %TARGET%:%REMOTE%/backend/scripts/seed_demo_gp.py
if errorlevel 1 exit /b 1

echo === Ensure /app/scripts exists in API container ===
ssh -i "%KEY%" -o BatchMode=yes %TARGET% "cd %REMOTE% && docker compose exec -T api mkdir -p /app/scripts"

echo === Copy seed scripts into API container ===
ssh -i "%KEY%" -o BatchMode=yes %TARGET% "cd %REMOTE% && docker compose cp backend/scripts/seed_demo.py api:/app/scripts/seed_demo.py && docker compose cp backend/scripts/seed_demo_gp.py api:/app/scripts/seed_demo_gp.py"
if errorlevel 1 exit /b 1

echo === Seed Alpha Clinic (gynae) ===
ssh -i "%KEY%" -o BatchMode=yes %TARGET% "cd %REMOTE% && docker compose exec -T -e PYTHONIOENCODING=utf-8 api python scripts/seed_demo.py --wipe"
if errorlevel 1 exit /b 1

echo === Seed City General Clinic (GP) ===
ssh -i "%KEY%" -o BatchMode=yes %TARGET% "cd %REMOTE% && docker compose exec -T -e PYTHONIOENCODING=utf-8 api python scripts/seed_demo_gp.py --wipe"
if errorlevel 1 exit /b 1

echo.
echo Live API demo patients refreshed.
endlocal
