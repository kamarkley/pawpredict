import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dog import Dog
from app.schemas.dog import DogResponse, DogUpdate

router = APIRouter(prefix="/dogs", tags=["dogs"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[DogResponse])
def list_dogs(db: DatabaseSession) -> list[Dog]:
    return list(db.scalars(select(Dog).order_by(Dog.name)).all())


@router.get("/{dog_id}", response_model=DogResponse)
def get_dog(dog_id: uuid.UUID, db: DatabaseSession) -> Dog:
    dog = db.get(Dog, dog_id)
    if dog is None:
        raise HTTPException(status_code=404, detail="Dog not found.")
    return dog


@router.patch("/{dog_id}", response_model=DogResponse)
def update_dog(dog_id: uuid.UUID, data: DogUpdate, db: DatabaseSession) -> Dog:
    dog = db.get(Dog, dog_id)
    if dog is None:
        raise HTTPException(status_code=404, detail="Dog not found.")
    if data.birth_date is not None and data.birth_date > date.today():
        raise HTTPException(status_code=400, detail="Birth date cannot be in the future.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dog, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(dog)
    return dog
