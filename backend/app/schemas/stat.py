from pydantic import BaseModel


class StatPreferenceItem(BaseModel):
    code: str
    display_name: str
    description: str
    is_enabled: bool
    display_order: int


class StatPreferencesUpdate(BaseModel):
    stat_codes: list[str]
