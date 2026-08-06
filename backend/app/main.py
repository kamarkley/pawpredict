from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import check_database_connection
from app.routes.dogs import router as dogs_router
from app.routes.event_types import router as event_types_router
from app.routes.events import router as events_router
from app.routes.treat_types import router as treat_types_router

app = FastAPI(
    title="PawPredict API",
    description="API for tracking and predicting canine behavior.",
    version="0.1.0",
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
        return {
            "status": "healthy",
            "database": "connected",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed.",
        ) from exc