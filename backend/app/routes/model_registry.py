from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dog import Dog
from app.schemas.model_registry import (
    ModelEvaluationResponse,
    ModelRegistrySummaryResponse,
    ModelVersionResponse,
    TargetRegistrySummary,
)
from app.services.model_registry import (
    get_production_model,
    list_evaluations,
    list_models,
)

router = APIRouter(prefix="/dogs", tags=["model-registry"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/{dog_id}/models", response_model=list[ModelVersionResponse])
def dog_models(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    target: str | None = Query(default=None),
) -> list[ModelVersionResponse]:
    if db.get(Dog, dog_id) is None:
        raise HTTPException(status_code=404, detail="Dog not found.")
    return list_models(db, dog_id, target)


@router.get(
    "/{dog_id}/models/summary",
    response_model=ModelRegistrySummaryResponse,
)
def model_registry_summary(
    dog_id: uuid.UUID,
    db: DatabaseSession,
) -> ModelRegistrySummaryResponse:
    if db.get(Dog, dog_id) is None:
        raise HTTPException(status_code=404, detail="Dog not found.")

    versions = list_models(db, dog_id)
    targets: list[TargetRegistrySummary] = []

    for target in ("ANY", "PEE", "POOP"):
        target_versions = [version for version in versions if version.target == target]
        production = next(
            (version for version in target_versions if version.status == "PRODUCTION"),
            None,
        )
        targets.append(
            TargetRegistrySummary(
                target=target,
                production=production,
                shadow=[v for v in target_versions if v.status == "SHADOW"],
                candidates=[v for v in target_versions if v.status == "CANDIDATE"],
            )
        )

    return ModelRegistrySummaryResponse(dog_id=dog_id, targets=targets)


@router.get(
    "/{dog_id}/models/{model_version_id}/evaluations",
    response_model=list[ModelEvaluationResponse],
)
def model_evaluations(
    dog_id: uuid.UUID,
    model_version_id: uuid.UUID,
    db: DatabaseSession,
) -> list[ModelEvaluationResponse]:
    versions = list_models(db, dog_id)
    if not any(version.id == model_version_id for version in versions):
        raise HTTPException(status_code=404, detail="Model version not found.")
    return list_evaluations(db, model_version_id)
