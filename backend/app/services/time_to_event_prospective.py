"""Phase 5C: frozen prospective validation for PawPredict time-to-event challengers.

Research-only. This module freezes the pre-registered survival candidates chosen
by Phase 5B, then evaluates them only on landmarks occurring after the freeze
instant. Production inference and the model registry are untouched.

The prospective split is enforced by the frozen model artifact itself: model
parameters and the Kaplan-Meier timing baseline are fit once, serialized, and
never refit during evaluation.
"""
from __future__ import annotations

import math
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from app.services.potty_prediction import TrainingBundle
from app.services.time_to_event import SurvivalLandmark, SurvivalTarget, build_landmarks
from app.services.time_to_event_validation import (
    CandidateSpec,
    _calibration_points,
    _concordance_index,
    _interval_contains_event,
    _kaplan_meier_median,
    _make_pipeline,
    _mean_known_brier,
    cumulative_from_hazards,
    expand_person_period,
    expected_minutes_from_hazards,
    feature_set_for,
    hazard_curve,
)

ARTIFACT_VERSION = 1
MIN_FUTURE_LANDMARKS = 150
MIN_FUTURE_EVENTS = 30
MIN_FUTURE_DAYS = 4

# Frozen from the corrected Phase 5B evidence gate. Do not change these after
# prospective data starts accumulating; create a new artifact/version instead.
SELECTED_SPECS: dict[SurvivalTarget, CandidateSpec] = {
    "PEE": CandidateSpec(
        target="PEE",
        horizon_minutes=120,
        feature_set="FULL",
        feature_names=feature_set_for("PEE", "FULL"),
    ),
    "POOP": CandidateSpec(
        target="POOP",
        horizon_minutes=180,
        feature_set="LEAN",
        feature_names=feature_set_for("POOP", "LEAN"),
    ),
}


@dataclass
class FrozenSurvivalCandidate:
    spec: CandidateSpec
    pipeline: Any
    km_median_minutes: float | None
    training_landmarks: int
    training_events: int
    training_start: datetime | None
    training_end: datetime | None


@dataclass
class FrozenSurvivalBundle:
    artifact_version: int
    dog_id: str
    timezone_name: str
    frozen_at: datetime
    data_fingerprint: tuple[Any, ...]
    candidates: dict[SurvivalTarget, FrozenSurvivalCandidate]


@dataclass(frozen=True)
class ProspectiveMetrics:
    target: SurvivalTarget
    candidate_label: str
    frozen_at: datetime
    evaluated_at: datetime
    future_days: int
    future_landmarks: int
    future_events: int
    concordance_index: float | None
    mean_known_brier: float | None
    event_mae_minutes: float | None
    km_baseline_event_mae_minutes: float | None
    mae_improvement_pct: float | None
    middle_50_interval_coverage: float | None
    middle_75_interval_coverage: float | None
    bootstrap_p_improvement_positive: float | None
    bootstrap_p_cindex_above_half: float | None
    improvement_ci_low: float | None
    improvement_ci_high: float | None
    cindex_ci_low: float | None
    cindex_ci_high: float | None
    decision: str
    decision_reason: str
    calibration: tuple[Any, ...]


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def _is_resolved_by(
    landmark: SurvivalLandmark,
    horizon_minutes: int,
    as_of: datetime,
) -> bool:
    """Whether the landmark's known follow-up ends on or before ``as_of``.

    ``build_landmarks`` historically labels a no-event tail as HORIZON even when
    the requested horizon extends past the dataset end. Phase 5C refuses to use
    those incomplete tail landmarks. EVENT/SLEEP/UNOBSERVED landmarks are usable
    as soon as their observed stop time has occurred.
    """
    if landmark.censor_reason == "HORIZON":
        return landmark.at + timedelta(minutes=horizon_minutes) <= as_of
    return landmark.at + timedelta(minutes=landmark.duration_minutes) <= as_of


def resolved_landmarks(
    bundle: TrainingBundle,
    spec: CandidateSpec,
    *,
    start_after: datetime | None = None,
    as_of: datetime | None = None,
) -> list[SurvivalLandmark]:
    current = as_of or bundle.generated_at
    landmarks = build_landmarks(
        bundle,
        spec.target,
        max_horizon_minutes=spec.horizon_minutes,
    )
    return [
        item
        for item in landmarks
        if (start_after is None or item.at > start_after)
        and _is_resolved_by(item, spec.horizon_minutes, current)
    ]


def fit_frozen_bundle(
    bundle: TrainingBundle,
    dog_id: str,
    timezone_name: str,
) -> FrozenSurvivalBundle:
    candidates: dict[SurvivalTarget, FrozenSurvivalCandidate] = {}
    for target, spec in SELECTED_SPECS.items():
        landmarks = resolved_landmarks(bundle, spec, as_of=bundle.generated_at)
        events = sum(item.event_observed for item in landmarks)
        if len(landmarks) < 240 or events < 30:
            raise ValueError(
                f"Not enough resolved {target} landmarks to freeze: "
                f"{len(landmarks)} landmarks / {events} events."
            )
        x_train, y_train = expand_person_period(
            landmarks,
            spec.feature_names,
            spec.horizon_minutes,
        )
        if len(x_train) == 0 or len(np.unique(y_train)) < 2:
            raise ValueError(f"{target} frozen candidate has no usable hazard rows.")
        pipeline = _make_pipeline()
        pipeline.fit(x_train, y_train)
        candidates[target] = FrozenSurvivalCandidate(
            spec=spec,
            pipeline=pipeline,
            km_median_minutes=_kaplan_meier_median(landmarks),
            training_landmarks=len(landmarks),
            training_events=events,
            training_start=landmarks[0].at if landmarks else None,
            training_end=landmarks[-1].at if landmarks else None,
        )
    return FrozenSurvivalBundle(
        artifact_version=ARTIFACT_VERSION,
        dog_id=str(dog_id),
        timezone_name=timezone_name,
        frozen_at=bundle.generated_at,
        data_fingerprint=bundle.fingerprint,
        candidates=candidates,
    )


def save_frozen_bundle(bundle: FrozenSurvivalBundle, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(
            f"Frozen artifact already exists: {destination}. "
            "Do not overwrite a prospective artifact; use a new filename/version."
        )
    with destination.open("wb") as handle:
        pickle.dump(bundle, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return destination


def load_frozen_bundle(path: str | Path) -> FrozenSurvivalBundle:
    with Path(path).open("rb") as handle:
        artifact = pickle.load(handle)
    if not isinstance(artifact, FrozenSurvivalBundle):
        raise TypeError("Unexpected frozen survival artifact type.")
    if artifact.artifact_version != ARTIFACT_VERSION:
        raise ValueError(
            f"Unsupported artifact version {artifact.artifact_version}; expected {ARTIFACT_VERSION}."
        )
    return artifact


def _predict_candidate(
    candidate: FrozenSurvivalCandidate,
    landmarks: Sequence[SurvivalLandmark],
) -> tuple[np.ndarray, np.ndarray]:
    cumulative_rows: list[np.ndarray] = []
    expected_rows: list[float] = []
    for item in landmarks:
        hazards = hazard_curve(
            candidate.pipeline,
            item,
            candidate.spec.feature_names,
            candidate.spec.horizon_minutes,
        )
        cumulative_rows.append(cumulative_from_hazards(hazards))
        expected_rows.append(expected_minutes_from_hazards(hazards))
    bins = candidate.spec.horizon_minutes // 10
    if not landmarks:
        return np.empty((0,), dtype=float), np.empty((0, bins), dtype=float)
    return np.asarray(expected_rows, dtype=float), np.asarray(cumulative_rows, dtype=float)


def _point_metrics(
    candidate: FrozenSurvivalCandidate,
    landmarks: Sequence[SurvivalLandmark],
) -> dict[str, Any]:
    expected, cumulative = _predict_candidate(candidate, landmarks)
    durations = np.asarray([item.duration_minutes for item in landmarks], dtype=float)
    events = np.asarray([item.event_observed for item in landmarks], dtype=bool)
    event_idx = np.flatnonzero(events)

    event_mae = None
    baseline_mae = None
    improvement = None
    c50 = None
    c75 = None
    if len(event_idx):
        event_durations = durations[event_idx]
        event_mae = float(np.mean(np.abs(expected[event_idx] - event_durations)))
        if candidate.km_median_minutes is not None:
            baseline_mae = float(
                np.mean(np.abs(event_durations - candidate.km_median_minutes))
            )
            if baseline_mae > 0:
                improvement = 100.0 * (baseline_mae - event_mae) / baseline_mae
        c50 = float(np.mean([
            _interval_contains_event(cumulative[int(idx)], durations[int(idx)], 0.25, 0.75)
            for idx in event_idx
        ]))
        c75 = float(np.mean([
            _interval_contains_event(cumulative[int(idx)], durations[int(idx)], 0.125, 0.875)
            for idx in event_idx
        ]))

    return {
        "durations": durations,
        "events": events,
        "expected": expected,
        "cumulative": cumulative,
        "cindex": _concordance_index(durations, events, expected),
        "brier": _mean_known_brier(
            landmarks, cumulative, candidate.spec.horizon_minutes
        ) if landmarks else None,
        "event_mae": event_mae,
        "baseline_mae": baseline_mae,
        "improvement": improvement,
        "coverage50": c50,
        "coverage75": c75,
        "calibration": _calibration_points(
            landmarks, cumulative, candidate.spec.horizon_minutes
        ) if landmarks else tuple(),
    }


def _day_block_bootstrap(
    candidate: FrozenSurvivalCandidate,
    landmarks: Sequence[SurvivalLandmark],
    timezone,
    *,
    replicates: int = 500,
    seed: int = 42,
) -> dict[str, float | None]:
    if replicates <= 0 or len(landmarks) < 2:
        return {
            "p_improvement_positive": None,
            "p_cindex_above_half": None,
            "improvement_ci_low": None,
            "improvement_ci_high": None,
            "cindex_ci_low": None,
            "cindex_ci_high": None,
        }

    day_to_items: dict[Any, list[SurvivalLandmark]] = {}
    for item in landmarks:
        day_to_items.setdefault(item.at.astimezone(timezone).date(), []).append(item)
    days = list(day_to_items)
    if len(days) < 2:
        return {
            "p_improvement_positive": None,
            "p_cindex_above_half": None,
            "improvement_ci_low": None,
            "improvement_ci_high": None,
            "cindex_ci_low": None,
            "cindex_ci_high": None,
        }

    rng = np.random.default_rng(seed)
    improvements: list[float] = []
    cindexes: list[float] = []
    for _ in range(replicates):
        sampled_days = rng.choice(days, size=len(days), replace=True)
        sample: list[SurvivalLandmark] = []
        for day in sampled_days:
            sample.extend(day_to_items[day])
        metrics = _point_metrics(candidate, sample)
        if metrics["improvement"] is not None and math.isfinite(metrics["improvement"]):
            improvements.append(float(metrics["improvement"]))
        if metrics["cindex"] is not None and math.isfinite(metrics["cindex"]):
            cindexes.append(float(metrics["cindex"]))

    def ci(values: list[float]) -> tuple[float | None, float | None]:
        if not values:
            return None, None
        return (
            float(np.quantile(values, 0.025)),
            float(np.quantile(values, 0.975)),
        )

    imp_low, imp_high = ci(improvements)
    c_low, c_high = ci(cindexes)
    return {
        "p_improvement_positive": (
            float(np.mean(np.asarray(improvements) > 0)) if improvements else None
        ),
        "p_cindex_above_half": (
            float(np.mean(np.asarray(cindexes) > 0.5)) if cindexes else None
        ),
        "improvement_ci_low": imp_low,
        "improvement_ci_high": imp_high,
        "cindex_ci_low": c_low,
        "cindex_ci_high": c_high,
    }


def _decision(
    landmarks: Sequence[SurvivalLandmark],
    frozen_at: datetime,
    evaluated_at: datetime,
    cindex: float | None,
    improvement: float | None,
    p_improvement_positive: float | None,
    p_cindex_above_half: float | None,
) -> tuple[str, str]:
    events = sum(item.event_observed for item in landmarks)
    future_days = max(0, (evaluated_at.date() - frozen_at.date()).days)
    if (
        len(landmarks) < MIN_FUTURE_LANDMARKS
        or events < MIN_FUTURE_EVENTS
        or future_days < MIN_FUTURE_DAYS
    ):
        return (
            "WAIT",
            f"Need >= {MIN_FUTURE_LANDMARKS} future landmarks, >= {MIN_FUTURE_EVENTS} "
            f"events, and >= {MIN_FUTURE_DAYS} calendar days; got "
            f"{len(landmarks)}, {events}, and {future_days}.",
        )
    if cindex is None or improvement is None:
        return "WAIT", "Prospective metrics are not yet estimable."
    if cindex <= 0.50 or improvement <= 0:
        return (
            "REJECT",
            "Prospective ordering or timing accuracy failed to beat the frozen baseline.",
        )
    if (
        cindex >= 0.55
        and improvement >= 10.0
        and (p_improvement_positive or 0.0) >= 0.80
        and (p_cindex_above_half or 0.0) >= 0.80
    ):
        return (
            "PRODUCT_REVIEW",
            "Prospective candidate cleared the pre-registered ranking, timing, and bootstrap evidence gates.",
        )
    return (
        "WATCH",
        "Prospective signal is positive but has not cleared every product-review gate.",
    )


def evaluate_frozen_candidate(
    frozen: FrozenSurvivalBundle,
    candidate: FrozenSurvivalCandidate,
    current_bundle: TrainingBundle,
    *,
    bootstrap_replicates: int = 500,
) -> ProspectiveMetrics:
    landmarks = resolved_landmarks(
        current_bundle,
        candidate.spec,
        start_after=frozen.frozen_at,
        as_of=current_bundle.generated_at,
    )
    point = _point_metrics(candidate, landmarks)
    bootstrap = _day_block_bootstrap(
        candidate,
        landmarks,
        current_bundle.timezone,
        replicates=bootstrap_replicates,
    )
    decision, reason = _decision(
        landmarks,
        frozen.frozen_at,
        current_bundle.generated_at,
        point["cindex"],
        point["improvement"],
        bootstrap["p_improvement_positive"],
        bootstrap["p_cindex_above_half"],
    )
    future_days = max(
        0,
        (current_bundle.generated_at.date() - frozen.frozen_at.date()).days,
    )
    return ProspectiveMetrics(
        target=candidate.spec.target,
        candidate_label=candidate.spec.label,
        frozen_at=frozen.frozen_at,
        evaluated_at=current_bundle.generated_at,
        future_days=future_days,
        future_landmarks=len(landmarks),
        future_events=sum(item.event_observed for item in landmarks),
        concordance_index=_round(point["cindex"]),
        mean_known_brier=_round(point["brier"]),
        event_mae_minutes=_round(point["event_mae"], 1),
        km_baseline_event_mae_minutes=_round(point["baseline_mae"], 1),
        mae_improvement_pct=_round(point["improvement"], 1),
        middle_50_interval_coverage=_round(point["coverage50"]),
        middle_75_interval_coverage=_round(point["coverage75"]),
        bootstrap_p_improvement_positive=_round(bootstrap["p_improvement_positive"]),
        bootstrap_p_cindex_above_half=_round(bootstrap["p_cindex_above_half"]),
        improvement_ci_low=_round(bootstrap["improvement_ci_low"], 1),
        improvement_ci_high=_round(bootstrap["improvement_ci_high"], 1),
        cindex_ci_low=_round(bootstrap["cindex_ci_low"]),
        cindex_ci_high=_round(bootstrap["cindex_ci_high"]),
        decision=decision,
        decision_reason=reason,
        calibration=tuple(point["calibration"]),
    )
