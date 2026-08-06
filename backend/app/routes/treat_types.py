from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.treat_type import TreatType
from app.schemas.treat_type import TreatTypeResponse

router = APIRouter(
    prefix="/treat-types",
    tags=["treat types"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[TreatTypeResponse])
def list_treat_types(db: DatabaseSession) -> list[TreatType]:
    statement = (
        select(TreatType)
        .where(TreatType.is_active.is_(True))
        .order_by(TreatType.name)
    )

    return list(db.scalars(statement).all())