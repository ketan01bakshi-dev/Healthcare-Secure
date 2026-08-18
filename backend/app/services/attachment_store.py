"""Store uploaded documents on disk instead of base64-in-JSON."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.core.config import settings

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def attachments_root() -> Path:
    configured = (getattr(settings, "attachments_dir", None) or "").strip()
    if configured:
        root = Path(configured)
    else:
        root = Path(__file__).resolve().parents[2] / "data" / "attachments"
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_attachment(
    *,
    blind_patient_id: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> str:
    """Write bytes to disk; return relative path under attachments root."""
    prefix = (blind_patient_id or "unknown")[:16]
    safe_name = _SAFE.sub("_", (filename or "document")[:80]) or "document"
    rel = f"{prefix}/{uuid.uuid4().hex}_{safe_name}"
    path = attachments_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    # Store content_type beside file for recovery
    meta = path.with_suffix(path.suffix + ".meta")
    meta.write_text(content_type or "application/octet-stream", encoding="utf-8")
    return rel.replace("\\", "/")


def load_attachment(relative_path: str) -> tuple[bytes, str]:
    """Load (bytes, content_type) from a relative attachment path."""
    rel = (relative_path or "").replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        raise FileNotFoundError("Invalid attachment path")
    path = attachments_root() / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    raw = path.read_bytes()
    meta = path.with_suffix(path.suffix + ".meta")
    ctype = (
        meta.read_text(encoding="utf-8").strip()
        if meta.is_file()
        else "application/octet-stream"
    )
    return raw, ctype
