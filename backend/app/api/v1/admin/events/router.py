from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.events.exceptions import (
    DepartmentInactiveError,
    DepartmentNotFoundError,
    EventNotFoundError,
    EventServiceError,
    OrganizationInactiveError,
    OrganizationNotFoundError,
)
from app.api.v1.admin.events.schemas import (
    EventCreate,
    EventResponse,
)
from app.api.v1.admin.events.service import EventService
from app.database.models.event import Event
from app.database.session import get_database_session


router = APIRouter(
    prefix=(
        "/organizations/{organization_id}"
        "/departments/{department_id}"
        "/events"
    ),
    tags=["Admin - Events"],
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_database_session),
]


def translate_event_error(
    error: EventServiceError,
) -> HTTPException:
    """Translate event errors into HTTP responses."""

    if isinstance(
        error,
        (
            OrganizationNotFoundError,
            DepartmentNotFoundError,
            EventNotFoundError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    if isinstance(
        error,
        (
            OrganizationInactiveError,
            DepartmentInactiveError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    )


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_event(
    organization_id: int,
    department_id: int,
    payload: EventCreate,
    session: DatabaseSession,
) -> Event:
    """Create an event within a department."""

    service = EventService(session)

    try:
        return await service.create_event(
            organization_id=organization_id,
            department_id=department_id,
            event_data=payload,
        )
    except EventServiceError as error:
        raise translate_event_error(error) from error


@router.get(
    "",
    response_model=list[EventResponse],
)
async def list_events(
    organization_id: int,
    department_id: int,
    session: DatabaseSession,
) -> list[Event]:
    """List events belonging to a department."""

    service = EventService(session)

    try:
        return await service.list_events(
            organization_id=organization_id,
            department_id=department_id,
        )
    except EventServiceError as error:
        raise translate_event_error(error) from error



@router.get(
    "/upcoming",
    response_model=list[EventResponse],
)
async def list_upcoming_events(
    organization_id: int,
    department_id: int,
    session: DatabaseSession,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=50,
        ),
    ] = 10,
) -> list[Event]:
    """List active upcoming events belonging to a department."""

    service = EventService(session)

    try:
        return await service.list_upcoming_events(
            organization_id=organization_id,
            department_id=department_id,
            limit=limit,
        )
    except EventServiceError as error:
        raise translate_event_error(error) from error


@router.get(
    "/{event_id}",
    response_model=EventResponse,
)
async def get_event(
    organization_id: int,
    department_id: int,
    event_id: int,
    session: DatabaseSession,
) -> Event:
    """Return one event within a department."""

    service = EventService(session)

    try:
        return await service.get_event(
            organization_id=organization_id,
            department_id=department_id,
            event_id=event_id,
        )
    except EventServiceError as error:
        raise translate_event_error(error) from error