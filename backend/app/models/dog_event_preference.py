import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DogEventPreference(Base):
    __tablename__ = "dog_event_preferences"

    dog_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dogs.id", ondelete="CASCADE"), primary_key=True
    )
    event_type_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("event_types.id", ondelete="CASCADE"), primary_key=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    display_order: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
