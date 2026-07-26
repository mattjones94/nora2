from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from zoneinfo import ZoneInfo

from app.api.v1.admin.departments.repository import DepartmentRepository
from app.api.v1.admin.events.exceptions import (
    DepartmentInactiveError,
    DepartmentNotFoundError,
    EventNotFoundError,
    OrganizationInactiveError,
    OrganizationNotFoundError,
)
from app.api.v1.admin.events.repository import EventRepository
from app.api.v1.admin.events.schemas import EventCreate
from app.api.v1.admin.organizations.repository import OrganizationRepository
from app.database.models.event import Event


class EventService:
    """Handle event application rules and transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

        self._event_repository = EventRepository(session)
        self._organization_repository = OrganizationRepository(session)
        self._department_repository = DepartmentRepository(session)

    async def _verify_organization_and_department(
        self,
        organization_id: int,
        department_id: int,
    ) -> None:
        organization = await self._organization_repository.get_by_id(
            organization_id=organization_id,
        )

        if organization is None:
            raise OrganizationNotFoundError()

        if organization.status != "active":
            raise OrganizationInactiveError()

        department = await self._department_repository.get_by_id(
            organization_id=organization_id,
            department_id=department_id,
        )

        if department is None:
            raise DepartmentNotFoundError()

        if department.status != "active":
            raise DepartmentInactiveError()

    async def create_event(
        self,
        organization_id: int,
        department_id: int,
        event_data: EventCreate,
    ) -> Event:
        await self._verify_organization_and_department(
            organization_id=organization_id,
            department_id=department_id,
        )

        try:
            event = await self._event_repository.create(
                organization_id=organization_id,
                department_id=department_id,
                event_data=event_data,
            )

            await self._session.commit()
            await self._session.refresh(event)

            return event

        except Exception:
            await self._session.rollback()
            raise

    async def list_events(
        self,
        organization_id: int,
        department_id: int,
    ) -> list[Event]:
        await self._verify_organization_and_department(
            organization_id=organization_id,
            department_id=department_id,
        )

        return await self._event_repository.list_by_department(
            organization_id=organization_id,
            department_id=department_id,
        )

    async def get_event(
        self,
        organization_id: int,
        department_id: int,
        event_id: int,
    ) -> Event:
        await self._verify_organization_and_department(
            organization_id=organization_id,
            department_id=department_id,
        )

        event = await self._event_repository.get_by_id(
            organization_id=organization_id,
            department_id=department_id,
            event_id=event_id,
        )

        if event is None:
            raise EventNotFoundError()

        return event

    
    async def list_upcoming_events(
        self,
        organization_id: int,
        department_id: int,
        limit: int = 10,
    ) -> list[Event]:
        """Return active upcoming events for a department."""

        await self._verify_organization_and_department(
            organization_id=organization_id,
            department_id=department_id,
        )

        local_now = datetime.now(
            ZoneInfo("America/New_York")
        ).replace(tzinfo=None)

        return await self._event_repository.list_upcoming_by_department(
            organization_id=organization_id,
            department_id=department_id,
            starts_from=local_now,
            limit=limit,
        )