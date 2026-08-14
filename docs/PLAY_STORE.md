# Play Store / signed AAB + Internal testing

Use **Play Internal testing** when you want more than a handful of doctors: only invited Google accounts can install. This does **not** replace clinic password + PIN — it only stops random people from installing a forwarded APK.

## A. One-time upload keystore

```cmd
keytool -genkey -v -keystore healthcare-upload.jks -keyalg RSA -keysize 2048 -validity 10000 -alias healthcare
```

Add `frontend/android/key.properties` (gitignored):

```
storePassword=...
keyPassword=...
keyAlias=healthcare
storeFile=C:/path/to/healthcare-upload.jks
```

Ensure `frontend/android/app/build.gradle` has `signingConfigs.release` reading `key.properties` (Capacitor Android Studio wizard can add this).

## B. Build the AAB

```cmd
scripts\build_aab.cmd
```

Upload `frontend/android/app/build/outputs/bundle/release/app-release.aab` (or the path printed by the script) to Play Console.

## C. Internal testing track (recommended for doctor demos)

1. Play Console → your app → **Testing → Internal testing**.
2. Create a release → upload the AAB → review → start rollout.
3. **Testers** → create an email list → add each doctor's Gmail.
4. Copy the **opt-in URL** and send it privately (not with clinic PINs).
5. Doctors open the link on their phone (signed into that Google account) → install from Play.
6. To revoke access: remove the Gmail from the tester list (they lose update access; uninstall on device if needed).

Still send **clinic name + clinic password + personal PIN** separately — never in the same message as the Play link if you can avoid it.

## D. Privacy policy

Host [`PRIVACY_POLICY.md`](PRIVACY_POLICY.md) (or paste into Play Console) before publishing. Replace the contact email.

## E. Sideload share APK (small private demos)

```cmd
scripts\build_share_apk.cmd
```

Produces `share\AarogyaOneConnect-v*.apk` with HTTPS API baked in and **no clinic-server override**. Send the APK alone; credentials only via [`share/SHARE_PACK.md`](../share/SHARE_PACK.md) (do not attach that file to the APK).

Android versions auto-bump in [`frontend/android/app/version.properties`](../frontend/android/app/version.properties).

For LAN HTTP installs, leave `CAPACITOR_HTTPS` unset and use Android Studio **Run** / debug APK.
