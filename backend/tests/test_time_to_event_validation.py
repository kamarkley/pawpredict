from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np

from app.services.time_to_event import SurvivalLandmark
from app.services.time_to_event_validation import (
    CandidateSpec,
    _interval_contains_event,
    _rolling_splits,
    cumulative_from_hazards,
    expand_person_period,
    feature_set_for,
    quantile_minutes,
)


def _lm(at, duration=120, event=False):
    base = {
        "minutes_since_pee": 20.0, "minutes_since_poop": 60.0,
        "minutes_since_potty_attempt": 30.0, "minutes_since_wake": 45.0,
        "pee_count_today": 2.0, "poop_count_today": 1.0,
        "recent_treat_30m": 0.0, "recent_zoomies_30m": 0.0,
        "recent_potty_attempt_30m": 0.0, "hour_sin": 0.2, "hour_cos": 0.8,
        "weekday_sin": 0.1, "weekday_cos": 0.9, "age_days": 120.0,
    }
    return SurvivalLandmark(at, base, duration, event, "EVENT" if event else "HORIZON")


def test_target_specific_lean_features():
    assert "minutes_since_pee" in feature_set_for("PEE", "LEAN")
    assert "minutes_since_poop" not in feature_set_for("PEE", "LEAN")
    assert "minutes_since_poop" in feature_set_for("POOP", "LEAN")


def test_person_period_width_tracks_selected_features_and_horizon():
    names = feature_set_for("PEE", "RECENCY")
    x, y = expand_person_period([_lm(datetime.now(timezone.utc), 35, True)], names, 180)
    assert x.shape[1] == len(names) + 2
    assert y.sum() == 1
    assert len(y) == 4


def test_cumulative_and_quantiles_are_monotone():
    cumulative = cumulative_from_hazards(np.asarray([0.1] * 12))
    assert np.all(np.diff(cumulative) >= 0)
    assert quantile_minutes(cumulative, 0.25) <= quantile_minutes(cumulative, 0.50)


def test_rolling_split_purges_overlapping_training_windows():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    landmarks = [_lm(start + timedelta(minutes=15*i), 120, i % 5 == 0) for i in range(800)]
    splits = _rolling_splits(landmarks, 120, n_folds=4)
    assert splits
    for train, test in splits:
        assert train[-1].at + timedelta(minutes=120) <= test[0].at


def test_horizon_aware_interval_coverage_keeps_wider_interval_nested():
    # CDF reaches 25%/50% but not 75% or 87.5% inside the finite horizon.
    cumulative = np.asarray([0.10, 0.20, 0.30, 0.40, 0.55, 0.60])
    duration = 50.0
    covered50 = _interval_contains_event(cumulative, duration, 0.25, 0.75)
    covered75 = _interval_contains_event(cumulative, duration, 0.125, 0.875)
    assert covered50 is True
    assert covered75 is True


def test_event_before_lower_bound_is_not_covered():
    cumulative = np.asarray([0.05, 0.10, 0.20, 0.30, 0.40, 0.50])
    assert _interval_contains_event(cumulative, 10.0, 0.25, 0.75) is False
