"""Phase 5B: rolling, purged validation for PawPredict time-to-event challengers.

This module is research-only. It does not modify production inference or the
model registry. It evaluates discrete-time logistic hazard models across
multiple forecast horizons and feature sets using expanding chronological folds
with a purge gap so training risk windows cannot overlap the test period.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, Sequence

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.services.potty_prediction import TrainingBundle
from app.services.time_to_event import SurvivalLandmark, SurvivalTarget, build_landmarks

FeatureSetName = Literal["FULL", "LEAN", "RECENCY", "ROUTINE"]

BIN_MINUTES = 10
N_FOLDS = 4
INITIAL_TRAIN_FRACTION = 0.60
MIN_TRAIN_LANDMARKS = 240
MIN_TRAIN_EVENTS = 30
MIN_TEST_EVENTS_TOTAL = 30

HORIZONS: dict[SurvivalTarget, tuple[int, ...]] = {
    "PEE": (120, 180, 240),
    "POOP": (180, 240, 360),
}

BASE_FEATURES = (
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
)


def feature_set_for(target: SurvivalTarget, name: FeatureSetName) -> tuple[str, ...]:
    target_recency = "minutes_since_pee" if target == "PEE" else "minutes_since_poop"
    target_count = "pee_count_today" if target == "PEE" else "poop_count_today"
    if name == "FULL":
        return BASE_FEATURES
    if name == "LEAN":
        return (target_recency, "minutes_since_wake", target_count, "hour_sin", "hour_cos")
    if name == "RECENCY":
        return (target_recency, "minutes_since_wake")
    if name == "ROUTINE":
        return (target_count, "hour_sin", "hour_cos", "weekday_sin", "weekday_cos")
    raise ValueError(f"Unknown feature set: {name}")


@dataclass(frozen=True)
class CandidateSpec:
    target: SurvivalTarget
    horizon_minutes: int
    feature_set: FeatureSetName
    feature_names: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.target}-{self.horizon_minutes}m-{self.feature_set.lower()}"


@dataclass(frozen=True)
class CalibrationPoint:
    endpoint_minutes: int
    n_known: int
    predicted_rate: float | None
    observed_rate: float | None
    absolute_gap: float | None


@dataclass(frozen=True)
class FoldMetrics:
    fold: int
    train_landmarks: int
    train_events: int
    test_landmarks: int
    test_events: int
    concordance_index: float | None
    mean_known_brier: float | None
    event_mae_minutes: float | None
    km_baseline_event_mae_minutes: float | None
    middle_50_interval_coverage: float | None
    middle_75_interval_coverage: float | None


@dataclass(frozen=True)
class CandidateSummary:
    spec: CandidateSpec
    fitted_folds: int
    test_landmarks: int
    test_events: int
    concordance_index: float | None
    mean_known_brier: float | None
    event_mae_minutes: float | None
    km_baseline_event_mae_minutes: float | None
    mae_improvement_pct: float | None
    middle_50_interval_coverage: float | None
    middle_75_interval_coverage: float | None
    calibration: tuple[CalibrationPoint, ...]
    fold_metrics: tuple[FoldMetrics, ...]
    decision: str


@dataclass
class CandidateResult:
    summary: CandidateSummary
    oof_durations: np.ndarray
    oof_events: np.ndarray
    oof_expected: np.ndarray
    oof_cumulative: np.ndarray


def _make_pipeline() -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(max_iter=3000, random_state=42)),
    ])


def _survival_row(
    landmark: SurvivalLandmark,
    elapsed_start: float,
    feature_names: Sequence[str],
    horizon_minutes: int,
) -> list[float]:
    row: list[float] = []
    for name in feature_names:
        value = landmark.base_features.get(name)
        row.append(np.nan if value is None else float(value))
    row.append(float(elapsed_start))
    row.append(float((elapsed_start / max(1, horizon_minutes)) ** 2))
    return row


def expand_person_period(
    landmarks: Sequence[SurvivalLandmark],
    feature_names: Sequence[str],
    horizon_minutes: int,
    *,
    bin_minutes: int = BIN_MINUTES,
) -> tuple[np.ndarray, np.ndarray]:
    x_rows: list[list[float]] = []
    y_rows: list[int] = []
    for landmark in landmarks:
        for start in range(0, horizon_minutes, bin_minutes):
            end = start + bin_minutes
            if not landmark.event_observed and landmark.duration_minutes < end:
                break
            if landmark.event_observed and landmark.duration_minutes <= start:
                break
            x_rows.append(_survival_row(landmark, float(start), feature_names, horizon_minutes))
            is_event = (
                landmark.event_observed
                and landmark.duration_minutes > start
                and landmark.duration_minutes <= end
            )
            y_rows.append(int(is_event))
            if is_event:
                break
    width = len(feature_names) + 2
    if not x_rows:
        return np.empty((0, width), dtype=float), np.empty((0,), dtype=int)
    return np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=int)


def hazard_curve(
    pipeline: Pipeline,
    landmark: SurvivalLandmark,
    feature_names: Sequence[str],
    horizon_minutes: int,
    *,
    bin_minutes: int = BIN_MINUTES,
) -> np.ndarray:
    x = np.asarray([
        _survival_row(landmark, float(start), feature_names, horizon_minutes)
        for start in range(0, horizon_minutes, bin_minutes)
    ], dtype=float)
    return np.clip(pipeline.predict_proba(x)[:, 1], 1e-6, 1 - 1e-6)


def survival_from_hazards(hazards: np.ndarray) -> np.ndarray:
    return np.cumprod(1.0 - np.asarray(hazards, dtype=float))


def cumulative_from_hazards(hazards: np.ndarray) -> np.ndarray:
    return 1.0 - survival_from_hazards(hazards)


def expected_minutes_from_hazards(hazards: np.ndarray, bin_minutes: int = BIN_MINUTES) -> float:
    survival = survival_from_hazards(hazards)
    prior = 1.0
    event_probs: list[float] = []
    for hazard in hazards:
        event_probs.append(prior * float(hazard))
        prior *= 1.0 - float(hazard)
    midpoints = (np.arange(len(hazards), dtype=float) + 0.5) * bin_minutes
    horizon = len(hazards) * bin_minutes
    return float(np.sum(np.asarray(event_probs) * midpoints) + survival[-1] * horizon)


def quantile_minutes(cumulative: np.ndarray, quantile: float, bin_minutes: int = BIN_MINUTES) -> float | None:
    idx = np.flatnonzero(np.asarray(cumulative) >= quantile)
    return None if len(idx) == 0 else float((int(idx[0]) + 1) * bin_minutes)




def _interval_contains_event(
    cumulative: np.ndarray,
    duration_minutes: float,
    lower_quantile: float,
    upper_quantile: float,
) -> bool:
    """Return whether an observed event falls inside a horizon-aware central interval.

    If the upper quantile is not reached inside the finite forecast horizon, the
    interval is right-open beyond the horizon rather than "missing". Because this
    helper is only used for events observed within the horizon, such an event is
    covered whenever it is at or above the lower bound. If the lower quantile is
    itself not reached, the interval starts beyond the horizon and the observed
    event cannot be covered.

    This keeps 50% and 75% coverage on the same event denominator and guarantees
    the wider central interval cannot report lower coverage merely because its
    upper quantile was unbounded.
    """
    lower = quantile_minutes(cumulative, lower_quantile)
    upper = quantile_minutes(cumulative, upper_quantile)
    if lower is None:
        return False
    if upper is None:
        return duration_minutes >= lower
    return lower <= duration_minutes <= upper


def _concordance_index(durations: np.ndarray, events: np.ndarray, expected: np.ndarray) -> float | None:
    if len(durations) < 2 or int(events.sum()) == 0:
        return None
    risk = -expected
    concordant = 0.0
    comparable = 0
    for i in np.flatnonzero(events):
        mask = durations > durations[i]
        if not np.any(mask):
            continue
        delta = risk[i] - risk[mask]
        concordant += float(np.sum(delta > 0)) + 0.5 * float(np.sum(delta == 0))
        comparable += int(mask.sum())
    return None if comparable == 0 else concordant / comparable


def _kaplan_meier_median(landmarks: Sequence[SurvivalLandmark]) -> float | None:
    if not landmarks:
        return None
    survival = 1.0
    times = sorted({x.duration_minutes for x in landmarks})
    for current in times:
        at_risk = sum(x.duration_minutes >= current for x in landmarks)
        events = sum(x.event_observed and x.duration_minutes == current for x in landmarks)
        if at_risk and events:
            survival *= 1.0 - events / at_risk
        if survival <= 0.5:
            return float(current)
    return None


def _known_mask(landmarks: Sequence[SurvivalLandmark], endpoint: int) -> tuple[np.ndarray, np.ndarray]:
    known: list[bool] = []
    outcome: list[int] = []
    for item in landmarks:
        positive = item.event_observed and item.duration_minutes <= endpoint
        negative = item.duration_minutes >= endpoint
        known.append(bool(positive or negative))
        outcome.append(int(positive))
    return np.asarray(known, dtype=bool), np.asarray(outcome, dtype=int)


def _calibration_points(
    landmarks: Sequence[SurvivalLandmark],
    cumulative: np.ndarray,
    horizon_minutes: int,
) -> tuple[CalibrationPoint, ...]:
    endpoints = sorted({x for x in (30, 60, 120, horizon_minutes) if x <= horizon_minutes})
    points: list[CalibrationPoint] = []
    for endpoint in endpoints:
        idx = min(cumulative.shape[1] - 1, endpoint // BIN_MINUTES - 1)
        known, y = _known_mask(landmarks, endpoint)
        if not np.any(known):
            points.append(CalibrationPoint(endpoint, 0, None, None, None))
            continue
        pred = cumulative[known, idx]
        obs = y[known]
        p = float(pred.mean())
        o = float(obs.mean())
        points.append(CalibrationPoint(endpoint, int(known.sum()), round(p, 4), round(o, 4), round(abs(p-o), 4)))
    return tuple(points)


def _mean_known_brier(
    landmarks: Sequence[SurvivalLandmark], cumulative: np.ndarray, horizon_minutes: int
) -> float | None:
    scores: list[float] = []
    for endpoint in range(BIN_MINUTES, horizon_minutes + 1, BIN_MINUTES):
        known, y = _known_mask(landmarks, endpoint)
        if not np.any(known):
            continue
        idx = endpoint // BIN_MINUTES - 1
        scores.append(float(np.mean((cumulative[known, idx] - y[known]) ** 2)))
    return None if not scores else float(np.mean(scores))


def _rolling_splits(
    landmarks: Sequence[SurvivalLandmark], horizon_minutes: int, n_folds: int = N_FOLDS
) -> list[tuple[list[SurvivalLandmark], list[SurvivalLandmark]]]:
    n = len(landmarks)
    initial = max(MIN_TRAIN_LANDMARKS, int(n * INITIAL_TRAIN_FRACTION))
    if initial >= n - n_folds:
        return []
    remaining = n - initial
    fold_size = max(1, remaining // n_folds)
    splits = []
    for fold in range(n_folds):
        test_start = initial + fold * fold_size
        test_end = n if fold == n_folds - 1 else min(n, test_start + fold_size)
        if test_start >= n or test_end <= test_start:
            continue
        test = list(landmarks[test_start:test_end])
        boundary = test[0].at
        train = [
            x for x in landmarks[:test_start]
            if x.at + timedelta(minutes=horizon_minutes) <= boundary
        ]
        if train and test:
            splits.append((train, test))
    return splits


def _decision(summary_values: dict[str, float | int | None]) -> str:
    events = int(summary_values["test_events"] or 0)
    cindex = summary_values["concordance_index"]
    improvement = summary_values["mae_improvement_pct"]
    if events < MIN_TEST_EVENTS_TOTAL:
        return "INSUFFICIENT_TEST_EVENTS"
    if cindex is None or cindex <= 0.50:
        return "REJECT"
    if improvement is None:
        return "NEEDS_BASELINE"
    if float(cindex) >= 0.55 and float(improvement) >= 10.0:
        return "PROMISING"
    if float(improvement) > 0:
        return "WATCH"
    return "REJECT"


def evaluate_candidate(bundle: TrainingBundle, spec: CandidateSpec) -> CandidateResult:
    landmarks = build_landmarks(
        bundle,
        spec.target,
        max_horizon_minutes=spec.horizon_minutes,
    )
    splits = _rolling_splits(landmarks, spec.horizon_minutes)

    fold_metrics: list[FoldMetrics] = []
    oof_landmarks: list[SurvivalLandmark] = []
    oof_expected: list[float] = []
    oof_cumulative: list[np.ndarray] = []
    km_predictions: list[float] = []
    km_event_durations: list[float] = []

    for fold_index, (train, test) in enumerate(splits, start=1):
        train_events = sum(x.event_observed for x in train)
        if len(train) < MIN_TRAIN_LANDMARKS or train_events < MIN_TRAIN_EVENTS:
            continue
        x_train, y_train = expand_person_period(train, spec.feature_names, spec.horizon_minutes)
        if len(x_train) == 0 or len(np.unique(y_train)) < 2:
            continue
        pipeline = _make_pipeline()
        pipeline.fit(x_train, y_train)

        cumulative_rows: list[np.ndarray] = []
        expected_rows: list[float] = []
        for item in test:
            hazards = hazard_curve(pipeline, item, spec.feature_names, spec.horizon_minutes)
            cumulative = cumulative_from_hazards(hazards)
            cumulative_rows.append(cumulative)
            expected_rows.append(expected_minutes_from_hazards(hazards))

        cumulative_arr = np.asarray(cumulative_rows, dtype=float)
        expected_arr = np.asarray(expected_rows, dtype=float)
        durations = np.asarray([x.duration_minutes for x in test], dtype=float)
        events = np.asarray([x.event_observed for x in test], dtype=bool)
        event_idx = np.flatnonzero(events)

        fold_mae = None
        c50 = None
        c75 = None
        if len(event_idx):
            fold_mae = float(np.mean(np.abs(expected_arr[event_idx] - durations[event_idx])))
            inside50 = [
                _interval_contains_event(
                    cumulative_arr[int(idx)], durations[int(idx)], 0.25, 0.75
                )
                for idx in event_idx
            ]
            inside75 = [
                _interval_contains_event(
                    cumulative_arr[int(idx)], durations[int(idx)], 0.125, 0.875
                )
                for idx in event_idx
            ]
            c50 = float(np.mean(inside50))
            c75 = float(np.mean(inside75))

        km_median = _kaplan_meier_median(train)
        km_mae = None
        if km_median is not None and len(event_idx):
            event_durations = durations[event_idx]
            km_mae = float(np.mean(np.abs(event_durations - km_median)))
            km_predictions.extend([km_median] * len(event_durations))
            km_event_durations.extend(event_durations.tolist())

        fold_metrics.append(FoldMetrics(
            fold=fold_index,
            train_landmarks=len(train),
            train_events=train_events,
            test_landmarks=len(test),
            test_events=int(events.sum()),
            concordance_index=_round(_concordance_index(durations, events, expected_arr)),
            mean_known_brier=_round(_mean_known_brier(test, cumulative_arr, spec.horizon_minutes)),
            event_mae_minutes=_round(fold_mae, 1),
            km_baseline_event_mae_minutes=_round(km_mae, 1),
            middle_50_interval_coverage=_round(c50),
            middle_75_interval_coverage=_round(c75),
        ))
        oof_landmarks.extend(test)
        oof_expected.extend(expected_arr.tolist())
        oof_cumulative.extend(cumulative_rows)

    if not oof_landmarks:
        empty = CandidateSummary(
            spec, 0, 0, 0, None, None, None, None, None, None, None, tuple(), tuple(), "NO_VALID_FOLDS"
        )
        return CandidateResult(empty, np.empty(0), np.empty(0, dtype=bool), np.empty(0), np.empty((0, spec.horizon_minutes // BIN_MINUTES)))

    durations = np.asarray([x.duration_minutes for x in oof_landmarks], dtype=float)
    events = np.asarray([x.event_observed for x in oof_landmarks], dtype=bool)
    expected = np.asarray(oof_expected, dtype=float)
    cumulative = np.asarray(oof_cumulative, dtype=float)
    event_idx = np.flatnonzero(events)
    event_mae = None if len(event_idx) == 0 else float(np.mean(np.abs(expected[event_idx] - durations[event_idx])))
    km_mae = None
    if km_predictions:
        km_mae = float(np.mean(np.abs(np.asarray(km_predictions) - np.asarray(km_event_durations))))
    improvement = None
    if event_mae is not None and km_mae not in (None, 0):
        improvement = 100.0 * (km_mae - event_mae) / km_mae

    c50_vals = [
        _interval_contains_event(cumulative[int(idx)], durations[int(idx)], 0.25, 0.75)
        for idx in event_idx
    ]
    c75_vals = [
        _interval_contains_event(cumulative[int(idx)], durations[int(idx)], 0.125, 0.875)
        for idx in event_idx
    ]

    values = {
        "test_events": int(events.sum()),
        "concordance_index": _concordance_index(durations, events, expected),
        "mae_improvement_pct": improvement,
    }
    summary = CandidateSummary(
        spec=spec,
        fitted_folds=len(fold_metrics),
        test_landmarks=len(oof_landmarks),
        test_events=int(events.sum()),
        concordance_index=_round(values["concordance_index"]),
        mean_known_brier=_round(_mean_known_brier(oof_landmarks, cumulative, spec.horizon_minutes)),
        event_mae_minutes=_round(event_mae, 1),
        km_baseline_event_mae_minutes=_round(km_mae, 1),
        mae_improvement_pct=_round(improvement, 1),
        middle_50_interval_coverage=_round(float(np.mean(c50_vals)) if c50_vals else None),
        middle_75_interval_coverage=_round(float(np.mean(c75_vals)) if c75_vals else None),
        calibration=_calibration_points(oof_landmarks, cumulative, spec.horizon_minutes),
        fold_metrics=tuple(fold_metrics),
        decision=_decision(values),
    )
    return CandidateResult(summary, durations, events, expected, cumulative)


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def candidate_grid(target: SurvivalTarget) -> list[CandidateSpec]:
    return [
        CandidateSpec(target, horizon, feature_set, feature_set_for(target, feature_set))
        for horizon in HORIZONS[target]
        for feature_set in ("FULL", "LEAN", "RECENCY", "ROUTINE")
    ]


def select_best_candidate(summaries: Sequence[CandidateSummary]) -> CandidateSummary | None:
    eligible = [x for x in summaries if x.decision == "PROMISING"]
    if not eligible:
        eligible = [x for x in summaries if x.decision == "WATCH"]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda x: (
            -(x.mae_improvement_pct if x.mae_improvement_pct is not None else -1e9),
            -(x.concordance_index if x.concordance_index is not None else -1e9),
            x.mean_known_brier if x.mean_known_brier is not None else 1e9,
        ),
    )[0]


def evaluate_target_grid(bundle: TrainingBundle, target: SurvivalTarget) -> list[CandidateResult]:
    return [evaluate_candidate(bundle, spec) for spec in candidate_grid(target)]
