# Aarogya One Connect — Pre-Release Test Report

**Date:** 23 August 2026  
**Build tested on device:** `AarogyaOneConnect-v1.58` (versionCode 59)  
**Device:** Google Pixel 10 (`57251FDCR00AK5`)  
**Cloud API:** `https://api.aarogyaoneconnect.in`  
**Tester:** Automated suite + ADB device checks + cloud smoke script  

---

## Executive summary

| Area | Result |
|------|--------|
| Backend automated tests | **53/53 PASS** |
| Frontend TypeScript | **PASS** |
| Cloud API smoke (auth, RBAC, patients) | **13/13 PASS** |
| Device install & launch | **PASS** |
| Debug instrumentation removed (source) | **PASS** (see rebuild note) |
| Play Store publication readiness | **NOT READY** — see blockers |

### Verdict: **CONDITIONAL GO**

**Safe for:** private clinic rollout via sideload APK or Play **Internal testing** with invited testers, after deploying backend debug cleanup and shipping **v1.59+** APK (debug fetch calls removed from frontend source in this session).

**Not yet safe for:** unrestricted public Play Store listing until Play Console assets, signed AAB, privacy policy URL, and Android hardening items below are completed.

---

## 1. Automated testing

### Backend (`pytest tests/`)

| Suite | Tests | Status |
|-------|-------|--------|
| Billing | 5 | PASS |
| Case summary | 1 | PASS |
| Lab orders | 2 | PASS |
| P1 reliability (auth, vitals, ABDM mock, visit counts) | 15 | PASS |
| Payments QR (mock Razorpay) | 3 | PASS |
| Referral PDF & handoff | 4 | PASS |
| STT memory / aliases | 6 | PASS |
| Transcription bilingual + Auto language | 14 | PASS |
| Video consult | 2 | PASS |
| **Total** | **53** | **ALL PASS** |

**Notes fixed during this run:**
- Transcription default language is now **`auto`** (intentional product change); test updated.
- Visit-count test used a fixed phone number polluted by persistent SQLite test DB; test now uses a unique 10-digit phone per run.

### Frontend

| Check | Status |
|-------|--------|
| `npx tsc --noEmit` | PASS |
| `npm run lint` | Skipped — Next.js lint wizard not configured (non-blocking) |

---

## 2. Cloud API smoke tests

Script: `scripts/release_smoke_test.py` (run against production API with Alpha Clinic demo credentials).

| Check | Result |
|-------|--------|
| `GET /auth/status` reachable over HTTPS | PASS |
| `auth_required: true` | PASS |
| No clinic/user roster leak on status | PASS |
| Clinic unlock (`POST /auth/clinic-unlock`) | PASS |
| Clinic ticket issued | PASS |
| Doctor PIN unlock | PASS |
| Session token issued | PASS |
| Authenticated patient list | PASS (7 patients) |
| Unauthenticated access blocked (401) | PASS |
| Clinical search (doctor) | PASS |
| Lab role blocked from vitals (403) | PASS |
| Lab clinical search allowed | PASS |

**Observation:** API responds over TLS but does **not** send `Strict-Transport-Security` header. Recommend adding HSTS at reverse proxy (Caddy/Nginx).

---

## 3. Device testing (Pixel 10 via ADB)

| Check | Result | Evidence |
|-------|--------|----------|
| Device connected | PASS | `adb devices` → `57251FDCR00AK5 device` |
| Package installed | PASS | `com.healthcare.secure` |
| Version | PASS | versionName **1.58**, versionCode **59** |
| App launch | PASS | `am start …MainActivity` — no crash |
| Capacitor bundle load | PASS | Logcat shows assets served from `https://localhost` |
| Fatal / AndroidRuntime errors on launch | PASS | None observed |

### Manual flows — **requires on-device verification by clinician**

The following were **not** fully automatable via ADB (no UI test harness configured). Perform on the connected phone before wide release:

- [ ] Clinic unlock: **Alpha Clinic** / clinic password → profile list appears
- [ ] Doctor PIN unlock (`dr_main` / PIN) → calendar/home loads
- [ ] Open patient → tokenize / MRN assignment
- [ ] Vitals entry and save
- [ ] Unified clinical note (text + mic inline) → Review → parse prescription
- [ ] Prescription share (SMS/WhatsApp) — verify **no double "Dr Dr."** prefix
- [ ] Share link TTL copy shows **72 hours**
- [ ] Forward case history with Hindi note normalization
- [ ] Themed select popups (blood group, language) — no dark OS picker
- [ ] FAB **+** dialog — backdrop blur visible
- [ ] Sign out vs Switch clinic behaviour
- [ ] Lab login (`lab1`) — Labs tab only; vitals blocked
- [ ] Receptionist login — reduced tab set
- [ ] Microphone permission prompt on first voice use
- [ ] Offline / airplane mode — graceful error (no silent data loss)

---

## 4. Security & privacy audit

### 4.1 Authentication & access control

| Control | Status | Notes |
|---------|--------|-------|
| Two-gate auth (clinic password + PIN) | PASS | Cloud smoke verified |
| Session header (`X-Doctor-Session`) | PASS | Not Bearer JWT — by design |
| Unauthenticated API blocked | PASS | 401 on protected routes |
| Role-based vitals (lab → 403) | PASS | Cloud smoke verified |
| Auth status does not leak roster | PASS | |
| Rate limiting on auth endpoints | PASS | Implemented (`check_rate_limit`) |
| Clinic ticket HMAC binding | PASS | `clinic_tickets.py` |

### 4.2 Data protection

| Control | Status | Notes |
|---------|--------|-------|
| Patient IDs HMAC-blinded (`SECRET_SALT`) | PASS | Documented in handbook |
| Phone encrypted at rest | PASS | `encrypt_phone` in roster |
| Prescription PDF presigned URLs | PASS | 72h TTL (`PRESIGNED_TTL_SECONDS`) |
| HTTPS API on share builds | PASS | `CAPACITOR_HTTPS=true` in `build_share_apk.cmd` |
| PHI in logs | **FIXED (source)** | Removed `#region agent log` blocks from backend + frontend |

### 4.3 Findings — open items

| Severity | Issue | Recommendation |
|----------|-------|----------------|
| **MEDIUM** | `clinical_search` doc says lab sees **own uploads only**; code filters by record **type** only, not `entered_by.user_id` | Filter `document`/`lab_result` by `entered_by.user_id == session.user_id` for lab role |
| **MEDIUM** | Clinic unlock ticket TTL **600s**, in-memory store — lost on API restart; users re-enter clinic password | Persist tickets in Redis/DB or extend TTL; document UX |
| **MEDIUM** | `android:allowBackup="true"` | Set `false` for release to prevent ADB backup of WebView localStorage sessions |
| **LOW** | `usesCleartextTraffic="true"` + permissive `network_security_config` | Restrict cleartext to debug builds; release profile HTTPS-only |
| **LOW** | No HSTS header on cloud API | Add at reverse proxy |
| **LOW** | Privacy policy placeholder email | Replace `privacy@your-clinic.example` and host public URL for Play Console |
| **INFO** | 72h PDF link TTL | Acceptable for demo; document for compliance review |

### 4.4 Debug instrumentation cleanup (this session)

Removed from production code paths:

- `backend/app/services/clinic_tickets.py`
- `backend/app/api/v1/endpoints/prescription.py`
- `backend/app/services/razorpay_client.py`
- `frontend/src/lib/doctorSession.ts`

**Action required:** Deploy backend changes to VPS; rebuild APK (**v1.59+**) so installed v1.58 picks up frontend cleanup.

Dev-only file retained: `.cursor/ssh_diag.py` (not shipped in APK).

---

## 5. Play Store readiness checklist

| Item | Status |
|------|--------|
| Signed upload keystore (`healthcare-upload.jks`) | **TODO** — see `docs/PLAY_STORE.md` |
| Release AAB (`scripts/build_aab.cmd`) | **TODO** |
| Privacy policy hosted at public URL | **TODO** |
| Play Console app listing (screenshots, description) | **TODO** |
| Data safety form (health data, encryption, no ads) | **TODO** |
| Target API 35 | PASS (manifest) |
| Package name `com.healthcare.secure` | PASS |
| Internal testing track + tester emails | Recommended before public |

---

## 6. Functional regression matrix (recent fixes)

| Feature | Automated | Manual on device |
|---------|-----------|------------------|
| Double "Dr" in share SMS | — | **Verify on phone** |
| 72h presigned PDF TTL | Backend unit | **Verify share copy** |
| Unified clinical note UI (mic inline) | — | **Verify on phone** |
| STT Auto language | 14 pytest | **Verify Hindi/English mic** |
| ThemedSelect (blood group etc.) | — | **Verify on phone** |
| Overlay blur on + dialog | — | **Verify on phone** |
| Forward case history Hindi normalize | referral pytest | **Verify on phone** |

---

## 7. Open blockers — status (updated 23 Aug 2026)

| Blocker | Priority | Status |
|---------|----------|--------|
| Lab clinical-search RBAC | P1 | **Fixed** — filters by `entered_by.user_id` for lab role |
| HSTS on cloud API | P1 | **Fixed** — nginx `Strict-Transport-Security` on all HTTPS vhosts |
| Android `allowBackup` + cleartext | P1 | **Fixed in source** — rebuild APK/AAB to ship (`assembleRelease` for share) |
| Clinic ticket TTL / persistence | P2 | **Fixed** — Postgres-backed tickets, 8h TTL, survives API restart |
| Privacy policy URL + contact | P2 | **Fixed** — https://www.aarogyaoneconnect.in/privacy.html |
| Play upload keystore + AAB | P3 | **TODO (user)** — `key.properties.example` + signing scaffold added |

## 8. Recommended release steps

1. **Deploy backend** — push debug-log removal + any lab RBAC fix to `api.aarogyaoneconnect.in`.
2. **Rebuild share APK** — `scripts\build_share_apk.cmd` → install v1.59 on test devices.
3. **Run manual checklist** (Section 3) on Pixel 10.
4. **Play Store path** — generate keystore, build AAB, host privacy policy, complete Internal testing.
5. **Rotate demo credentials** if `SHARE_PACK.md` may have leaked before external demos.

---

## 8. Test artifacts

| Artifact | Location |
|----------|----------|
| Cloud smoke script | `scripts/release_smoke_test.py` |
| Demo credentials (private) | `share/SHARE_PACK.md` |
| Play Store guide | `docs/PLAY_STORE.md` |
| Privacy policy draft | `docs/PRIVACY_POLICY.md` |

---

*Report generated as part of pre–App Store release validation. Re-run `pytest`, `release_smoke_test.py`, and the manual device checklist after any material code change.*
