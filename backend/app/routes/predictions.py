import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from app.schemas.prediction import PottyModelReport, PottyPredictionResponse
from app.services.potty_prediction import (
    get_training_bundle,
    model_report,
    predict_potty,
)
from app.services.prediction_ledger import run_prediction_telemetry
from app.security import CurrentUser, DatabaseSession, require_owned_dog

router = APIRouter(prefix="/dogs", tags=["predictions"])

@router.get(
    "/{dog_id}/predictions/potty",
    response_model=PottyPredictionResponse,
)
def potty_prediction(
    dog_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    user: CurrentUser,
    timezone_name: str = Query(default="UTC", alias="timezone"),
) -> PottyPredictionResponse:
    require_owned_dog(db, dog_id, user)

    now = datetime.now(timezone.utc)

    try:
        bundle = get_training_bundle(
            db,
            dog_id,
            timezone_name,
            now,
        )
        response = predict_potty(bundle, now)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    # The champion result is already computed. Model-ledger writes, outcome
    # resolution, and challenger scoring run after the HTTP response so shadow
    # work cannot add latency or break the user-facing prediction.
    background_tasks.add_task(
        run_prediction_telemetry,
        dog_id,
        timezone_name,
        now,
    )

    return response


@router.get(
    "/{dog_id}/predictions/potty/report",
    response_model=PottyModelReport,
)
def potty_model_report(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    user: CurrentUser,
    timezone_name: str = Query(default="UTC", alias="timezone"),
) -> PottyModelReport:
    require_owned_dog(db, dog_id, user)
    try:
        bundle = get_training_bundle(
            db,
            dog_id,
            timezone_name,
            datetime.now(timezone.utc),
        )
        return model_report(bundle)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
