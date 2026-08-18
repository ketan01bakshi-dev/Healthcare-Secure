@echo off
REM Build HTTPS debug APK for sharing (points at cloud API).
REM Android versionCode/versionName auto-bump on assemble (see android/app/build.gradle).
setlocal EnableDelayedExpansion
cd /d "%~dp0..\frontend"
set CAPACITOR_HTTPS=true
if not defined NEXT_PUBLIC_API_BASE_URL set NEXT_PUBLIC_API_BASE_URL=https://api.aarogyaoneconnect.in
call npm run mobile:build
if errorlevel 1 exit /b 1
cd android
if not defined JAVA_HOME set JAVA_HOME=C:\Program Files\Android\Android Studio\jbr
call gradlew.bat assembleDebug --no-daemon
if errorlevel 1 exit /b 1
set VERSION_NAME=0.0
for /f "usebackq tokens=1,* delims==" %%A in (`node ..\scripts\read-android-version.mjs`) do (
  if /I "%%A"=="VERSION_NAME" set VERSION_NAME=%%B
)
mkdir "%~dp0..\share" 2>nul
copy /Y app\build\outputs\apk\debug\app-debug.apk "%~dp0..\share\AarogyaOneConnect-v!VERSION_NAME!.apk"
echo.
echo Share pack APK:
echo   share\AarogyaOneConnect-v!VERSION_NAME!.apk
echo Also send share\SHARE_PACK.md credentials privately.
endlocal
