import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Dog(Base):
    __tablename__ = "dogs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    breed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # The PostgreSQL column uses a custom enum. Reading it as text keeps
    # the first model simple while preserving the database constraint.
    sex: Mapped[str] = mapped_column(nullable=False)

    weight_lbs: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    neutered: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )