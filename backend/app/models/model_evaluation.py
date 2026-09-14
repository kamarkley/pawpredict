from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ModelEvaluation(Base):
    """
    One evaluation window for one model version.

    Keeping evaluations separate from ModelVersion means one version can have:
    offline validation, rolling backtests, shadow results, and later monitoring
    windows without overwriting its history.
    """

    __tablename__ = "model_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "model_version_id",
            "evaluation_key",
            name="model_evaluations_unique_key",
        ),
        CheckConstraint(
            "evaluation_type IN ("
            "'TRAIN', 'VALIDATION', 'ROLLING_BACKTEST', "
            "'HISTORICAL_CONFIRMATION', 'PROSPECTIVE_SHADOW', "
            "'PRODUCTION_MONITORING'"
            ")",
            name="model_evaluations_type_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False,
    )

    evaluation_key: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_type: Mapped[str] = mapped_column(Text, nullable=False)
    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    snapshot_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    positive_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prevalence: Mapped[float | None] = mapped_column(Float, nullable=True)

    pr_auc: Mapped[float | None] = mapped_column(Float, nullable=True)
    roc_auc: Mapped[float | None] = mapped_column(Float, nullable=True)
    brier_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ece: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibration_intercept: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibration_slope: Mapped[float | None] = mapped_column(Float, nullable=True)

    event_capture_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    alert_episodes_per_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    episode_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    alert_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
