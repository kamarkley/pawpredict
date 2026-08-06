import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dog import Dog
from app.models.saved_option import SavedOption
from app.schemas.saved_option import SavedOptionCreate, SavedOptionResponse, SavedOptionUpdate

router = APIRouter(prefix="/saved-options", tags=["saved options"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[SavedOptionResponse])
def list_saved_options(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    category: str | None = Query(default=None),
    include_inactive: bool = False,
) -> list[SavedOption]:
    statement = select(SavedOption).where(SavedOption.dog_id == dog_id)
    if category:
        statement = statement.where(SavedOption.category == category.upper())
    if not include_inactive:
        statement = statement.where(SavedOption.is_active.is_(True))
    statement = statement.order_by(SavedOption.category, SavedOption.name)
    return list(db.scalars(statement).all())


@router.post("", response_model=SavedOptionResponse, status_code=status.HTTP_201_CREATED)
def create_saved_option(data: SavedOptionCreate, db: DatabaseSession) -> SavedOption:
    if db.get(Dog, data.dog_id) is None:
        raise HTTPException(status_code=404, detail="Dog not found.")

    option = SavedOption(
        id=uuid.uuid4(), dog_id=data.dog_id, category=data.category.strip().upper(),
        name=data.name.strip(), is_active=True,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
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
            db.commit()
            db.refresh(existing)
            return existing
        raise HTTPException(status_code=409, detail="That option already exists.") from exc
    db.refresh(option)
    return option


@router.patch("/{option_id}", response_model=SavedOptionResponse)
def update_saved_option(option_id: uuid.UUID, data: SavedOptionUpdate, db: DatabaseSession) -> SavedOption:
    option = db.get(SavedOption, option_id)
    if option is None:
        raise HTTPException(status_code=404, detail="Saved option not found.")
    if data.name is not None:
        option.name = data.name.strip()
    if data.is_active is not None:
        option.is_active = data.is_active
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="That option already exists.") from exc
    db.refresh(option)
    return option
