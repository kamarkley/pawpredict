import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dog import Dog
from app.schemas.prediction import PottyModelReport, PottyPredictionResponse
from app.services.potty_prediction import get_training_bundle, model_report, predict_potty

router = APIRouter(prefix="/dogs", tags=["predictions"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/{dog_id}/predictions/potty", response_model=PottyPredictionResponse)
def potty_prediction(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    timezone_name: str = Query(default="UTC", alias="timezone"),
) -> PottyPredictionResponse:
    if db.get(Dog, dog_id) is None:
        raise HTTPException(status_code=404, detail="Dog not found.")
    try:
        bundle = get_training_bundle(db, dog_id, timezone_name, datetime.now(timezone.utc))
        return predict_potty(bundle, datetime.now(timezone.utc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{dog_id}/predictions/potty/report", response_model=PottyModelReport)
def potty_model_report(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    timezone_name: str = Query(default="UTC", alias="timezone"),
) -> PottyModelReport:
    if db.get(Dog, dog_id) is None:
        raise HTTPException(status_code=404, detail="Dog not found.")
    try:
        bundle = get_training_bundle(db, dog_id, timezone_name, datetime.now(timezone.utc))
        return model_report(bundle)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
