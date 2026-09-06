#!/usr/bin/env python3
"""
Build competitor benchmarking and sales walk-in cheat sheet in Word (docx) format.
Professional B2B documents aligned with Aarogya One Connect's brand positioning (Aug 2026).
"""

from __future__ import annotations

from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent


def set_run_font(run, size=11, bold=False, italic=False, color=None):
    run.font.name = "Calibri"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = color


def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        set_run_font(
            run,
            size={1: 16, 2: 13, 3: 11}.get(level, 11),
            bold=True,
            color=RGBColor(0x1E, 0x52, 0x4E) if level == 1 else RGBColor(0x2A, 0x6F, 0x6A),
        )
    h.paragraph_format.space_before = Pt(12)
    h.paragraph_format.space_after = Pt(4)
    return h


def add_p(doc, text, *, bold=False, italic=False, size=10.5, space_after=6, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, italic=italic, color=color)
    return p


def add_bullets(doc, items, level=0):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.left_indent = Inches(0.25 * (level + 1))
        p.paragraph_format.space_after = Pt(4)
        
        # Split on markdown-like bold indicators for basic formatting if any
        parts = item.split("**")
        for idx, part in enumerate(parts):
            is_bold = (idx % 2 == 1)
            run = p.add_run(part)
            set_run_font(run, size=10, bold=is_bold)


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        for p in hdr[i].paragraphs:
            p.paragraph_format.space_after = Pt(2)
            for run in p.runs:
                set_run_font(run, size=9.5, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
            
            # Set background color to dark teal for headers
            tcPr = hdr[i]._element.get_or_add_tcPr()
            shd = qn("w:shd")
            tcPr.append(
                doc.element.makeelement(
                    shd,
                    attrib={qn("w:val"): "clear", qn("w:color"): "auto", qn("w:fill"): "1E524E"}
                )
            )

    for r_i, row in enumerate(rows):
        cells = table.rows[r_i + 1].cells
        # Zebra striping color: clear or subtle slate tint
        fill_color = "F8FAFC" if r_i % 2 == 1 else "FFFFFF"
        for c_i, val in enumerate(row):
            cells[c_i].text = str(val)
            for p in cells[c_i].paragraphs:
                p.paragraph_format.space_after = Pt(2)
                for run in p.runs:
                    set_run_font(run, size=9)
            
            if fill_color != "FFFFFF":
                tcPr = cells[c_i]._element.get_or_add_tcPr()
                shd = qn("w:shd")
                tcPr.append(
                    doc.element.makeelement(
                        shd,
                        attrib={qn("w:val"): "clear", qn("w:color"): "auto", qn("w:fill"): fill_color}
                    )
                )
    doc.add_paragraph()


def build_benchmarking():
    doc = Document()
    
    # Page setup
    section = doc.sections[0]
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

    # Title & Metadata
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Aarogya One Connect — Competitor Benchmarking & Positioning")
    set_run_font(run, size=18, bold=True, color=RGBColor(0x1E, 0x52, 0x4E))
    title.paragraph_format.space_after = Pt(2)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = meta.add_run("Aug 2026 · Confidential B2B Sales Enablement Document")
    set_run_font(run, size=9.5, italic=True, color=RGBColor(0x64, 0x74, 0x8B))
    meta.paragraph_format.space_after = Pt(18)

    add_heading(doc, "1. Market Segmentation Map", 1)
    add_p(
        doc,
        "Aarogya One Connect is positioned commercially at the lower end of each market price band "
        "while delivering premium operational workflow value (Voice Rx, 4-role desks, gynae depth, and HMAC privacy). "
        "Unlike legacy systems that meter features or charge per doctor, Aarogya utilizes a transparent flat-clinic model."
    )
    
    headers_map = ["Segment", "India Price Band / mo", "Primary Competitors", "Aarogya Position & Pricing"]
    rows_map = [
        ["Solo OPD Pro", "₹1,500 – ₹3,000", "Eka Doc, Clinicea Starter, Practo Ray base", "Starter Plan: ₹1,999/mo (Flat, 4 staff seats)"],
        ["Polyclinic (3–5 docs)", "₹5,000 – ₹10,000", "Eka Clinic Pro, HealthPlix Pro ×5, Clinicea Pro", "Clinic Plan: ₹5,499/mo (Flat, up to 5 doctors)"],
        ["Chain / Network", "₹12,000 – ₹50,000+", "MocDoc, DocEngage, hospital HIS", "Network Plan: from ₹12,999/mo (Multi-site console)"],
    ]
    add_table(doc, headers_map, rows_map)

    add_heading(doc, "2. Competitor Benchmarking Profiles", 1)

    # HealthPlix
    add_heading(doc, "2.1 HealthPlix (Founded 2014 · ~12 Years Old)", 2)
    add_p(doc, "HealthPlix is a mature EMR platform backed by $22M+ Series C funding, serving over 12,000 doctors. They follow a strict doctor-first EMR focus.")
    add_bullets(doc, [
        "**Pricing Tiers:** Charged per doctor at ₹11,999/yr (Pro) or ₹17,999/yr (Elite). A 3-doctor clinic pays ₹35,997 to ₹53,997/yr.",
        "**Doctor Sentiment (Positive):** Extremely fast prescription creation; high support satisfaction; strong regional language printing (14 languages); built-in ABDM/ABHA.",
        "**Doctor Sentiment (Negative):** Pricing is sales-led and lacks immediate public transparency; per-doctor subscription model makes expansion expensive; does not offer dedicated reception or lab role separation.",
        "**Aarogya Positioning:** Starter matches HealthPlix's pricing band but includes 3 staff seats and Voice Rx. At polyclinic level, Aarogya is over 45% cheaper due to flat-clinic pricing."
    ])

    # Eka Care
    add_heading(doc, "2.2 Eka Care (Founded Dec 2020 · ~5 Years Old)", 2)
    add_p(doc, "Eka Care is an AI-native practice OS focused on digital presence and voice-powered EMR. They have raised $19.5M.")
    add_bullets(doc, [
        "**Pricing Tiers:** Solo plans at ₹16,999/yr (Doc Plus) and ₹18,749/yr (Doc Pro). Polyclinic tier is ₹1,00,000/yr (Clinic Pro for 5 docs).",
        "**Doctor Sentiment (Positive):** Sleek, modern mobile-first interface; clean prescription templates; integration with Google My Business and reviews.",
        "**Doctor Sentiment (Negative):** Significant complaints about support response times and service reliability; numerous hidden/metered costs: ₹1 per WhatsApp message, teleconsult 50p/min after 200 min, and storage at ₹1,200 per 20GB.",
        "**Aarogya Positioning:** Aarogya Clinic plan is ₹54,990/yr — roughly 45% below Eka Clinic Pro — and bundles Voice Rx and all core desks flat with no metered storage or basic WhatsApp billing shocks."
    ])

    # Practo Ray
    add_heading(doc, "2.3 Practo Ray (Founded 2008 · ~17 Years Old)", 2)
    add_p(doc, "Practo Ray is India's most recognized booking system, tightly coupled with its patient-facing doctor search marketplace.")
    add_bullets(doc, [
        "**Pricing Tiers:** Base SaaS is ₹999–₹3,999/mo per doctor, but marketplace commissions (6-12%) and premium listing fees (Reach/Prime) add ₹1,500–₹3,000/mo for a busy clinic.",
        "**Doctor Sentiment (Positive):** High volume of patient discovery for new consultancies; standard EMR and billing functionality.",
        "**Doctor Sentiment (Negative):** Serious doctor complaints regarding complex pricing, high transaction deductions, and feeling commoditized by Practo's algorithms; support is frequently reported as unresponsive once the sale is complete.",
        "**Aarogya Positioning:** For established practices that do not rely on Practo leads, Aarogya is the ultimate B2B alternative: 0% transaction commissions, flat billing, and full clinical data ownership."
    ])

    # Clinicea
    add_heading(doc, "2.4 Clinicea (Founded 2012 · ~14 Years Old)", 2)
    add_p(doc, "Clinicea is an unfunded cloud EMR focused on extreme customization and multi-specialty workflows across 6 continents.")
    add_bullets(doc, [
        "**Pricing Tiers:** Billed per doctor at ₹1,999/mo (Starter), ₹2,999/mo (Pro), and ₹3,999/mo (Enterprise). 5-doctor clinic on Pro costs ₹1,79,940/year.",
        "**Doctor Sentiment (Positive):** Highly customizable EMR cards that mimic paper; responsive customer support; deep financial and inventory features.",
        "**Doctor Sentiment (Negative):** Expensive at polyclinic scale; lacks built-in native voice/AI dictation scribes; missing two-way automated WhatsApp workflows.",
        "**Aarogya Positioning:** Aarogya is significantly cheaper at scale (₹54,990/yr flat vs. Clinicea's ₹1.8L/yr) and comes with native Voice Rx dictation built-in."
    ])

    # MocDoc & DocEngage
    add_heading(doc, "2.5 MocDoc & DocEngage (Legacy HIS & Modular CRM)", 2)
    add_p(doc, "MocDoc (Founded 2012, Chennai) is a full-stack HIS, while DocEngage (Founded ~2015, Hyderabad) is a highly transparent modular healthcare CRM.")
    add_bullets(doc, [
        "**Pricing Tiers:** MocDoc is quote-based (~₹3,000–₹10,000/mo); DocEngage is ₹499–₹1,299 per user/mo (Practice Management Advanced is ₹699/mo/user).",
        "**Doctor Sentiment (Positive):** Complete department billing, laboratory integration, and ward management (MocDoc); modular telemedicine and home-care extensions (DocEngage).",
        "**Doctor Sentiment (Negative):** Long implementation periods (weeks to months); extreme interface complexity for outpatient doctors; per-user cost scaling on DocEngage gets expensive.",
        "**Aarogya Positioning:** Aarogya is built exclusively for OPD speed, not inpatient wards. Clinics can self-onboard and go live in minutes, with flat-clinic pricing for unlimited staff."
    ])

    add_heading(doc, "3. Feature × Price Benchmarking Matrix", 1)
    
    headers_matrix = ["Dimension", "Aarogya", "HealthPlix", "Eka Care", "Practo Ray", "Clinicea Pro"]
    rows_matrix = [
        ["Monthly (Solo Equiv.)", "₹1,999", "₹999/doctor", "₹1,562", "₹2,000–4,000+", "₹2,999/doctor"],
        ["5-Doc Clinic / yr", "₹54,990", "₹59,995", "₹1,00,000", "₹1.2L–2.4L+", "₹1,79,940"],
        ["Voice / AI Scribe Rx", "✅ Core (Hindi/En)", "✅ (H.A.L.O)", "Partial", "❌", "❌"],
        ["4-Role OPD Desks", "✅ Included", "❌ Staff only", "Partial", "Partial", "Partial"],
        ["UPI QR Billing", "✅ (Razorpay QR)", "Add-on", "Add-on", "✅", "✅"],
        ["ANC / Gynae Depth", "✅ Specialization", "Generic EMR", "Generic EMR", "Generic EMR", "Templates"],
        ["Transaction Fees", "❌ None", "❌ None", "❌ None", "⚠️ 6-12% commission", "❌ None"],
        ["Data Privacy", "✅ HMAC Blind ID", "❌ Standard", "❌ Standard", "❌ Standard", "❌ Standard"],
    ]
    add_table(doc, headers_matrix, rows_matrix)

    add_heading(doc, "4. Doctor Value Narrative (Sales Playbook)", 1)
    
    add_heading(doc, "4.1 Key Value Levers", 2)
    add_bullets(doc, [
        "**Voice-to-Rx:** Dictate notes in English, Hindi, or mixed speech. AI structures a signed prescription in seconds. Doctors save 15–20 minutes per day, reclaiming 60–80 hours per year.",
        "**Unified 4-Desks:** Seamless handoff. The nurse records vitals on a tablet; the receptionist manages billing on a desktop; the doctor dictates on a mobile app; the lab uploads results. Everything is synced instantly under a single flat clinic fee.",
        "**Flat, Commission-Free Pricing:** Never get penalized for growing. While Practo Ray charges transaction fees for marketplace bookings, and Eka meters storage and WhatsApp credits, Aarogya is one predictable flat bill.",
        "**HMAC Blind Patient Identity:** Ultimate clinical privacy. Raw patient identities (names, full phone numbers) are never stored in plain text on clinical records. They are hashed using HMAC-SHA256, protecting the doctor from DPDPA liability."
    ])

    # Save
    path = ROOT / "Competitor_Benchmarking.docx"
    doc.save(str(path))
    return path


def build_cheat_sheet():
    doc = Document()
    
    # Page setup - tighter margins for 1-page fit
    section = doc.sections[0]
    section.top_margin = Inches(0.5)
    section.bottom_margin = Inches(0.5)
    section.left_margin = Inches(0.5)
    section.right_margin = Inches(0.5)

    # Brand Title
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Aarogya One Connect — Sales Walk-In Cheat Sheet")
    set_run_font(run, size=15, bold=True, color=RGBColor(0x1E, 0x52, 0x4E))
    title.paragraph_format.space_after = Pt(2)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("The Modern Outpatient (OPD) Operating System vs. Legacy Software")
    set_run_font(run, size=10, italic=True, color=RGBColor(0x2A, 0x6F, 0x6A))
    subtitle.paragraph_format.space_after = Pt(12)

    # Core Value Pitch
    add_p(
        doc,
        "Why continue typing on slow, complex medical software? Aarogya One Connect is a modern, mobile-first "
        "OPD operating system designed specifically for Indian clinics. We place our pricing at the lower-end "
        "of the market (from ₹1,999/mo) while offering features incumbents charge premium add-ons for.",
        bold=True
    )
    
    add_heading(doc, "1. Quick Benchmarking at a Glance", 2)
    
    headers = ["Friction Point", "Practo Ray / Incumbents", "HealthPlix / Eka Care", "Aarogya One Connect"]
    rows = [
        ["Pricing model", "Per-doctor subscription + fees", "Per-doctor annual contract", "Flat per clinic (Unlimited staff)"],
        ["Hidden costs", "6-12% booking commission", "₹1/msg WhatsApp, storage fees", "None. Flat B2B monthly plan"],
        ["Voice dictation", "❌ Typing only", "Limited or Pro tier only", "✅ Voice-to-Rx (Hindi + English)"],
        ["Workspaces", "Single-desk view", "Doctor + basic receptionist", "✅ 4 Desks (Dr/Nurse/Reception/Lab)"],
        ["Patient Data", "Shared with marketplace search", "Standard cloud server", "✅ HMAC Hashed Blind Privacy (DPDP)"],
    ]
    add_table(doc, headers, rows)

    add_heading(doc, "2. Three Reasons Doctors Switch to Aarogya", 2)
    
    add_bullets(doc, [
        "**Reclaim 20 Minutes a Day:** Dictate prescriptions on your phone in English, Hindi, or both. Our AI structures clinical notes and generates a signed professional Rx PDF instantly. No typing required.",
        "**Never Pay for Expanding Your Staff:** Incumbents charge you every time you add a doctor or receptionist. Aarogya offers flat clinic pricing. Receptionists, nurses, and lab staff collaborate seamlessly on their own devices at zero extra cost.",
        "**100% Free of Transaction Fees:** Practo and online marketplaces take commissions from every appointment. With Aarogya, patients scan a Razorpay UPI QR code generated directly on their visit card. 100% of the collection goes to your bank account."
    ])

    add_heading(doc, "3. Value-Driven Pricing (excl. 18% GST)", 2)
    
    add_bullets(doc, [
        "**Starter (Solo Consultations):** ₹1,999/month (or ₹19,990/year) — 1 Doctor + 3 Staff Seats, Voice-to-Rx, and all 4 desks.",
        "**Clinic (Modern Polyclinic):** ₹5,499/month (or ₹54,990/year) — Up to 5 Doctors + Unlimited Staff, Advanced Gynae/ANC charts, and referral inbox.",
        "**Network (Healthcare Chains):** From ₹12,999/month — Multi-site tenant, dedicated manager, and historic data migration."
    ])

    doc.add_paragraph() # spacing
    
    # Call to action footer
    cta = doc.add_paragraph()
    cta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run1 = cta.add_run("Schedule a 10-Minute Clinical Walkthrough\n")
    set_run_font(run1, size=11, bold=True, color=RGBColor(0x1E, 0x52, 0x4E))
    run2 = cta.add_run("sales@aarogyaoneconnect.in  ·  +91 75660 99983  ·  www.aarogyaoneconnect.in")
    set_run_font(run2, size=10, bold=True, color=RGBColor(0x2A, 0x6F, 0x6A))

    # Save
    path = ROOT / "Competitor_Sheet_Sales.docx"
    doc.save(str(path))
    return path


if __name__ == "__main__":
    p1 = build_benchmarking()
    p2 = build_cheat_sheet()
    print(f"Successfully generated B2B DOCX files:\n1. {p1}\n2. {p2}")
