"""Remove all patient data for one clinic_id. Keeps users, PINs, and other clinics.

  python scripts/wipe_clinic_patients.py --clinic default --yes
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path("/app") if Path("/app/app").is_dir() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select, update  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.appointment import Appointment  # noqa: E402
from app.models.clinic_mrn_counter import ClinicMrnCounter  # noqa: E402
from app.models.clinic_patient import ClinicPatient  # noqa: E402
from app.models.payment_intent import PaymentIntent  # noqa: E402
from app.models.record import ClinicalRecord  # noqa: E402
from app.models.stt_memory import SttAlias, SttCorrectionFeedback  # noqa: E402
from app.api.v1.endpoints.queue import QueueEntry  # noqa: E402
from app.services.attachment_store import attachments_root  # noqa: E402


def _delete_attachments(blinds: set[str]) -> int:
    root = attachments_root()
    removed = 0
    prefixes = {b[:16] for b in blinds if b}
    if not root.is_dir() or not prefixes:
        return 0
    for child in root.iterdir():
        if child.is_dir() and child.name in prefixes:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    return removed


def wipe(clinic_id: str) -> dict[str, int]:
    cid = (clinic_id or "").strip()
    db = SessionLocal()
    counts: dict[str, int] = {}
    try:
        blinds = {
            r[0]
            for r in db.execute(
                select(ClinicalRecord.blind_patient_id).where(
                    ClinicalRecord.clinic_id == cid
                )
            ).all()
            if r[0]
        }
        blinds |= {
            r[0]
            for r in db.execute(
                select(ClinicPatient.blind_patient_id).where(
                    ClinicPatient.clinic_id == cid
                )
            ).all()
            if r[0]
        }

        def _count_del(model) -> int:
            n = db.execute(delete(model).where(model.clinic_id == cid)).rowcount or 0
            return int(n)

        counts["clinical_records"] = _count_del(ClinicalRecord)
        counts["clinic_patients"] = _count_del(ClinicPatient)
        counts["appointments"] = _count_del(Appointment)
        counts["clinic_queue"] = _count_del(QueueEntry)
        counts["payment_intents"] = _count_del(PaymentIntent)
        counts["stt_aliases"] = _count_del(SttAlias)
        counts["stt_feedback"] = _count_del(SttCorrectionFeedback)
        counts["mrn_counters_reset"] = db.execute(
            update(ClinicMrnCounter)
            .where(ClinicMrnCounter.clinic_id == cid)
            .values(next_value=1)
        ).rowcount or 0
        db.commit()
        counts["attachment_dirs"] = _delete_attachments(blinds)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Wipe patient data for one clinic")
    parser.add_argument("--clinic", required=True, help="clinic_id (Alpha Clinic = default)")
    parser.add_argument("--yes", action="store_true", help="Required confirmation")
    args = parser.parse_args()
    if not args.yes:
        raise SystemExit("Refusing to wipe without --yes")
    counts = wipe(args.clinic)
    print(f"Wiped patient data for clinic_id={args.clinic!r}")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
