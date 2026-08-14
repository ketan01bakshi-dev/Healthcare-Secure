# General Physician demo — cue cards

Use this pitch when demoing **City General Clinic** (general medicine). For gynecology, see [`DEMO_CLIENT.md`](DEMO_CLIENT.md).

## Unlock

1. Install latest `share\AarogyaOneConnect-v*.apk`
2. API: `https://api.aarogyaoneconnect.in` (baked into share APK)
3. Clinic name: **City General Clinic**
4. Clinic password: **ClinicShare2026** (unless reset via Forgot)
5. Profile: **Dr Rajesh Kumar** · PIN **3641**

Also available: **Priya Sharma** (staff `4582`), **Front Desk** (`5193`), **Lab Desk** (`6827`).

Credentials live in private `share\SHARE_PACK.md` — send the APK alone; send PINs separately.

---

## 0) 10-minute pitch map

| Minute | Tab | Lock / action | What to say |
|--------|-----|---------------|-------------|
| 0–1 | Unlock | Dr Rajesh Kumar | Same APK — different clinic name selects GP tenant |
| 1–2 | Patient Info | Waiting List **Open** Sita / Ramesh | Queue + All patients (no obstetric profile section) |
| 2–4 | Visit | **Sita Patel** | Vitals charts — elevated BP trend (no pregnancy case brief) |
| 4–6 | Visit | **Arjun Mehta** or **Rohit Jain** | Voice → Prepare → Sign Rx (or Load demo script → URTI) |
| 6–7 | Records | Ramesh Kumar | Timeline, thyroid/lab results, Analyze report |
| 7–8 | Patient Info | **Anjali Rao** | Billing ledger + Show pay QR |
| 8–9 | More | — | Analytics today/week/top meds |
| 9–10 | Sign out → **Front Desk** | Anjali again | Receptionist: Patient Info + billing only |

---

## 1) Speech → prescription (hero flow)

1. All patients → lock **Arjun Mehta** · `9876512003` / MRN `GP-2003`
2. **Visit** → record (or Load demo script → *URTI*) → **Prepare for review** → **Sign prescription**
3. Show **Records** timeline — signed Rx under Dr Rajesh Kumar

**Speak (or paste):**

> Cough, fever, and sore throat for three days. Throat congested, chest clear on auscultation. Diagnosis acute upper respiratory tract infection. Paracetamol five hundred milligrams three times a day after food for three days. Azithromycin five hundred milligrams once daily for three days.

---

## 2) Patient cheat sheet

| Patient | Mobile | MRN | Showcase |
|---------|--------|-----|----------|
| **Ramesh Kumar** | 9876512001 | GP-2001 | Type 2 DM — HbA1c trend, metformin Rx |
| **Sita Patel** | 9876512002 | GP-2002 | Hypertension — BP alerts, amlodipine |
| **Arjun Mehta** | 9876512003 | GP-2003 | URTI — voice-to-Rx demo |
| **Kamala Devi** | 9876512004 | GP-2004 | Geriatric — polypharmacy |
| **Vikram Singh** | 9876512005 | GP-2005 | Hypothyroidism — TSH trend |
| **Neha Shah** | 9876512006 | GP-2006 | MRN / audit security |
| **Rohit Jain** | 9876512007 | — | Clean slate for live mic |
| **Anjali Rao** | 9876512008 | GP-2008 | Billing ~₹1,850 due + pay QR |

---

## 3) Billing & front desk

1. Sign in as **Front Desk** (`reception_gp` / PIN `1111`).
2. Lock **Anjali Rao** · `9876512008`.
3. **Billing** → amount due → **Show pay QR**.

---

## 4) vs Gynecology clinic

| | Main Clinic (gynae) | City General Clinic (GP) |
|--|---------------------|--------------------------|
| Unlock name | Main Clinic | City General Clinic |
| Obstetric profile | Yes | Hidden |
| Case brief / ANC | Yes | Hidden |
| Demo scripts | Dysmenorrhea, ANC, PCOS | URTI, DM, HTN |
| Patients | GYN-* mobiles | GP-* mobiles |

Both clinics share the same API URL and APK — data is isolated by `clinic_id`.
