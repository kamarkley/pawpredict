import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DogStatPreference(Base):
    __tablename__ = "dog_stat_preferences"

    dog_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dogs.id", ondelete="CASCADE"), primary_key=True
    )
    stat_code: Mapped[str] = mapped_column(
        Text, ForeignKey("stat_types.code", ondelete="CASCADE"), primary_key=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
