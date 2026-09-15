from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np

from app.services.potty_prediction import EventRecord, FeatureContext
from app.services.time_to_event import (
    forecast_from_hazards,
    make_landmark,
    survival_from_hazards,
)


def _context(events, observations=None):
    return FeatureContext(
        events=events,
        observations=observations or [],
        dog_birth_date=date(2026, 5, 13),
        local_timezone=timezone.utc,
        now=datetime(2026, 9, 15, 12, tzinfo=timezone.utc),
    )


def test_exact_event_before_censor_is_observed():
    start = datetime(2026, 9, 15, 10, tzinfo=timezone.utc)
    events = [EventRecord(start + timedelta(minutes=35), "PEE", None, None)]
    observation = SimpleNamespace(
        start_time=start + timedelta(minutes=60),
        end_time=start + timedelta(minutes=90),
    )
    landmark = make_landmark(_context(events, [observation]), "PEE", start)
    assert landmark is not None
    assert landmark.event_observed is True
    assert landmark.duration_minutes == 35
    assert landmark.censor_reason == "EVENT"


def test_unknown_interval_censors_before_later_exact_event():
    start = datetime(2026, 9, 15, 10, tzinfo=timezone.utc)
    events = [EventRecord(start + timedelta(minutes=80), "PEE", None, None)]
    observation = SimpleNamespace(
        start_time=start + timedelta(minutes=40),
        end_time=start + timedelta(minutes=70),
    )
    landmark = make_landmark(_context(events, [observation]), "PEE", start)
    assert landmark is not None
    assert landmark.event_observed is False
    assert landmark.duration_minutes == 40
    assert landmark.censor_reason == "UNOBSERVED"


def test_survival_is_monotone_and_forecast_probabilities_ordered():
    hazards = np.asarray([0.05] * 12)
    survival = survival_from_hazards(hazards)
    assert np.all(np.diff(survival) <= 0)
    forecast = forecast_from_hazards("PEE", hazards)
    assert 0 <= forecast.probability_30m <= forecast.probability_60m <= forecast.probability_120m <= 1
