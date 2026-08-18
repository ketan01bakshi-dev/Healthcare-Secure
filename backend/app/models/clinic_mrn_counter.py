"""Per-clinic sequential MRN counter."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClinicMrnCounter(Base):
    """Next MRN sequence number for a clinic (DEFAULT-000001, EAST-000002, …)."""

    __tablename__ = "clinic_mrn_counters"

    clinic_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
