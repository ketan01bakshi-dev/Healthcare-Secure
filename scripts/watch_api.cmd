@echo off
REM Watch /health and restart uvicorn if the API stops answering.
REM Usage (from repo root):
REM   scripts\watch_api.cmd
REM   scripts\watch_api.cmd http://127.0.0.1:8000 15
REM Leave this window open while the clinic is open.
setlocal EnableExtensions
set "API_BASE=%~1"
if "%API_BASE%"=="" set "API_BASE=http://127.0.0.1:8000"
set "INTERVAL=%~2"
if "%INTERVAL%"=="" set "INTERVAL=15"
set "FAILS=0"
set "MAX_FAILS=3"
set "BACKEND=%~dp0..\backend"

echo Watching %API_BASE%/health every %INTERVAL%s (restart after %MAX_FAILS% failures)
echo Press Ctrl+C to stop.
echo.

:loop
powershell -NoProfile -Command ^
  "try { $r = Invoke-WebRequest -Uri '%API_BASE%/health' -TimeoutSec 5 -UseBasicParsing; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { exit 0 } else { exit 1 } } catch { exit 1 }"
if errorlevel 1 (
  set /a FAILS+=1
  echo [%DATE% %TIME%] health FAIL ^(%FAILS%/%MAX_FAILS%^)
  if %FAILS% GEQ %MAX_FAILS% (
    echo Restarting API...
    call :restart_api
    set "FAILS=0"
  )
) else (
  if not "%FAILS%"=="0" echo [%DATE% %TIME%] health OK again
  set "FAILS=0"
)
timeout /t %INTERVAL% /nobreak >nul
goto loop

:restart_api
REM Kill listeners on port 8000, then start uvicorn with Whisper preload off.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  taskkill /F /PID %%p >nul 2>&1
)
timeout /t 2 /nobreak >nul
cd /d "%BACKEND%"
set WHISPER_PRELOAD=false
start "Healthcare-API" /MIN cmd /c ".\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000"
timeout /t 5 /nobreak >nul
exit /b 0
