from datetime import datetime, timedelta, timezone

from app.services.time_to_event import SurvivalLandmark
from app.services.time_to_event_prospective import _decision, _is_resolved_by


def landmark(at, duration, observed=False, reason="HORIZON"):
    return SurvivalLandmark(
        at=at,
        base_features={},
        duration_minutes=duration,
        event_observed=observed,
        censor_reason=reason,
    )


def test_incomplete_horizon_tail_is_not_treated_as_resolved():
    now = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
    item = landmark(now - timedelta(minutes=30), 120, False, "HORIZON")
    assert not _is_resolved_by(item, 120, now)


def test_event_before_dataset_end_is_resolved_even_if_full_horizon_is_not():
    now = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
    item = landmark(now - timedelta(minutes=30), 20, True, "EVENT")
    assert _is_resolved_by(item, 120, now)


def test_decision_waits_before_minimum_future_evidence():
    frozen = datetime(2026, 9, 10, tzinfo=timezone.utc)
    evaluated = datetime(2026, 9, 15, tzinfo=timezone.utc)
    items = [landmark(frozen + timedelta(hours=i), 60, i % 3 == 0, "EVENT" if i % 3 == 0 else "HORIZON") for i in range(40)]
    decision, _ = _decision(items, frozen, evaluated, 0.62, 20.0, 0.9, 0.9)
    assert decision == "WAIT"


def test_decision_product_review_requires_all_gates():
    frozen = datetime(2026, 9, 1, tzinfo=timezone.utc)
    evaluated = datetime(2026, 9, 10, tzinfo=timezone.utc)
    items = [
        landmark(
            frozen + timedelta(hours=i),
            60,
            i % 4 == 0,
            "EVENT" if i % 4 == 0 else "HORIZON",
        )
        for i in range(160)
    ]
    decision, _ = _decision(items, frozen, evaluated, 0.61, 18.0, 0.9, 0.9)
    assert decision == "PRODUCT_REVIEW"
