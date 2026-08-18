"""Clinic-scoped patient roster for directory / reopen (name + last4, encrypted phone)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, PrimaryKeyConstraint, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClinicPatient(Base):
    """Named patient known to a clinic — filled on lock / appointment, not from blind IDs alone."""

    __tablename__ = "clinic_patients"
    __table_args__ = (
        PrimaryKeyConstraint("clinic_id", "blind_patient_id", name="pk_clinic_patients"),
    )

    clinic_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    blind_patient_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    phone_last4: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    phone_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    clinic_mrn: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    age_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    visit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    lab_orders_json: Mapped[str | None] = mapped_column(Text, nullable=True)
