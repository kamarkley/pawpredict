from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.model_evaluation import ModelEvaluation
from app.models.model_registry_event import ModelRegistryEvent
from app.models.model_version import ModelVersion


VALID_STATUSES = {"CANDIDATE", "SHADOW", "PRODUCTION", "RETIRED", "REJECTED"}
TARGETS = ("ANY", "PEE", "POOP")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_model_by_label(
    db: Session,
    dog_id: uuid.UUID,
    target: str,
    version_label: str,
) -> ModelVersion | None:
    return db.scalar(
        select(ModelVersion).where(
            ModelVersion.dog_id == dog_id,
            ModelVersion.target == target,
            ModelVersion.version_label == version_label,
        )
    )


def list_models(
    db: Session,
    dog_id: uuid.UUID,
    target: str | None = None,
) -> list[ModelVersion]:
    statement = (
        select(ModelVersion)
        .where(ModelVersion.dog_id == dog_id)
        .order_by(
            ModelVersion.target.asc(),
            ModelVersion.created_at.desc(),
        )
    )
    if target:
        statement = statement.where(ModelVersion.target == target)
    return list(db.scalars(statement).all())


def list_evaluations(
    db: Session,
    model_version_id: uuid.UUID,
) -> list[ModelEvaluation]:
    return list(
        db.scalars(
            select(ModelEvaluation)
            .where(ModelEvaluation.model_version_id == model_version_id)
            .order_by(ModelEvaluation.window_end.desc().nullslast(), ModelEvaluation.created_at.desc())
        ).all()
    )


def get_production_model(
    db: Session,
    dog_id: uuid.UUID,
    target: str,
) -> ModelVersion | None:
    return db.scalar(
        select(ModelVersion).where(
            ModelVersion.dog_id == dog_id,
            ModelVersion.target == target,
            ModelVersion.status == "PRODUCTION",
        )
    )


def upsert_model_version(
    db: Session,
    *,
    dog_id: uuid.UUID,
    target: str,
    version_label: str,
    model_family: str,
    status: str,
    feature_names: list[str],
    training_window_days: int | None,
    sample_weight_half_life_days: float | None,
    calibration_method: str,
    trained_through: datetime | None = None,
    training_examples: int | None = None,
    positive_examples: int | None = None,
    prevalence: float | None = None,
    git_commit: str | None = None,
    artifact_uri: str | None = None,
    config_json: dict[str, Any] | None = None,
    reason: str | None = None,
    actor: str = "system",
) -> ModelVersion:
    if target not in TARGETS:
        raise ValueError(f"Unsupported target: {target}")
    if status not in VALID_STATUSES:
        raise ValueError(f"Unsupported model status: {status}")

    existing = get_model_by_label(db, dog_id, target, version_label)
    created = existing is None

    if existing is None:
        existing = ModelVersion(
            id=uuid.uuid4(),
            dog_id=dog_id,
            target=target,
            version_label=version_label,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(existing)

    old_status = existing.status if not created else None

    existing.model_family = model_family
    existing.status = status
    existing.feature_names = list(feature_names)
    existing.training_window_days = training_window_days
    existing.sample_weight_half_life_days = sample_weight_half_life_days
    existing.calibration_method = calibration_method
    existing.trained_through = trained_through
    existing.training_examples = training_examples
    existing.positive_examples = positive_examples
    existing.prevalence = prevalence
    existing.git_commit = git_commit
    existing.artifact_uri = artifact_uri
    existing.config_json = dict(config_json or {})
    existing.updated_at = _now()

    db.flush()

    if created:
        db.add(
            ModelRegistryEvent(
                id=uuid.uuid4(),
                dog_id=dog_id,
                model_version_id=existing.id,
                target=target,
                event_type="REGISTERED",
                from_status=None,
                to_status=status,
                reason=reason,
                actor=actor,
                metadata_json={},
                created_at=_now(),
            )
        )
    elif old_status != status:
        db.add(
            ModelRegistryEvent(
                id=uuid.uuid4(),
                dog_id=dog_id,
                model_version_id=existing.id,
                target=target,
                event_type="STATUS_CHANGED",
                from_status=old_status,
                to_status=status,
                reason=reason,
                actor=actor,
                metadata_json={},
                created_at=_now(),
            )
        )

    return existing


def upsert_evaluation(
    db: Session,
    *,
    model_version_id: uuid.UUID,
    evaluation_key: str,
    evaluation_type: str,
    window_start: datetime | None,
    window_end: datetime | None,
    snapshot_count: int | None,
    positive_count: int | None,
    prevalence: float | None,
    pr_auc: float | None,
    roc_auc: float | None,
    brier_score: float | None,
    ece: float | None,
    calibration_intercept: float | None = None,
    calibration_slope: float | None = None,
    event_capture_rate: float | None = None,
    alert_episodes_per_day: float | None = None,
    episode_precision: float | None = None,
    alert_threshold: float | None = None,
    metrics_json: dict[str, Any] | None = None,
) -> ModelEvaluation:
    existing = db.scalar(
        select(ModelEvaluation).where(
            ModelEvaluation.model_version_id == model_version_id,
            ModelEvaluation.evaluation_key == evaluation_key,
        )
    )

    if existing is None:
        existing = ModelEvaluation(
            id=uuid.uuid4(),
            model_version_id=model_version_id,
            evaluation_key=evaluation_key,
            evaluation_type=evaluation_type,
            created_at=_now(),
        )
        db.add(existing)

    existing.evaluation_type = evaluation_type
    existing.window_start = window_start
    existing.window_end = window_end
    existing.snapshot_count = snapshot_count
    existing.positive_count = positive_count
    existing.prevalence = prevalence
    existing.pr_auc = pr_auc
    existing.roc_auc = roc_auc
    existing.brier_score = brier_score
    existing.ece = ece
    existing.calibration_intercept = calibration_intercept
    existing.calibration_slope = calibration_slope
    existing.event_capture_rate = event_capture_rate
    existing.alert_episodes_per_day = alert_episodes_per_day
    existing.episode_precision = episode_precision
    existing.alert_threshold = alert_threshold
    existing.metrics_json = dict(metrics_json or {})

    db.flush()
    return existing


def change_status(
    db: Session,
    model_version: ModelVersion,
    *,
    new_status: str,
    reason: str,
    actor: str = "system",
) -> ModelVersion:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Unsupported model status: {new_status}")

    old_status = model_version.status
    if old_status == new_status:
        return model_version

    model_version.status = new_status
    model_version.updated_at = _now()
    db.add(
        ModelRegistryEvent(
            id=uuid.uuid4(),
            dog_id=model_version.dog_id,
            model_version_id=model_version.id,
            target=model_version.target,
            event_type="STATUS_CHANGED",
            from_status=old_status,
            to_status=new_status,
            reason=reason,
            actor=actor,
            metadata_json={},
            created_at=_now(),
        )
    )
    db.flush()
    return model_version


def promote_to_production(
    db: Session,
    model_version: ModelVersion,
    *,
    reason: str,
    actor: str = "system",
) -> ModelVersion:
    """
    Transactional champion promotion.

    Retires the current champion for the same dog/target, promotes the selected
    version, and leaves an append-only decision trail.
    """
    current = get_production_model(db, model_version.dog_id, model_version.target)

    if current is not None and current.id != model_version.id:
        current.status = "RETIRED"
        current.updated_at = _now()
        db.add(
            ModelRegistryEvent(
                id=uuid.uuid4(),
                dog_id=current.dog_id,
                model_version_id=current.id,
                target=current.target,
                event_type="RETIRED_FOR_PROMOTION",
                from_status="PRODUCTION",
                to_status="RETIRED",
                reason=reason,
                actor=actor,
                metadata_json={"replacement_model_version_id": str(model_version.id)},
                created_at=_now(),
            )
        )

    previous_status = model_version.status
    model_version.status = "PRODUCTION"
    model_version.updated_at = _now()
    db.add(
        ModelRegistryEvent(
            id=uuid.uuid4(),
            dog_id=model_version.dog_id,
            model_version_id=model_version.id,
            target=model_version.target,
            event_type="PROMOTED",
            from_status=previous_status,
            to_status="PRODUCTION",
            reason=reason,
            actor=actor,
            metadata_json={
                "previous_production_model_version_id": str(current.id)
                if current is not None and current.id != model_version.id
                else None
            },
            created_at=_now(),
        )
    )

    db.flush()
    return model_version
