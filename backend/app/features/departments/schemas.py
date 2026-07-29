from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class DepartmentCreate(BaseModel):
    """Data accepted when creating a department."""

    name: str = Field(
        min_length=1,
        max_length=255,
    )

    slug: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    description: str | None = Field(
        default=None,
        max_length=5000,
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )


class DepartmentUpdate(BaseModel):
    """Data accepted when updating a department."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    description: str | None = Field(
        default=None,
        max_length=5000,
    )

    status: Literal[
        "active",
        "inactive",
    ] | None = None

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )


class DepartmentResponse(BaseModel):
    """Department data returned through the API."""

    id: int
    organization_id: int
    name: str
    slug: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )