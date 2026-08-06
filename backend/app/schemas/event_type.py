from typing import Optional

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
    option_category: Optional[str]
    option_required: bool
    supports_numeric: bool
    numeric_label: Optional[str]
    numeric_required: bool
    allowed_units: list[str]
    supports_severity: bool
    severity_required: bool
    start_label: Optional[str]
    end_label: Optional[str]
    default_enabled: bool
