from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.department_details.repository import (
    DepartmentDetailRepository,
)
from app.api.v1.admin.departments.repository import (
    DepartmentRepository,
)
from app.tools.context import ToolContext
from app.tools.errors import ToolExecutionError


TOOL_NAME = "get_department_details"

TOOL_DESCRIPTION = (
    "Return information about one specific department within the "
    "organization assigned to the current conversation. Use this when "
    "the user asks what a department does or requests its contact name, "
    "email, phone number, location, office hours, website, or other "
    "department information."
)


class GetDepartmentDetailsArguments(BaseModel):
    """Arguments the LLM may supply to the department-details tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    department_slug: str = Field(
        min_length=1,
        max_length=100,
        description=(
            "The organization-scoped department slug, "
            "such as 'information-technology' or 'student-life'."
        ),
    )


class GetDepartmentDetailsResult(BaseModel):
    """Display-safe department information returned by the tool."""

    organization_id: int
    organization_slug: str

    department_id: int
    department_name: str
    department_slug: str
    description: str | None

    details_available: bool

    primary_contact_name: str | None
    primary_contact_title: str | None
    email: str | None
    phone: str | None
    location: str | None
    office_hours: str | None
    website_url: str | None
    additional_information: str | None


class DepartmentDetailsToolError(ToolExecutionError):
    """Base error raised by the department-details tool."""


class ToolDepartmentNotFoundError(DepartmentDetailsToolError):
    """Raised when the department cannot be resolved."""

    def __init__(
        self,
        department_slug: str,
    ) -> None:
        super().__init__(
            f"Department '{department_slug}' was not found "
            "within the current organization."
        )


class ToolDepartmentInactiveError(DepartmentDetailsToolError):
    """Raised when the requested department is inactive."""

    def __init__(
        self,
        department_slug: str,
    ) -> None:
        super().__init__(
            f"Department '{department_slug}' is inactive."
        )


async def get_department_details(
    session: AsyncSession,
    context: ToolContext,
    arguments: GetDepartmentDetailsArguments,
) -> GetDepartmentDetailsResult:
    """Return department information using trusted organization scope."""

    department_slug = (
        arguments.department_slug
        .strip()
        .lower()
    )

    department_repository = DepartmentRepository(
        session
    )

    department = await department_repository.get_by_slug(
        organization_id=context.organization_id,
        slug=department_slug,
    )

    if department is None:
        raise ToolDepartmentNotFoundError(
            department_slug=department_slug,
        )

    if department.status != "active":
        raise ToolDepartmentInactiveError(
            department_slug=department_slug,
        )

    detail_repository = DepartmentDetailRepository(
        session
    )

    detail = await detail_repository.get_by_department(
        organization_id=context.organization_id,
        department_id=department.id,
    )

    if (
        detail is not None
        and detail.status != "active"
    ):
        detail = None

    return GetDepartmentDetailsResult(
        organization_id=context.organization_id,
        organization_slug=context.organization_slug,
        department_id=department.id,
        department_name=department.name,
        department_slug=department.slug,
        description=department.description,
        details_available=detail is not None,
        primary_contact_name=(
            detail.primary_contact_name
            if detail is not None
            else None
        ),
        primary_contact_title=(
            detail.primary_contact_title
            if detail is not None
            else None
        ),
        email=(
            detail.email
            if detail is not None
            else None
        ),
        phone=(
            detail.phone
            if detail is not None
            else None
        ),
        location=(
            detail.location
            if detail is not None
            else None
        ),
        office_hours=(
            detail.office_hours
            if detail is not None
            else None
        ),
        website_url=(
            detail.website_url
            if detail is not None
            else None
        ),
        additional_information=(
            detail.additional_information
            if detail is not None
            else None
        ),
    )