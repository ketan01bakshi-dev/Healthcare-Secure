"""Aggregate v1 API routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    analytics,
    appointments,
    auth,
    health,
    history,
    integrations,
    payments,
    prescription,
    queue,
    video_consult,
)

api_router = APIRouter()

for sub in (
    health.router,
    auth.router,
    prescription.router,
    history.router,
    queue.router,
    appointments.router,
    integrations.router,
    analytics.router,
    video_consult.router,
    payments.router,
):
    for route in sub.routes:
        api_router.routes.append(route)
