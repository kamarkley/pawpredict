from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import check_database_connection
from app.routes.dog_event_preferences import router as preferences_router
from app.routes.dogs import router as dogs_router
from app.routes.event_types import router as event_types_router
from app.routes.events import router as events_router
from app.routes.saved_options import router as saved_options_router

app = FastAPI(
    title="PawPredict API",
    description="API for configurable canine behavior tracking.",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(dogs_router)
app.include_router(event_types_router)
app.include_router(events_router)
app.include_router(saved_options_router)
app.include_router(preferences_router)


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
