import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.models.dog_event_preference import DogEventPreference
from app.models.event_type import EventType
from app.schemas.event_type import EventTypeResponse
from app.security import CurrentUser, DatabaseSession, require_owned_dog

router = APIRouter(prefix="/event-types", tags=["event types"])


@router.get("", response_model=list[EventTypeResponse])
def list_event_types(
    db: DatabaseSession,
    user: CurrentUser,
    dog_id: uuid.UUID | None = Query(default=None),
    enabled_only: bool = False,
    include_inactive: bool = False,
) -> list[EventType]:
    statement = select(EventType)
    if not include_inactive:
        statement = statement.where(EventType.is_active.is_(True))
    if dog_id is not None:
        require_owned_dog(db, dog_id, user)
    if dog_id is not None and enabled_only:
        statement = statement.join(
            DogEventPreference,
            (DogEventPreference.event_type_id == EventType.id)
            & (DogEventPreference.dog_id == dog_id),
        ).where(DogEventPreference.is_enabled.is_(True))
        statement = statement.order_by(DogEventPreference.display_order, EventType.id)
    else:
        statement = statement.order_by(EventType.id)
    return list(db.scalars(statement).all())
