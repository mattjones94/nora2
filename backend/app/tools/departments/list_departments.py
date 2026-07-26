from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.departments.service import (
    DepartmentService,
)
from app.tools.context import ToolContext


TOOL_NAME = "list_departments"

TOOL_DESCRIPTION = (
    "Return the active departments available within the organization "
    "assigned to the current conversation. Use this when the user asks "
    "which departments, offices, divisions, or service areas are available."
)


class ListDepartmentsArguments(BaseModel):
    """Arguments the LLM may supply to the department-list tool."""

    model_config = ConfigDict(
        extra="forbid",
    )


class DepartmentListItem(BaseModel):
    """One display-safe department returned by the tool."""

    id: int
    name: str
    slug: str
    description: str | None


class ListDepartmentsResult(BaseModel):
    """Structured department list returned to the conversation system."""

    organization_id: int
    organization_slug: str
    departments: list[DepartmentListItem]


async def list_departments(
    session: AsyncSession,
    context: ToolContext,
    arguments: ListDepartmentsArguments,
) -> ListDepartmentsResult:
    """Return active departments within the trusted organization scope."""

    department_service = DepartmentService(
        session
    )

    departments = await department_service.list_by_organization(
        organization_id=context.organization_id,
        include_inactive=False,
    )

    return ListDepartmentsResult(
        organization_id=context.organization_id,
        organization_slug=context.organization_slug,
        departments=[
            DepartmentListItem(
                id=department.id,
                name=department.name,
                slug=department.slug,
                description=department.description,
            )
            for department in departments
        ],
    )