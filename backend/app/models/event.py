import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

event_state_enum = ENUM("START", "END", name="event_state", create_type=False)
event_location_enum = ENUM(
    "INSIDE", "OUTSIDE", "NOT_APPLICABLE", name="event_location", create_type=False
)
entry_method_enum = ENUM("QUICK_LOG", "MANUAL", name="entry_method", create_type=False)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    dog_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dogs.id", ondelete="CASCADE"), nullable=False
    )
    event_type_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("event_types.id", ondelete="RESTRICT"), nullable=False
    )
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[Optional[str]] = mapped_column(event_state_enum, nullable=True)
    location: Mapped[str] = mapped_column(
        event_location_enum, nullable=False, default="NOT_APPLICABLE"
    )
    treat_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("treat_types.id", ondelete="SET NULL"), nullable=True
    )
    option_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saved_options.id", ondelete="SET NULL"), nullable=True
    )
    numeric_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entry_method: Mapped[str] = mapped_column(
        entry_method_enum, nullable=False, default="QUICK_LOG"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
