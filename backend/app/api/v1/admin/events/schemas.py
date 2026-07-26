from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


EventStatus = Literal["active", "cancelled", "inactive"]


class EventCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    title: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str | None = None

    starts_at: datetime

    ends_at: datetime | None = None

    is_all_day: bool = False

    timezone: str = Field(
        default="America/New_York",
        min_length=1,
        max_length=64,
    )

    location: str | None = Field(
        default=None,
        max_length=255,
    )

    event_url: HttpUrl | None = None

    @model_validator(mode="after")
    def validate_event_times(self) -> "EventCreate":
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError(
                "ends_at must be equal to or later than starts_at"
            )

        return self


class EventResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    organization_id: int
    department_id: int

    title: str
    description: str | None

    starts_at: datetime
    ends_at: datetime | None

    is_all_day: bool
    timezone: str

    location: str | None
    event_url: str | None

    status: EventStatus

    created_at: datetime
    updated_at: datetime