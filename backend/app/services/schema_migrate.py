"""Ensure new columns exist on SQLite/Postgres (create_all does not ALTER)."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _column_names(engine: Engine, table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def ensure_schema_columns(engine: Engine) -> None:
    """Add clinic_id (and related) columns when upgrading an existing DB."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        # clinical_records.clinic_id
        cols = _column_names(engine, "clinical_records")
        if cols and "clinic_id" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE clinical_records "
                    "ADD COLUMN clinic_id VARCHAR(64) NOT NULL DEFAULT 'default'"
                )
            )
            if dialect == "sqlite":
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS "
                        "ix_clinical_records_clinic_id "
                        "ON clinical_records (clinic_id)"
                    )
                )

        # clinic_sessions.clinic_id
        cols = _column_names(engine, "clinic_sessions")
        if cols and "clinic_id" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE clinic_sessions "
                    "ADD COLUMN clinic_id VARCHAR(64) NOT NULL DEFAULT 'default'"
                )
            )

        # clinic_queue.clinic_id
        cols = _column_names(engine, "clinic_queue")
        if cols and "clinic_id" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE clinic_queue "
                    "ADD COLUMN clinic_id VARCHAR(64) NOT NULL DEFAULT 'default'"
                )
            )

        # clinic_patients.age_years
        cols = _column_names(engine, "clinic_patients")
        if cols and "age_years" not in cols:
            conn.execute(
                text("ALTER TABLE clinic_patients ADD COLUMN age_years FLOAT")
            )

        # clinic_patients.lab_orders_json — Visit ticks shared with Lab desk
        cols = _column_names(engine, "clinic_patients")
        if cols and "lab_orders_json" not in cols:
            conn.execute(
                text("ALTER TABLE clinic_patients ADD COLUMN lab_orders_json TEXT")
            )

        # appointments.modality (in_person | video)
        cols = _column_names(engine, "appointments")
        if cols and "modality" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE appointments "
                    "ADD COLUMN modality VARCHAR(20) NOT NULL DEFAULT 'in_person'"
                )
            )

# Tables whose display_name is a patient name (EncryptedText) -> primary key columns.
_PATIENT_NAME_TABLES: dict[str, tuple[str, ...]] = {
    "clinic_patients": ("clinic_id", "blind_patient_id"),
    "appointments": ("id",),
    "clinic_queue": ("id",),
}


def encrypt_patient_names(engine: Engine) -> int:
    """
    Encrypt legacy plaintext patient names in place; returns rows changed.

    Idempotent: rows that already hold a valid Fernet token are skipped. On
    Postgres the VARCHAR(120) columns are widened to TEXT first, because a
    Fernet token is longer than the name it wraps.
    """
    from app.core.encrypted_type import encrypt_text, is_encrypted

    changed = 0
    with engine.begin() as conn:
        insp = inspect(conn)
        tables = set(insp.get_table_names())
        for table, pk in _PATIENT_NAME_TABLES.items():
            if table not in tables:
                continue
            cols = {c["name"]: c for c in insp.get_columns(table)}
            if "display_name" not in cols:
                continue
            if engine.dialect.name == "postgresql" and getattr(
                cols["display_name"]["type"], "length", None
            ):
                conn.execute(
                    text(f"ALTER TABLE {table} ALTER COLUMN display_name TYPE TEXT")
                )
            pk_sql = ", ".join(pk)
            rows = conn.execute(
                text(f"SELECT {pk_sql}, display_name FROM {table}")
            ).all()
            where = " AND ".join(f"{c} = :{c}" for c in pk)
            for row in rows:
                name = row[-1]
                if not name or is_encrypted(name):
                    continue
                params = {c: row[i] for i, c in enumerate(pk)}
                params["name"] = encrypt_text(name)
                conn.execute(
                    text(f"UPDATE {table} SET display_name = :name WHERE {where}"),
                    params,
                )
                changed += 1
    return changed
