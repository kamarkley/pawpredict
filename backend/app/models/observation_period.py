import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

observation_status_enum = ENUM(
    "OBSERVED",
    "UNOBSERVED",
    name="observation_status",
    create_type=False,
)


class ObservationPeriod(Base):
    __tablename__ = "observation_periods"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    dog_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dogs.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        observation_status_enum,
        nullable=False,
        default="UNOBSERVED",
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason_option_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("saved_options.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    peed_during: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    pooped_during: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    potty_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    likely_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    camera_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
