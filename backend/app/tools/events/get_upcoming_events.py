from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.departments.repository import (
    DepartmentRepository,
)
from app.features.events.service import EventService
from app.tools.context import ToolContext
from app.tools.errors import ToolExecutionError


TOOL_NAME = "get_upcoming_events"

TOOL_DESCRIPTION = (
    "Return actual active upcoming event records scheduled for one "
    "department within the organization assigned to the current "
    "conversation. Use this only when the user asks to list upcoming "
    "events or requests event titles, schedules, dates, times, "
    "locations, or event URLs. Do not use this merely because the "
    "message mentions events, event programming, campus activities, "
    "or asks which department handles or organizes them."
)

TOOL_PRESENTATION_GUIDANCE = (
    "Present events in chronological order using their starts_at values.",
    "Include the published event title, date, time, timezone, location, "
    "and event URL when each value is available.",
    "Clearly identify events marked as all-day events.",
)

TOOL_EMPTY_RESULT_GUIDANCE = (
    "State that the department does not currently have any "
    "active upcoming events listed."
)


class GetUpcomingEventsArguments(BaseModel):
    """Arguments the LLM may supply to the upcoming-events tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    department_slug: str = Field(
        min_length=1,
        max_length=100,
        description=(
            "The organization-scoped department slug, "
            "such as 'student-life'."
        ),
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of upcoming events to return.",
    )


class UpcomingEventItem(BaseModel):
    """One display-safe event returned by the tool."""

    model_config = ConfigDict(
        extra="forbid",
    )

    title: str
    description: str | None

    starts_at: datetime
    ends_at: datetime | None

    is_all_day: bool
    timezone: str

    location: str | None
    event_url: str | None


class GetUpcomingEventsResult(BaseModel):
    """Structured result returned to the conversation system."""

    model_config = ConfigDict(
        extra="forbid",
    )

    organization_slug: str

    department_name: str
    department_slug: str

    events: list[UpcomingEventItem]


class UpcomingEventsToolError(ToolExecutionError):
    """Base error raised while executing the upcoming-events tool."""


class ToolDepartmentNotFoundError(
    UpcomingEventsToolError
):
    """Raised when the requested department cannot be resolved."""

    failure_category = "department_not_found"

    def __init__(
        self,
        department_slug: str,
    ) -> None:
        super().__init__(
            f"Department '{department_slug}' was not found "
            "within the current organization."
        )


class ToolDepartmentInactiveError(
    UpcomingEventsToolError
):
    """Raised when the requested department is inactive."""

    failure_category = "department_inactive"

    def __init__(
        self,
        department_slug: str,
    ) -> None:
        super().__init__(
            f"Department '{department_slug}' is inactive."
        )


async def get_upcoming_events(
    session: AsyncSession,
    context: ToolContext,
    arguments: GetUpcomingEventsArguments,
) -> GetUpcomingEventsResult:
    """Retrieve upcoming events using trusted organization scope."""

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

    event_service = EventService(
        session
    )

    events = await event_service.list_upcoming_events(
        organization_id=context.organization_id,
        department_id=department.id,
        limit=arguments.limit,
    )

    return GetUpcomingEventsResult(
        organization_slug=context.organization_slug,
        department_name=department.name,
        department_slug=department.slug,
        events=[
            UpcomingEventItem(
                title=event.title,
                description=event.description,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                is_all_day=event.is_all_day,
                timezone=event.timezone,
                location=event.location,
                event_url=event.event_url,
            )
            for event in events
        ],
    )