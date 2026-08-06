from pydantic import BaseModel, ConfigDict


class EventTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    display_name: str
    category: str
    supports_state: bool
    supports_location: bool
    supports_treat: bool