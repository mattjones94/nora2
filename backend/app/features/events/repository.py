from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.event import Event
from app.features.events.schemas import (
    EventCreate,
    EventStatus,
)


class EventRepository:
    """Handle persistence operations for events."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def create(
        self,
        organization_id: int,
        department_id: int,
        event_data: EventCreate,
    ) -> Event:
        event_values = event_data.model_dump()

        if event_values["event_url"] is not None:
            event_values["event_url"] = str(
                event_values["event_url"]
            )

        event = Event(
            organization_id=organization_id,
            department_id=department_id,
            **event_values,
        )

        self._session.add(event)

        await self._session.flush()
        await self._session.refresh(event)

        return event

    async def get_by_id(
        self,
        organization_id: int,
        department_id: int,
        event_id: int,
    ) -> Event | None:
        statement = select(Event).where(
            Event.id == event_id,
            Event.organization_id == organization_id,
            Event.department_id == department_id,
        )

        result = await self._session.execute(
            statement
        )

        return result.scalar_one_or_none()

    async def list_by_department(
        self,
        organization_id: int,
        department_id: int,
    ) -> list[Event]:
        statement = (
            select(Event)
            .where(
                Event.organization_id
                == organization_id,
                Event.department_id
                == department_id,
            )
            .order_by(
                Event.starts_at.asc(),
                Event.id.asc(),
            )
        )

        result = await self._session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )

    async def list_upcoming_by_department(
        self,
        organization_id: int,
        department_id: int,
        starts_from: datetime,
        limit: int = 10,
    ) -> list[Event]:
        """
        Return active department events starting on or after the
        supplied date and time.
        """

        statement = (
            select(Event)
            .where(
                Event.organization_id
                == organization_id,
                Event.department_id
                == department_id,
                Event.status == "active",
                Event.starts_at >= starts_from,
            )
            .order_by(
                Event.starts_at.asc(),
                Event.id.asc(),
            )
            .limit(limit)
        )

        result = await self._session.scalars(
            statement
        )

        return list(
            result.all()
        )

    async def list_by_organization(
        self,
        organization_id: int,
        event_status: EventStatus | None,
        limit: int,
        offset: int,
    ) -> list[Event]:
        """
        Return events belonging to an organization.

        A status filter is applied when one is supplied.
        """

        statement = select(Event).where(
            Event.organization_id
            == organization_id,
        )

        if event_status is not None:
            statement = statement.where(
                Event.status == event_status,
            )

        statement = (
            statement
            .order_by(
                Event.starts_at.asc(),
                Event.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.scalars(
            statement
        )

        return list(
            result.all()
        )

    async def list_upcoming_by_organization(
        self,
        organization_id: int,
        starts_from: datetime,
        limit: int,
    ) -> list[Event]:
        """
        Return active organization events starting on or after the
        supplied date and time.
        """

        statement = (
            select(Event)
            .where(
                Event.organization_id
                == organization_id,
                Event.status == "active",
                Event.starts_at >= starts_from,
            )
            .order_by(
                Event.starts_at.asc(),
                Event.id.asc(),
            )
            .limit(limit)
        )

        result = await self._session.scalars(
            statement
        )

        return list(
            result.all()
        )