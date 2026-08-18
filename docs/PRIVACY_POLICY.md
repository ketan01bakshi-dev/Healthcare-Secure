# Privacy policy (clinic app — Play Store / staff notice)

**App:** Aarogya One Connect (`com.healthcare.secure`)  
**Last updated:** July 2026  

This is a **clinic staff** application for recording visits, vitals, lab results, and prescriptions. It is not a consumer patient portal.

## Data we process

- Staff sign-in identifiers and PIN verification (PINs should be stored hashed).
- Patient identifiers entered by staff (name, phone, optional MRN/ABHA) are used to compute a **blind ID**; raw phone/name are not intended as permanent database columns.
- Clinical content: notes, vitals, lab values, prescription fields, and uploaded documents.
- Device settings: clinic server URL, language, temperature unit preference (stored on the device).

## Where data is stored

- On the **clinic’s own server** (PC or cloud VPS you configure), not on Google’s servers by default.
- Documents may be stored as files under the clinic API’s attachment directory.
- The phone app talks only to the clinic API URL you set.

## Sharing

- Prescription PDFs may be shared via the device share sheet / print when staff choose to.
- There is no advertising SDK and no sale of patient data.

## Security

- Use HTTPS in production (`CAPACITOR_HTTPS=true` + TLS on the API).
- Restrict staff access with PINs and roles (doctor / staff / lab).
- The clinic operator is the data controller under applicable law (e.g. India’s DPDP Act).

## Contact

Replace with your clinic contact email before publishing on Play Store:

`privacy@your-clinic.example`

## Changes

We may update this policy when features change; keep a dated copy with your Play listing.
