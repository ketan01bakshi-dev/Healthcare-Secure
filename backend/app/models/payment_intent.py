"""Razorpay UPI QR payment intents — de-identified patient linkage only."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentIntent(Base):
    """Tracks a gateway QR payment until paid or expired (no PHI columns)."""

    __tablename__ = "payment_intents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    clinic_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    blind_patient_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount_inr: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="razorpay")
    provider_order_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    provider_qr_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="created",
        index=True,
        doc="created | qr_active | paid | failed | expired",
    )
    billing_record_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        default=None,
    )
    qr_string: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    qr_image_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
