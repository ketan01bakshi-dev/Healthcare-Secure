@echo off
REM Dump Postgres from Docker Compose (or local DATABASE_URL postgres).
REM Usage:
REM   scripts\backup_pg.cmd
REM   scripts\backup_pg.cmd healthcare_backup
setlocal
set "ROOT=%~dp0.."
set "OUTDIR=%ROOT%\backend\backups"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%i"
set "OUTFILE=%OUTDIR%\pg_%STAMP%.sql"

echo Writing %OUTFILE%
docker compose -f "%ROOT%\docker-compose.yml" exec -T db pg_dump -U healthcare healthcare > "%OUTFILE%"
if errorlevel 1 (
  echo FAILED: is Compose up? Or use: docker compose exec db pg_dump ...
  exit /b 1
)
echo Done.
endlocal
