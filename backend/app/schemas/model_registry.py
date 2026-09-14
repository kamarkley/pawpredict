from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ModelEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_version_id: UUID
    evaluation_key: str
    evaluation_type: str
    window_start: datetime | None
    window_end: datetime | None
    snapshot_count: int | None
    positive_count: int | None
    prevalence: float | None
    pr_auc: float | None
    roc_auc: float | None
    brier_score: float | None
    ece: float | None
    calibration_intercept: float | None
    calibration_slope: float | None
    event_capture_rate: float | None
    alert_episodes_per_day: float | None
    episode_precision: float | None
    alert_threshold: float | None
    metrics_json: dict[str, Any]
    created_at: datetime


class ModelVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dog_id: UUID
    target: str
    version_label: str
    model_family: str
    status: str
    feature_names: list[str]
    training_window_days: int | None
    sample_weight_half_life_days: float | None
    calibration_method: str
    trained_through: datetime | None
    training_examples: int | None
    positive_examples: int | None
    prevalence: float | None
    git_commit: str | None
    artifact_uri: str | None
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TargetRegistrySummary(BaseModel):
    target: str
    production: ModelVersionResponse | None
    shadow: list[ModelVersionResponse]
    candidates: list[ModelVersionResponse]


class ModelRegistrySummaryResponse(BaseModel):
    dog_id: UUID
    targets: list[TargetRegistrySummary]
