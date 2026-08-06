import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dog import Dog
from app.models.dog_stat_preference import DogStatPreference
from app.models.stat_type import StatType
from app.schemas.stat import StatPreferenceItem, StatPreferencesUpdate

router = APIRouter(prefix="/dogs/{dog_id}/stat-preferences", tags=["stat preferences"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[StatPreferenceItem])
def get_preferences(dog_id: uuid.UUID, db: DatabaseSession) -> list[StatPreferenceItem]:
    if db.get(Dog, dog_id) is None:
        raise HTTPException(status_code=404, detail="Dog not found.")

    rows = db.execute(
        select(StatType, DogStatPreference)
        .outerjoin(
            DogStatPreference,
            (DogStatPreference.stat_code == StatType.code)
            & (DogStatPreference.dog_id == dog_id),
        )
        .order_by(DogStatPreference.display_order.nulls_last(), StatType.display_order)
    ).all()

    return [
        StatPreferenceItem(
            code=stat.code,
            display_name=stat.display_name,
            description=stat.description,
            is_enabled=(preference.is_enabled if preference else stat.default_enabled),
            display_order=(preference.display_order if preference else stat.display_order),
        )
        for stat, preference in rows
    ]


@router.put("", response_model=list[StatPreferenceItem])
def update_preferences(
    dog_id: uuid.UUID,
    data: StatPreferencesUpdate,
    db: DatabaseSession,
) -> list[StatPreferenceItem]:
    if db.get(Dog, dog_id) is None:
        raise HTTPException(status_code=404, detail="Dog not found.")

    valid_codes = set(db.scalars(select(StatType.code)).all())
    requested = data.stat_codes
    if len(requested) != len(set(requested)):
        raise HTTPException(status_code=400, detail="Dashboard stats cannot be duplicated.")
    if not set(requested).issubset(valid_codes):
        raise HTTPException(status_code=400, detail="One or more dashboard stats are invalid.")

    now = datetime.now(timezone.utc)
    requested_order = {code: index for index, code in enumerate(requested, start=1)}
    stat_types = db.scalars(select(StatType).order_by(StatType.display_order)).all()

    for stat in stat_types:
        preference = db.get(DogStatPreference, (dog_id, stat.code))
        enabled = stat.code in requested_order
        order = requested_order.get(stat.code, stat.display_order + 100)
        if preference is None:
            db.add(
                DogStatPreference(
                    dog_id=dog_id,
                    stat_code=stat.code,
                    is_enabled=enabled,
                    display_order=order,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            preference.is_enabled = enabled
            preference.display_order = order
            preference.updated_at = now

    db.commit()
    return get_preferences(dog_id, db)
