from sqlalchemy import Boolean, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StatType(Base):
    __tablename__ = "stat_types"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    default_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
