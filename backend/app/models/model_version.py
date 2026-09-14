from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ModelVersion(Base):
    """
    Immutable-ish metadata describing one PawPredict model configuration.

    The trained estimator is still built by PawPredict's ML service. This table
    is the control-plane record: what the model is, how it was trained, its
    lifecycle status, and enough information to reproduce it.
    """

    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint(
            "dog_id",
            "target",
            "version_label",
            name="model_versions_unique_dog_target_label",
        ),
        CheckConstraint(
            "target IN ('ANY', 'PEE', 'POOP')",
            name="model_versions_target_valid",
        ),
        CheckConstraint(
            "status IN ('CANDIDATE', 'SHADOW', 'PRODUCTION', 'RETIRED', 'REJECTED')",
            name="model_versions_status_valid",
        ),
        CheckConstraint(
            "calibration_method IN ('raw', 'sigmoid', 'isotonic')",
            name="model_versions_calibration_valid",
        ),
        Index(
            "uq_model_versions_one_production_per_target",
            "dog_id",
            "target",
            unique=True,
            postgresql_where=text("status = 'PRODUCTION'"),
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

    target: Mapped[str] = mapped_column(Text, nullable=False)
    version_label: Mapped[str] = mapped_column(Text, nullable=False)
    model_family: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="logistic_regression",
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="CANDIDATE",
    )

    feature_names: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
    )
    training_window_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    sample_weight_half_life_days: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    calibration_method: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="raw",
    )

    trained_through: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    training_examples: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    positive_examples: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    prevalence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    git_commit: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_uri: Mapped[str | None] = mapped_column(Text, nullable=True)

    config_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
