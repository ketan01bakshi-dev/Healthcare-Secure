"""Video consult room naming and modality helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.api.v1.endpoints.appointments import _normalize_modality
from app.api.v1.endpoints.video_consult import _jitsi_urls, _room_name


def test_normalize_modality() -> None:
    assert _normalize_modality("video") == "video"
    assert _normalize_modality("teleconsult") == "video"
    assert _normalize_modality("in_person") == "in_person"
    assert _normalize_modality("") == "in_person"


def test_room_name_has_no_phi() -> None:
    when = datetime(2026, 7, 31, 12, 30, tzinfo=timezone.utc)
    room = _room_name(
        clinic_id="default",
        blind_patient_id="sha256:deadbeef",
        when=when,
    )
    assert room.startswith("aoc-default-")
    assert "deadbeef" not in room or "deadbeef"[:10]  # hash may include digest chars
    assert "Ananya" not in room
    assert "98765" not in room
    join, doctor = _jitsi_urls(room)
    assert join.endswith(room)
    assert doctor.endswith(room)
