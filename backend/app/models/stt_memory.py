"""STT correction feedback and clinic alias vocabulary (de-identified)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


class SttCorrectionFeedback(Base):
    """
    De-identified parse→sign correction pair for clinic vocabulary learning.

    Stores English transcripts and structured clinical JSON only — never raw
    phone/name columns (blind_patient_id is the HMAC token).
    """

    __tablename__ = "stt_correction_feedback"
    __table_args__ = (
        Index(
            "ix_stt_feedback_clinic_created",
            "clinic_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    blind_patient_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    transcripts: Mapped[list[Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
    )
    parsed_clinical: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
    )
    final_clinical: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
    )
    med_name_edits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SttAlias(Base):
    """Clinic-scoped spoken/misspelled → preferred clinical term."""

    __tablename__ = "stt_aliases"
    __table_args__ = (
        Index(
            "ix_stt_aliases_clinic_from",
            "clinic_id",
            "from_term",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    from_term: Mapped[str] = mapped_column(String(120), nullable=False)
    to_term: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="medication")
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
