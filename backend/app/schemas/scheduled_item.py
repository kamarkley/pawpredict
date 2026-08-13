import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

ScheduledItemType = Literal[
    "VET_APPOINTMENT", "GROOMING_APPOINTMENT", "BATH", "MEDICATION", "DAYCARE", "TRAINING", "OTHER"
]


class ScheduledItemCreate(BaseModel):
    dog_id: uuid.UUID
    title: str = Field(min_length=1, max_length=120)
    item_type: ScheduledItemType
    scheduled_for: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_time and self.end_time <= self.scheduled_for:
            raise ValueError("End time must be after the scheduled start.")
        return self


class ScheduledItemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    item_type: Optional[ScheduledItemType] = None
    scheduled_for: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=500)
    is_completed: Optional[bool] = None


class ScheduledItemResponse(BaseModel):
    id: uuid.UUID
    dog_id: uuid.UUID
    title: str
    item_type: str
    scheduled_for: datetime
    end_time: Optional[datetime]
    location: Optional[str]
    notes: Optional[str]
    is_completed: bool
    linked_event_id: Optional[uuid.UUID]
    created_at: datetime
