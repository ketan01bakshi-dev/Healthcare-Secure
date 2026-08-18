"""Scheduled appointments with optional SMS confirmation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Appointment(Base):
    """Clinic appointment — scoped by clinic_id; phone encrypted for SMS."""

    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_clinic_scheduled", "clinic_id", "scheduled_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    blind_patient_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Fernet token or empty when SMS already sent and number discarded
    phone_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    phone_last4: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[str] = mapped_column(String(8), nullable=False, default="15")
    reason: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    # in_person | video
    modality: Mapped[str] = mapped_column(String(20), nullable=False, default="in_person")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="booked")
    sms_status: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    def to_public(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "clinic_id": self.clinic_id,
            "display_name": self.display_name,
            "phone_last4": self.phone_last4,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "duration_minutes": int(self.duration_minutes or "15"),
            "reason": self.reason,
            "modality": (self.modality or "in_person").strip().lower() or "in_person",
            "status": self.status,
            "sms_status": self.sms_status,
            "created_by": self.created_by,
            "notes": self.notes,
        }
