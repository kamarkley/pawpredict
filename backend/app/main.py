from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import check_database_connection
from app.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.models.chart_preference import ChartType, DogChartPreference  # noqa: F401
from app.models.scheduled_item import ScheduledItem  # noqa: F401
from app.models.treat_type import TreatType  # noqa: F401
from app.models.ui_preference import DogUIPreference  # noqa: F401
from app.routes.dashboard_preferences import router as dashboard_preferences_router
from app.routes.data_export import router as data_export_router
from app.routes.dog_event_preferences import router as preferences_router
from app.routes.dog_stat_preferences import router as stat_preferences_router
from app.routes.dogs import router as dogs_router
from app.routes.event_types import router as event_types_router
from app.routes.events import router as events_router
from app.routes.model_registry import router as model_registry_router
from app.routes.observation_periods import router as observation_periods_router
from app.routes.predictions import router as predictions_router
from app.routes.saved_options import router as saved_options_router
from app.routes.scheduled_items import router as scheduled_items_router
from app.routes.treat_types import router as treat_types_router

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=os.getenv("APP_ENV", "production"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
    )

app = FastAPI(
    title="PawPredict API",
    description="API for personalized canine routine tracking and predictions.",
    version="2.0.0",
)

origins = [
    value.strip()
    for value in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,https://pawpredict.vercel.app",
    ).split(",")
    if value.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Server-Timing"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)

app.include_router(dogs_router)
app.include_router(event_types_router)
app.include_router(events_router)
app.include_router(observation_periods_router)
app.include_router(saved_options_router)
app.include_router(preferences_router)
app.include_router(stat_preferences_router)
app.include_router(dashboard_preferences_router)
app.include_router(scheduled_items_router)
app.include_router(predictions_router)
app.include_router(model_registry_router)
app.include_router(data_export_router)
app.include_router(treat_types_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to the PawPredict API"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/health/database")
def database_health_check() -> dict[str, str]:
    try:
        check_database_connection()
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database connection failed.") from exc
