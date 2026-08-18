@echo off
REM Build a release Android App Bundle for Play Console / sideload tooling.
REM Prerequisites: Android Studio, JDK 17, keystore configured.
REM Android versionCode/versionName auto-bump on bundle (see android/app/build.gradle).
setlocal
cd /d "%~dp0..\frontend"
call npm run mobile:build
if errorlevel 1 exit /b 1
cd android
if not defined JAVA_HOME set JAVA_HOME=C:\Program Files\Android\Android Studio\jbr
call gradlew.bat bundleRelease --no-daemon
if errorlevel 1 (
  echo If gradlew is missing, open the project in Android Studio once, then re-run.
  exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%A in (`node ..\scripts\read-android-version.mjs`) do (
  if /I "%%A"=="VERSION_NAME" echo Bumped versionName=%%B
  if /I "%%A"=="VERSION_CODE" echo Bumped versionCode=%%B
)
echo.
echo AAB output:
echo   frontend\android\app\build\outputs\bundle\release\app-release.aab
echo Upload that file in Google Play Console, or use bundletool for APKs.
endlocal
