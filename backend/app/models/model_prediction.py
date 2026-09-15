from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ModelPrediction(Base):
    """
    Immutable prediction ledger row.

    Every row is tied to the exact registered model version that produced it.
    CHAMPION rows represent the model serving the user; SHADOW rows are silent
    challenger scores. Outcomes are resolved only after the prediction horizon
    closes and only when the window is observable.
    """

    __tablename__ = "model_predictions"
    __table_args__ = (
        CheckConstraint(
            "target IN ('ANY', 'PEE', 'POOP')",
            name="model_predictions_target_valid",
        ),
        CheckConstraint(
            "role IN ('CHAMPION', 'SHADOW')",
            name="model_predictions_role_valid",
        ),
        CheckConstraint(
            "outcome_status IN ('PENDING', 'RESOLVED', 'INELIGIBLE')",
            name="model_predictions_outcome_status_valid",
        ),
        CheckConstraint(
            "probability >= 0 AND probability <= 1",
            name="model_predictions_probability_valid",
        ),
        UniqueConstraint(
            "dog_id",
            "model_version_id",
            "target",
            "role",
            "prediction_bucket_time",
            name="model_predictions_unique_bucket",
        ),
        Index(
            "idx_model_predictions_pending",
            "dog_id",
            "outcome_status",
            "horizon_end",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    dog_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dogs.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )

    target: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)

    prediction_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    prediction_bucket_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    horizon_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    probability: Mapped[float] = mapped_column(Float, nullable=False)

    feature_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    outcome_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="PENDING",
    )
    observed_outcome: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    outcome_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ineligible_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
