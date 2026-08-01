from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.departments.service import (
    DepartmentService,
)
from app.tools.context import ToolContext


TOOL_NAME = "list_departments"

TOOL_DESCRIPTION = (
    "Return the active departments available within the organization "
    "assigned to the current conversation. Use this when the user asks "
    "which departments, offices, divisions, or service areas are "
    "available. Also use this for department discovery when the user "
    "describes a specific service, problem, activity, program, or area "
    "of work and asks which department handles it, but no specific "
    "department has already been identified. The returned department "
    "names, slugs, and descriptions are the authoritative options for "
    "department discovery. Do not use this tool merely because the "
    "user says they need help, need help with something, mentions the "
    "campus, or asks who they should talk to without describing a "
    "specific service, problem, activity, program, or area of work. "
    "For such vague requests, the model should ask a short clarification "
    "question instead of calling a department tool. Do not invent a "
    "department slug from a generic service or problem label such as "
    "'support', 'help-center', 'password', or 'account assistance'. "
    "The organization slug identifies the organization and is never a "
    "department slug."
)

TOOL_PRESENTATION_GUIDANCE = (
    "Use each department's published name and description.",
    "When the user asks which department handles a service, problem, "
    "activity, or program, identify the best matching department using "
    "only the published descriptions and briefly explain the match.",
    "Do not list every department when the user requested one matching "
    "department unless multiple published departments are equally "
    "relevant.",
    "List all departments when the user asks which departments are "
    "available or explicitly requests a department list.",
)

TOOL_EMPTY_RESULT_GUIDANCE = (
    "State that the organization does not currently list any "
    "active departments."
)


class ListDepartmentsArguments(BaseModel):
    """Arguments the LLM may supply to the department-list tool."""

    model_config = ConfigDict(
        extra="forbid",
    )


class DepartmentListItem(BaseModel):
    """One display-safe department returned by the tool."""

    model_config = ConfigDict(
        extra="forbid",
    )

    name: str
    slug: str
    description: str | None


class ListDepartmentsResult(BaseModel):
    """Structured department list returned to the conversation system."""

    model_config = ConfigDict(
        extra="forbid",
    )

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
        organization_slug=context.organization_slug,
        departments=[
            DepartmentListItem(
                name=department.name,
                slug=department.slug,
                description=department.description,
            )
            for department in departments
        ],
    )