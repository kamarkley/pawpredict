"""Experimental time-to-event challenger for PawPredict.

This module deliberately does not participate in production inference yet. It
uses the same FeatureContext and observation/sleep semantics as the validated
10-minute classifiers, then fits a discrete-time hazard model for PEE and POOP.

Why discrete-time survival?
---------------------------
PawPredict has right-censoring: we sometimes stop observing before the next
potty event, and an event may simply not occur inside the forecast horizon.
A regular regression target would either drop those examples or invent a time.
Here each landmark contributes one row per future risk interval until the exact
event occurs or the landmark is censored.

Unknown potty timing inside an observation period is never converted to a fake
exact timestamp. The landmark is censored at the start of that period.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Sequence

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.services.potty_prediction import FEATURE_NAMES, FeatureContext, TrainingBundle

SurvivalTarget = Literal["PEE", "POOP"]

BIN_MINUTES = 10
MAX_HORIZON_MINUTES = 120
LANDMARK_STEP_MINUTES = 15
MIN_LANDMARKS = 120
MIN_EVENTS = 20

# Start with the existing production feature vocabulary. Elapsed-time terms are
# appended below and let the conditional hazard vary over the 2-hour horizon.
SURVIVAL_FEATURE_NAMES = tuple(FEATURE_NAMES) + (
    "elapsed_minutes",
    "elapsed_minutes_sq",
)


@dataclass(frozen=True)
class SurvivalLandmark:
    at: datetime
    base_features: dict[str, float | None]
    duration_minutes: float
    event_observed: bool
    censor_reason: str


@dataclass(frozen=True)
class SurvivalForecast:
    target: SurvivalTarget
    probability_30m: float
    probability_60m: float
    probability_120m: float
    expected_minutes: float
    p25_minutes: float | None
    median_minutes: float | None
    p75_minutes: float | None
    survival_at_horizon: float


@dataclass(frozen=True)
class SurvivalMetrics:
    target: SurvivalTarget
    fitted: bool
    landmarks: int
    events: int
    censored: int
    test_landmarks: int
    test_events: int
    concordance_index: float | None
    mean_known_brier: float | None
    event_mae_minutes: float | None
    middle_50_interval_coverage: float | None
    km_baseline_event_mae_minutes: float | None
    probability_event_120m: float | None


@dataclass
class FittedSurvivalModel:
    target: SurvivalTarget
    fitted: bool
    pipeline: Pipeline | None
    metrics: SurvivalMetrics
    train_landmarks: list[SurvivalLandmark]
    test_landmarks: list[SurvivalLandmark]


def _round_metric(value: float | None, digits: int = 4) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


def _first_blocking_time(
    context: FeatureContext,
    start: datetime,
    end: datetime,
) -> tuple[datetime | None, str | None]:
    """Return the first time exact outcome observability is lost."""
    candidates: list[tuple[datetime, str]] = []
    for interval in context.unobserved_intervals:
        if interval.start < end and interval.end > start:
            candidates.append((max(start, interval.start), "UNOBSERVED"))
    for interval in context.sleep_intervals:
        if interval.start < end and interval.end > start:
            candidates.append((max(start, interval.start), "SLEEP"))
    if not candidates:
        return None, None
    return min(candidates, key=lambda item: item[0])


def _next_exact_event_time(
    context: FeatureContext,
    target: SurvivalTarget,
    at: datetime,
) -> datetime | None:
    times = context.times_by_code.get(target, [])
    index = bisect_right(times, at)
    return times[index] if index < len(times) else None


def make_landmark(
    context: FeatureContext,
    target: SurvivalTarget,
    at: datetime,
    *,
    max_horizon_minutes: int = MAX_HORIZON_MINUTES,
) -> SurvivalLandmark | None:
    """Build one right-censored landmark from an observed, awake time point."""
    if context.is_sleeping(at) or context.is_unobserved(at):
        return None

    max_end = at + timedelta(minutes=max_horizon_minutes)
    next_event = _next_exact_event_time(context, target, at)
    blocking_time, blocking_reason = _first_blocking_time(context, at, max_end)

    event_is_observed = (
        next_event is not None
        and next_event <= max_end
        and (blocking_time is None or next_event <= blocking_time)
    )

    if event_is_observed:
        stop = next_event
        reason = "EVENT"
    elif blocking_time is not None:
        stop = blocking_time
        reason = blocking_reason or "CENSORED"
    else:
        stop = max_end
        reason = "HORIZON"

    duration = max(0.0, (stop - at).total_seconds() / 60.0)
    # A zero-length censor contributes no usable risk interval.
    if duration <= 0.0:
        return None

    return SurvivalLandmark(
        at=at,
        base_features=context.feature_row(at),
        duration_minutes=duration,
        event_observed=bool(event_is_observed),
        censor_reason=reason,
    )


def build_landmarks(
    bundle: TrainingBundle,
    target: SurvivalTarget,
    *,
    landmark_step_minutes: int = LANDMARK_STEP_MINUTES,
    max_horizon_minutes: int = MAX_HORIZON_MINUTES,
) -> list[SurvivalLandmark]:
    """Create chronological landmarks without fabricating interval event times."""
    landmarks: list[SurvivalLandmark] = []
    last_kept: datetime | None = None

    for raw_time in bundle.snapshot_times:
        at = raw_time
        if last_kept is not None:
            minutes = (at - last_kept).total_seconds() / 60.0
            if minutes < landmark_step_minutes:
                continue
        landmark = make_landmark(
            bundle.context,
            target,
            at,
            max_horizon_minutes=max_horizon_minutes,
        )
        if landmark is not None:
            landmarks.append(landmark)
            last_kept = at
    return landmarks


def _survival_row(
    landmark: SurvivalLandmark,
    elapsed_start: float,
) -> list[float]:
    row: list[float] = []
    for name in FEATURE_NAMES:
        value = landmark.base_features.get(name)
        row.append(np.nan if value is None else float(value))
    row.append(float(elapsed_start))
    row.append(float((elapsed_start / MAX_HORIZON_MINUTES) ** 2))
    return row


def expand_person_period(
    landmarks: Sequence[SurvivalLandmark],
    *,
    bin_minutes: int = BIN_MINUTES,
    max_horizon_minutes: int = MAX_HORIZON_MINUTES,
) -> tuple[np.ndarray, np.ndarray]:
    """Expand landmarks into discrete hazard rows.

    A row is positive only in the interval containing an observed exact event.
    Censored examples contribute only intervals known to be event-free.
    """
    x_rows: list[list[float]] = []
    y_rows: list[int] = []

    for landmark in landmarks:
        for start in range(0, max_horizon_minutes, bin_minutes):
            end = start + bin_minutes
            # If censoring happened before this interval ends, the interval's
            # outcome is not fully known and must not be used as a negative.
            if not landmark.event_observed and landmark.duration_minutes < end:
                break

            # For an observed event, include intervals through the event bin.
            if landmark.event_observed and landmark.duration_minutes <= start:
                break

            x_rows.append(_survival_row(landmark, float(start)))
            is_event_bin = (
                landmark.event_observed
                and landmark.duration_minutes > start
                and landmark.duration_minutes <= end
            )
            y_rows.append(int(is_event_bin))
            if is_event_bin:
                break

    width = len(SURVIVAL_FEATURE_NAMES)
    if not x_rows:
        return np.empty((0, width), dtype=float), np.empty((0,), dtype=int)
    return np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=int)


def _make_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scale", StandardScaler()),
            # No class weighting: calibrated conditional hazards matter more
            # here than forcing a 50/50 decision boundary.
            ("model", LogisticRegression(max_iter=3000, random_state=42)),
        ]
    )


def hazard_curve(
    pipeline: Pipeline,
    base_features: dict[str, float | None],
    *,
    bin_minutes: int = BIN_MINUTES,
    max_horizon_minutes: int = MAX_HORIZON_MINUTES,
) -> np.ndarray:
    pseudo = SurvivalLandmark(
        at=datetime.min,
        base_features=base_features,
        duration_minutes=float(max_horizon_minutes),
        event_observed=False,
        censor_reason="PREDICTION",
    )
    rows = [
        _survival_row(pseudo, float(start))
        for start in range(0, max_horizon_minutes, bin_minutes)
    ]
    x = np.asarray(rows, dtype=float)
    return np.clip(pipeline.predict_proba(x)[:, 1], 1e-6, 1 - 1e-6)


def survival_from_hazards(hazards: np.ndarray) -> np.ndarray:
    """Survival probability at each bin end."""
    return np.cumprod(1.0 - np.asarray(hazards, dtype=float))


def _quantile_from_survival(
    survival: np.ndarray,
    quantile: float,
    *,
    bin_minutes: int = BIN_MINUTES,
) -> float | None:
    cumulative = 1.0 - survival
    indexes = np.flatnonzero(cumulative >= quantile)
    if len(indexes) == 0:
        return None
    return float((int(indexes[0]) + 1) * bin_minutes)


def forecast_from_hazards(
    target: SurvivalTarget,
    hazards: np.ndarray,
    *,
    bin_minutes: int = BIN_MINUTES,
) -> SurvivalForecast:
    survival = survival_from_hazards(hazards)
    event_probs = np.empty_like(survival)
    prior_survival = 1.0
    for index, hazard in enumerate(hazards):
        event_probs[index] = prior_survival * hazard
        prior_survival *= 1.0 - hazard

    midpoints = (np.arange(len(hazards), dtype=float) + 0.5) * bin_minutes
    horizon = float(len(hazards) * bin_minutes)
    expected = float(np.sum(event_probs * midpoints) + survival[-1] * horizon)

    def probability_by(minutes: int) -> float:
        bins = min(len(survival), max(1, int(math.ceil(minutes / bin_minutes))))
        return float(1.0 - survival[bins - 1])

    return SurvivalForecast(
        target=target,
        probability_30m=round(probability_by(30), 4),
        probability_60m=round(probability_by(60), 4),
        probability_120m=round(float(1.0 - survival[-1]), 4),
        expected_minutes=round(expected, 1),
        p25_minutes=_quantile_from_survival(survival, 0.25, bin_minutes=bin_minutes),
        median_minutes=_quantile_from_survival(survival, 0.50, bin_minutes=bin_minutes),
        p75_minutes=_quantile_from_survival(survival, 0.75, bin_minutes=bin_minutes),
        survival_at_horizon=round(float(survival[-1]), 4),
    )


def _predict_landmarks(
    pipeline: Pipeline,
    landmarks: Sequence[SurvivalLandmark],
    target: SurvivalTarget,
) -> tuple[np.ndarray, np.ndarray, list[SurvivalForecast]]:
    expected: list[float] = []
    p120: list[float] = []
    forecasts: list[SurvivalForecast] = []
    for landmark in landmarks:
        hazards = hazard_curve(pipeline, landmark.base_features)
        forecast = forecast_from_hazards(target, hazards)
        expected.append(forecast.expected_minutes)
        p120.append(forecast.probability_120m)
        forecasts.append(forecast)
    return np.asarray(expected), np.asarray(p120), forecasts


def _concordance_index(
    durations: np.ndarray,
    events: np.ndarray,
    expected_minutes: np.ndarray,
) -> float | None:
    """Harrell-style C-index; shorter predicted time means higher risk."""
    if len(durations) < 2 or int(events.sum()) == 0:
        return None
    risk = -expected_minutes
    concordant = 0.0
    comparable = 0
    for i in np.flatnonzero(events):
        mask = durations > durations[i]
        if not np.any(mask):
            continue
        comparison = risk[i] - risk[mask]
        concordant += float(np.sum(comparison > 0))
        concordant += 0.5 * float(np.sum(comparison == 0))
        comparable += int(mask.sum())
    if comparable == 0:
        return None
    return concordant / comparable


def _known_brier(
    pipeline: Pipeline,
    landmarks: Sequence[SurvivalLandmark],
) -> float | None:
    if not landmarks:
        return None

    cumulative_event = []
    for landmark in landmarks:
        hazards = hazard_curve(pipeline, landmark.base_features)
        cumulative_event.append(1.0 - survival_from_hazards(hazards))
    cumulative_event_array = np.asarray(cumulative_event, dtype=float)

    scores: list[float] = []
    for endpoint in range(BIN_MINUTES, MAX_HORIZON_MINUTES + 1, BIN_MINUTES):
        predictions: list[float] = []
        outcomes: list[int] = []
        bin_index = endpoint // BIN_MINUTES - 1
        for row_index, landmark in enumerate(landmarks):
            # Known positive by endpoint, or known event-free through endpoint.
            positive = landmark.event_observed and landmark.duration_minutes <= endpoint
            known_negative = landmark.duration_minutes >= endpoint
            if not positive and not known_negative:
                continue
            predictions.append(float(cumulative_event_array[row_index, bin_index]))
            outcomes.append(int(positive))
        if outcomes:
            p = np.asarray(predictions)
            y = np.asarray(outcomes)
            scores.append(float(np.mean((p - y) ** 2)))
    return float(np.mean(scores)) if scores else None


def _kaplan_meier_median(landmarks: Sequence[SurvivalLandmark]) -> float | None:
    if not landmarks:
        return None
    ordered = sorted(landmarks, key=lambda item: item.duration_minutes)
    survival = 1.0
    unique_times = sorted({item.duration_minutes for item in ordered})
    for current in unique_times:
        at_risk = sum(item.duration_minutes >= current for item in ordered)
        events = sum(
            item.event_observed and item.duration_minutes == current
            for item in ordered
        )
        if at_risk and events:
            survival *= 1.0 - events / at_risk
        if survival <= 0.5:
            return float(current)
    return None


def fit_survival_challenger(
    bundle: TrainingBundle,
    target: SurvivalTarget,
) -> FittedSurvivalModel:
    landmarks = build_landmarks(bundle, target)
    events = sum(item.event_observed for item in landmarks)
    enough = len(landmarks) >= MIN_LANDMARKS and events >= MIN_EVENTS

    if not enough:
        metrics = SurvivalMetrics(
            target=target,
            fitted=False,
            landmarks=len(landmarks),
            events=events,
            censored=len(landmarks) - events,
            test_landmarks=0,
            test_events=0,
            concordance_index=None,
            mean_known_brier=None,
            event_mae_minutes=None,
            middle_50_interval_coverage=None,
            km_baseline_event_mae_minutes=None,
            probability_event_120m=None,
        )
        return FittedSurvivalModel(target, False, None, metrics, landmarks, [])

    split = max(1, min(len(landmarks) - 1, int(len(landmarks) * 0.8)))
    train = landmarks[:split]
    test = landmarks[split:]
    x_train, y_train = expand_person_period(train)

    if len(x_train) == 0 or len(np.unique(y_train)) < 2:
        metrics = SurvivalMetrics(
            target=target,
            fitted=False,
            landmarks=len(landmarks),
            events=events,
            censored=len(landmarks) - events,
            test_landmarks=len(test),
            test_events=sum(item.event_observed for item in test),
            concordance_index=None,
            mean_known_brier=None,
            event_mae_minutes=None,
            middle_50_interval_coverage=None,
            km_baseline_event_mae_minutes=None,
            probability_event_120m=None,
        )
        return FittedSurvivalModel(target, False, None, metrics, train, test)

    evaluation_pipeline = _make_pipeline()
    evaluation_pipeline.fit(x_train, y_train)

    durations = np.asarray([item.duration_minutes for item in test], dtype=float)
    observed = np.asarray([item.event_observed for item in test], dtype=bool)
    expected, p120, forecasts = _predict_landmarks(evaluation_pipeline, test, target)

    c_index = _concordance_index(durations, observed, expected)
    brier = _known_brier(evaluation_pipeline, test)

    event_indexes = np.flatnonzero(observed)
    event_mae: float | None = None
    interval_coverage: float | None = None
    km_mae: float | None = None
    if len(event_indexes):
        event_mae = float(np.mean(np.abs(expected[event_indexes] - durations[event_indexes])))
        covered = []
        for index in event_indexes:
            forecast = forecasts[int(index)]
            if forecast.p25_minutes is None or forecast.p75_minutes is None:
                continue
            covered.append(
                forecast.p25_minutes
                <= durations[int(index)]
                <= forecast.p75_minutes
            )
        if covered:
            interval_coverage = float(np.mean(covered))

        km_median = _kaplan_meier_median(train)
        if km_median is not None:
            km_mae = float(np.mean(np.abs(durations[event_indexes] - km_median)))

    # Fit the inference challenger on all available landmarks only after the
    # chronological evaluation above has been computed.
    x_all, y_all = expand_person_period(landmarks)
    final_pipeline = _make_pipeline()
    final_pipeline.fit(x_all, y_all)

    metrics = SurvivalMetrics(
        target=target,
        fitted=True,
        landmarks=len(landmarks),
        events=events,
        censored=len(landmarks) - events,
        test_landmarks=len(test),
        test_events=int(observed.sum()),
        concordance_index=_round_metric(c_index),
        mean_known_brier=_round_metric(brier),
        event_mae_minutes=_round_metric(event_mae, 1),
        middle_50_interval_coverage=_round_metric(interval_coverage),
        km_baseline_event_mae_minutes=_round_metric(km_mae, 1),
        probability_event_120m=_round_metric(float(np.mean(p120)) if len(p120) else None),
    )
    return FittedSurvivalModel(target, True, final_pipeline, metrics, train, test)


def predict_time_to_event(
    fitted: FittedSurvivalModel,
    bundle: TrainingBundle,
    at: datetime | None = None,
) -> SurvivalForecast | None:
    if not fitted.fitted or fitted.pipeline is None:
        return None
    current_time = at or bundle.generated_at
    if bundle.context.is_sleeping(current_time) or bundle.context.is_unobserved(current_time):
        return None
    row = bundle.context.feature_row(current_time)
    hazards = hazard_curve(fitted.pipeline, row)
    return forecast_from_hazards(fitted.target, hazards)
