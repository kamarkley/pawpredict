import uuid
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

DogSex = Literal["MALE", "FEMALE", "UNKNOWN"]


class DogCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    birth_date: date
    breed: Optional[str] = Field(default=None, max_length=100)
    sex: DogSex = "UNKNOWN"
    weight_lbs: Optional[Decimal] = Field(default=None, gt=0, le=999)
    neutered: Optional[bool] = None


class DogUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    birth_date: Optional[date] = None
    breed: Optional[str] = Field(default=None, max_length=100)
    sex: Optional[DogSex] = None
    weight_lbs: Optional[Decimal] = Field(default=None, gt=0, le=999)
    neutered: Optional[bool] = None


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
