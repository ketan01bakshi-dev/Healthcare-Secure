# Demo Patient Directory — Both Clinics

**Purpose:** Comprehensive patient roster for client demos. Seed with `--wipe` before each major pitch so timelines, billing, and queues look fresh.

| Clinic | Unlock name | Seed command | Pitch doc |
|--------|-------------|--------------|-----------|
| **Gynecology** | Alpha Clinic | `scripts\seed_demo.cmd --wipe` | [`DEMO_CLIENT.md`](DEMO_CLIENT.md) |
| **General Physician** | City General Clinic | `scripts\seed_demo_gp.cmd --wipe` | [`DEMO_GP.md`](DEMO_GP.md) |

API: `https://api.aarogyaoneconnect.in` · Credentials: private `share/SHARE_PACK.md`

---

## Capability coverage map

| Capability | Alpha Clinic patient | City General patient |
|------------|----------------------|----------------------|
| Voice-to-Rx (hero) | Sunita Devi / Aisha Begum | Arjun Mehta / Rohit Jain |
| Case brief + ANC alerts + GA charts | Ananya Reddy | — (gynae-only) |
| Critical vitals / Rx hints | Rekha Sharma | Sita Patel |
| Labs + paid bill | Kavita Mehta | Ramesh Kumar |
| Billing amount due + pay QR | Sonal Desai | Anjali Rao |
| Fully settled (₹0 due) | Pooja Sinha | Geeta Joshi |
| Waiting list / walk-in | Lakshmi Iyer | Sita Patel / Aarav Sharma |
| Video consult | Ananya Reddy / Fatima Khan | — |
| MRN / audit security | Neha Kapoor | Neha Shah |
| Pediatric vitals | Isha Gupta (16y) | Aarav Sharma (6y) |
| High-risk specialty | Deepa Verma (twins) | Harish Gupta (CAD) |
| Screening / wellness | Jyoti Malhotra (Pap) | Geeta Joshi |
| Referral handoff | Nandini Rao | — |
| Mental health / counselling | — | Shalini Menon |
| Acute walk-in Rx | Sunita Devi | Mohan Lal (AGE) / Deepak Nair (asthma) |
| Analytics / top meds | Kavita + volume seeds | Ramesh + volume seeds |
| Clean slate (live mic) | Aisha Begum | Rohit Jain |

---

## A) Alpha Clinic — Gynecology (16 patients)

Unlock: **Alpha Clinic** · Doctor: **Dr Nirmala Tiwari** · PIN in `SHARE_PACK.md`

| # | Patient | Mobile | MRN | Age / profile | Seeded clinical data | Demo action |
|---|---------|--------|-----|---------------|----------------------|-------------|
| 1 | **Ananya Reddy** ★ | 9876501001 | GYN-1001 | 28y · G2P1 · ~28w ANC | Obstetric profile (LMP/EDD/GPLA/B+), rising BP + falling Hb vitals ×4, labs (Hb 9.8, TSH, urine alb, FBS), signed Rx (IFA, Ca, Labetalol), USG PDF + Analyze, billing due, video consult timeline, future ANC + tele slots | Visit → Case brief, ANC alerts, GA charts, consult pack, Records → Analyze USG |
| 2 | **Priya Nair** | 9876501007 | GYN-1007 | Early ANC ~12w | Obstetric profile, early vitals, NT scan cadence **due** | Visit → scan checklist NT due |
| 3 | **Rekha Sharma** | 9876501008 | GYN-1008 | PIH / anemia | High BP + low Hb vitals, critical alerts, unpaid charges | Visit → alerts; draft Rx without iron / with Methergine → Rx hints |
| 4 | **Kavita Mehta** | 9876501002 | — | PCOS / infertility | Hormonal workup, pelvic USG, paid lab bill | Records + More → Analytics |
| 5 | **Sunita Devi** | 9876501003 | — | Dysmenorrhea | Signed Rx (mefenamic + TXA), part-paid consult | Visit → Voice / Load demo script → Sign Rx |
| 6 | **Meera Joshi** | 9876501004 | GYN-1004 | Postpartum | Postpartum profile + next appointment (14d) | Patient Info → next appointment / ICS |
| 7 | **Fatima Khan** | 9876501005 | — | Infertility | Labs + **tomorrow video** booking | Patient Info → appointments (day-before SMS story) |
| 8 | **Lakshmi Iyer** | 9876501006 | — | PMB / menopause | Endometrium USG, Waiting List **Open**, walk-in charge | Waiting List → lock |
| 9 | **Neha Kapoor** | 9876501009 | GYN-1009 | Security | MRN-keyed identity + audit trail | Lock by MRN; show timeline survives phone change |
| 10 | **Aisha Begum** | 9876501010 | — | Voice clean slate | Minimal history | Live mic Voice-to-Rx (or Load demo transcript) |
| 11 | **Sonal Desai** | 9876501011 | GYN-1011 | Billing hero | Charges + partial payment → **~₹2,150 due** | Front Desk → Billing → Show pay QR |
| 12 | **Deepa Verma** | 9876501012 | GYN-1012 | Twins ~24w | DCDA twin obstetric profile, high-risk notes, aspirin Rx, partial bill | Visit → high-risk ANC / twin story |
| 13 | **Jyoti Malhotra** | 9876501013 | GYN-1013 | 42y screening | Pap NILM lab, normal cervix Rx, **fully paid** | Screening counselling beat |
| 14 | **Pooja Sinha** | 9876501014 | GYN-1014 | Settled bill | Vitals + charges fully paid → **₹0 due** | Contrast with Sonal billing pitch |
| 15 | **Isha Gupta** | 9876501015 | GYN-1015 | **Age 16** | Pediatric vitals ranges, adolescent dysmenorrhea Rx | Lock → show age-aware vitals + guardian story |
| 16 | **Nandini Rao** | 9876501016 | GYN-1016 | AUB / referral | Complex AUB Rx + handoff advice | Forward Case History / referral pack |

### Alpha — voice scripts (quick paste)

**Sunita (dysmenorrhea):**  
> Severe lower abdominal pain and heavy menstrual flow for three days. Abdomen soft, tender hypogastrium. Diagnosis primary dysmenorrhea and menorrhagia. Mefenamic acid five hundred milligrams three times a day after food for three days. Tranexamic acid five hundred milligrams three times a day for five days.

**Ananya (ANC):**  
> Antenatal care at twenty eight weeks. Mild backache and fatigue. Fundal height appropriate, fetal heart present. Mild anemia. Iron folic acid one tablet once daily after food for thirty days. Calcium five hundred milligrams twice daily for thirty days. Labetalol one hundred milligrams twice daily for seven days.

---

## B) City General Clinic — GP (14 patients)

Unlock: **City General Clinic** · Doctor: **Dr Rajesh Kumar** · PIN in `SHARE_PACK.md`

| # | Patient | Mobile | MRN | Age / profile | Seeded clinical data | Demo action |
|---|---------|--------|-----|---------------|----------------------|-------------|
| 1 | **Ramesh Kumar** ★ | 9876512001 | GP-2001 | 52y · T2DM | FBS/HbA1c trend ×4, metformin + statin Rx | Visit → vitals charts / DM follow-up |
| 2 | **Sita Patel** | 9876512002 | GP-2002 | 58y · HTN | Rising BP to 162/104, amlodipine + telmisartan | Visit → BP alerts |
| 3 | **Arjun Mehta** | 9876512003 | GP-2003 | URTI | Signed URTI Rx (paracetamol + azithromycin) | Visit → Voice / Load URTI script |
| 4 | **Kamala Devi** | 9876512004 | GP-2004 | Geriatric | Polypharmacy chronic review | Geriatric polypharmacy beat |
| 5 | **Vikram Singh** | 9876512005 | GP-2005 | Thyroid | TSH trend + levothyroxine | Lab timeline / thyroid |
| 6 | **Neha Shah** | 9876512006 | GP-2006 | Security | MRN + audit | Lock by MRN |
| 7 | **Rohit Jain** | 9876512007 | — | Voice clean slate | Minimal | Live mic |
| 8 | **Anjali Rao** | 9876512008 | GP-2008 | Billing hero | Charges − partial → **~₹1,850 due** | Front Desk → Show pay QR |
| 9 | **Aarav Sharma** | 9876512009 | GP-2009 | **Age 6** | Fever 101.2°F, pediatric vitals, syrup Rx | Pediatric ranges + mother story |
| 10 | **Deepak Nair** | 9876512010 | GP-2010 | Asthma | SpO2 trend, budesonide-formoterol + salbutamol | Chronic respiratory beat |
| 11 | **Mohan Lal** | 9876512011 | GP-2011 | AGE | Dehydration notes, ORS + ondansetron + racecadotril | Acute walk-in Rx |
| 12 | **Harish Gupta** | 9876512012 | GP-2012 | 61y · CAD | Post-MI vitals ×3, LDL lab, DAPT + statin + metoprolol | Chronic IHD follow-up |
| 13 | **Geeta Joshi** | 9876512013 | GP-2013 | Settled | Wellness vitals + **₹0 due** | Contrast with Anjali |
| 14 | **Shalini Menon** | 9876512014 | GP-2014 | Anxiety / insomnia | Counselling Rx (melatonin) + sleep hygiene advice | Mental health / counselling |

### GP — voice script (quick paste)

**Arjun (URTI):**  
> Cough, fever, and sore throat for three days. Throat congested, chest clear on auscultation. Diagnosis acute upper respiratory tract infection. Paracetamol five hundred milligrams three times a day after food for three days. Azithromycin five hundred milligrams once daily for three days.

---

## C) 10-minute dual-clinic demo path

### Path 1 — Gynecology (Alpha)

| Min | Role | Lock | Show |
|-----|------|------|------|
| 0–1 | Doctor | — | Unlock, Hindi toggle, roles |
| 1–2 | Doctor | Lakshmi / Ananya | Waiting List + All patients |
| 2–4 | Doctor | **Ananya Reddy** | Case brief, ANC, GA, consult pack |
| 4–5 | Doctor | **Deepa Verma** or **Isha Gupta** | Twins high-risk **or** adolescent vitals |
| 5–6 | Doctor | **Sunita** / **Aisha** | Voice → Sign Rx |
| 6–7 | Doctor | Ananya | Records + Analyze USG |
| 7–8 | Front Desk | **Sonal Desai** | Billing due + pay QR (then **Pooja** = ₹0) |
| 8–9 | Doctor | — | More → Analytics |
| 9–10 | Lab | Ananya / Kavita | Lab desk uploads |

### Path 2 — GP (City General)

| Min | Role | Lock | Show |
|-----|------|------|------|
| 0–1 | Doctor | — | Same APK, different clinic name |
| 1–2 | Doctor | Sita / Ramesh | Queue (no obstetric section) |
| 2–4 | Doctor | **Sita Patel** | BP trend alerts |
| 4–5 | Doctor | **Aarav Sharma** | Pediatric fever |
| 5–6 | Doctor | **Arjun** / **Rohit** | Voice → Sign Rx |
| 6–7 | Doctor | Ramesh / Harish | Labs + chronic Rx timeline |
| 7–8 | Front Desk | **Anjali Rao** | Billing + pay QR |
| 8–9 | Doctor | — | Analytics |
| 9–10 | — | Switch clinic | Show Alpha isolation (different patients) |

---

## D) How to reseed

### Local (backend venv)

```cmd
scripts\seed_demo.cmd --wipe
scripts\seed_demo_gp.cmd --wipe
```

### Cloud VPS (live API)

From the repo root on your laptop:

```cmd
scripts\seed_live_demo.cmd
```

This uploads both seed scripts to the VPS, copies them into the API container, and runs `--wipe` for Alpha (`default`) and City General (`gp`).

Verify afterwards:

```cmd
python scripts\release_smoke_test.py https://api.aarogyaoneconnect.in
python scripts\verify_live_demo.py https://api.aarogyaoneconnect.in
```

Or on the VPS directly:

```bash
cd /root/Healthcare-Secure
docker compose exec -T api mkdir -p /app/scripts
docker compose cp backend/scripts/seed_demo.py api:/app/scripts/seed_demo.py
docker compose cp backend/scripts/seed_demo_gp.py api:/app/scripts/seed_demo_gp.py
docker compose exec -T -e PYTHONIOENCODING=utf-8 api python scripts/seed_demo.py --wipe
docker compose exec -T -e PYTHONIOENCODING=utf-8 api python scripts/seed_demo_gp.py --wipe
```

**Note:** `--wipe` only removes rows tagged `demo:seed` / `demo:seed-gp`. Real patient data (if any) is left alone.

---

## E) Role checklist during demo

| Role | Must show |
|------|-----------|
| **Doctor** | Visit, Voice Rx, Case brief (gynae), Records, Analytics, Forward case |
| **Staff / Nurse** | Vitals entry, history, queue |
| **Receptionist** | Patient Info, billing, Show pay QR (no Visit/Rx) |
| **Lab** | Orders list, report upload, structured results |

---

*Last updated: Sep 2026 · Regenerate seed before external demos.*
