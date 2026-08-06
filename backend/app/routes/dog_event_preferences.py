import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dog import Dog
from app.models.dog_event_preference import DogEventPreference
from app.models.event_type import EventType
from app.schemas.event_type import EventTypeResponse

router = APIRouter(prefix="/dogs/{dog_id}/event-preferences", tags=["event preferences"])
DatabaseSession = Annotated[Session, Depends(get_db)]


class EventPreferenceItem(BaseModel):
    event_type: EventTypeResponse
    is_enabled: bool
    display_order: int | None


class EventPreferencesUpdate(BaseModel):
    event_type_ids: list[int]


@router.get("", response_model=list[EventPreferenceItem])
def get_preferences(dog_id: uuid.UUID, db: DatabaseSession) -> list[EventPreferenceItem]:
    if db.get(Dog, dog_id) is None:
        raise HTTPException(status_code=404, detail="Dog not found.")
    rows = db.execute(
        select(EventType, DogEventPreference)
        .outerjoin(
            DogEventPreference,
            (DogEventPreference.event_type_id == EventType.id)
            & (DogEventPreference.dog_id == dog_id),
        )
        .where(EventType.is_active.is_(True))
        .order_by(DogEventPreference.display_order.nulls_last(), EventType.id)
    ).all()
    return [
        EventPreferenceItem(
            event_type=EventTypeResponse.model_validate(event_type),
            is_enabled=(preference.is_enabled if preference else event_type.default_enabled),
            display_order=(preference.display_order if preference else event_type.id),
        )
        for event_type, preference in rows
    ]


@router.put("", response_model=list[EventPreferenceItem])
def update_preferences(
    dog_id: uuid.UUID, data: EventPreferencesUpdate, db: DatabaseSession
) -> list[EventPreferenceItem]:
    if not data.event_type_ids:
        raise HTTPException(status_code=400, detail="At least one event type must remain enabled.")
    if db.get(Dog, dog_id) is None:
        raise HTTPException(status_code=404, detail="Dog not found.")

    active_ids = set(db.scalars(select(EventType.id).where(EventType.is_active.is_(True))).all())
    requested = set(data.event_type_ids)
    if not requested.issubset(active_ids):
        raise HTTPException(status_code=400, detail="One or more event types are invalid.")

    now = datetime.now(timezone.utc)
    for order, event_type_id in enumerate(sorted(active_ids), start=1):
        preference = db.get(DogEventPreference, (dog_id, event_type_id))
        if preference is None:
            preference = DogEventPreference(
                dog_id=dog_id, event_type_id=event_type_id,
                is_enabled=event_type_id in requested, display_order=order,
                created_at=now, updated_at=now,
            )
            db.add(preference)
        else:
            preference.is_enabled = event_type_id in requested
            preference.display_order = order
    db.commit()
    return get_preferences(dog_id, db)
