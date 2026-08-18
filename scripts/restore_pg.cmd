@echo off
REM Restore a pg_dump .sql into Compose Postgres. Stop API first if needed.
REM Usage:
REM   scripts\restore_pg.cmd backend\backups\pg_YYYYMMDD_HHMMSS.sql
setlocal
if "%~1"=="" (
  echo Usage: scripts\restore_pg.cmd path\to\backup.sql
  exit /b 1
)
set "ROOT=%~dp0.."
set "FILE=%~1"
if not exist "%FILE%" (
  echo File not found: %FILE%
  exit /b 1
)
echo WARNING: This replaces data in Compose DB "healthcare".
echo Restoring %FILE% ...
type "%FILE%" | docker compose -f "%ROOT%\docker-compose.yml" exec -T db psql -U healthcare -d healthcare
if errorlevel 1 (
  echo FAILED
  exit /b 1
)
echo Done.
endlocal
