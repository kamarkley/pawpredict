from datetime import datetime
from typing import Optional

from sqlalchemy import ARRAY, Boolean, DateTime, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EventType(Base):
    __tablename__ = "event_types"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    supports_state: Mapped[bool] = mapped_column(Boolean, nullable=False)
    supports_location: Mapped[bool] = mapped_column(Boolean, nullable=False)
    supports_treat: Mapped[bool] = mapped_column(Boolean, nullable=False)
    option_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    option_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    supports_numeric: Mapped[bool] = mapped_column(Boolean, nullable=False)
    numeric_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    numeric_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allowed_units: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    supports_severity: Mapped[bool] = mapped_column(Boolean, nullable=False)
    severity_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    start_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    end_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
