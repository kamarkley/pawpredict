from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from app.schemas.model_registry import (
    ModelEvaluationResponse,
    ModelRegistrySummaryResponse,
    ModelVersionResponse,
    TargetRegistrySummary,
)
from app.security import CurrentUser, DatabaseSession, require_owned_dog
from app.services.model_registry import list_evaluations, list_models

router = APIRouter(prefix="/dogs", tags=["model-registry"])


@router.get("/{dog_id}/models", response_model=list[ModelVersionResponse])
def dog_models(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    user: CurrentUser,
    target: str | None = Query(default=None),
) -> list[ModelVersionResponse]:
    require_owned_dog(db, dog_id, user)
    return list_models(db, dog_id, target)


@router.get(
    "/{dog_id}/models/summary",
    response_model=ModelRegistrySummaryResponse,
)
def model_registry_summary(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> ModelRegistrySummaryResponse:
    require_owned_dog(db, dog_id, user)
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
    user: CurrentUser,
) -> list[ModelEvaluationResponse]:
    require_owned_dog(db, dog_id, user)
    versions = list_models(db, dog_id)
    if not any(version.id == model_version_id for version in versions):
        raise HTTPException(status_code=404, detail="Model version not found.")
    return list_evaluations(db, model_version_id)
