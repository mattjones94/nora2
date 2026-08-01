from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)


ResourceType = Literal[
    "document",
    "external_link",
    "form",
    "guide",
    "website",
    "information",
]

ResourceStatus = Literal[
    "draft",
    "published",
    "inactive",
]

ResourceKeyword = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
    ),
]


class ResourceCreate(BaseModel):
    """Data accepted when creating an organization resource."""

    department_id: int | None = Field(
        default=None,
        gt=0,
    )

    title: str = Field(
        min_length=1,
        max_length=255,
    )

    slug: str = Field(
        min_length=1,
        max_length=150,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    resource_type: ResourceType

    category: str | None = Field(
        default=None,
        max_length=100,
    )

    summary: str | None = Field(
        default=None,
        max_length=5000,
    )

    content_text: str | None = Field(
        default=None,
        max_length=50000,
    )

    url: HttpUrl | None = None

    aliases: list[
        ResourceKeyword
    ] = Field(
        default_factory=list,
        max_length=50,
    )

    topics: list[
        ResourceKeyword
    ] = Field(
        default_factory=list,
        max_length=50,
    )

    when_to_use: str | None = Field(
        default=None,
        max_length=5000,
    )

    when_not_to_use: str | None = Field(
        default=None,
        max_length=5000,
    )

    status: ResourceStatus = "draft"

    display_order: int = Field(
        default=0,
        ge=0,
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    @field_validator(
        "aliases",
        "topics",
    )
    @classmethod
    def normalize_keywords(
        cls,
        values: list[str],
    ) -> list[str]:
        """
        Strip, validate, and case-insensitively deduplicate keywords.

        The first spelling and ordering supplied by the administrator
        are retained.
        """

        normalized_values: list[str] = []
        seen_values: set[str] = set()

        for value in values:
            normalized_value = value.strip()

            if not normalized_value:
                raise ValueError(
                    "Resource keywords cannot be empty."
                )

            comparison_value = (
                normalized_value.casefold()
            )

            if comparison_value in seen_values:
                continue

            seen_values.add(
                comparison_value
            )

            normalized_values.append(
                normalized_value
            )

        return normalized_values


class ResourceUpdate(BaseModel):
    """Data accepted when updating selected resource fields."""

    department_id: int | None = Field(
        default=None,
        gt=0,
    )

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    resource_type: ResourceType | None = None

    category: str | None = Field(
        default=None,
        max_length=100,
    )

    summary: str | None = Field(
        default=None,
        max_length=5000,
    )

    content_text: str | None = Field(
        default=None,
        max_length=50000,
    )

    url: HttpUrl | None = None

    aliases: list[
        ResourceKeyword
    ] | None = Field(
        default=None,
        max_length=50,
    )

    topics: list[
        ResourceKeyword
    ] | None = Field(
        default=None,
        max_length=50,
    )

    when_to_use: str | None = Field(
        default=None,
        max_length=5000,
    )

    when_not_to_use: str | None = Field(
        default=None,
        max_length=5000,
    )

    status: ResourceStatus | None = None

    display_order: int | None = Field(
        default=None,
        ge=0,
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    @field_validator(
        "aliases",
        "topics",
    )
    @classmethod
    def normalize_keywords(
        cls,
        values: list[str] | None,
    ) -> list[str] | None:
        """Normalize supplied keyword collections."""

        if values is None:
            return None

        normalized_values: list[str] = []
        seen_values: set[str] = set()

        for value in values:
            normalized_value = value.strip()

            if not normalized_value:
                raise ValueError(
                    "Resource keywords cannot be empty."
                )

            comparison_value = (
                normalized_value.casefold()
            )

            if comparison_value in seen_values:
                continue

            seen_values.add(
                comparison_value
            )

            normalized_values.append(
                normalized_value
            )

        return normalized_values


class ResourceResponse(BaseModel):
    """Resource data returned through the administrative API."""

    id: int
    organization_id: int
    department_id: int | None

    title: str
    slug: str

    resource_type: ResourceType
    category: str | None

    summary: str | None
    content_text: str | None
    url: str | None

    aliases: list[str] | None
    topics: list[str] | None

    when_to_use: str | None
    when_not_to_use: str | None

    status: ResourceStatus
    display_order: int

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )