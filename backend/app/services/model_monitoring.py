"""Production ML monitoring for PawPredict.

This module intentionally works from the immutable prediction ledger instead of
re-running historical inference. That keeps monitoring aligned with what the
user actually saw in production and preserves champion/shadow comparisons.

Drift is live-to-live: a recent window is compared with the immediately
preceding window of the same length. Until both windows contain enough ledger
rows, drift status is INSUFFICIENT_DATA rather than manufacturing a baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
from typing import Any, Iterable, Sequence

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session


ACTIVE_LIFECYCLE_STATUSES = ("PRODUCTION", "SHADOW")
DEFAULT_WINDOWS = (7, 14, 30)
STATUS_VALUES = {"HEALTHY", "WATCH", "DEGRADED", "INSUFFICIENT_DATA"}


@dataclass(frozen=True)
class MonitoringThresholds:
    min_resolved: int = 100
    min_positives: int = 5
    min_drift_predictions: int = 200
    min_feature_values: int = 100

    coverage_watch: float = 0.70
    coverage_degraded: float = 0.50

    ece_watch: float = 0.06
    ece_degraded: float = 0.10

    calibration_gap_watch: float = 0.05
    calibration_gap_degraded: float = 0.10

    psi_watch: float = 0.10
    psi_degraded: float = 0.25

    brier_relative_watch: float = 0.10
    brier_relative_degraded: float = 0.25
    brier_absolute_watch: float = 0.005
    brier_absolute_degraded: float = 0.010


THRESHOLDS = MonitoringThresholds()


@dataclass
class WindowMetrics:
    prediction_count: int
    resolved_count: int
    ineligible_count: int
    pending_count: int
    closed_count: int
    coverage_rate: float | None
    positive_count: int
    observed_positive_rate: float | None
    avg_probability: float | None
    brier_score: float | None
    ece: float | None
    calibration_gap: float | None


@dataclass
class FeatureDriftMetric:
    feature_name: str
    recent_count: int
    reference_count: int
    recent_mean: float | None
    reference_mean: float | None
    recent_std: float | None
    reference_std: float | None
    psi: float | None
    drift_status: str


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def brier_score(probabilities: Sequence[float], outcomes: Sequence[int | bool]) -> float | None:
    if not probabilities or len(probabilities) != len(outcomes):
        return None
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    if p.size == 0:
        return None
    return float(np.mean((p - y) ** 2))


def expected_calibration_error(
    probabilities: Sequence[float],
    outcomes: Sequence[int | bool],
    bins: int = 10,
) -> float | None:
    """Weighted absolute calibration error using fixed probability bins."""
    if not probabilities or len(probabilities) != len(outcomes):
        return None

    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    mask = np.isfinite(p) & np.isfinite(y)
    p = np.clip(p[mask], 0.0, 1.0)
    y = y[mask]
    if p.size == 0:
        return None

    edges = np.linspace(0.0, 1.0, bins + 1)
    # p==1 should land in the final bin.
    bin_ids = np.minimum(np.digitize(p, edges[1:-1], right=False), bins - 1)

    total = float(p.size)
    ece = 0.0
    for idx in range(bins):
        member = bin_ids == idx
        count = int(member.sum())
        if count == 0:
            continue
        avg_p = float(p[member].mean())
        avg_y = float(y[member].mean())
        ece += (count / total) * abs(avg_p - avg_y)
    return float(ece)


def _categorical_psi(reference: np.ndarray, recent: np.ndarray, epsilon: float) -> float:
    values = sorted(set(reference.tolist()) | set(recent.tolist()))
    ref_n = max(len(reference), 1)
    rec_n = max(len(recent), 1)
    psi = 0.0
    for value in values:
        ref_pct = max(float(np.sum(reference == value)) / ref_n, epsilon)
        rec_pct = max(float(np.sum(recent == value)) / rec_n, epsilon)
        psi += (rec_pct - ref_pct) * math.log(rec_pct / ref_pct)
    return float(psi)


def population_stability_index(
    reference: Sequence[float],
    recent: Sequence[float],
    bins: int = 10,
    epsilon: float = 1e-6,
) -> float | None:
    """Population Stability Index (PSI).

    Low-cardinality numeric features are treated categorically; continuous
    features use quantile bins learned from the reference period.
    """
    ref = np.asarray(reference, dtype=float)
    rec = np.asarray(recent, dtype=float)
    ref = ref[np.isfinite(ref)]
    rec = rec[np.isfinite(rec)]
    if ref.size == 0 or rec.size == 0:
        return None

    ref_unique = np.unique(ref)
    rec_unique = np.unique(rec)
    union_unique = np.unique(np.concatenate([ref_unique, rec_unique]))
    if union_unique.size <= 10:
        return _categorical_psi(ref, rec, epsilon)

    quantiles = np.linspace(0.0, 1.0, bins + 1)
    edges = np.unique(np.quantile(ref, quantiles))
    if edges.size < 3:
        # Reference is effectively constant but the recent distribution is not.
        if np.allclose(ref, rec[: min(ref.size, rec.size)], atol=1e-12, rtol=0.0) and np.std(rec) < 1e-12:
            return 0.0
        return 1.0

    edges[0] = -np.inf
    edges[-1] = np.inf
    ref_counts, _ = np.histogram(ref, bins=edges)
    rec_counts, _ = np.histogram(rec, bins=edges)

    ref_pct = ref_counts.astype(float) / max(ref_counts.sum(), 1)
    rec_pct = rec_counts.astype(float) / max(rec_counts.sum(), 1)
    ref_pct = np.clip(ref_pct, epsilon, None)
    rec_pct = np.clip(rec_pct, epsilon, None)
    return float(np.sum((rec_pct - ref_pct) * np.log(rec_pct / ref_pct)))


def summarize_window(rows: Sequence[dict[str, Any]]) -> WindowMetrics:
    prediction_count = len(rows)
    resolved = [row for row in rows if row.get("outcome_status") == "RESOLVED"]
    ineligible_count = sum(1 for row in rows if row.get("outcome_status") == "INELIGIBLE")
    pending_count = sum(1 for row in rows if row.get("outcome_status") == "PENDING")
    closed_count = len(resolved) + ineligible_count
    coverage_rate = (len(resolved) / closed_count) if closed_count else None

    probabilities: list[float] = []
    outcomes: list[int] = []
    for row in resolved:
        probability = _to_float(row.get("probability"))
        outcome = row.get("observed_outcome")
        if probability is None or outcome is None:
            continue
        probabilities.append(probability)
        outcomes.append(1 if bool(outcome) else 0)

    positive_count = int(sum(outcomes))
    observed_positive_rate = float(np.mean(outcomes)) if outcomes else None
    avg_probability = float(np.mean(probabilities)) if probabilities else None
    brier = brier_score(probabilities, outcomes)
    ece = expected_calibration_error(probabilities, outcomes)
    calibration_gap = (
        abs(avg_probability - observed_positive_rate)
        if avg_probability is not None and observed_positive_rate is not None
        else None
    )

    return WindowMetrics(
        prediction_count=prediction_count,
        resolved_count=len(outcomes),
        ineligible_count=ineligible_count,
        pending_count=pending_count,
        closed_count=closed_count,
        coverage_rate=coverage_rate,
        positive_count=positive_count,
        observed_positive_rate=observed_positive_rate,
        avg_probability=avg_probability,
        brier_score=brier,
        ece=ece,
        calibration_gap=calibration_gap,
    )


def _feature_values(rows: Sequence[dict[str, Any]], feature_name: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        snapshot = row.get("feature_snapshot")
        if not isinstance(snapshot, dict):
            continue
        value = _to_float(snapshot.get(feature_name))
        if value is not None:
            values.append(value)
    return values


def feature_drift_metrics(
    recent_rows: Sequence[dict[str, Any]],
    reference_rows: Sequence[dict[str, Any]],
    feature_names: Sequence[str],
    thresholds: MonitoringThresholds = THRESHOLDS,
) -> list[FeatureDriftMetric]:
    metrics: list[FeatureDriftMetric] = []
    for feature_name in feature_names:
        recent = _feature_values(recent_rows, feature_name)
        reference = _feature_values(reference_rows, feature_name)
        psi = None
        status = "INSUFFICIENT_DATA"
        if len(recent) >= thresholds.min_feature_values and len(reference) >= thresholds.min_feature_values:
            psi = population_stability_index(reference, recent)
            if psi is None:
                status = "INSUFFICIENT_DATA"
            elif psi >= thresholds.psi_degraded:
                status = "DEGRADED"
            elif psi >= thresholds.psi_watch:
                status = "WATCH"
            else:
                status = "HEALTHY"

        metrics.append(
            FeatureDriftMetric(
                feature_name=feature_name,
                recent_count=len(recent),
                reference_count=len(reference),
                recent_mean=float(np.mean(recent)) if recent else None,
                reference_mean=float(np.mean(reference)) if reference else None,
                recent_std=float(np.std(recent)) if recent else None,
                reference_std=float(np.std(reference)) if reference else None,
                psi=psi,
                drift_status=status,
            )
        )
    return metrics


def _brier_change(recent: float | None, reference: float | None) -> tuple[float | None, float | None]:
    if recent is None or reference is None:
        return None, None
    delta = recent - reference
    relative = delta / reference if reference > 1e-12 else None
    return delta, relative


def classify_health(
    recent: WindowMetrics,
    reference: WindowMetrics,
    prediction_psi: float | None,
    feature_metrics: Sequence[FeatureDriftMetric],
    thresholds: MonitoringThresholds = THRESHOLDS,
) -> tuple[str, str, str, list[str]]:
    """Return (overall, performance, drift, reasons)."""
    reasons: list[str] = []

    performance_status = "HEALTHY"
    if recent.resolved_count < thresholds.min_resolved or recent.positive_count < thresholds.min_positives:
        performance_status = "INSUFFICIENT_DATA"
        reasons.append(
            f"Performance needs at least {thresholds.min_resolved} resolved predictions and "
            f"{thresholds.min_positives} positives; got {recent.resolved_count} and {recent.positive_count}."
        )
    else:
        perf_degraded = False
        perf_watch = False

        if recent.coverage_rate is not None:
            if recent.coverage_rate < thresholds.coverage_degraded:
                perf_degraded = True
                reasons.append(f"Observed coverage {recent.coverage_rate:.1%} is below {thresholds.coverage_degraded:.0%}.")
            elif recent.coverage_rate < thresholds.coverage_watch:
                perf_watch = True
                reasons.append(f"Observed coverage {recent.coverage_rate:.1%} is below {thresholds.coverage_watch:.0%}.")

        if recent.ece is not None:
            if recent.ece >= thresholds.ece_degraded:
                perf_degraded = True
                reasons.append(f"ECE {recent.ece:.3f} exceeds degraded threshold {thresholds.ece_degraded:.2f}.")
            elif recent.ece >= thresholds.ece_watch:
                perf_watch = True
                reasons.append(f"ECE {recent.ece:.3f} exceeds watch threshold {thresholds.ece_watch:.2f}.")

        if recent.calibration_gap is not None:
            if recent.calibration_gap >= thresholds.calibration_gap_degraded:
                perf_degraded = True
                reasons.append(
                    f"Calibration gap {recent.calibration_gap:.3f} exceeds degraded threshold "
                    f"{thresholds.calibration_gap_degraded:.2f}."
                )
            elif recent.calibration_gap >= thresholds.calibration_gap_watch:
                perf_watch = True
                reasons.append(
                    f"Calibration gap {recent.calibration_gap:.3f} exceeds watch threshold "
                    f"{thresholds.calibration_gap_watch:.2f}."
                )

        reference_ready = (
            reference.resolved_count >= thresholds.min_resolved
            and reference.positive_count >= thresholds.min_positives
        )
        if reference_ready:
            delta, relative = _brier_change(recent.brier_score, reference.brier_score)
            if delta is not None:
                if (
                    delta >= thresholds.brier_absolute_degraded
                    and relative is not None
                    and relative >= thresholds.brier_relative_degraded
                ):
                    perf_degraded = True
                    reasons.append(
                        f"Brier worsened by {delta:.4f} ({relative:.1%}) versus the preceding window."
                    )
                elif (
                    delta >= thresholds.brier_absolute_watch
                    or (relative is not None and relative >= thresholds.brier_relative_watch)
                ):
                    perf_watch = True
                    rel_text = f" ({relative:.1%})" if relative is not None else ""
                    reasons.append(f"Brier worsened by {delta:.4f}{rel_text} versus the preceding window.")

        if perf_degraded:
            performance_status = "DEGRADED"
        elif perf_watch:
            performance_status = "WATCH"

    drift_status = "HEALTHY"
    if (
        recent.prediction_count < thresholds.min_drift_predictions
        or reference.prediction_count < thresholds.min_drift_predictions
    ):
        drift_status = "INSUFFICIENT_DATA"
        reasons.append(
            f"Drift needs at least {thresholds.min_drift_predictions} predictions in both recent and reference windows; "
            f"got {recent.prediction_count} and {reference.prediction_count}."
        )
    else:
        drift_degraded = False
        drift_watch = False
        if prediction_psi is not None:
            if prediction_psi >= thresholds.psi_degraded:
                drift_degraded = True
                reasons.append(f"Prediction PSI {prediction_psi:.3f} indicates material distribution drift.")
            elif prediction_psi >= thresholds.psi_watch:
                drift_watch = True
                reasons.append(f"Prediction PSI {prediction_psi:.3f} is above the watch threshold.")

        feature_degraded = [m.feature_name for m in feature_metrics if m.drift_status == "DEGRADED"]
        feature_watch = [m.feature_name for m in feature_metrics if m.drift_status == "WATCH"]
        if feature_degraded:
            drift_degraded = True
            reasons.append("Degraded feature PSI: " + ", ".join(feature_degraded) + ".")
        elif feature_watch:
            drift_watch = True
            reasons.append("Feature PSI on watch: " + ", ".join(feature_watch) + ".")

        if drift_degraded:
            drift_status = "DEGRADED"
        elif drift_watch:
            drift_status = "WATCH"

    if "DEGRADED" in (performance_status, drift_status):
        overall = "DEGRADED"
    elif "WATCH" in (performance_status, drift_status):
        overall = "WATCH"
    elif "INSUFFICIENT_DATA" in (performance_status, drift_status):
        overall = "INSUFFICIENT_DATA"
    else:
        overall = "HEALTHY"

    assert overall in STATUS_VALUES
    return overall, performance_status, drift_status, reasons


def _load_feature_names(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []


def _fetch_active_versions(db: Session, dog_id: str | None = None) -> list[dict[str, Any]]:
    sql = """
        select
            id,
            dog_id,
            target,
            version_label,
            status,
            feature_names
        from model_versions
        where status in ('PRODUCTION', 'SHADOW')
    """
    params: dict[str, Any] = {}
    if dog_id:
        sql += " and dog_id = :dog_id"
        params["dog_id"] = dog_id
    sql += " order by dog_id, target, status desc, version_label"
    return [dict(row) for row in db.execute(text(sql), params).mappings().all()]


def _fetch_prediction_rows(
    db: Session,
    model_version_id: str,
    start_time: datetime,
    end_time: datetime,
) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            select
                probability,
                outcome_status,
                observed_outcome,
                feature_snapshot,
                prediction_time,
                role
            from model_predictions
            where model_version_id = :model_version_id
              and prediction_time >= :start_time
              and prediction_time < :end_time
            order by prediction_time
            """
        ),
        {
            "model_version_id": model_version_id,
            "start_time": start_time,
            "end_time": end_time,
        },
    ).mappings().all()
    return [dict(row) for row in rows]


def _prediction_probabilities(rows: Sequence[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _to_float(row.get("probability"))
        if value is not None:
            values.append(value)
    return values


def _persist_snapshot(
    db: Session,
    *,
    version: dict[str, Any],
    as_of: datetime,
    window_days: int,
    recent_start: datetime,
    reference_start: datetime,
    recent: WindowMetrics,
    reference: WindowMetrics,
    prediction_psi: float | None,
    feature_metrics: Sequence[FeatureDriftMetric],
    overall_status: str,
    performance_status: str,
    drift_status: str,
    reasons: Sequence[str],
) -> str:
    brier_delta, brier_relative = _brier_change(recent.brier_score, reference.brier_score)
    prevalence_delta = (
        recent.observed_positive_rate - reference.observed_positive_rate
        if recent.observed_positive_rate is not None and reference.observed_positive_rate is not None
        else None
    )
    max_feature_psi = max((m.psi for m in feature_metrics if m.psi is not None), default=None)

    snapshot_id = db.execute(
        text(
            """
            insert into model_monitoring_snapshots (
                dog_id,
                model_version_id,
                target,
                lifecycle_status,
                as_of_date,
                as_of_time,
                window_days,
                recent_start,
                recent_end,
                reference_start,
                reference_end,
                prediction_count,
                resolved_count,
                ineligible_count,
                pending_count,
                coverage_rate,
                positive_count,
                observed_positive_rate,
                avg_probability,
                brier_score,
                ece,
                calibration_gap,
                reference_prediction_count,
                reference_resolved_count,
                reference_positive_count,
                reference_observed_positive_rate,
                reference_brier_score,
                brier_delta,
                brier_relative_change,
                prevalence_delta,
                prediction_psi,
                max_feature_psi,
                performance_status,
                drift_status,
                health_status,
                health_reasons,
                updated_at
            ) values (
                :dog_id,
                :model_version_id,
                :target,
                :lifecycle_status,
                :as_of_date,
                :as_of_time,
                :window_days,
                :recent_start,
                :recent_end,
                :reference_start,
                :reference_end,
                :prediction_count,
                :resolved_count,
                :ineligible_count,
                :pending_count,
                :coverage_rate,
                :positive_count,
                :observed_positive_rate,
                :avg_probability,
                :brier_score,
                :ece,
                :calibration_gap,
                :reference_prediction_count,
                :reference_resolved_count,
                :reference_positive_count,
                :reference_observed_positive_rate,
                :reference_brier_score,
                :brier_delta,
                :brier_relative_change,
                :prevalence_delta,
                :prediction_psi,
                :max_feature_psi,
                :performance_status,
                :drift_status,
                :health_status,
                cast(:health_reasons as jsonb),
                now()
            )
            on conflict (model_version_id, as_of_date, window_days)
            do update set
                lifecycle_status = excluded.lifecycle_status,
                as_of_time = excluded.as_of_time,
                recent_start = excluded.recent_start,
                recent_end = excluded.recent_end,
                reference_start = excluded.reference_start,
                reference_end = excluded.reference_end,
                prediction_count = excluded.prediction_count,
                resolved_count = excluded.resolved_count,
                ineligible_count = excluded.ineligible_count,
                pending_count = excluded.pending_count,
                coverage_rate = excluded.coverage_rate,
                positive_count = excluded.positive_count,
                observed_positive_rate = excluded.observed_positive_rate,
                avg_probability = excluded.avg_probability,
                brier_score = excluded.brier_score,
                ece = excluded.ece,
                calibration_gap = excluded.calibration_gap,
                reference_prediction_count = excluded.reference_prediction_count,
                reference_resolved_count = excluded.reference_resolved_count,
                reference_positive_count = excluded.reference_positive_count,
                reference_observed_positive_rate = excluded.reference_observed_positive_rate,
                reference_brier_score = excluded.reference_brier_score,
                brier_delta = excluded.brier_delta,
                brier_relative_change = excluded.brier_relative_change,
                prevalence_delta = excluded.prevalence_delta,
                prediction_psi = excluded.prediction_psi,
                max_feature_psi = excluded.max_feature_psi,
                performance_status = excluded.performance_status,
                drift_status = excluded.drift_status,
                health_status = excluded.health_status,
                health_reasons = excluded.health_reasons,
                updated_at = now()
            returning id
            """
        ),
        {
            "dog_id": str(version["dog_id"]),
            "model_version_id": str(version["id"]),
            "target": version["target"],
            "lifecycle_status": version["status"],
            "as_of_date": as_of.date(),
            "as_of_time": as_of,
            "window_days": window_days,
            "recent_start": recent_start,
            "recent_end": as_of,
            "reference_start": reference_start,
            "reference_end": recent_start,
            "prediction_count": recent.prediction_count,
            "resolved_count": recent.resolved_count,
            "ineligible_count": recent.ineligible_count,
            "pending_count": recent.pending_count,
            "coverage_rate": recent.coverage_rate,
            "positive_count": recent.positive_count,
            "observed_positive_rate": recent.observed_positive_rate,
            "avg_probability": recent.avg_probability,
            "brier_score": recent.brier_score,
            "ece": recent.ece,
            "calibration_gap": recent.calibration_gap,
            "reference_prediction_count": reference.prediction_count,
            "reference_resolved_count": reference.resolved_count,
            "reference_positive_count": reference.positive_count,
            "reference_observed_positive_rate": reference.observed_positive_rate,
            "reference_brier_score": reference.brier_score,
            "brier_delta": brier_delta,
            "brier_relative_change": brier_relative,
            "prevalence_delta": prevalence_delta,
            "prediction_psi": prediction_psi,
            "max_feature_psi": max_feature_psi,
            "performance_status": performance_status,
            "drift_status": drift_status,
            "health_status": overall_status,
            "health_reasons": json.dumps(list(reasons)),
        },
    ).scalar_one()

    db.execute(
        text("delete from model_feature_drift where monitoring_snapshot_id = :snapshot_id"),
        {"snapshot_id": str(snapshot_id)},
    )

    for metric in feature_metrics:
        db.execute(
            text(
                """
                insert into model_feature_drift (
                    monitoring_snapshot_id,
                    dog_id,
                    model_version_id,
                    target,
                    feature_name,
                    recent_count,
                    reference_count,
                    recent_mean,
                    reference_mean,
                    recent_std,
                    reference_std,
                    psi,
                    drift_status
                ) values (
                    :monitoring_snapshot_id,
                    :dog_id,
                    :model_version_id,
                    :target,
                    :feature_name,
                    :recent_count,
                    :reference_count,
                    :recent_mean,
                    :reference_mean,
                    :recent_std,
                    :reference_std,
                    :psi,
                    :drift_status
                )
                """
            ),
            {
                "monitoring_snapshot_id": str(snapshot_id),
                "dog_id": str(version["dog_id"]),
                "model_version_id": str(version["id"]),
                "target": version["target"],
                "feature_name": metric.feature_name,
                "recent_count": metric.recent_count,
                "reference_count": metric.reference_count,
                "recent_mean": metric.recent_mean,
                "reference_mean": metric.reference_mean,
                "recent_std": metric.recent_std,
                "reference_std": metric.reference_std,
                "psi": metric.psi,
                "drift_status": metric.drift_status,
            },
        )

    return str(snapshot_id)


def run_monitoring(
    db: Session,
    *,
    dog_id: str | None = None,
    as_of: datetime | None = None,
    windows: Iterable[int] = DEFAULT_WINDOWS,
    thresholds: MonitoringThresholds = THRESHOLDS,
) -> list[dict[str, Any]]:
    """Compute and persist monitoring snapshots for production/shadow models."""
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    else:
        as_of = as_of.astimezone(timezone.utc)

    window_values = sorted({int(value) for value in windows if int(value) > 0})
    if not window_values:
        raise ValueError("At least one positive monitoring window is required.")

    versions = _fetch_active_versions(db, dog_id=dog_id)
    results: list[dict[str, Any]] = []

    for version in versions:
        feature_names = _load_feature_names(version.get("feature_names"))
        for window_days in window_values:
            recent_start = as_of - timedelta(days=window_days)
            reference_start = recent_start - timedelta(days=window_days)

            reference_rows = _fetch_prediction_rows(
                db,
                model_version_id=str(version["id"]),
                start_time=reference_start,
                end_time=recent_start,
            )
            recent_rows = _fetch_prediction_rows(
                db,
                model_version_id=str(version["id"]),
                start_time=recent_start,
                end_time=as_of,
            )

            recent_metrics = summarize_window(recent_rows)
            reference_metrics = summarize_window(reference_rows)

            prediction_psi = None
            if (
                recent_metrics.prediction_count >= thresholds.min_drift_predictions
                and reference_metrics.prediction_count >= thresholds.min_drift_predictions
            ):
                prediction_psi = population_stability_index(
                    _prediction_probabilities(reference_rows),
                    _prediction_probabilities(recent_rows),
                )

            features = feature_drift_metrics(
                recent_rows,
                reference_rows,
                feature_names,
                thresholds=thresholds,
            )
            health_status, performance_status, drift_status, reasons = classify_health(
                recent_metrics,
                reference_metrics,
                prediction_psi,
                features,
                thresholds=thresholds,
            )

            snapshot_id = _persist_snapshot(
                db,
                version=version,
                as_of=as_of,
                window_days=window_days,
                recent_start=recent_start,
                reference_start=reference_start,
                recent=recent_metrics,
                reference=reference_metrics,
                prediction_psi=prediction_psi,
                feature_metrics=features,
                overall_status=health_status,
                performance_status=performance_status,
                drift_status=drift_status,
                reasons=reasons,
            )

            results.append(
                {
                    "snapshot_id": snapshot_id,
                    "dog_id": str(version["dog_id"]),
                    "target": version["target"],
                    "version_label": version["version_label"],
                    "lifecycle_status": version["status"],
                    "window_days": window_days,
                    "prediction_count": recent_metrics.prediction_count,
                    "resolved_count": recent_metrics.resolved_count,
                    "positive_count": recent_metrics.positive_count,
                    "coverage_rate": recent_metrics.coverage_rate,
                    "brier_score": recent_metrics.brier_score,
                    "ece": recent_metrics.ece,
                    "prediction_psi": prediction_psi,
                    "health_status": health_status,
                    "performance_status": performance_status,
                    "drift_status": drift_status,
                    "health_reasons": reasons,
                }
            )

    db.commit()
    return results
