import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    event_data: EventCreate,
    db: DatabaseSession,
) -> Event:
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

    event = Event(
        id=uuid.uuid4(),
        dog_id=event_data.dog_id,
        event_type_id=event_data.event_type_id,
        event_time=event_data.event_time or datetime.now(timezone.utc),
        state=event_data.state,
        location=event_data.location,
        treat_type_id=event_data.treat_type_id,
        notes=event_data.notes,
        entry_method=event_data.entry_method,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event