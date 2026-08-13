"""Feature engineering utilities for PawPredict's potty-risk model."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


@dataclass(frozen=True)
class EventRow:
    event_time: datetime
    event_type_code: str
    option_name: str | None = None


def minutes_since(events: Iterable[EventRow], at: datetime, code: str) -> float | None:
    prior = [e.event_time for e in events if e.event_type_code == code and e.event_time <= at]
    if not prior:
        return None
    return (at - max(prior)).total_seconds() / 60.0


def cyclical_hour(at: datetime) -> tuple[float, float]:
    hour = at.hour + at.minute / 60.0
    angle = 2 * math.pi * hour / 24.0
    return math.sin(angle), math.cos(angle)


def target_next_10m(events: Iterable[EventRow], at: datetime) -> int:
    end = at + timedelta(minutes=10)
    return int(any(e.event_type_code in {"PEE", "POOP"} and at < e.event_time <= end for e in events))


def snapshot_features(events: list[EventRow], at: datetime, birth_date: datetime) -> dict[str, float | int | None]:
    sin_hour, cos_hour = cyclical_hour(at)
    day_start = at.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "minutes_since_pee": minutes_since(events, at, "PEE"),
        "minutes_since_poop": minutes_since(events, at, "POOP"),
        "minutes_since_potty_attempt": minutes_since(events, at, "POTTY_ATTEMPT"),
        "minutes_since_nap_end": minutes_since([e for e in events if e.event_type_code == "SLEEP"], at, "SLEEP"),
        "pee_count_today": sum(e.event_type_code == "PEE" and day_start <= e.event_time <= at for e in events),
        "poop_count_today": sum(e.event_type_code == "POOP" and day_start <= e.event_time <= at for e in events),
        "recent_treat_30m": int(any(e.event_type_code == "TREAT" and at - timedelta(minutes=30) <= e.event_time <= at for e in events)),
        "recent_zoomies_30m": int(any(e.event_type_code == "ZOOMIES" and at - timedelta(minutes=30) <= e.event_time <= at for e in events)),
        "hour_sin": sin_hour,
        "hour_cos": cos_hour,
        "age_days": (at.date() - birth_date.date()).days,
        "target_10m": target_next_10m(events, at),
    }
