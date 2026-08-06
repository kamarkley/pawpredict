import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SavedOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dog_id: uuid.UUID
    category: str
    name: str
    is_active: bool


class SavedOptionCreate(BaseModel):
    dog_id: uuid.UUID
    category: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)


class SavedOptionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


OptionCategory = Literal[
    "POTTY_RESULT", "SLEEP_LOCATION", "TREAT", "MEAL_AMOUNT",
    "MEDICATION", "SYMPTOM", "SOCIAL_ACTIVITY", "BEHAVIOR",
    "GROOMING", "VET_VISIT"
]
