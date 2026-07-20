"""Clinical record ORM models — never store raw patient identifiers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


class ClinicalRecord(Base):
    """
    De-identified clinical encounter row.

    Identity linkage uses ``blind_patient_id`` (HMAC token) only. Raw mobile
    numbers, national IDs, and similar identifiers must never be columns here.
    """

    __tablename__ = "clinical_records"
    __table_args__ = (
        # Speeds history search: filter by token, order by created_at DESC.
        Index(
            "ix_clinical_records_blind_patient_id_created_at",
            "blind_patient_id",
            "created_at",
        ),
    )

    # UUID primary key (stable unique record ID).
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    blind_patient_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="HMAC-SHA256 blind token; irreversible patient linkage key",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # JSONB on PostgreSQL; JSON on SQLite for local development.
    encounter_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
    )

    def __repr__(self) -> str:
        return (
            f"<ClinicalRecord id={self.id!s} "
            f"blind_patient_id={self.blind_patient_id[:8]}…>"
        )
