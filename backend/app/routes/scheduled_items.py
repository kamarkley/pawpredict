import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.models.scheduled_item import ScheduledItem
from app.schemas.scheduled_item import ScheduledItemCreate, ScheduledItemResponse, ScheduledItemUpdate
from app.security import CurrentUser, DatabaseSession, require_owned_dog

router = APIRouter(prefix="/scheduled-items", tags=["scheduled items"])


def response(item: ScheduledItem) -> ScheduledItemResponse:
    return ScheduledItemResponse(
        **{field: getattr(item, field) for field in ScheduledItemResponse.model_fields}
    )


def owned_item(
    db: DatabaseSession,
    item_id: uuid.UUID,
    user: CurrentUser,
) -> ScheduledItem:
    item = db.get(ScheduledItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Scheduled item not found.")
    require_owned_dog(db, item.dog_id, user)
    return item


@router.post("", response_model=ScheduledItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    data: ScheduledItemCreate,
    db: DatabaseSession,
    user: CurrentUser,
) -> ScheduledItemResponse:
    require_owned_dog(db, data.dog_id, user)
    now = datetime.now(timezone.utc)
    item = ScheduledItem(
        id=uuid.uuid4(),
        **data.model_dump(),
        is_completed=False,
        linked_event_id=None,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return response(item)


@router.get("", response_model=list[ScheduledItemResponse])
def list_items(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    user: CurrentUser,
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> list[ScheduledItemResponse]:
    require_owned_dog(db, dog_id, user)
    stmt = (
        select(ScheduledItem)
        .where(ScheduledItem.dog_id == dog_id)
        .order_by(ScheduledItem.scheduled_for)
    )
    if start_time is not None:
        stmt = stmt.where(ScheduledItem.scheduled_for >= start_time)
    if end_time is not None:
        stmt = stmt.where(ScheduledItem.scheduled_for < end_time)
    return [response(item) for item in db.scalars(stmt).all()]


@router.patch("/{item_id}", response_model=ScheduledItemResponse)
def update_item(
    item_id: uuid.UUID,
    data: ScheduledItemUpdate,
    db: DatabaseSession,
    user: CurrentUser,
) -> ScheduledItemResponse:
    item = owned_item(db, item_id, user)
    values = data.model_dump(exclude_unset=True)
    start = values.get("scheduled_for", item.scheduled_for)
    end = values.get("end_time", item.end_time)
    if end is not None and end <= start:
        raise HTTPException(status_code=400, detail="End time must be after the scheduled start.")
    for field, value in values.items():
        setattr(item, field, value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return response(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: uuid.UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> None:
    item = owned_item(db, item_id, user)
    db.delete(item)
    db.commit()
