from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    """Data accepted when creating an organization."""

    name: str = Field(
        min_length=1,
        max_length=255,
    )

    slug: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )


class OrganizationResponse(BaseModel):
    """Organization data returned through the API."""

    id: int
    name: str
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )