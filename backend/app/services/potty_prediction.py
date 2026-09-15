"""Registry-driven personalized potty-risk modeling for PawPredict.

Production behavior
-------------------
Each target (ANY / PEE / POOP) loads its PRODUCTION model configuration from
the model registry. The registry controls feature selection, history window,
sample weighting, and calibration. If a registry row is missing or malformed,
PawPredict falls back to the known-safe legacy V1 configuration.

The user-facing prediction path remains synchronous and independent of shadow
challengers. Shadow scoring lives in prediction_ledger.py and failures there
must never prevent a champion response.
"""
from __future__ import annotations

import math
import uuid
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dog import Dog
from app.models.event import Event
from app.models.event_type import EventType
from app.models.model_version import ModelVersion
from app.models.observation_period import ObservationPeriod
from app.models.saved_option import SavedOption
from app.schemas.prediction import (
    ForecastPoint,
    PottyModelReport,
    PottyPredictionResponse,
    PredictionDriver,
    TargetModelMetrics,
)
from app.services.model_registry import get_production_model

HORIZON_MINUTES = 10
SNAPSHOT_STEP_MINUTES = 5
MAX_HISTORY_DAYS = 60
MIN_TRAINING_EXAMPLES = 120
MIN_POSITIVE_EXAMPLES = 20

FEATURE_NAMES = [
    "minutes_since_pee",
    "minutes_since_poop",
    "minutes_since_potty_attempt",
    "minutes_since_wake",
    "pee_count_today",
    "poop_count_today",
    "recent_treat_30m",
    "recent_zoomies_30m",
    "recent_potty_attempt_30m",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
    "age_days",
]

FEATURE_LABELS = {
    "minutes_since_pee": "Time since last pee",
    "minutes_since_poop": "Time since last poop",
    "minutes_since_potty_attempt": "Time since potty attempt",
    "minutes_since_wake": "Time since waking",
    "pee_count_today": "Pees already today",
    "poop_count_today": "Poops already today",
    "recent_treat_30m": "Recent treat",
    "recent_zoomies_30m": "Recent zoomies",
    "recent_potty_attempt_30m": "Recent potty attempt",
    "hour_sin": "Time of day",
    "hour_cos": "Time of day",
    "weekday_sin": "Day-of-week pattern",
    "weekday_cos": "Day-of-week pattern",
    "age_days": "Age",
}

TargetName = Literal["ANY", "PEE", "POOP"]

_BUNDLE_CACHE: dict[
    tuple[str, str],
    tuple[tuple[Any, ...], "TrainingBundle"],
] = {}


@dataclass(frozen=True)
class EventRecord:
    event_time: datetime
    code: str
    state: str | None
    option_name: str | None


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class RuntimeModelConfig:
    target: TargetName
    model_version_id: uuid.UUID | None
    version_label: str
    model_family: str
    feature_names: tuple[str, ...]
    training_window_days: int
    sample_weight_half_life_days: float | None
    calibration_method: str
    status: str
    source: Literal["REGISTRY", "LEGACY_FALLBACK"]


@dataclass
class FittedTarget:
    target: TargetName
    fitted: bool
    pipeline: Pipeline | None
    calibrator: Any | None
    metrics: TargetModelMetrics
    config: RuntimeModelConfig
    training_rows: list[dict[str, float | None]]
    training_y: np.ndarray


@dataclass
class TrainingBundle:
    dog: Dog
    timezone: ZoneInfo
    context: "FeatureContext"
    feature_rows: list[dict[str, float | None]]
    snapshot_times: np.ndarray
    matrix: np.ndarray
    targets: dict[TargetName, np.ndarray]
    models: dict[TargetName, FittedTarget]
    generated_at: datetime
    data_days: int
    exact_potty_events: int
    interval_potty_windows: int
    observed_coverage_7d: float
    fingerprint: tuple[Any, ...]


class FeatureContext:
    def __init__(
        self,
        events: list[EventRecord],
        observations: list[ObservationPeriod],
        dog_birth_date: date,
        local_timezone: ZoneInfo,
        now: datetime,
    ) -> None:
        self.events = sorted(events, key=lambda event: event.event_time)
        self.birth_date = dog_birth_date
        self.local_timezone = local_timezone
        self.now = now
        self.times_by_code: dict[str, list[datetime]] = {}
        for event in self.events:
            self.times_by_code.setdefault(event.code, []).append(event.event_time)

        self.wake_times = sorted(
            event.event_time
            for event in self.events
            if event.code in {"SLEEP", "SLEEP_NIGHT"} and event.state == "END"
        )
        self.sleep_intervals = self._build_sleep_intervals()
        self.unobserved_intervals = [
            Interval(period.start_time, period.end_time or (now + timedelta(days=2)))
            for period in observations
            if period.start_time < now
        ]
        self.observations = observations

    def _build_sleep_intervals(self) -> list[Interval]:
        intervals: list[Interval] = []
        for code in ("SLEEP", "SLEEP_NIGHT"):
            open_start: datetime | None = None
            for event in (item for item in self.events if item.code == code and item.state):
                if event.state == "START":
                    if open_start is not None and event.event_time > open_start:
                        intervals.append(Interval(open_start, event.event_time))
                    open_start = event.event_time
                elif event.state == "END" and open_start is not None:
                    if event.event_time > open_start:
                        intervals.append(Interval(open_start, event.event_time))
                    open_start = None
            if open_start is not None:
                intervals.append(Interval(open_start, self.now + timedelta(days=2)))
        return sorted(intervals, key=lambda interval: interval.start)

    @staticmethod
    def _last_at_or_before(times: list[datetime], at: datetime) -> datetime | None:
        index = bisect_right(times, at) - 1
        return times[index] if index >= 0 else None

    @staticmethod
    def _count_between(times: list[datetime], start: datetime, end: datetime) -> int:
        return max(0, bisect_right(times, end) - bisect_left(times, start))

    @staticmethod
    def _has_between(times: list[datetime], start: datetime, end: datetime) -> bool:
        index = bisect_left(times, start)
        return index < len(times) and times[index] <= end

    @staticmethod
    def _overlaps(intervals: list[Interval], start: datetime, end: datetime) -> bool:
        return any(interval.start < end and interval.end > start for interval in intervals)

    def overlaps_unobserved(self, start: datetime, end: datetime) -> bool:
        return self._overlaps(self.unobserved_intervals, start, end)

    def overlaps_sleep(self, start: datetime, end: datetime) -> bool:
        return self._overlaps(self.sleep_intervals, start, end)

    def is_sleeping(self, at: datetime) -> bool:
        return self._overlaps(self.sleep_intervals, at, at + timedelta(seconds=1))

    def is_unobserved(self, at: datetime) -> bool:
        return self._overlaps(self.unobserved_intervals, at, at + timedelta(seconds=1))

    def minutes_since(self, code: str, at: datetime) -> float | None:
        latest = self._last_at_or_before(self.times_by_code.get(code, []), at)
        if latest is None:
            return None
        return max(0.0, (at - latest).total_seconds() / 60.0)

    def minutes_since_wake(self, at: datetime) -> float | None:
        latest = self._last_at_or_before(self.wake_times, at)
        if latest is None:
            return None
        return max(0.0, (at - latest).total_seconds() / 60.0)

    def local_day_start_utc(self, at: datetime) -> datetime:
        local = at.astimezone(self.local_timezone)
        local_start = datetime.combine(local.date(), time.min, tzinfo=self.local_timezone)
        return local_start.astimezone(timezone.utc)

    def feature_row(self, at: datetime) -> dict[str, float | None]:
        local = at.astimezone(self.local_timezone)
        hour = local.hour + local.minute / 60.0
        hour_angle = 2.0 * math.pi * hour / 24.0
        weekday_angle = 2.0 * math.pi * local.weekday() / 7.0
        day_start = self.local_day_start_utc(at)

        pee_times = self.times_by_code.get("PEE", [])
        poop_times = self.times_by_code.get("POOP", [])
        attempt_times = self.times_by_code.get("POTTY_ATTEMPT", [])
        treat_times = self.times_by_code.get("TREAT", [])
        zoomies_times = self.times_by_code.get("ZOOMIES", [])

        recent_start = at - timedelta(minutes=30)
        return {
            "minutes_since_pee": self.minutes_since("PEE", at),
            "minutes_since_poop": self.minutes_since("POOP", at),
            "minutes_since_potty_attempt": self.minutes_since("POTTY_ATTEMPT", at),
            "minutes_since_wake": self.minutes_since_wake(at),
            "pee_count_today": float(self._count_between(pee_times, day_start, at)),
            "poop_count_today": float(self._count_between(poop_times, day_start, at)),
            "recent_treat_30m": float(self._has_between(treat_times, recent_start, at)),
            "recent_zoomies_30m": float(self._has_between(zoomies_times, recent_start, at)),
            "recent_potty_attempt_30m": float(self._has_between(attempt_times, recent_start, at)),
            "hour_sin": math.sin(hour_angle),
            "hour_cos": math.cos(hour_angle),
            "weekday_sin": math.sin(weekday_angle),
            "weekday_cos": math.cos(weekday_angle),
            "age_days": float((local.date() - self.birth_date).days),
        }

    def target(self, at: datetime, target: TargetName) -> int:
        end = at + timedelta(minutes=HORIZON_MINUTES)
        if target == "PEE":
            times = self.times_by_code.get("PEE", [])
        elif target == "POOP":
            times = self.times_by_code.get("POOP", [])
        else:
            times = sorted(
                self.times_by_code.get("PEE", []) + self.times_by_code.get("POOP", [])
            )
        index = bisect_right(times, at)
        return int(index < len(times) and times[index] <= end)


def _safe_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _matrix(
    rows: list[dict[str, float | None]],
    feature_names: tuple[str, ...] | list[str] = FEATURE_NAMES,
) -> np.ndarray:
    if not rows:
        return np.empty((0, len(feature_names)), dtype=float)
    return np.array(
        [
            [
                np.nan if row[name] is None else float(row[name])
                for name in feature_names
            ]
            for row in rows
        ],
        dtype=float,
    )


def _round_probability(value: float) -> float:
    return round(max(0.01, min(0.99, float(value))), 4)


def _metric_or_none(value: float | None) -> float | None:
    return None if value is None or not math.isfinite(value) else round(float(value), 4)


def _legacy_config(target: TargetName) -> RuntimeModelConfig:
    return RuntimeModelConfig(
        target=target,
        model_version_id=None,
        version_label=f"legacy-v1-{target.lower()}",
        model_family="logistic_regression",
        feature_names=tuple(FEATURE_NAMES),
        training_window_days=MAX_HISTORY_DAYS,
        sample_weight_half_life_days=None,
        calibration_method="raw",
        status="PRODUCTION",
        source="LEGACY_FALLBACK",
    )


def _validate_registry_version(
    version: ModelVersion,
    target: TargetName,
) -> RuntimeModelConfig:
    if version.target != target:
        raise ValueError("Registry target mismatch.")
    if version.model_family != "logistic_regression":
        raise ValueError(f"Unsupported model family: {version.model_family}")
    if not version.feature_names:
        raise ValueError("Registered model has no features.")

    unknown = sorted(set(version.feature_names) - set(FEATURE_NAMES))
    if unknown:
        raise ValueError(f"Unknown registered features: {', '.join(unknown)}")

    window = version.training_window_days or MAX_HISTORY_DAYS
    if window < 1 or window > MAX_HISTORY_DAYS:
        raise ValueError(
            f"training_window_days must be between 1 and {MAX_HISTORY_DAYS}"
        )

    if version.calibration_method not in {"raw", "sigmoid", "isotonic"}:
        raise ValueError(
            f"Unsupported calibration method: {version.calibration_method}"
        )

    half_life = version.sample_weight_half_life_days
    if half_life is not None and half_life <= 0:
        raise ValueError("sample_weight_half_life_days must be positive.")

    return RuntimeModelConfig(
        target=target,
        model_version_id=version.id,
        version_label=version.version_label,
        model_family=version.model_family,
        feature_names=tuple(version.feature_names),
        training_window_days=int(window),
        sample_weight_half_life_days=float(half_life) if half_life is not None else None,
        calibration_method=version.calibration_method,
        status=version.status,
        source="REGISTRY",
    )


def resolve_production_config(
    db: Session,
    dog_id: uuid.UUID,
    target: TargetName,
) -> RuntimeModelConfig:
    """
    Read the champion from the registry.

    Missing/malformed rows fall back to the known V1 recipe. A registry query
    error is isolated with rollback so prediction can continue.
    """
    try:
        version = get_production_model(db, dog_id, target)
    except Exception:
        db.rollback()
        return _legacy_config(target)

    if version is None:
        return _legacy_config(target)

    try:
        return _validate_registry_version(version, target)
    except (TypeError, ValueError):
        return _legacy_config(target)


def runtime_config_from_version(
    version: ModelVersion,
    target: TargetName,
) -> RuntimeModelConfig:
    return _validate_registry_version(version, target)


def _make_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, random_state=42)),
        ]
    )


def _sample_weights(
    times: np.ndarray,
    half_life_days: float | None,
) -> np.ndarray | None:
    if half_life_days is None or len(times) == 0:
        return None
    latest = times[-1]
    ages = np.array(
        [
            max(0.0, (latest - timestamp).total_seconds() / 86400.0)
            for timestamp in times
        ],
        dtype=float,
    )
    return np.exp(-math.log(2.0) * ages / half_life_days)


def _fit_pipeline(
    x: np.ndarray,
    y: np.ndarray,
    times: np.ndarray,
    half_life_days: float | None,
) -> Pipeline:
    pipeline = _make_pipeline()
    weights = _sample_weights(times, half_life_days)
    if weights is None:
        pipeline.fit(x, y)
    else:
        pipeline.fit(x, y, model__sample_weight=weights)
    return pipeline


def _apply_calibrator(calibrator: Any | None, probabilities: np.ndarray) -> np.ndarray:
    if calibrator is None:
        return probabilities

    if isinstance(calibrator, LogisticRegression):
        eps = 1e-6
        clipped = np.clip(probabilities, eps, 1 - eps)
        logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
        return calibrator.predict_proba(logits)[:, 1]

    if isinstance(calibrator, IsotonicRegression):
        return np.asarray(calibrator.predict(probabilities), dtype=float)

    return probabilities


def _fit_calibrator(
    method: str,
    raw_probability: np.ndarray,
    y: np.ndarray,
) -> Any | None:
    if method == "raw" or len(np.unique(y)) < 2:
        return None

    if method == "sigmoid":
        eps = 1e-6
        clipped = np.clip(raw_probability, eps, 1 - eps)
        logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
        calibrator = LogisticRegression(max_iter=2000, random_state=42)
        calibrator.fit(logits, y)
        return calibrator

    if method == "isotonic":
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(raw_probability, y)
        return calibrator

    return None


def _fit_target(
    config: RuntimeModelConfig,
    rows: list[dict[str, float | None]],
    times: np.ndarray,
    y: np.ndarray,
) -> FittedTarget:
    target = config.target
    positives = int(y.sum())
    total = int(len(y))
    prevalence = float(positives / total) if total else 0.0
    enough = (
        total >= MIN_TRAINING_EXAMPLES
        and positives >= MIN_POSITIVE_EXAMPLES
        and (total - positives) >= MIN_POSITIVE_EXAMPLES
    )

    if not enough:
        metrics = TargetModelMetrics(
            target=target,
            fitted=False,
            training_examples=total,
            positive_examples=positives,
            prevalence=round(prevalence, 4),
        )
        return FittedTarget(
            target=target,
            fitted=False,
            pipeline=None,
            calibrator=None,
            metrics=metrics,
            config=config,
            training_rows=rows,
            training_y=y,
        )

    x = _matrix(rows, config.feature_names)

    roc_auc: float | None = None
    pr_auc: float | None = None
    brier: float | None = None
    precision: float | None = None
    recall: float | None = None

    # Honest chronological evaluation. Calibrated models use 60/20/20;
    # raw models preserve the legacy 80/20 evaluation.
    if config.calibration_method == "raw":
        split = max(1, min(total - 1, int(total * 0.8)))
        x_train, x_test = x[:split], x[split:]
        y_train, y_test = y[:split], y[split:]
        t_train = times[:split]

        if len(np.unique(y_train)) >= 2:
            eval_pipeline = _fit_pipeline(
                x_train,
                y_train,
                t_train,
                config.sample_weight_half_life_days,
            )
            test_probability = eval_pipeline.predict_proba(x_test)[:, 1]
        else:
            test_probability = np.array([], dtype=float)
    else:
        train_end = max(1, min(total - 2, int(total * 0.6)))
        cal_end = max(train_end + 1, min(total - 1, int(total * 0.8)))

        x_train, y_train, t_train = (
            x[:train_end],
            y[:train_end],
            times[:train_end],
        )
        x_cal, y_cal = x[train_end:cal_end], y[train_end:cal_end]
        x_test, y_test = x[cal_end:], y[cal_end:]

        if len(np.unique(y_train)) >= 2 and len(np.unique(y_cal)) >= 2:
            eval_pipeline = _fit_pipeline(
                x_train,
                y_train,
                t_train,
                config.sample_weight_half_life_days,
            )
            cal_raw = eval_pipeline.predict_proba(x_cal)[:, 1]
            eval_calibrator = _fit_calibrator(
                config.calibration_method,
                cal_raw,
                y_cal,
            )
            test_raw = eval_pipeline.predict_proba(x_test)[:, 1]
            test_probability = _apply_calibrator(eval_calibrator, test_raw)
        else:
            test_probability = np.array([], dtype=float)

    if len(test_probability) and len(y_test):
        test_prediction = (test_probability >= 0.5).astype(int)
        if len(np.unique(y_test)) > 1:
            roc_auc = float(roc_auc_score(y_test, test_probability))
            pr_auc = float(average_precision_score(y_test, test_probability))
            brier = float(brier_score_loss(y_test, test_probability))
        precision = float(
            precision_score(y_test, test_prediction, zero_division=0)
        )
        recall = float(
            recall_score(y_test, test_prediction, zero_division=0)
        )

    # Final inference model.
    final_calibrator: Any | None = None
    if config.calibration_method == "raw":
        final_pipeline = _fit_pipeline(
            x,
            y,
            times,
            config.sample_weight_half_life_days,
        )
    else:
        base_end = max(1, min(total - 1, int(total * 0.8)))
        x_base, y_base, t_base = x[:base_end], y[:base_end], times[:base_end]
        x_cal, y_cal = x[base_end:], y[base_end:]

        if len(np.unique(y_base)) < 2 or len(np.unique(y_cal)) < 2:
            final_pipeline = _fit_pipeline(
                x,
                y,
                times,
                config.sample_weight_half_life_days,
            )
        else:
            final_pipeline = _fit_pipeline(
                x_base,
                y_base,
                t_base,
                config.sample_weight_half_life_days,
            )
            raw_cal = final_pipeline.predict_proba(x_cal)[:, 1]
            final_calibrator = _fit_calibrator(
                config.calibration_method,
                raw_cal,
                y_cal,
            )

    metrics = TargetModelMetrics(
        target=target,
        fitted=True,
        training_examples=total,
        positive_examples=positives,
        prevalence=round(prevalence, 4),
        roc_auc=_metric_or_none(roc_auc),
        pr_auc=_metric_or_none(pr_auc),
        brier_score=_metric_or_none(brier),
        precision=_metric_or_none(precision),
        recall=_metric_or_none(recall),
    )
    return FittedTarget(
        target=target,
        fitted=True,
        pipeline=final_pipeline,
        calibrator=final_calibrator,
        metrics=metrics,
        config=config,
        training_rows=rows,
        training_y=y,
    )


def fit_registered_model(
    bundle: TrainingBundle,
    config: RuntimeModelConfig,
) -> FittedTarget:
    cutoff = bundle.generated_at - timedelta(days=config.training_window_days)
    mask = np.array(
        [timestamp >= cutoff for timestamp in bundle.snapshot_times],
        dtype=bool,
    )
    rows = [
        row
        for row, keep in zip(bundle.feature_rows, mask)
        if bool(keep)
    ]
    times = bundle.snapshot_times[mask]
    y = bundle.targets[config.target][mask]
    return _fit_target(config, rows, times, y)


def _bucket_minutes(value: float | None) -> str:
    if value is None:
        return "missing"
    if value < 30:
        return "0-30"
    if value < 60:
        return "30-60"
    if value < 90:
        return "60-90"
    if value < 120:
        return "90-120"
    return "120+"


def _empirical_probability(
    rows: list[dict[str, float | None]],
    y: np.ndarray,
    current: dict[str, float | None],
) -> float:
    total = len(rows)
    if not total:
        return 0.1
    base = float(y.mean())

    current_hour = math.atan2(
        current["hour_sin"] or 0.0,
        current["hour_cos"] or 1.0,
    )
    current_pee_bucket = _bucket_minutes(current["minutes_since_pee"])
    current_wake_bucket = _bucket_minutes(current["minutes_since_wake"])

    groups: list[tuple[float, int, float]] = [(base, total, 1.0)]

    hour_indexes: list[int] = []
    pee_indexes: list[int] = []
    wake_indexes: list[int] = []
    for index, row in enumerate(rows):
        angle = math.atan2(
            row["hour_sin"] or 0.0,
            row["hour_cos"] or 1.0,
        )
        distance = abs(
            (angle - current_hour + math.pi) % (2 * math.pi) - math.pi
        )
        if distance <= math.pi / 6:
            hour_indexes.append(index)
        if _bucket_minutes(row["minutes_since_pee"]) == current_pee_bucket:
            pee_indexes.append(index)
        if _bucket_minutes(row["minutes_since_wake"]) == current_wake_bucket:
            wake_indexes.append(index)

    for indexes, weight in (
        (hour_indexes, 1.4),
        (pee_indexes, 1.6),
        (wake_indexes, 1.2),
    ):
        if len(indexes) >= 12:
            positives = float(y[indexes].sum())
            smoothed = (positives + base * 20.0) / (len(indexes) + 20.0)
            groups.append((smoothed, len(indexes), weight))

    numerator = sum(probability * weight for probability, _, weight in groups)
    denominator = sum(weight for _, _, weight in groups)
    return _round_probability(numerator / denominator)


def predict_fitted_target(
    fitted: FittedTarget,
    row: dict[str, float | None],
) -> float:
    if fitted.fitted and fitted.pipeline is not None:
        matrix = _matrix([row], fitted.config.feature_names)
        raw = fitted.pipeline.predict_proba(matrix)[:, 1]
        probability = _apply_calibrator(fitted.calibrator, raw)[0]
        return _round_probability(float(probability))

    return _empirical_probability(
        fitted.training_rows,
        fitted.training_y,
        row,
    )


def _format_minutes(value: float | None) -> str:
    if value is None:
        return "not enough prior logs"
    rounded = int(round(value))
    if rounded < 60:
        return f"{rounded} min"
    hours, minutes = divmod(rounded, 60)
    return f"{hours} hr {minutes} min" if minutes else f"{hours} hr"


def _prediction_drivers(
    bundle: TrainingBundle,
    row: dict[str, float | None],
) -> list[PredictionDriver]:
    fitted = bundle.models["ANY"]
    if not fitted.fitted or fitted.pipeline is None:
        candidates = [
            (
                "Time since last pee",
                row["minutes_since_pee"],
                "since the latest exact pee log",
            ),
            (
                "Time since last poop",
                row["minutes_since_poop"],
                "since the latest exact poop log",
            ),
            (
                "Time since waking",
                row["minutes_since_wake"],
                "since the latest logged wake-up",
            ),
        ]
        return [
            PredictionDriver(
                label=label,
                direction="NEUTRAL",
                detail=f"{_format_minutes(value)} {suffix}",
            )
            for label, value, suffix in candidates
            if value is not None
        ][:3]

    matrix = _matrix([row], fitted.config.feature_names)
    imputer: SimpleImputer = fitted.pipeline.named_steps["impute"]
    scaler: StandardScaler = fitted.pipeline.named_steps["scale"]
    model: LogisticRegression = fitted.pipeline.named_steps["model"]
    transformed = scaler.transform(imputer.transform(matrix))[0]
    contributions = transformed * model.coef_[0]

    ranked: list[tuple[float, str]] = []
    seen_labels: set[str] = set()
    for index in np.argsort(np.abs(contributions))[::-1]:
        name = fitted.config.feature_names[int(index)]
        label = FEATURE_LABELS[name]
        if label in seen_labels:
            continue
        seen_labels.add(label)
        ranked.append((float(contributions[index]), name))
        if len(ranked) >= 4:
            break

    drivers: list[PredictionDriver] = []
    for contribution, name in ranked:
        raw = row[name]
        if name.startswith("minutes_since"):
            detail_value = _format_minutes(raw)
        elif name in {"pee_count_today", "poop_count_today"}:
            detail_value = str(int(raw or 0))
        elif name.startswith("recent_"):
            detail_value = "yes" if raw else "no"
        elif name in {"hour_sin", "hour_cos"}:
            detail_value = "current time-of-day pattern"
        elif name in {"weekday_sin", "weekday_cos"}:
            detail_value = "today's weekday pattern"
        elif name == "age_days":
            detail_value = f"{int(raw or 0)} days old"
        else:
            detail_value = str(raw)

        drivers.append(
            PredictionDriver(
                label=FEATURE_LABELS[name],
                direction=(
                    "UP"
                    if contribution > 0.03
                    else "DOWN"
                    if contribution < -0.03
                    else "NEUTRAL"
                ),
                detail=detail_value,
            )
        )
    return drivers


def _confidence(
    bundle: TrainingBundle,
) -> tuple[Literal["EARLY", "GROWING", "STRONG"], str]:
    any_metrics = bundle.models["ANY"].metrics
    if not any_metrics.fitted:
        return (
            "EARLY",
            "Early estimate — more clean observed data will unlock the fitted model",
        )

    if (
        any_metrics.positive_examples >= 80
        and any_metrics.training_examples >= 600
        and bundle.data_days >= 14
        and (any_metrics.pr_auc or 0.0)
        >= max(0.25, any_metrics.prevalence * 1.35)
    ):
        return (
            "STRONG",
            "Strong personalized signal from the available tracking history",
        )
    return (
        "GROWING",
        "Personalized model is active and will keep improving with new logs",
    )


def _recommendation(
    probability: float,
    sleeping: bool,
    unobserved: bool,
) -> str:
    if sleeping:
        return (
            "Sleep is currently logged, so PawPredict pauses the take-out "
            "recommendation until wake-up."
        )
    if unobserved:
        return (
            "This is an unobserved window, so treat the current risk as a rough "
            "estimate rather than an exact take-out cue."
        )
    if probability >= 0.65:
        return "High chance — a potty break now is a good idea."
    if probability >= 0.4:
        return (
            "Risk is rising — consider a potty break in the next 5–10 minutes."
        )
    return (
        "Lower chance right now — keep logging and PawPredict will update as "
        "the routine changes."
    )


def _observation_coverage(
    observations: list[ObservationPeriod],
    now: datetime,
    days: int = 7,
) -> float:
    start = now - timedelta(days=days)
    minutes = days * 24 * 60
    unobserved = 0.0
    for period in observations:
        period_end = period.end_time or now
        overlap_start = max(start, period.start_time)
        overlap_end = min(now, period_end)
        if overlap_end > overlap_start:
            unobserved += (
                overlap_end - overlap_start
            ).total_seconds() / 60.0
    return round(
        max(0.0, min(1.0, 1.0 - unobserved / minutes)),
        4,
    )


def _load_records(
    db: Session,
    dog: Dog,
    now: datetime,
) -> tuple[list[EventRecord], list[ObservationPeriod]]:
    query_start = now - timedelta(days=MAX_HISTORY_DAYS + 2)
    rows = db.execute(
        select(Event, EventType, SavedOption)
        .join(EventType, Event.event_type_id == EventType.id)
        .outerjoin(SavedOption, Event.option_id == SavedOption.id)
        .where(
            Event.dog_id == dog.id,
            Event.event_time >= query_start,
            Event.event_time <= now,
        )
        .order_by(Event.event_time.asc())
    ).all()

    events = [
        EventRecord(
            event_time=event.event_time,
            code=event_type.code,
            state=event.state,
            option_name=option.name if option else None,
        )
        for event, event_type, option in rows
    ]

    observations = list(
        db.scalars(
            select(ObservationPeriod)
            .where(
                ObservationPeriod.dog_id == dog.id,
                ObservationPeriod.start_time <= now,
                (
                    ObservationPeriod.end_time.is_(None)
                    | (ObservationPeriod.end_time >= query_start)
                ),
            )
            .order_by(ObservationPeriod.start_time.asc())
        ).all()
    )
    return events, observations


def _floor_to_step(value: datetime, minutes: int) -> datetime:
    discard = timedelta(
        minutes=value.minute % minutes,
        seconds=value.second,
        microseconds=value.microsecond,
    )
    return value - discard


def _data_fingerprint(
    db: Session,
    dog_id: uuid.UUID,
) -> tuple[Any, ...]:
    event_count, event_updated = db.execute(
        select(func.count(Event.id), func.max(Event.updated_at)).where(
            Event.dog_id == dog_id
        )
    ).one()

    observation_count, observation_updated = db.execute(
        select(
            func.count(ObservationPeriod.id),
            func.max(ObservationPeriod.updated_at),
        ).where(ObservationPeriod.dog_id == dog_id)
    ).one()

    try:
        registry_count, registry_updated = db.execute(
            select(
                func.count(ModelVersion.id),
                func.max(ModelVersion.updated_at),
            ).where(ModelVersion.dog_id == dog_id)
        ).one()
    except Exception:
        db.rollback()
        registry_count, registry_updated = 0, None

    return (
        int(event_count or 0),
        event_updated.isoformat() if event_updated else "",
        int(observation_count or 0),
        observation_updated.isoformat() if observation_updated else "",
        int(registry_count or 0),
        registry_updated.isoformat() if registry_updated else "",
    )


def build_training_bundle(
    db: Session,
    dog_id: uuid.UUID,
    timezone_name: str,
    now: datetime | None = None,
) -> TrainingBundle:
    current_time = now or datetime.now(timezone.utc)
    dog = db.get(Dog, dog_id)
    if dog is None:
        raise ValueError("Dog not found.")

    local_timezone = _safe_timezone(timezone_name)
    events, observations = _load_records(db, dog, current_time)
    context = FeatureContext(
        events,
        observations,
        dog.birth_date,
        local_timezone,
        current_time,
    )

    exact_potty_events = sum(
        event.code in {"PEE", "POOP"}
        for event in events
    )
    interval_potty_windows = sum(
        bool(period.peed_during or period.pooped_during)
        for period in observations
    )

    if events:
        earliest = min(event.event_time for event in events)
        training_start = max(
            earliest,
            current_time - timedelta(days=MAX_HISTORY_DAYS),
        )
        data_days = max(
            1,
            (
                current_time.astimezone(local_timezone).date()
                - earliest.astimezone(local_timezone).date()
            ).days
            + 1,
        )
    else:
        training_start = current_time - timedelta(days=1)
        data_days = 0

    feature_rows: list[dict[str, float | None]] = []
    snapshot_times: list[datetime] = []
    target_values: dict[TargetName, list[int]] = {
        "ANY": [],
        "PEE": [],
        "POOP": [],
    }

    at = (
        _floor_to_step(training_start, SNAPSHOT_STEP_MINUTES)
        + timedelta(minutes=SNAPSHOT_STEP_MINUTES)
    )
    end = current_time - timedelta(minutes=HORIZON_MINUTES)

    while at <= end:
        horizon_end = at + timedelta(minutes=HORIZON_MINUTES)
        if (
            not context.overlaps_unobserved(at, horizon_end)
            and not context.overlaps_sleep(at, horizon_end)
        ):
            snapshot_times.append(at)
            feature_rows.append(context.feature_row(at))
            for target in ("ANY", "PEE", "POOP"):
                target_values[target].append(
                    context.target(at, target)
                )
        at += timedelta(minutes=SNAPSHOT_STEP_MINUTES)

    matrix = _matrix(feature_rows)
    targets: dict[TargetName, np.ndarray] = {
        target: np.asarray(values, dtype=int)
        for target, values in target_values.items()
    }
    times_array = np.asarray(snapshot_times, dtype=object)

    configs = {
        target: resolve_production_config(db, dog_id, target)
        for target in ("ANY", "PEE", "POOP")
    }

    models: dict[TargetName, FittedTarget] = {}
    for target in ("ANY", "PEE", "POOP"):
        config = configs[target]
        cutoff = current_time - timedelta(
            days=config.training_window_days
        )
        mask = np.array(
            [timestamp >= cutoff for timestamp in times_array],
            dtype=bool,
        )
        target_rows = [
            row
            for row, keep in zip(feature_rows, mask)
            if bool(keep)
        ]
        target_times = times_array[mask]
        target_y = targets[target][mask]
        models[target] = _fit_target(
            config,
            target_rows,
            target_times,
            target_y,
        )

    return TrainingBundle(
        dog=dog,
        timezone=local_timezone,
        context=context,
        feature_rows=feature_rows,
        snapshot_times=times_array,
        matrix=matrix,
        targets=targets,
        models=models,
        generated_at=current_time,
        data_days=data_days,
        exact_potty_events=exact_potty_events,
        interval_potty_windows=interval_potty_windows,
        observed_coverage_7d=_observation_coverage(
            observations,
            current_time,
        ),
        fingerprint=_data_fingerprint(db, dog_id),
    )


def get_training_bundle(
    db: Session,
    dog_id: uuid.UUID,
    timezone_name: str,
    now: datetime | None = None,
) -> TrainingBundle:
    key = (str(dog_id), timezone_name)
    fingerprint = _data_fingerprint(db, dog_id)
    cached = _BUNDLE_CACHE.get(key)
    if cached is not None and cached[0] == fingerprint:
        return cached[1]

    bundle = build_training_bundle(
        db,
        dog_id,
        timezone_name,
        now,
    )
    _BUNDLE_CACHE[key] = (fingerprint, bundle)
    return bundle


def model_report(bundle: TrainingBundle) -> PottyModelReport:
    confidence, confidence_label = _confidence(bundle)
    any_model = bundle.models["ANY"]

    top_features: list[str] = []
    if any_model.fitted and any_model.pipeline is not None:
        model: LogisticRegression = any_model.pipeline.named_steps["model"]
        order = np.argsort(np.abs(model.coef_[0]))[::-1]
        for index in order:
            name = any_model.config.feature_names[int(index)]
            label = FEATURE_LABELS[name]
            if label not in top_features:
                top_features.append(label)
            if len(top_features) >= 6:
                break

    return PottyModelReport(
        mode="TRAINED_MODEL" if any_model.fitted else "EARLY_ESTIMATE",
        confidence=confidence,
        confidence_label=confidence_label,
        data_days=bundle.data_days,
        exact_potty_events=bundle.exact_potty_events,
        interval_potty_windows=bundle.interval_potty_windows,
        usable_training_examples=any_model.metrics.training_examples,
        observed_coverage_7d=bundle.observed_coverage_7d,
        generated_at=bundle.generated_at,
        models=[
            bundle.models[target].metrics
            for target in ("ANY", "PEE", "POOP")
        ],
        top_features=top_features,
    )


def current_model_probabilities(
    bundle: TrainingBundle,
    at: datetime,
) -> tuple[dict[TargetName, float], dict[str, float | None]]:
    row = bundle.context.feature_row(at)
    probabilities: dict[TargetName, float] = {
        target: predict_fitted_target(
            bundle.models[target],
            row,
        )
        for target in ("ANY", "PEE", "POOP")
    }
    return probabilities, row


def predict_potty(
    bundle: TrainingBundle,
    at: datetime | None = None,
) -> PottyPredictionResponse:
    current_time = at or bundle.generated_at
    probabilities, row = current_model_probabilities(
        bundle,
        current_time,
    )

    # Preserve the current PawPredict display behavior for parity.
    probability_pee = probabilities["PEE"]
    probability_poop = probabilities["POOP"]
    probability_any = max(
        probabilities["ANY"],
        probability_pee,
        probability_poop,
    )

    sleeping = bundle.context.is_sleeping(current_time)
    unobserved = bundle.context.is_unobserved(current_time)

    forecast: list[ForecastPoint] = []
    for minutes_ahead in (0, 10, 20, 30, 40, 50, 60):
        future_time = current_time + timedelta(minutes=minutes_ahead)
        future_row = bundle.context.feature_row(future_time)
        probability = predict_fitted_target(
            bundle.models["ANY"],
            future_row,
        )
        forecast.append(
            ForecastPoint(
                minutes_ahead=minutes_ahead,
                probability=probability,
            )
        )

    confidence, confidence_label = _confidence(bundle)
    return PottyPredictionResponse(
        generated_at=current_time,
        horizon_minutes=HORIZON_MINUTES,
        probability_any=probability_any,
        probability_pee=probability_pee,
        probability_poop=probability_poop,
        mode=(
            "TRAINED_MODEL"
            if bundle.models["ANY"].fitted
            else "EARLY_ESTIMATE"
        ),
        confidence=confidence,
        confidence_label=confidence_label,
        recommendation=_recommendation(
            probability_any,
            sleeping,
            unobserved,
        ),
        currently_sleeping=sleeping,
        currently_unobserved=unobserved,
        minutes_since_pee=row["minutes_since_pee"],
        minutes_since_poop=row["minutes_since_poop"],
        minutes_since_wake=row["minutes_since_wake"],
        data_days=bundle.data_days,
        training_examples=(
            bundle.models["ANY"].metrics.training_examples
        ),
        exact_potty_events=bundle.exact_potty_events,
        drivers=_prediction_drivers(bundle, row),
        forecast=forecast,
    )
