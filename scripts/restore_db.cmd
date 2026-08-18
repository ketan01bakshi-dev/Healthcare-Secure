@echo off
REM Restore a backup: scripts\restore_db.cmd backend\backups\healthcare_YYYYMMDD_HHMMSS.db
setlocal
cd /d "%~dp0.."
if "%~1"=="" (
  echo Usage: scripts\restore_db.cmd path\to\backup.db
  exit /b 1
)
if not exist "%~1" (
  echo File not found: %~1
  exit /b 1
)
echo Stop the API before restoring.
copy /Y "%~1" "backend\healthcare.db"
echo Restored to backend\healthcare.db
endlocal
