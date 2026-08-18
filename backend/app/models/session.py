"""ORM models for durable clinic sessions (survive API restart)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClinicSession(Base):
    """Persisted unlock session — token is the opaque client header value."""

    __tablename__ = "clinic_sessions"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    clinic_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="default", index=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
