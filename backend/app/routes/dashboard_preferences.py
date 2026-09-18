from __future__ import annotations

import uuid
from datetime import datetime, timezone
from fastapi import (
    APIRouter,
    HTTPException,
    status,
)
from sqlalchemy import select
from app.models.chart_preference import (
    ChartType,
    DogChartPreference,
)
from app.models.ui_preference import DogUIPreference
from app.schemas.chart_preference import (
    ChartPreferenceResponse,
    ChartPreferencesUpdate,
)
from app.schemas.ui_preference import (
    UIPreferenceResponse,
    UIPreferenceUpdate,
)
from app.security import CurrentUser, DatabaseSession, require_owned_dog


router = APIRouter(
    prefix="/dogs",
    tags=["dashboard-preferences"],
)

def ensure_dog_access(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> None:
    require_owned_dog(db, dog_id, user)


@router.get(
    "/{dog_id}/chart-preferences",
    response_model=list[ChartPreferenceResponse],
)
def get_chart_preferences(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> list[ChartPreferenceResponse]:
    ensure_dog_access(dog_id, db, user)

    statement = (
        select(
            ChartType,
            DogChartPreference,
        )
        .join(
            DogChartPreference,
            DogChartPreference.chart_type_id
            == ChartType.id,
        )
        .where(
            DogChartPreference.dog_id == dog_id,
            ChartType.is_active.is_(True),
        )
        .order_by(
            DogChartPreference.display_order,
            ChartType.default_order,
        )
    )

    rows = db.execute(statement).all()

    return [
        ChartPreferenceResponse(
            code=chart.code,
            display_name=chart.display_name,
            description=chart.description,
            required_event_codes=(
                chart.required_event_codes or []
            ),
            is_enabled=preference.is_enabled,
            display_order=preference.display_order,
        )
        for chart, preference in rows
    ]


@router.put(
    "/{dog_id}/chart-preferences",
    response_model=list[ChartPreferenceResponse],
)
def update_chart_preferences(
    dog_id: uuid.UUID,
    data: ChartPreferencesUpdate,
    db: DatabaseSession,
    user: CurrentUser,
) -> list[ChartPreferenceResponse]:
    ensure_dog_access(dog_id, db, user)

    chart_types = db.scalars(
        select(ChartType).where(
            ChartType.is_active.is_(True)
        )
    ).all()

    chart_by_code = {
        chart.code: chart
        for chart in chart_types
    }

    supplied_codes = [
        item.code
        for item in data.preferences
    ]

    if len(supplied_codes) != len(
        set(supplied_codes)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate chart codes are not allowed.",
        )

    unknown_codes = [
        code
        for code in supplied_codes
        if code not in chart_by_code
    ]

    if unknown_codes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unknown chart codes: "
                + ", ".join(unknown_codes)
            ),
        )

    now = datetime.now(timezone.utc)

    for item in data.preferences:
        chart = chart_by_code[item.code]

        preference = db.get(
            DogChartPreference,
            {
                "dog_id": dog_id,
                "chart_type_id": chart.id,
            },
        )

        if preference is None:
            preference = DogChartPreference(
                dog_id=dog_id,
                chart_type_id=chart.id,
                is_enabled=item.is_enabled,
                display_order=item.display_order,
                created_at=now,
                updated_at=now,
            )

            db.add(preference)

        else:
            preference.is_enabled = (
                item.is_enabled
            )

            preference.display_order = (
                item.display_order
            )

            preference.updated_at = now

    db.commit()

    return get_chart_preferences(
        dog_id,
        db,
        user,
    )


@router.get(
    "/{dog_id}/ui-preferences",
    response_model=UIPreferenceResponse,
)
def get_ui_preferences(
    dog_id: uuid.UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> UIPreferenceResponse:
    ensure_dog_access(dog_id, db, user)

    preference = db.get(
        DogUIPreference,
        dog_id,
    )

    if preference is None:
        now = datetime.now(timezone.utc)

        preference = DogUIPreference(
            dog_id=dog_id,
            accent_color="#6D63D9",
            updated_at=now,
        )

        db.add(preference)
        db.commit()
        db.refresh(preference)

    return UIPreferenceResponse(
        accent_color=preference.accent_color,
    )


@router.put(
    "/{dog_id}/ui-preferences",
    response_model=UIPreferenceResponse,
)
def update_ui_preferences(
    dog_id: uuid.UUID,
    data: UIPreferenceUpdate,
    db: DatabaseSession,
    user: CurrentUser,
) -> UIPreferenceResponse:
    ensure_dog_access(dog_id, db, user)

    preference = db.get(
        DogUIPreference,
        dog_id,
    )

    now = datetime.now(timezone.utc)

    if preference is None:
        preference = DogUIPreference(
            dog_id=dog_id,
            accent_color=data.accent_color,
            updated_at=now,
        )

        db.add(preference)

    else:
        preference.accent_color = (
            data.accent_color
        )

        preference.updated_at = now

    db.commit()
    db.refresh(preference)

    return UIPreferenceResponse(
        accent_color=preference.accent_color,
    )
