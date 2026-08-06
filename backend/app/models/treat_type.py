import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TreatType(Base):
    __tablename__ = "treat_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    brand: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )