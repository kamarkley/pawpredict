import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.saved_option import SavedOption
from app.schemas.saved_option import SavedOptionCreate, SavedOptionResponse, SavedOptionUpdate
from app.security import CurrentUser, DatabaseSession, require_owned_dog

router = APIRouter(prefix="/saved-options", tags=["saved options"])


@router.get("", response_model=list[SavedOptionResponse])
def list_saved_options(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    user: CurrentUser,
    category: str | None = Query(default=None),
    include_inactive: bool = False,
) -> list[SavedOption]:
    require_owned_dog(db, dog_id, user)
    statement = select(SavedOption).where(SavedOption.dog_id == dog_id)
    if category:
        statement = statement.where(SavedOption.category == category.upper())
    if not include_inactive:
        statement = statement.where(SavedOption.is_active.is_(True))
    return list(db.scalars(statement.order_by(SavedOption.category, SavedOption.name)).all())


@router.post("", response_model=SavedOptionResponse, status_code=status.HTTP_201_CREATED)
def create_saved_option(
    data: SavedOptionCreate,
    db: DatabaseSession,
    user: CurrentUser,
) -> SavedOption:
    require_owned_dog(db, data.dog_id, user)
    now = datetime.now(timezone.utc)
    option = SavedOption(
        id=uuid.uuid4(),
        dog_id=data.dog_id,
        category=data.category.strip().upper(),
        name=data.name.strip(),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(option)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(
            select(SavedOption).where(
                SavedOption.dog_id == data.dog_id,
                SavedOption.category == data.category.strip().upper(),
                func.lower(SavedOption.name) == data.name.strip().lower(),
            )
        )
        if existing and not existing.is_active:
            existing.is_active = True
            existing.updated_at = now
            db.commit()
            db.refresh(existing)
            return existing
        raise HTTPException(status_code=409, detail="That option already exists.") from exc
    db.refresh(option)
    return option


@router.patch("/{option_id}", response_model=SavedOptionResponse)
def update_saved_option(
    option_id: uuid.UUID,
    data: SavedOptionUpdate,
    db: DatabaseSession,
    user: CurrentUser,
) -> SavedOption:
    option = db.get(SavedOption, option_id)
    if option is None:
        raise HTTPException(status_code=404, detail="Saved option not found.")
    require_owned_dog(db, option.dog_id, user)
    if data.name is not None:
        option.name = data.name.strip()
    if data.is_active is not None:
        option.is_active = data.is_active
    option.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="That option already exists.") from exc
    db.refresh(option)
    return option
