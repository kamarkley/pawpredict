"""Champion/challenger prediction logging and delayed outcome resolution."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.model_prediction import ModelPrediction
from app.models.model_version import ModelVersion
from app.services.potty_prediction import (
    HORIZON_MINUTES,
    SNAPSHOT_STEP_MINUTES,
    TrainingBundle,
    _floor_to_step,
    current_model_probabilities,
    fit_registered_model,
    predict_fitted_target,
    runtime_config_from_version,
)

logger = logging.getLogger(__name__)

_SHADOW_MODEL_CACHE: dict[
    tuple[str, tuple[Any, ...]],
    Any,
] = {}


def _shadow_versions(
    db: Session,
    dog_id: uuid.UUID,
) -> list[ModelVersion]:
    return list(
        db.scalars(
            select(ModelVersion)
            .where(
                ModelVersion.dog_id == dog_id,
                ModelVersion.status == "SHADOW",
            )
            .order_by(
                ModelVersion.target.asc(),
                ModelVersion.created_at.asc(),
            )
        ).all()
    )


def _cached_shadow_model(
    bundle: TrainingBundle,
    version: ModelVersion,
):
    key = (str(version.id), bundle.fingerprint)
    cached = _SHADOW_MODEL_CACHE.get(key)
    if cached is not None:
        return cached

    config = runtime_config_from_version(
        version,
        version.target,
    )
    fitted = fit_registered_model(bundle, config)
    _SHADOW_MODEL_CACHE[key] = fitted

    # Prevent an unbounded cache if many versions are tested over time.
    if len(_SHADOW_MODEL_CACHE) > 100:
        oldest_key = next(iter(_SHADOW_MODEL_CACHE))
        _SHADOW_MODEL_CACHE.pop(oldest_key, None)

    return fitted


def _ledger_insert(
    db: Session,
    *,
    dog_id: uuid.UUID,
    model_version_id: uuid.UUID,
    target: str,
    role: str,
    prediction_time: datetime,
    probability: float,
    feature_snapshot: dict[str, float | None],
) -> None:
    bucket = _floor_to_step(
        prediction_time,
        SNAPSHOT_STEP_MINUTES,
    )
    horizon_end = prediction_time + timedelta(
        minutes=HORIZON_MINUTES,
    )

    statement = (
        insert(ModelPrediction)
        .values(
            id=uuid.uuid4(),
            dog_id=dog_id,
            model_version_id=model_version_id,
            target=target,
            role=role,
            prediction_time=prediction_time,
            prediction_bucket_time=bucket,
            horizon_end=horizon_end,
            probability=float(probability),
            feature_snapshot=feature_snapshot,
            outcome_status="PENDING",
            observed_outcome=None,
            outcome_resolved_at=None,
            ineligible_reason=None,
            created_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(
            constraint="model_predictions_unique_bucket"
        )
    )
    db.execute(statement)


def log_champion_and_shadow_predictions(
    db: Session,
    bundle: TrainingBundle,
    prediction_time: datetime,
) -> dict[str, int]:
    """
    Persist champion scores and silently score every SHADOW model.

    This function is intentionally safe to call after the user-facing champion
    prediction has already been computed. Callers should still wrap the whole
    ledger operation in try/except so logging can never fail the API response.
    """
    probabilities, row = current_model_probabilities(
        bundle,
        prediction_time,
    )

    champion_logged = 0
    shadow_logged = 0
    shadow_failed = 0

    # Champion rows.
    for target in ("ANY", "PEE", "POOP"):
        fitted = bundle.models[target]
        model_version_id = fitted.config.model_version_id

        # Legacy fallback predictions remain fully functional, but are not
        # written to the registry ledger because there is no version FK.
        if model_version_id is None:
            continue

        feature_snapshot = {
            name: row.get(name)
            for name in fitted.config.feature_names
        }
        _ledger_insert(
            db,
            dog_id=bundle.dog.id,
            model_version_id=model_version_id,
            target=target,
            role="CHAMPION",
            prediction_time=prediction_time,
            probability=probabilities[target],
            feature_snapshot=feature_snapshot,
        )
        champion_logged += 1

    # Shadow rows. Each challenger is isolated so one bad challenger does not
    # block the remaining challengers.
    try:
        shadow_versions = _shadow_versions(
            db,
            bundle.dog.id,
        )
    except Exception:
        logger.exception("Could not load shadow model registry rows.")
        return {
            "champion_logged": champion_logged,
            "shadow_logged": 0,
            "shadow_failed": 1,
        }

    for version in shadow_versions:
        try:
            fitted = _cached_shadow_model(
                bundle,
                version,
            )
            probability = predict_fitted_target(
                fitted,
                row,
            )
            feature_snapshot = {
                name: row.get(name)
                for name in fitted.config.feature_names
            }
            _ledger_insert(
                db,
                dog_id=bundle.dog.id,
                model_version_id=version.id,
                target=version.target,
                role="SHADOW",
                prediction_time=prediction_time,
                probability=probability,
                feature_snapshot=feature_snapshot,
            )
            shadow_logged += 1
        except Exception:
            shadow_failed += 1
            logger.exception(
                "Shadow model %s failed; champion response remains unaffected.",
                version.id,
            )

    return {
        "champion_logged": champion_logged,
        "shadow_logged": shadow_logged,
        "shadow_failed": shadow_failed,
    }


def resolve_pending_predictions(
    db: Session,
    bundle: TrainingBundle,
    now: datetime,
    *,
    limit: int = 500,
) -> dict[str, int]:
    """
    Resolve matured prediction outcomes.

    A prediction is INELIGIBLE when its 10-minute horizon overlaps:
    - an unobserved interval, or
    - logged sleep.

    Otherwise, the exact PEE/POOP events determine the target outcome.
    """
    pending = list(
        db.scalars(
            select(ModelPrediction)
            .where(
                ModelPrediction.dog_id == bundle.dog.id,
                ModelPrediction.outcome_status == "PENDING",
                ModelPrediction.horizon_end <= now,
            )
            .order_by(ModelPrediction.horizon_end.asc())
            .limit(limit)
        ).all()
    )

    resolved = 0
    ineligible = 0

    for prediction in pending:
        start = prediction.prediction_time
        end = prediction.horizon_end

        if bundle.context.overlaps_unobserved(start, end):
            prediction.outcome_status = "INELIGIBLE"
            prediction.observed_outcome = None
            prediction.outcome_resolved_at = now
            prediction.ineligible_reason = "UNOBSERVED_WINDOW"
            ineligible += 1
            continue

        if bundle.context.overlaps_sleep(start, end):
            prediction.outcome_status = "INELIGIBLE"
            prediction.observed_outcome = None
            prediction.outcome_resolved_at = now
            prediction.ineligible_reason = "SLEEP_WINDOW"
            ineligible += 1
            continue

        outcome = bool(
            bundle.context.target(
                start,
                prediction.target,
            )
        )
        prediction.outcome_status = "RESOLVED"
        prediction.observed_outcome = outcome
        prediction.outcome_resolved_at = now
        prediction.ineligible_reason = None
        resolved += 1

    db.flush()
    return {
        "pending_checked": len(pending),
        "resolved": resolved,
        "ineligible": ineligible,
    }



def run_prediction_telemetry(
    dog_id: uuid.UUID,
    timezone_name: str,
    prediction_time: datetime,
) -> None:
    """
    Out-of-response telemetry worker for FastAPI BackgroundTasks.

    It owns its database session, so the request can return the champion result
    immediately. Any shadow/model-ledger failure is logged and swallowed.
    """
    from app.services.potty_prediction import get_training_bundle

    try:
        with SessionLocal() as db:
            bundle = get_training_bundle(
                db,
                dog_id,
                timezone_name,
                prediction_time,
            )
            resolve_pending_predictions(
                db,
                bundle,
                prediction_time,
            )
            log_champion_and_shadow_predictions(
                db,
                bundle,
                prediction_time,
            )
            db.commit()
    except Exception:
        logger.exception(
            "Background prediction telemetry failed for dog %s; "
            "the champion API response was already unaffected.",
            dog_id,
        )
