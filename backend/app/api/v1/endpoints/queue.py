"""Today's clinic waiting queue (lightweight — not a full HIS)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String, Uuid, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base, get_db
from app.services.doctor_auth import ClinicalSession, DoctorSession
from app.services.security import tokenize_patient_identifier

router = APIRouter(prefix="/queue")


class QueueEntry(Base):
    __tablename__ = "clinic_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="default", index=True
    )
    queue_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    blind_patient_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[str] = mapped_column(String(120), nullable=False, default="")


class QueueAddRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=120)
    raw_identifier: str = Field(..., min_length=1)
    note: str = Field(default="", max_length=200)


class QueueOut(BaseModel):
    id: UUID
    display_name: str
    note: str
    status: str
    created_at: datetime | None
    created_by: str


def _today() -> str:
    return date.today().isoformat()


@router.get("/today", response_model=list[QueueOut])
def list_today(
    _auth: DoctorSession,
    db: Session = Depends(get_db),
) -> list[QueueOut]:
    if _auth.role == "lab":
        raise HTTPException(status_code=403, detail="Lab cannot view the waiting list")
    rows = db.scalars(
        select(QueueEntry)
        .where(
            QueueEntry.queue_date == _today(),
            QueueEntry.clinic_id == _auth.clinic_id,
        )
        .order_by(QueueEntry.created_at.asc())
    ).all()
    return [
        QueueOut(
            id=r.id,
            display_name=r.display_name,
            note=r.note,
            status=r.status,
            created_at=r.created_at,
            created_by=r.created_by,
        )
        for r in rows
        if r.status != "done"
    ]


@router.post("/today", response_model=QueueOut)
def add_to_queue(
    body: QueueAddRequest,
    session: ClinicalSession,
    db: Session = Depends(get_db),
) -> QueueOut:
    try:
        blind = tokenize_patient_identifier(body.raw_identifier.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    row = QueueEntry(
        clinic_id=session.clinic_id,
        queue_date=_today(),
        display_name=body.display_name.strip(),
        blind_patient_id=blind,
        note=(body.note or "").strip()[:200],
        status="waiting",
        created_by=session.display_name,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return QueueOut(
        id=row.id,
        display_name=row.display_name,
        note=row.note,
        status=row.status,
        created_at=row.created_at,
        created_by=row.created_by,
    )


@router.post("/today/{entry_id}/done")
def mark_done(
    entry_id: UUID,
    _auth: ClinicalSession,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    row = db.get(QueueEntry, entry_id)
    if (
        row is None
        or row.queue_date != _today()
        or row.clinic_id != _auth.clinic_id
    ):
        raise HTTPException(status_code=404, detail="Queue entry not found")
    row.status = "done"
    db.commit()
    return {"status": "ok"}
