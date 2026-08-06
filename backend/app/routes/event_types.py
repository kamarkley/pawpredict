from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.event_type import EventType
from app.schemas.event_type import EventTypeResponse

router = APIRouter(
    prefix="/event-types",
    tags=["event types"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[EventTypeResponse])
def list_event_types(db: DatabaseSession) -> list[EventType]:
    statement = (
        select(EventType)
        .where(EventType.is_active.is_(True))
        .order_by(EventType.id)
    )

    return list(db.scalars(statement).all())