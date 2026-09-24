import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from sqlalchemy import select
from app.models.event import Event
from app.models.event_type import EventType
from app.models.observation_period import ObservationPeriod
from app.models.saved_option import SavedOption
from app.models.scheduled_item import ScheduledItem
from app.security import CurrentUser, DatabaseSession, require_owned_dog

router = APIRouter(prefix="/dogs", tags=["data export"])

def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@router.get("/{dog_id}/export")
def export_dog_data(dog_id: uuid.UUID, db: DatabaseSession, user: CurrentUser) -> dict:
    dog = require_owned_dog(db, dog_id, user)

    event_rows = db.execute(
        select(Event, EventType, SavedOption)
        .join(EventType, Event.event_type_id == EventType.id)
        .outerjoin(SavedOption, Event.option_id == SavedOption.id)
        .where(Event.dog_id == dog_id)
        .order_by(Event.event_time.asc())
    ).all()
    periods = db.scalars(
        select(ObservationPeriod)
        .where(ObservationPeriod.dog_id == dog_id)
        .order_by(ObservationPeriod.start_time.asc())
    ).all()
    scheduled = db.scalars(
        select(ScheduledItem)
        .where(ScheduledItem.dog_id == dog_id)
        .order_by(ScheduledItem.scheduled_for.asc())
    ).all()

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "dog": {
            "id": str(dog.id),
            "name": dog.name,
            "birth_date": dog.birth_date.isoformat(),
            "breed": dog.breed,
            "sex": dog.sex,
            "weight_lbs": float(dog.weight_lbs) if dog.weight_lbs is not None else None,
            "neutered": dog.neutered,
        },
        "events": [
            {
                "id": str(event.id),
                "event_type_code": event_type.code,
                "event_type_name": event_type.display_name,
                "event_time": iso(event.event_time),
                "state": event.state,
                "location": event.location,
                "option_name": option.name if option else None,
                "numeric_value": float(event.numeric_value) if event.numeric_value is not None else None,
                "unit": event.unit,
                "severity": event.severity,
                "notes": event.notes,
                "entry_method": event.entry_method,
            }
            for event, event_type, option in event_rows
        ],
        "observation_periods": [
            {
                "id": str(period.id),
                "start_time": iso(period.start_time),
                "end_time": iso(period.end_time),
                "status": period.status,
                "reason": period.reason,
                "notes": period.notes,
                "peed_during": period.peed_during,
                "pooped_during": period.pooped_during,
                "potty_location": period.potty_location,
                "likely_state": period.likely_state,
                "camera_checked": period.camera_checked,
            }
            for period in periods
        ],
        "scheduled_items": [
            {
                "id": str(item.id),
                "title": item.title,
                "item_type": item.item_type,
                "scheduled_for": iso(item.scheduled_for),
                "end_time": iso(item.end_time),
                "location": item.location,
                "notes": item.notes,
                "is_completed": item.is_completed,
                "linked_event_id": str(item.linked_event_id) if item.linked_event_id else None,
            }
            for item in scheduled
        ],
    }
