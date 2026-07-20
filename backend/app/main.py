"""FastAPI application entrypoint with CORS for local frontend development."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Warm local Whisper and ensure ORM tables exist for local SQLite POC."""
    # Import models so metadata is registered, then create missing tables.
    from app.core.database import Base, engine
    import app.models.record  # noqa: F401

    Base.metadata.create_all(bind=engine)

    if settings.whisper_provider.lower() == "local" and settings.whisper_preload:
        try:
            from app.services.transcription import preload_local_whisper_model

            preload_local_whisper_model()
        except Exception as exc:  # noqa: BLE001 — allow API to start; fail on transcribe
            print(f"[whisper] local model preload skipped: {exc}")
    yield


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# Restrict CORS to localhost frontend origins (never use "*" with credentials in production).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-Correlation-ID",
        "X-Doctor-Session",
    ],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
async def root_health() -> dict[str, str]:
    """Liveness probe for load balancers and local checks."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": __version__,
        "whisper_provider": settings.whisper_provider,
    }
