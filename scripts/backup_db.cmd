@echo off
REM Backup SQLite clinic DB (run from backend\ or repo root).
setlocal
cd /d "%~dp0.."
if not exist "backend\backups" mkdir "backend\backups"
set STAMP=%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
set STAMP=%STAMP: =0%
set SRC=backend\healthcare.db
if not exist "%SRC%" set SRC=backend\app\healthcare.db
if not exist "%SRC%" (
  echo No healthcare.db found under backend\.
  exit /b 1
)
copy /Y "%SRC%" "backend\backups\healthcare_%STAMP%.db" >nul
echo Backed up to backend\backups\healthcare_%STAMP%.db
endlocal
