"""ORM model for clinic password overrides (self-serve reset without env edit)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClinicCredential(Base):
    """Runtime clinic password hash — overrides CLINICS env password when set."""

    __tablename__ = "clinic_credentials"

    clinic_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    updated_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
