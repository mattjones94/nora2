from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DepartmentDetailUpsert(BaseModel):
    """
    Complete department-details form accepted from the admin UI.

    PUT requests create the record when missing or replace its editable
    values when it already exists.
    """

    primary_contact_name: str | None = Field(
        default=None,
        max_length=255,
    )

    primary_contact_title: str | None = Field(
        default=None,
        max_length=255,
    )

    email: str | None = Field(
        default=None,
        max_length=320,
    )

    phone: str | None = Field(
        default=None,
        max_length=50,
    )

    location: str | None = Field(
        default=None,
        max_length=255,
    )

    office_hours: str | None = Field(
        default=None,
        max_length=5000,
    )

    website_url: str | None = Field(
        default=None,
        max_length=2048,
    )

    additional_information: str | None = Field(
        default=None,
        max_length=10000,
    )

    status: Literal[
        "active",
        "inactive",
    ] = "active"

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )


class DepartmentDetailResponse(BaseModel):
    """Department-details data returned through the admin API."""

    id: int
    organization_id: int
    department_id: int

    primary_contact_name: str | None
    primary_contact_title: str | None
    email: str | None
    phone: str | None
    location: str | None
    office_hours: str | None
    website_url: str | None
    additional_information: str | None

    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )