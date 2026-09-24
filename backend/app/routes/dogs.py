import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.models.chart_preference import ChartType, DogChartPreference
from app.models.dog import Dog
from app.models.dog_event_preference import DogEventPreference
from app.models.dog_stat_preference import DogStatPreference
from app.models.event_type import EventType
from app.models.saved_option import SavedOption
from app.models.stat_type import StatType
from app.models.treat_type import TreatType
from app.models.ui_preference import DogUIPreference
from app.schemas.dog import DogCreate, DogResponse, DogUpdate
from app.security import CurrentUser, DatabaseSession, require_owned_dog

router = APIRouter(prefix="/dogs", tags=["dogs"])

DEFAULT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("POTTY_RESULT", "Outside"), ("POTTY_RESULT", "Accident"),
    ("POTTY_RESULT", "Pee pad"), ("POTTY_RESULT", "Litter box"),
    ("SLEEP_LOCATION", "Crate"), ("SLEEP_LOCATION", "Kennel"),
    ("SLEEP_LOCATION", "Dog bed"), ("SLEEP_LOCATION", "Couch"),
    ("SLEEP_LOCATION", "Owner's bed"),
    ("OBSERVATION_REASON", "Work"), ("OBSERVATION_REASON", "Errands"),
    ("OBSERVATION_REASON", "Daycare"), ("OBSERVATION_REASON", "Training class"),
    ("OBSERVATION_REASON", "With sitter"), ("OBSERVATION_REASON", "Boarding"),
    ("OBSERVATION_REASON", "Sleeping"), ("OBSERVATION_REASON", "Other"),
    ("SYMPTOM", "Vomiting"), ("SYMPTOM", "Diarrhea"),
    ("SYMPTOM", "Coughing"), ("SYMPTOM", "Itching"),
    ("SYMPTOM", "Lethargy"), ("SYMPTOM", "Loss of appetite"),
    ("SOCIAL_ACTIVITY", "Dog park"), ("SOCIAL_ACTIVITY", "Daycare"),
    ("SOCIAL_ACTIVITY", "Training class"), ("SOCIAL_ACTIVITY", "Playdate"),
    ("SOCIAL_ACTIVITY", "Public outing"),
    ("BEHAVIOR", "Barking"), ("BEHAVIOR", "Chewing"),
    ("BEHAVIOR", "Biting"), ("BEHAVIOR", "Whining"),
    ("BEHAVIOR", "Separation distress"), ("BEHAVIOR", "Calm behavior"),
    ("BEHAVIOR", "Successful settling"),
    ("GROOMING", "Bath"), ("GROOMING", "Brushing"), ("GROOMING", "Nail trim"),
)


def seed_new_dog(db: DatabaseSession, dog: Dog, now: datetime) -> None:
    event_types = list(db.scalars(select(EventType).where(EventType.is_active.is_(True))).all())
    for event_type in event_types:
        db.add(
            DogEventPreference(
                dog_id=dog.id,
                event_type_id=event_type.id,
                is_enabled=event_type.default_enabled,
                display_order=event_type.id,
                created_at=now,
                updated_at=now,
            )
        )

    stat_types = list(db.scalars(select(StatType).order_by(StatType.display_order)).all())
    for stat_type in stat_types:
        db.add(
            DogStatPreference(
                dog_id=dog.id,
                stat_code=stat_type.code,
                is_enabled=stat_type.default_enabled,
                display_order=stat_type.display_order,
                created_at=now,
                updated_at=now,
            )
        )

    chart_types = list(db.scalars(select(ChartType).where(ChartType.is_active.is_(True))).all())
    for chart in chart_types:
        db.add(
            DogChartPreference(
                dog_id=dog.id,
                chart_type_id=chart.id,
                is_enabled=chart.default_enabled,
                display_order=chart.default_order,
                created_at=now,
                updated_at=now,
            )
        )

    db.add(DogUIPreference(dog_id=dog.id, accent_color="#6D63D9", updated_at=now))
    for category, name in DEFAULT_OPTIONS:
        db.add(
            SavedOption(
                id=uuid.uuid4(),
                dog_id=dog.id,
                category=category,
                name=name,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )

    # Mirror the original configurable-tracking seed behavior for newly
    # onboarded dogs so the required Treat selector is useful immediately.
    treat_names = db.scalars(
        select(TreatType.name)
        .where(TreatType.is_active.is_(True))
        .order_by(TreatType.name)
    ).all()
    for name in treat_names:
        db.add(
            SavedOption(
                id=uuid.uuid4(),
                dog_id=dog.id,
                category="TREAT",
                name=name,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )


@router.get("", response_model=list[DogResponse])
def list_dogs(db: DatabaseSession, user: CurrentUser) -> list[Dog]:
    return list(
        db.scalars(
            select(Dog)
            .where(Dog.owner_user_id == user.id)
            .order_by(Dog.name)
        ).all()
    )


@router.post("", response_model=DogResponse, status_code=status.HTTP_201_CREATED)
def create_dog(data: DogCreate, db: DatabaseSession, user: CurrentUser) -> Dog:
    if data.birth_date > date.today():
        raise HTTPException(status_code=400, detail="Birth date cannot be in the future.")
    now = datetime.now(timezone.utc)
    dog = Dog(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name=data.name.strip(),
        birth_date=data.birth_date,
        breed=data.breed.strip() if data.breed else None,
        sex=data.sex,
        weight_lbs=data.weight_lbs,
        neutered=data.neutered,
        created_at=now,
        updated_at=now,
    )
    db.add(dog)
    db.flush()
    seed_new_dog(db, dog, now)
    db.commit()
    db.refresh(dog)
    return dog


@router.get("/{dog_id}", response_model=DogResponse)
def get_dog(dog_id: uuid.UUID, db: DatabaseSession, user: CurrentUser) -> Dog:
    return require_owned_dog(db, dog_id, user)


@router.patch("/{dog_id}", response_model=DogResponse)
def update_dog(
    dog_id: uuid.UUID,
    data: DogUpdate,
    db: DatabaseSession,
    user: CurrentUser,
) -> Dog:
    dog = require_owned_dog(db, dog_id, user)
    if data.birth_date is not None and data.birth_date > date.today():
        raise HTTPException(status_code=400, detail="Birth date cannot be in the future.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dog, field, value.strip() if isinstance(value, str) else value)
    dog.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(dog)
    return dog
