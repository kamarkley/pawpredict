import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dog import Dog
from app.models.event import Event
from app.models.event_type import EventType
from app.models.treat_type import TreatType
from app.schemas.event import EventCreate, EventResponse

router = APIRouter(
    prefix="/events",
    tags=["events"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


def build_event_response(
    event: Event,
    event_type: EventType,
    treat: TreatType | None,
) -> EventResponse:
    return EventResponse(
        id=event.id,
        dog_id=event.dog_id,
        event_type_id=event.event_type_id,
        event_type_code=event_type.code,
        event_type_name=event_type.display_name,
        event_time=event.event_time,
        state=event.state,
        location=event.location,
        treat_type_id=event.treat_type_id,
        treat_name=treat.name if treat else None,
        notes=event.notes,
        entry_method=event.entry_method,
        created_at=event.created_at,
    )


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    event_data: EventCreate,
    db: DatabaseSession,
) -> EventResponse:
    dog = db.get(Dog, event_data.dog_id)

    if dog is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dog not found.",
        )

    event_type = db.get(EventType, event_data.event_type_id)

    if event_type is None or not event_type.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid event type.",
        )

    if event_data.state is not None and not event_type.supports_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This event type does not support a start or end state.",
        )

    if event_type.supports_state and event_data.state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This event requires a start or end state.",
        )

    if (
        event_data.location != "NOT_APPLICABLE"
        and not event_type.supports_location
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This event type does not support a location.",
        )

    if event_type.supports_location and event_data.location == "NOT_APPLICABLE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This event requires an inside or outside location.",
        )

    treat: TreatType | None = None

    if event_data.treat_type_id is not None:
        if not event_type.supports_treat:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This event type does not support a treat selection.",
            )

        treat = db.get(TreatType, event_data.treat_type_id)

        if treat is None or not treat.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid treat type.",
            )

    if event_type.supports_treat and event_data.treat_type_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A treat type is required.",
        )

    now = datetime.now(timezone.utc)

    event = Event(
        id=uuid.uuid4(),
        dog_id=event_data.dog_id,
        event_type_id=event_data.event_type_id,
        event_time=event_data.event_time or now,
        state=event_data.state,
        location=event_data.location,
        treat_type_id=event_data.treat_type_id,
        notes=event_data.notes,
        entry_method=event_data.entry_method,
        created_at=now,
        updated_at=now,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return build_event_response(event, event_type, treat)


@router.get("", response_model=list[EventResponse])
def list_events(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> list[EventResponse]:
    statement = (
        select(Event, EventType, TreatType)
        .join(EventType, Event.event_type_id == EventType.id)
        .outerjoin(TreatType, Event.treat_type_id == TreatType.id)
        .where(Event.dog_id == dog_id)
        .order_by(Event.event_time.desc())
    )

    if start_time is not None:
        statement = statement.where(Event.event_time >= start_time)

    if end_time is not None:
        statement = statement.where(Event.event_time < end_time)

    rows = db.execute(statement).all()

    return [
        build_event_response(event, event_type, treat)
        for event, event_type, treat in rows
    ]