import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

EventState = Literal["START", "END"]
EventLocation = Literal["INSIDE", "OUTSIDE", "NOT_APPLICABLE"]
EntryMethod = Literal["QUICK_LOG", "MANUAL"]


class EventCreate(BaseModel):
    dog_id: uuid.UUID
    event_type_id: int
    event_time: Optional[datetime] = None
    state: Optional[EventState] = None
    location: EventLocation = "NOT_APPLICABLE"
    option_id: Optional[uuid.UUID] = None
    numeric_value: Optional[Decimal] = None
    unit: Optional[str] = Field(default=None, max_length=30)
    severity: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = Field(default=None, max_length=500)
    entry_method: EntryMethod = "QUICK_LOG"

    @field_validator("numeric_value")
    @classmethod
    def numeric_value_must_be_positive(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is not None and value <= 0:
            raise ValueError("Numeric value must be greater than zero.")
        return value


class EventUpdate(BaseModel):
    event_time: Optional[datetime] = None
    state: Optional[EventState] = None
    location: Optional[EventLocation] = None
    option_id: Optional[uuid.UUID] = None
    numeric_value: Optional[Decimal] = None
    unit: Optional[str] = Field(default=None, max_length=30)
    severity: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = Field(default=None, max_length=500)


class EventResponse(BaseModel):
    id: uuid.UUID
    dog_id: uuid.UUID
    event_type_id: int
    event_type_code: str
    event_type_name: str
    event_time: datetime
    state: Optional[str]
    location: str
    option_id: Optional[uuid.UUID]
    option_name: Optional[str]
    numeric_value: Optional[Decimal]
    unit: Optional[str]
    severity: Optional[int]
    notes: Optional[str]
    entry_method: str
    created_at: datetime
