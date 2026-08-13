import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dog import Dog
from app.models.observation_period import ObservationPeriod
from app.models.saved_option import SavedOption
from app.schemas.observation_period import (
    ObservationPeriodCreate,
    ObservationPeriodResponse,
    ObservationPeriodUpdate,
)

router = APIRouter(prefix="/observation-periods", tags=["observation periods"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def build_response(
    period: ObservationPeriod,
    option: SavedOption | None,
) -> ObservationPeriodResponse:
    return ObservationPeriodResponse(
        id=period.id,
        dog_id=period.dog_id,
        start_time=period.start_time,
        end_time=period.end_time,
        status=period.status,
        reason_option_id=period.reason_option_id,
        reason_name=option.name if option else period.reason,
        notes=period.notes,
        peed_during=period.peed_during,
        pooped_during=period.pooped_during,
        potty_location=period.potty_location,
        likely_state=period.likely_state,
        camera_checked=period.camera_checked,
        created_at=period.created_at,
    )


def validate_reason(db: Session, dog_id: uuid.UUID, option_id: uuid.UUID) -> SavedOption:
    option = db.get(SavedOption, option_id)
    if (
        option is None
        or not option.is_active
        or option.dog_id != dog_id
        or option.category != "OBSERVATION_REASON"
    ):
        raise HTTPException(status_code=400, detail="Invalid observation reason.")
    return option


def ensure_no_overlap(
    db: Session,
    *,
    dog_id: uuid.UUID,
    start_time: datetime,
    end_time: datetime | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = select(ObservationPeriod.id).where(
        ObservationPeriod.dog_id == dog_id,
        or_(ObservationPeriod.end_time.is_(None), ObservationPeriod.end_time > start_time),
    )
    if end_time is not None:
        statement = statement.where(ObservationPeriod.start_time < end_time)
    if exclude_id is not None:
        statement = statement.where(ObservationPeriod.id != exclude_id)
    if db.scalar(statement.limit(1)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This observation period overlaps an existing period.",
        )


@router.post("", response_model=ObservationPeriodResponse, status_code=status.HTTP_201_CREATED)
def create_period(
    data: ObservationPeriodCreate,
    db: DatabaseSession,
) -> ObservationPeriodResponse:
    if db.get(Dog, data.dog_id) is None:
        raise HTTPException(status_code=404, detail="Dog not found.")
    option = validate_reason(db, data.dog_id, data.reason_option_id)
    now = datetime.now(timezone.utc)
    start_time = data.start_time or now
    if data.end_time is not None and data.end_time <= start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time.")
    ensure_no_overlap(
        db,
        dog_id=data.dog_id,
        start_time=start_time,
        end_time=data.end_time,
    )
    period = ObservationPeriod(
        id=uuid.uuid4(),
        dog_id=data.dog_id,
        start_time=start_time,
        end_time=data.end_time,
        status="UNOBSERVED",
        reason=option.name,
        reason_option_id=option.id,
        notes=data.notes,
        peed_during=data.peed_during,
        pooped_during=data.pooped_during,
        potty_location=data.potty_location,
        likely_state=data.likely_state,
        camera_checked=data.camera_checked,
        created_at=now,
        updated_at=now,
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return build_response(period, option)


@router.get("", response_model=list[ObservationPeriodResponse])
def list_periods(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    active_only: bool = Query(default=False),
) -> list[ObservationPeriodResponse]:
    statement = (
        select(ObservationPeriod, SavedOption)
        .outerjoin(SavedOption, ObservationPeriod.reason_option_id == SavedOption.id)
        .where(ObservationPeriod.dog_id == dog_id)
        .order_by(ObservationPeriod.start_time.desc())
    )
    if active_only:
        statement = statement.where(ObservationPeriod.end_time.is_(None))
    if start_time is not None:
        statement = statement.where(
            or_(ObservationPeriod.end_time.is_(None), ObservationPeriod.end_time > start_time)
        )
    if end_time is not None:
        statement = statement.where(ObservationPeriod.start_time < end_time)
    return [build_response(period, option) for period, option in db.execute(statement).all()]


@router.patch("/{period_id}", response_model=ObservationPeriodResponse)
def update_period(
    period_id: uuid.UUID,
    data: ObservationPeriodUpdate,
    db: DatabaseSession,
) -> ObservationPeriodResponse:
    period = db.get(ObservationPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Observation period not found.")
    values = data.model_dump(exclude_unset=True)
    start_time = values.get("start_time", period.start_time)
    end_time = values.get("end_time", period.end_time)
    if start_time is None:
        raise HTTPException(status_code=400, detail="Start time cannot be empty.")
    if end_time is not None and end_time <= start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time.")
    option_id = values.get("reason_option_id", period.reason_option_id)
    if option_id is None:
        raise HTTPException(status_code=400, detail="Observation reason is required.")
    option = validate_reason(db, period.dog_id, option_id)
    ensure_no_overlap(
        db,
        dog_id=period.dog_id,
        start_time=start_time,
        end_time=end_time,
        exclude_id=period.id,
    )
    for field, value in values.items():
        setattr(period, field, value)
    period.reason = option.name
    period.reason_option_id = option.id
    period.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(period)
    return build_response(period, option)


@router.post("/{period_id}/end", response_model=ObservationPeriodResponse)
def end_period(period_id: uuid.UUID, db: DatabaseSession) -> ObservationPeriodResponse:
    period = db.get(ObservationPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Observation period not found.")
    if period.end_time is not None:
        raise HTTPException(status_code=400, detail="Observation period has already ended.")
    now = datetime.now(timezone.utc)
    if now <= period.start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time.")
    period.end_time = now
    period.updated_at = now
    option = db.get(SavedOption, period.reason_option_id) if period.reason_option_id else None
    db.commit()
    db.refresh(period)
    return build_response(period, option)


@router.delete("/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_period(period_id: uuid.UUID, db: DatabaseSession) -> None:
    period = db.get(ObservationPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Observation period not found.")
    db.delete(period)
    db.commit()
