@echo off
REM Seed gynecology clinic demo data for showcasing the app.
REM Usage (from repo root):
REM   scripts\seed_demo.cmd
REM   scripts\seed_demo.cmd --wipe
REM   scripts\seed_demo.cmd --clinic east
REM   scripts\seed_demo.cmd --clinic east --wipe
setlocal EnableExtensions
set "BACKEND=%~dp0..\backend"
cd /d "%BACKEND%"
if not exist ".venv\Scripts\python.exe" (
  echo Create the backend venv first: python -m venv .venv ^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
".venv\Scripts\python.exe" scripts\seed_demo.py %*
exit /b %ERRORLEVEL%
