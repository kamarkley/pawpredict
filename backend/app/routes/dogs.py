import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dog import Dog
from app.schemas.dog import DogResponse

router = APIRouter(
    prefix="/dogs",
    tags=["dogs"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[DogResponse])
def list_dogs(db: DatabaseSession) -> list[Dog]:
    statement = select(Dog).order_by(Dog.name)
    return list(db.scalars(statement).all())


@router.get("/{dog_id}", response_model=DogResponse)
def get_dog(dog_id: uuid.UUID, db: DatabaseSession) -> Dog:
    dog = db.get(Dog, dog_id)

    if dog is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dog not found.",
        )

    return dog