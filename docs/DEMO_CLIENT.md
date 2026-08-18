# Client demo — cue cards (doctor pitch)

Two specialty demos on the **same APK and API** — pick the clinic at unlock:

| Demo | Clinic name | Pitch doc |
|------|-------------|-----------|
| Gynecology | **Alpha Clinic** | This file |
| General Physician | **City General Clinic** | [`DEMO_GP.md`](DEMO_GP.md) |

## Cloud phone (recommended for pitch)

1. Install `share\AarogyaOneConnect-v*.apk`
2. Clinic server: `https://api.aarogyaoneconnect.in`
3. Unlock **Alpha Clinic** (gynae) or **City General Clinic** (GP) — see [`SHARE_PACK.md`](../share/SHARE_PACK.md) for PINs

---

## Local laptop (optional)

Sign in: **Dr. Nirmala Tiwari** · PIN **1234**  
Also: **Front Desk** · **1111** · staff **Staff** / **5678** · lab **Lab Desk** / **9999**

Seed gynae: `scripts\seed_demo.cmd --wipe`  
Seed GP: `scripts\seed_demo_gp.cmd --wipe`  
APK rebuild: `scripts\build_share_apk.cmd`

Speak clearly in English (Groq/Whisper). Or use **Load demo script** on Visit if the mic is noisy.

---

## 0) 10-minute pitch map

| Minute | Tab | Lock / action | What to say |
|--------|-----|---------------|-------------|
| 0–1 | Unlock | Doctor | Roles, Hindi toggle, clinic server URL |
| 1–2 | Patient Info | Waiting List **Open** Lakshmi / Ananya | Queue + All patients directory |
| 2–4 | Visit | **Ananya Reddy** | Case brief, ANC alerts, GA charts, consult pack |
| 4–6 | Visit | **Sunita** or **Aisha** | Voice → Prepare → Sign Rx (or Load demo script) |
| 6–7 | Records | Ananya | Timeline, Analyze USG, audit |
| 7–8 | Patient Info | **Sonal Desai** | Billing ledger + Show pay QR |
| 8–9 | More | — | Analytics today/week/top meds |
| 9–10 | Sign out → **Front Desk** | Sonal again | Receptionist sees Patient Info + billing, not Visit/Rx |

---

## 1) Speech → prescription (hero flow)

1. All patients → lock **Sunita Devi** · `9876501003`
2. **Visit** → record (or Load demo script → *Dysmenorrhea*) → **Prepare for review** → edit → **Sign prescription** → Print/Share
3. Show **Records** timeline: signed Rx appears with doctor name (no raw phone in DB)

**Speak (or paste):**

> Severe lower abdominal pain and heavy menstrual flow for three days. Abdomen soft, tender hypogastrium. Diagnosis primary dysmenorrhea and menorrhagia. Mefenamic acid five hundred milligrams three times a day after food for three days. Tranexamic acid five hundred milligrams three times a day for five days.

**Second voice case — Ananya Reddy** `9876501001` / MRN `GYN-1001`:

> Antenatal care at twenty eight weeks. Mild backache and fatigue. Fundal height appropriate, fetal heart present. Mild anemia. Iron folic acid one tablet once daily after food for thirty days. Calcium five hundred milligrams twice daily for thirty days. Labetalol one hundred milligrams twice daily for seven days.

**Security beat (same Visit):** say a phone number in the recording — parse must **refuse** (PHI redaction).

---

## 2) Patient analytics & decision support

| Patient | Mobile | Show |
|---------|--------|------|
| **Ananya Reddy** | 9876501001 | Case brief, ANC alerts, GA charts, consult pack, video timeline, Analyze USG, billing due |
| **Priya Nair** | 9876501007 | Scan cadence — NT **due** |
| **Rekha Sharma** | 9876501008 | Critical BP/Hb; Rx hints; unpaid charges |
| **Kavita Mehta** | 9876501002 | PCOS labs + paid bill + More → Analytics |
| **Lakshmi Iyer** | 9876501006 | Waiting List **Open** → lock |
| **Sonal Desai** | 9876501011 | **Billing pitch** — amount due + Show pay QR |
| **Fatima Khan** | 9876501005 | Tomorrow **video** appointment |

**More → Clinic analytics:** today counts, week bars, top medications/diagnoses, vitals trend for locked patient.

---

## 3) Billing & front desk

1. Sign in as **Front Desk** (or stay as doctor).
2. **Patient Info** → All patients → lock **Sonal Desai** · `9876501011` / MRN `GYN-1011`.
3. Expand **Billing**: today’s charges, total paid, **amount due** (~₹2,150).
4. **Show pay QR** (cloud may use Razorpay mock until live keys are set).

---

## 4) Security story (60 seconds)

1. Lock by **name + mobile** (or MRN).
2. Records timeline — blind IDs; audit shows who entered vitals.
3. Voice parse with spoken mobile → **blocked**.
4. **Neha Kapoor** `GYN-1009` / **Meera Joshi** `GYN-1004` — MRN identity story.

---

## 5) Ops tips

- Phone APK must be rebuilt after share-lockdown UI (`scripts\build_share_apk.cmd`)
- Cloud clinic URL: `https://api.aarogyaoneconnect.in`
- Credentials: see private `share\SHARE_PACK.md` (do **not** attach to the APK)
- Clinic password: `ClinicShare2026` · doctor PIN for Alpha Clinic: `4829`
- After frontend changes: rebuild APK — API deploy alone does not update screens
- General Physician pitch: [`DEMO_GP.md`](DEMO_GP.md)
