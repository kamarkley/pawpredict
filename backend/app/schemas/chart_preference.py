from __future__ import annotations

from pydantic import BaseModel, Field


class ChartPreferenceResponse(BaseModel):
    code: str
    display_name: str
    description: str | None
    required_event_codes: list[str]
    is_enabled: bool
    display_order: int


class ChartPreferenceUpdateItem(BaseModel):
    code: str
    is_enabled: bool
    display_order: int = Field(ge=0)


class ChartPreferencesUpdate(BaseModel):
    preferences: list[ChartPreferenceUpdateItem]