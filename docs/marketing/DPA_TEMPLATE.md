# Data Processing Addendum (DPA)

**Aarogya One Connect — Security and Compliance Framework**

This Data Processing Addendum (“Addendum”) forms part of the Agreement between **[Your Legal Entity Name]** (“Processor”) and the **[Clinic/Hospital Name]** (“Controller”) (collectively, the “Parties”).

---

## 1. Professional Context

This Addendum reflects the Processor’s commitment to the **Digital Personal Data Protection Act, 2023 (DPDP Act)** and international best practices in healthcare data handling. The Service is designed as a professional workspace for clinic staff, utilizing identity minimization and role-based access control.

## 2. Processor’s Commitments

The Processor shall:

2.1 **Documented Instructions:** Process Personal Data only to provide the Service and as instructed by the Controller.

2.2 **Confidentiality:** Ensure all personnel authorized to process data are committed to strict confidentiality.

2.3 **Technical Excellence:** Implement industry-leading security measures, including:
- **Identity Minimization:** HMAC-based blind patient identifiers.
- **Access Control:** Multi-gate authentication (Clinic Gate + Per-user PIN).
- **Data Hardening:** Encryption-at-rest for roster data and encryption-in-transit (TLS 1.3).
- **Tenant Isolation:** Logical separation of clinic data at the database layer.

2.4 **Sub-processing Transparency:** Maintain a curated list of high-tier infrastructure providers (Schedule C).

2.5 **Breach Response:** Notify the Controller within **72 hours** of confirming any unauthorized data access affecting the Controller’s tenant.

## 3. Controller’s Obligations

The Controller shall:

3.1 **Lawful Basis:** Ensure a valid legal basis for collecting patient information under the DPDP Act.

3.2 **Staff Hygiene:** Manage internal access roles and ensure staff adhere to PIN security policies.

3.3 **Patient Notice:** Provide necessary privacy disclosures to patients as the primary care provider.

## 4. Data Lifecycle

4.1 **Retention:** Data is retained for the duration of the active subscription.

4.2 **Portability & Exit:** Upon termination, the Controller may request a structured export of clinical records. Processor will securely purge production data within **90 days** post-termination, subject to backup rotation cycles.

---

## Schedule A — Processing Specification

| Attribute | Details |
|-----------|---------|
| **Subject Matter** | OPD Clinic Operations and Patient Management |
| **Data Categories** | Clinical notes, vitals, lab results, prescriptions, billing records |
| **Data Subjects** | Clinic patients and authorized staff users |
| **Hosting Region** | Primary: India (Mumbai Region) |

## Schedule B — Security Standards

- **Infrastructure:** Tier-III data center environment.
- **Monitoring:** Real-time health probes and unauthorized access logging.
- **Hardening:** HSTS enforcement, backup-prevention on mobile clients, and restricted shell access.

## Schedule C — Approved Sub-processors

| Provider | Purpose | Data Location |
|----------|---------|---------------|
| [Hosting Provider] | Cloud Infrastructure | India |
| [STT Provider] | Voice Transcription | [Region] |
| [LLM Provider] | Clinical Parsing | [Region] |
| Razorpay | Payment Processing | India |

---

*Executed on [Date] by the authorized representatives of the Parties.*
