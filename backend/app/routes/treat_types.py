from fastapi import APIRouter
from sqlalchemy import select

from app.models.treat_type import TreatType
from app.schemas.treat_type import TreatTypeResponse
from app.security import CurrentUser, DatabaseSession

router = APIRouter(prefix="/treat-types", tags=["treat types"])


@router.get("", response_model=list[TreatTypeResponse])
def list_treat_types(db: DatabaseSession, user: CurrentUser) -> list[TreatType]:
    del user
    return list(
        db.scalars(
            select(TreatType)
            .where(TreatType.is_active.is_(True))
            .order_by(TreatType.name)
        ).all()
    )
