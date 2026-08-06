import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

EventState = Literal["START", "END"]
EventLocation = Literal["INSIDE", "OUTSIDE", "NOT_APPLICABLE"]
EntryMethod = Literal["QUICK_LOG", "MANUAL"]


class EventCreate(BaseModel):
    dog_id: uuid.UUID
    event_type_id: int
    event_time: Optional[datetime] = None
    state: Optional[EventState] = None
    location: EventLocation = "NOT_APPLICABLE"
    treat_type_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    entry_method: EntryMethod = "QUICK_LOG"


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dog_id: uuid.UUID
    event_type_id: int
    event_time: datetime
    state: Optional[str]
    location: str
    treat_type_id: Optional[uuid.UUID]
    notes: Optional[str]
    entry_method: str
    created_at: datetime