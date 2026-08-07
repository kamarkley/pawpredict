import re

from pydantic import BaseModel, field_validator


HEX_COLOR_PATTERN = re.compile(
    r"^#[0-9A-Fa-f]{6}$"
)


class UIPreferenceResponse(BaseModel):
    accent_color: str


class UIPreferenceUpdate(BaseModel):
    accent_color: str

    @field_validator("accent_color")
    @classmethod
    def validate_accent_color(
        cls,
        value: str,
    ) -> str:
        if not HEX_COLOR_PATTERN.match(value):
            raise ValueError(
                "Accent color must be a valid six-digit hex color."
            )

        return value.upper()