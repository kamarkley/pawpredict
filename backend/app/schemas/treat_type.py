import uuid

from pydantic import BaseModel, ConfigDict


class TreatTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    brand: str | None