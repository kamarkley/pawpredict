from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PredictionDriver(BaseModel):
    label: str
    direction: Literal["UP", "DOWN", "NEUTRAL"]
    detail: str


class ForecastPoint(BaseModel):
    minutes_ahead: int
    probability: float


class TargetModelMetrics(BaseModel):
    target: Literal["ANY", "PEE", "POOP"]
    fitted: bool
    training_examples: int
    positive_examples: int
    prevalence: float
    roc_auc: float | None = None
    pr_auc: float | None = None
    brier_score: float | None = None
    precision: float | None = None
    recall: float | None = None


class PottyModelReport(BaseModel):
    mode: Literal["TRAINED_MODEL", "EARLY_ESTIMATE"]
    confidence: Literal["EARLY", "GROWING", "STRONG"]
    confidence_label: str
    data_days: int
    exact_potty_events: int
    interval_potty_windows: int
    usable_training_examples: int
    observed_coverage_7d: float
    generated_at: datetime
    models: list[TargetModelMetrics]
    top_features: list[str]


class PottyPredictionResponse(BaseModel):
    generated_at: datetime
    horizon_minutes: int
    probability_any: float
    probability_pee: float
    probability_poop: float
    mode: Literal["TRAINED_MODEL", "EARLY_ESTIMATE"]
    confidence: Literal["EARLY", "GROWING", "STRONG"]
    confidence_label: str
    recommendation: str
    currently_sleeping: bool
    currently_unobserved: bool
    minutes_since_pee: float | None
    minutes_since_poop: float | None
    minutes_since_wake: float | None
    data_days: int
    training_examples: int
    exact_potty_events: int
    drivers: list[PredictionDriver]
    forecast: list[ForecastPoint]
