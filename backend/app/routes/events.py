import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dog import Dog
from app.models.event import Event
from app.models.event_type import EventType
from app.models.saved_option import SavedOption
from app.schemas.event import EventCreate, EventResponse, EventUpdate

router = APIRouter(prefix="/events", tags=["events"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def build_event_response(event: Event, event_type: EventType, option: SavedOption | None) -> EventResponse:
    return EventResponse(
        id=event.id, dog_id=event.dog_id, event_type_id=event.event_type_id,
        event_type_code=event_type.code, event_type_name=event_type.display_name,
        event_time=event.event_time, state=event.state, location=event.location,
        option_id=event.option_id, option_name=option.name if option else None,
        numeric_value=event.numeric_value, unit=event.unit, severity=event.severity,
        notes=event.notes, entry_method=event.entry_method, created_at=event.created_at,
    )


def validate_details(
    *, dog_id: uuid.UUID, event_type: EventType, state: str | None,
    option_id: uuid.UUID | None, numeric_value: Decimal | None,
    unit: str | None, severity: int | None, db: Session,
) -> SavedOption | None:
    if event_type.supports_state and state is None:
        raise HTTPException(status_code=400, detail="This event requires a start or end state.")
    if not event_type.supports_state and state is not None:
        raise HTTPException(status_code=400, detail="This event does not support a state.")

    option = None
    if event_type.option_category:
        if event_type.option_required and option_id is None:
            raise HTTPException(status_code=400, detail=f"Choose a {event_type.option_category.lower().replace('_', ' ')}.")
        option = db.get(SavedOption, option_id) if option_id is not None else None
        if option_id is not None and (
            option is None or not option.is_active or option.dog_id != dog_id
            or option.category != event_type.option_category
        ):
            raise HTTPException(status_code=400, detail="Invalid saved option.")
    elif option_id is not None:
        raise HTTPException(status_code=400, detail="This event does not support a saved option.")

    if event_type.numeric_required and numeric_value is None:
        raise HTTPException(status_code=400, detail=f"{event_type.numeric_label or 'Value'} is required.")
    if numeric_value is not None and not event_type.supports_numeric:
        raise HTTPException(status_code=400, detail="This event does not support a numeric value.")
    if numeric_value is not None and event_type.allowed_units:
        if unit not in event_type.allowed_units:
            raise HTTPException(status_code=400, detail="Choose a valid unit.")
    if unit and numeric_value is None:
        raise HTTPException(status_code=400, detail="A unit requires a numeric value.")
    if event_type.severity_required and severity is None:
        raise HTTPException(status_code=400, detail="Severity is required.")
    if severity is not None and not event_type.supports_severity:
        raise HTTPException(status_code=400, detail="This event does not support severity.")
    return option


def get_event_context(db: Session, event_id: uuid.UUID) -> tuple[Event, EventType]:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    event_type = db.get(EventType, event.event_type_id)
    if event_type is None:
        raise HTTPException(status_code=500, detail="Event type not found.")
    return event, event_type


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(data: EventCreate, db: DatabaseSession) -> EventResponse:
    if db.get(Dog, data.dog_id) is None:
        raise HTTPException(status_code=404, detail="Dog not found.")
    event_type = db.get(EventType, data.event_type_id)
    if event_type is None or not event_type.is_active:
        raise HTTPException(status_code=400, detail="Invalid event type.")
    option = validate_details(
        dog_id=data.dog_id, event_type=event_type, state=data.state,
        option_id=data.option_id, numeric_value=data.numeric_value,
        unit=data.unit, severity=data.severity, db=db,
    )
    now = datetime.now(timezone.utc)
    event = Event(
        id=uuid.uuid4(), dog_id=data.dog_id, event_type_id=data.event_type_id,
        event_time=data.event_time or now, state=data.state,
        location=data.location, treat_type_id=None, option_id=data.option_id,
        numeric_value=data.numeric_value, unit=data.unit, severity=data.severity,
        notes=data.notes, entry_method=data.entry_method, created_at=now, updated_at=now,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return build_event_response(event, event_type, option)


@router.get("", response_model=list[EventResponse])
def list_events(
    dog_id: uuid.UUID, db: DatabaseSession,
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> list[EventResponse]:
    statement = (
        select(Event, EventType, SavedOption)
        .join(EventType, Event.event_type_id == EventType.id)
        .outerjoin(SavedOption, Event.option_id == SavedOption.id)
        .where(Event.dog_id == dog_id)
        .order_by(Event.event_time.desc())
    )
    if start_time is not None:
        statement = statement.where(Event.event_time >= start_time)
    if end_time is not None:
        statement = statement.where(Event.event_time < end_time)
    return [build_event_response(event, event_type, option) for event, event_type, option in db.execute(statement).all()]


@router.patch("/{event_id}", response_model=EventResponse)
def update_event(event_id: uuid.UUID, data: EventUpdate, db: DatabaseSession) -> EventResponse:
    event, event_type = get_event_context(db, event_id)
    values = data.model_dump(exclude_unset=True)
    effective = {
        "state": values.get("state", event.state),
        "option_id": values.get("option_id", event.option_id),
        "numeric_value": values.get("numeric_value", event.numeric_value),
        "unit": values.get("unit", event.unit),
        "severity": values.get("severity", event.severity),
    }
    option = validate_details(dog_id=event.dog_id, event_type=event_type, db=db, **effective)
    if "event_time" in values and values["event_time"] is None:
        raise HTTPException(status_code=400, detail="Event time cannot be empty.")
    for field, value in values.items():
        setattr(event, field, value)
    event.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    return build_event_response(event, event_type, option)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: uuid.UUID, db: DatabaseSession) -> None:
    event, _ = get_event_context(db, event_id)
    db.delete(event)
    db.commit()
