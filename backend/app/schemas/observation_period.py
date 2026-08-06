import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ObservationPeriodCreate(BaseModel):
    dog_id: uuid.UUID
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reason_option_id: uuid.UUID
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_range(self) -> "ObservationPeriodCreate":
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("End time must be after start time.")
        return self


class ObservationPeriodUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reason_option_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class ObservationPeriodResponse(BaseModel):
    id: uuid.UUID
    dog_id: uuid.UUID
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    reason_option_id: Optional[uuid.UUID]
    reason_name: Optional[str]
    notes: Optional[str]
    created_at: datetime
