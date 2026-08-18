"""Hash a clinic PIN for CLINIC_USERS (pbkdf2$salt$hex).

Usage (from backend with venv)::

    .\\.venv\\Scripts\\python ..\\scripts\\hash_pin.py 1234
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(ROOT))

from app.services.doctor_auth import hash_pin  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: hash_pin.py <pin>")
        raise SystemExit(1)
    print(hash_pin(sys.argv[1]))


if __name__ == "__main__":
    main()
