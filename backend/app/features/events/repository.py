from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.features.events.schemas import EventCreate
from app.database.models.event import Event


class EventRepository:
    """Handle persistence operations for events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        organization_id: int,
        department_id: int,
        event_data: EventCreate,
    ) -> Event:
        event_values = event_data.model_dump()

        if event_values["event_url"] is not None:
            event_values["event_url"] = str(event_values["event_url"])

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

        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_department(
        self,
        organization_id: int,
        department_id: int,
    ) -> list[Event]:
        statement = (
            select(Event)
            .where(
                Event.organization_id == organization_id,
                Event.department_id == department_id,
            )
            .order_by(
                Event.starts_at.asc(),
                Event.id.asc(),
            )
        )

        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def list_upcoming_by_department(
        self,
        organization_id: int,
        department_id: int,
        starts_from: datetime,
        limit: int = 10,
    ) -> list[Event]:
        """Return active events starting on or after the supplied date and time."""

        statement = (
            select(Event)
            .where(
                Event.organization_id == organization_id,
                Event.department_id == department_id,
                Event.status == "active",
                Event.starts_at >= starts_from,
            )
            .order_by(
                Event.starts_at.asc(),
                Event.id.asc(),
            )
            .limit(limit)
        )

        result = await self._session.scalars(statement)

        return list(result.all())