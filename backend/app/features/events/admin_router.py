from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.event import Event
from app.database.session import get_database_session
from app.features.events.exceptions import (
    DepartmentInactiveError,
    DepartmentNotFoundError,
    EventNotFoundError,
    EventServiceError,
    OrganizationInactiveError,
    OrganizationNotFoundError,
)
from app.features.events.schemas import (
    EventCreate,
    EventResponse,
    EventStatus,
)
from app.features.events.service import EventService


router = APIRouter(
    prefix="/organizations/{organization_id}",
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


@router.get(
    "/events",
    response_model=list[EventResponse],
)
async def list_organization_events(
    organization_id: int,
    session: DatabaseSession,
    event_status: Annotated[
        EventStatus | None,
        Query(
            alias="status",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
) -> list[Event]:
    """
    List events belonging to an organization.

    Results may be filtered by status and paginated with limit
    and offset.
    """

    service = EventService(session)

    try:
        return await service.list_organization_events(
            organization_id=organization_id,
            event_status=event_status,
            limit=limit,
            offset=offset,
        )
    except EventServiceError as error:
        raise translate_event_error(error) from error


@router.get(
    "/events/upcoming",
    response_model=list[EventResponse],
)
async def list_upcoming_organization_events(
    organization_id: int,
    session: DatabaseSession,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=50,
        ),
    ] = 25,
) -> list[Event]:
    """List active upcoming events belonging to an organization."""

    service = EventService(session)

    try:
        return await service.list_upcoming_organization_events(
            organization_id=organization_id,
            limit=limit,
        )
    except EventServiceError as error:
        raise translate_event_error(error) from error


@router.post(
    "/departments/{department_id}/events",
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
    "/departments/{department_id}/events",
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
    "/departments/{department_id}/events/upcoming",
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
    "/departments/{department_id}/events/{event_id}",
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