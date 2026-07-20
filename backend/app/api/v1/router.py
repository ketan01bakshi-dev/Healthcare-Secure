"""Aggregate v1 API routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, history, prescription

api_router = APIRouter()

# Include leaf routers (each already carries its own path prefix).
# Avoid nesting APIRouter-inside-APIRouter in a way that leaves unresolved
# ``_IncludedRouter`` mounts on some FastAPI versions.
for sub in (health.router, auth.router, prescription.router, history.router):
    for route in sub.routes:
        api_router.routes.append(route)
