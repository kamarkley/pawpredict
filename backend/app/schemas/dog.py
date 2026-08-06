import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field


class DogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    birth_date: date
    breed: Optional[str]
    sex: str
    weight_lbs: Optional[Decimal]
    neutered: Optional[bool]

    @computed_field
    @property
    def age_in_days(self) -> int:
        return (date.today() - self.birth_date).days

    @computed_field
    @property
    def age_in_weeks(self) -> int:
        return self.age_in_days // 7