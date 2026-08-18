@echo off
REM Send day-before appointment reminder SMS (tomorrow in Asia/Kolkata).
REM Schedule daily with Windows Task Scheduler, e.g. 9:00 AM.
REM
REM Usage (from repo root):
REM   scripts\remind_day_before.cmd
REM   scripts\remind_day_before.cmd http://127.0.0.1:8000
REM
REM Auth: set APPOINTMENT_REMINDER_TOKEN in backend/.env and pass the same
REM value below, OR unlock as doctor and set REMINDER_SESSION to the token.
setlocal EnableExtensions
set "API_BASE=%~1"
if "%API_BASE%"=="" set "API_BASE=http://127.0.0.1:8000"
set "TOKEN=%APPOINTMENT_REMINDER_TOKEN%"
if "%TOKEN%"=="" set "TOKEN=%REMINDER_TOKEN%"

echo Reminding upcoming appointments via %API_BASE%/api/v1/appointments/remind-upcoming

if not "%TOKEN%"=="" (
  powershell -NoProfile -Command ^
    "try { $r = Invoke-RestMethod -Method Post -Uri '%API_BASE%/api/v1/appointments/remind-upcoming' -Headers @{ 'X-Reminder-Token' = '%TOKEN%' }; $r | ConvertTo-Json -Compress; exit 0 } catch { Write-Error $_; exit 1 }"
  goto :eof
)

if not "%REMINDER_SESSION%"=="" (
  powershell -NoProfile -Command ^
    "try { $r = Invoke-RestMethod -Method Post -Uri '%API_BASE%/api/v1/appointments/remind-upcoming' -Headers @{ 'X-Doctor-Session' = '%REMINDER_SESSION%' }; $r | ConvertTo-Json -Compress; exit 0 } catch { Write-Error $_; exit 1 }"
  goto :eof
)

echo ERROR: Set APPOINTMENT_REMINDER_TOKEN in backend/.env ^(and this env^)
echo        or set REMINDER_SESSION to a doctor session token.
exit /b 1
