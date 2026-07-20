"""Ephemeral clinical prescription PDF — clinic letterhead template + auto date/time."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fpdf import FPDF

from app.core.config import settings
from app.services.lml_parser import ClinicalParseResult, PHIContentError

# Assets live next to this package: backend/app/assets/
_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
_DEFAULT_SEAL = _ASSETS_DIR / "doctor_seal.png"
_DEFAULT_LETTERHEAD = _ASSETS_DIR / "letterhead.png"

# Common clinic offsets when IANA tzdata is unavailable (e.g. Windows without tzdata).
_FIXED_OFFSETS: dict[str, timedelta] = {
    "Asia/Kolkata": timedelta(hours=5, minutes=30),
    "Asia/Calcutta": timedelta(hours=5, minutes=30),
    "UTC": timedelta(0),
}


def _resolve_tzinfo(name: str):
    try:
        return ZoneInfo(name)
    except Exception:
        offset = _FIXED_OFFSETS.get(name)
        if offset is not None:
            return timezone(offset, name=name)
        return timezone.utc


def _now_local(tz_name: str | None = None) -> datetime:
    """Wall-clock issue time in the clinic timezone (auto-fetched)."""
    zone = _resolve_tzinfo(tz_name or settings.prescription_timezone)
    return datetime.now(timezone.utc).astimezone(zone)


def _format_issued(issued: datetime) -> tuple[str, str]:
    """Return (human local IST label, ISO-8601) for the prescription stamp."""
    local = issued if issued.tzinfo else issued.replace(tzinfo=timezone.utc)
    # Always present India time clearly (clinic default Asia/Kolkata).
    offset = local.utcoffset()
    is_ist = offset == timedelta(hours=5, minutes=30)
    human = local.strftime("%d %b %Y, %I:%M %p").replace(" 0", " ")
    if is_ist:
        human = f"{human} IST"
    elif offset is not None:
        total = int(offset.total_seconds() // 60)
        sign = "+" if total >= 0 else "-"
        human = f"{human} UTC{sign}{abs(total) // 60:02d}:{abs(total) % 60:02d}"
    else:
        human = f"{human} UTC"
    iso = local.isoformat(timespec="seconds")
    return human, iso


def _resolve_zone(name: str):
    """Backward-compatible alias."""
    return _resolve_tzinfo(name)


class _PrescriptionPDF(FPDF):
    """A4 prescription on a clinic letterhead template with doctor seal block."""

    def __init__(
        self,
        *,
        clinic_name: str,
        clinic_subtitle: str,
        clinic_address: str,
        doctor_name: str,
        doctor_credentials: str,
        letterhead_path: Path | None,
        seal_path: Path | None,
    ) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.clinic_name = clinic_name
        self.clinic_subtitle = clinic_subtitle
        self.clinic_address = clinic_address
        self.doctor_name = doctor_name
        self.doctor_credentials = doctor_credentials
        self.letterhead_path = letterhead_path
        self.seal_path = seal_path
        self.set_auto_page_break(auto=True, margin=28)
        self.set_margins(16, 36, 16)

    def header(self) -> None:
        if self.letterhead_path and self.letterhead_path.is_file():
            try:
                self.image(str(self.letterhead_path), x=0, y=0, w=210)
            except Exception:
                self._draw_letterhead_band()
        else:
            self._draw_letterhead_band()
        self.set_y(34)

    def _draw_letterhead_band(self) -> None:
        """Built-in template when no letterhead image is provided."""
        self.set_fill_color(20, 56, 54)
        self.rect(0, 0, 210, 32, style="F")
        self.set_text_color(232, 242, 241)
        self.set_xy(16, 7)
        self.set_font("Helvetica", "B", 16)
        self.cell(140, 8, self.clinic_name, align="L")
        self.set_xy(16, 15)
        self.set_font("Helvetica", "", 9)
        self.cell(140, 5, self.clinic_subtitle, align="L")
        if self.clinic_address:
            self.set_xy(16, 21)
            self.set_font("Helvetica", "", 8)
            self.cell(140, 5, self.clinic_address, align="L")
        # Doctor line on the right of the header
        self.set_xy(130, 8)
        self.set_font("Helvetica", "B", 10)
        self.cell(64, 5, self.doctor_name, align="R")
        if self.doctor_credentials:
            self.set_xy(130, 14)
            self.set_font("Helvetica", "", 8)
            self.cell(64, 4, self.doctor_credentials, align="R")
        self.set_text_color(30, 30, 30)

    def footer(self) -> None:
        self.set_y(-18)
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.2)
        self.line(16, self.get_y(), 194, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(110, 110, 110)
        self.multi_cell(
            0,
            3.5,
            f"{self.clinic_name}  |  Confidential clinical document. "
            "Patient identified only by anonymous token. "
            f"Page {self.page_no()}/{{nb}}",
            align="C",
        )


def _section_title(pdf: FPDF, title: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 82, 78)
    pdf.cell(0, 7, title.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(61, 155, 148)
    pdf.set_line_width(0.4)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.l_margin + 64, y)
    pdf.ln(3)
    pdf.set_text_color(30, 30, 30)


def _bullet_list(pdf: FPDF, items: list[str], empty_label: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 10)
    if not items:
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, empty_label, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(30, 30, 30)
        return
    for item in items:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5.5, f"  -  {item}")


def _medication_table(pdf: FPDF, clinical: ClinicalParseResult) -> None:
    pdf.set_x(pdf.l_margin)
    headers = ("Medication", "Dosage", "Frequency", "Duration")
    col_widths = (62, 36, 40, 36)
    row_h = 8

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(30, 82, 78)
    pdf.set_text_color(255, 255, 255)
    for header, width in zip(headers, col_widths, strict=True):
        pdf.cell(width, row_h, f" {header}", border=0, fill=True)
    pdf.ln(row_h)
    pdf.set_x(pdf.l_margin)

    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Helvetica", "", 9)

    if not clinical.medications:
        pdf.set_fill_color(245, 247, 247)
        pdf.cell(
            sum(col_widths),
            row_h,
            "  No medications recorded",
            border=0,
            fill=True,
        )
        pdf.ln(row_h)
        return

    for index, med in enumerate(clinical.medications):
        if index % 2 == 0:
            pdf.set_fill_color(245, 247, 247)
        else:
            pdf.set_fill_color(255, 255, 255)
        cells = (
            (med.name or "-")[:42],
            (med.dosage or "-")[:22],
            (med.frequency or "-")[:24],
            (med.duration or "-")[:22],
        )
        for text, width in zip(cells, col_widths, strict=True):
            pdf.cell(width, row_h, f" {text}", border=0, fill=True)
        pdf.ln(row_h)


def _draw_doctor_seal(pdf: _PrescriptionPDF, x: float, y: float, size: float = 32) -> None:
    """Place seal image if provided; otherwise draw a circular clinic seal stamp."""
    if pdf.seal_path and pdf.seal_path.is_file():
        try:
            pdf.image(str(pdf.seal_path), x=x, y=y, w=size, h=size)
            return
        except Exception:
            pass

    cx = x + size / 2
    cy = y + size / 2
    r = size / 2
    pdf.set_draw_color(30, 82, 78)
    pdf.set_line_width(0.8)
    pdf.ellipse(cx - r, cy - r, size, size, style="D")
    pdf.set_line_width(0.35)
    pdf.ellipse(cx - r + 2, cy - r + 2, size - 4, size - 4, style="D")
    pdf.set_text_color(30, 82, 78)
    pdf.set_font("Helvetica", "B", 6)
    pdf.set_xy(x, cy - 6)
    pdf.cell(size, 4, "DOCTOR SEAL", align="C")
    pdf.set_xy(x, cy - 1)
    pdf.set_font("Helvetica", "B", 5)
    clinic_short = (pdf.clinic_name or "CLINIC")[:22]
    pdf.cell(size, 3.5, clinic_short, align="C")
    pdf.set_xy(x, cy + 4)
    pdf.set_font("Helvetica", "", 5)
    pdf.cell(size, 3, (pdf.doctor_name or "")[:20], align="C")
    pdf.set_text_color(30, 30, 30)


def _signature_block(
    pdf: _PrescriptionPDF,
    *,
    issued_human: str,
) -> None:
    pdf.ln(10)
    # Keep seal + signature on the current page when possible
    if pdf.get_y() > 240:
        pdf.add_page()

    sig_y = pdf.get_y()
    seal_x = 16
    _draw_doctor_seal(pdf, seal_x, sig_y, size=30)

    line_x = 55
    pdf.set_draw_color(120, 120, 120)
    pdf.set_line_width(0.3)
    pdf.line(line_x, sig_y + 22, 120, sig_y + 22)
    pdf.set_xy(line_x, sig_y + 23)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(65, 4, pdf.doctor_name, align="L")
    pdf.set_xy(line_x, sig_y + 27)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(90, 90, 90)
    cred = pdf.doctor_credentials or "Authorized Clinician"
    pdf.cell(65, 4, cred, align="L")

    # Auto date/time stamp (right)
    pdf.set_xy(130, sig_y + 8)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(30, 82, 78)
    pdf.cell(64, 4, "Issued", align="L")
    pdf.set_xy(130, sig_y + 13)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(64, 4, issued_human, align="L")
    pdf.set_draw_color(150, 150, 150)
    pdf.line(130, sig_y + 22, 194, sig_y + 22)
    pdf.set_xy(130, sig_y + 23)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(64, 4, "Date & time (auto)", align="L")


def prescription_issue_timestamp(
    tz_name: str | None = None,
) -> tuple[datetime, str, str]:
    """Auto-fetch clinic-local issue time → (datetime, human label, ISO string)."""
    issued = _now_local(tz_name)
    human, iso = _format_issued(issued)
    return issued, human, iso


def generate_prescription_pdf(
    clinical: ClinicalParseResult,
    *,
    patient_token: str,
    clinic_name: str | None = None,
    clinic_subtitle: str | None = None,
    doctor_name: str | None = None,
    doctor_credentials: str | None = None,
    issued_at: datetime | None = None,
) -> io.BytesIO:
    """
    Compile a prescription PDF from the clinic letterhead template.

    Date/time is taken automatically from the clinic timezone when ``issued_at``
    is omitted. Optional assets:
      - ``app/assets/letterhead.png`` (full-page or header background)
      - ``app/assets/doctor_seal.png`` (circular seal / stamp image)
    """
    if clinical.phi_detected:
        raise PHIContentError(
            clinical.phi_redaction_reason
            or "Cannot generate prescription PDF: PHI detected in source content"
        )

    token = (patient_token or "").strip()
    if not token:
        raise ValueError("patient_token (anonymous blind patient ID) is required")

    name = (
        clinic_name or settings.clinic_name or settings.app_name
    ).strip()
    subtitle = (
        clinic_subtitle
        or settings.clinic_subtitle
        or "Secure Clinical Prescription - De-identified Patient Record"
    ).strip()
    doctor = (doctor_name or settings.doctor_name or "Attending Clinician").strip()
    credentials = (
        doctor_credentials
        if doctor_credentials is not None
        else settings.doctor_credentials
    ).strip()
    address = (settings.clinic_address or "").strip()

    seal_cfg = (settings.doctor_seal_path or "").strip()
    letter_cfg = (settings.prescription_letterhead_path or "").strip()
    seal_path = Path(seal_cfg) if seal_cfg else _DEFAULT_SEAL
    letterhead_path = Path(letter_cfg) if letter_cfg else _DEFAULT_LETTERHEAD
    if not seal_path.is_file():
        seal_path = None
    if not letterhead_path.is_file():
        letterhead_path = None

    issued = issued_at or _now_local()
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=_resolve_tzinfo(settings.prescription_timezone))
    issued_human, issued_iso = _format_issued(issued)

    pdf = _PrescriptionPDF(
        clinic_name=name,
        clinic_subtitle=subtitle,
        clinic_address=address,
        doctor_name=doctor,
        doctor_credentials=credentials,
        letterhead_path=letterhead_path,
        seal_path=seal_path,
    )
    pdf.alias_nb_pages()
    pdf.add_page()

    # Document title + auto date/time meta
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(20, 56, 54)
    pdf.cell(0, 8, "CLINICAL PRESCRIPTION", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 5, f"Issued: {issued_human}", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, f"Timestamp: {issued_iso}", ln=True)
    pdf.ln(2)

    # Anonymous patient token
    pdf.set_fill_color(232, 242, 241)
    pdf.set_draw_color(61, 155, 148)
    pdf.set_line_width(0.5)
    box_y = pdf.get_y()
    pdf.rect(16, box_y, 178, 18, style="DF")
    pdf.set_xy(20, box_y + 3)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(30, 82, 78)
    pdf.cell(0, 4, "ANONYMOUS PATIENT TOKEN", ln=True)
    pdf.set_x(20)
    pdf.set_font("Courier", "B", 11)
    pdf.set_text_color(20, 40, 40)
    pdf.multi_cell(170, 5, token)
    pdf.set_y(box_y + 22)
    pdf.set_x(pdf.l_margin)

    _section_title(pdf, "Symptoms")
    _bullet_list(pdf, clinical.symptoms, "No symptoms recorded.")

    _section_title(pdf, "Clinical Observations")
    _bullet_list(
        pdf,
        clinical.clinical_observations,
        "No clinical observations recorded.",
    )

    _section_title(pdf, "Diagnoses")
    _bullet_list(pdf, clinical.diagnoses, "No diagnoses recorded.")

    _section_title(pdf, "Medications")
    _medication_table(pdf, clinical)

    _signature_block(pdf, issued_human=issued_human)

    buffer = io.BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer
