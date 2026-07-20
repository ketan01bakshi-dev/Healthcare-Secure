"""Health check endpoints."""

from fastapi import APIRouter

from app import __version__

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """API v1 health check (no PHI)."""
    return {"status": "healthy", "version": __version__}
