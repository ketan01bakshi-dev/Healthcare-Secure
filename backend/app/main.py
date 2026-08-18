"""FastAPI application entrypoint with CORS for local frontend development."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings


def _trusted_hosts() -> list[str]:
    """Filter placeholder ALLOWED_HOSTS entries; always allow localhost variants."""
    placeholders = {"", "your_lan_ip", "change_me"}
    hosts: list[str] = []
    for h in settings.allowed_hosts or []:
        cleaned = (h or "").strip().lower()
        if not cleaned or cleaned in placeholders:
            continue
        hosts.append(cleaned)
    for extra in ("localhost", "127.0.0.1"):
        if extra not in hosts:
            hosts.append(extra)
    return hosts


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create tables, then serve; optionally warm Whisper in the background."""
    from app.core.database import Base, engine
    import app.models.record  # noqa: F401
    import app.models.session  # noqa: F401
    import app.models.appointment  # noqa: F401
    import app.models.clinic_credential  # noqa: F401
    import app.models.clinic_patient  # noqa: F401
    import app.models.clinic_mrn_counter  # noqa: F401
    import app.models.stt_memory  # noqa: F401
    import app.models.payment_intent  # noqa: F401
    import app.api.v1.endpoints.queue  # noqa: F401

    Base.metadata.create_all(bind=engine)

    try:
        from app.services.schema_migrate import ensure_schema_columns

        ensure_schema_columns(engine)
    except Exception as exc:  # noqa: BLE001
        print(f"[schema] migrate skipped: {exc}")

    try:
        from app.services.doctor_auth import purge_expired_sessions

        purge_expired_sessions()
    except Exception as exc:  # noqa: BLE001
        print(f"[auth] session purge skipped: {exc}")

    warm_task: asyncio.Task | None = None
    if settings.whisper_provider.lower() == "local" and settings.whisper_preload:

        async def _warm_whisper() -> None:
            try:
                from app.services.transcription import preload_local_whisper_model

                await asyncio.to_thread(preload_local_whisper_model)
            except Exception as exc:  # noqa: BLE001
                print(f"[whisper] local model preload skipped: {exc}")

        warm_task = asyncio.create_task(_warm_whisper())

    yield

    if warm_task and not warm_task.done():
        warm_task.cancel()


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

_hosts = _trusted_hosts()
# Enforce Host allow-list in production; keep LAN phone access easy in development.
if (settings.app_env or "").strip().lower() == "production" and _hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)
elif (settings.app_env or "").strip().lower() != "production":
    # TestClient uses Host: testserver
    if "testserver" not in _hosts:
        _hosts = [*_hosts, "testserver"]

# Explicit list (env) plus private/loopback browser origins so local Next.js on
# http://192.168.x.x:PORT can call the cloud API without listing every LAN IP.
_LOCAL_BROWSER_ORIGIN_RE = (
    r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    r"|https?://(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=_LOCAL_BROWSER_ORIGIN_RE,
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
