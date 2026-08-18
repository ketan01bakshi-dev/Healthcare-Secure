@echo off
REM Seed general physician clinic demo data (clinic_id=gp).
REM Usage (from repo root):
REM   scripts\seed_demo_gp.cmd
REM   scripts\seed_demo_gp.cmd --wipe
setlocal EnableExtensions
set "BACKEND=%~dp0..\backend"
cd /d "%BACKEND%"
if not exist ".venv\Scripts\python.exe" (
  echo Create the backend venv first: python -m venv .venv ^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
".venv\Scripts\python.exe" scripts\seed_demo_gp.py %*
exit /b %ERRORLEVEL%
