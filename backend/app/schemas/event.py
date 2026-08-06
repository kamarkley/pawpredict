import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

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

class EventUpdate(BaseModel):
    event_time: Optional[datetime] = None
    state: Optional[EventState] = None
    location: Optional[EventLocation] = None
    treat_type_id: Optional[uuid.UUID] = None
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
    treat_type_id: Optional[uuid.UUID]
    treat_name: Optional[str]
    notes: Optional[str]
    entry_method: str
    created_at: datetime