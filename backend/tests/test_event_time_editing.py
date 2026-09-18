from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.routes.events import validate_event_time
from app.schemas.event import EventUpdate


def test_historical_event_time_is_valid_for_editing():
    yesterday = datetime.now(timezone.utc) - timedelta(days=1, hours=2)
    validate_event_time(yesterday)
    update = EventUpdate(event_time=yesterday)
    assert update.event_time == yesterday


def test_future_event_time_is_rejected():
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    with pytest.raises(HTTPException) as exc:
        validate_event_time(future)
    assert exc.value.status_code == 400
    assert "future" in str(exc.value.detail).lower()
