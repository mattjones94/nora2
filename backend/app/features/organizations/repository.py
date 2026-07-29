from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.organization import Organization


class OrganizationRepository:
    """Handle persistence operations for organizations."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def get_by_id(
        self,
        organization_id: int,
    ) -> Organization | None:
        """Find an organization by its primary key."""

        return await self._session.get(
            Organization,
            organization_id,
        )

    async def get_by_slug(
        self,
        organization_slug: str,
    ) -> Organization | None:
        """Find an organization by its public slug."""

        statement = select(
            Organization
        ).where(
            Organization.slug == organization_slug,
        )

        result = await self._session.scalars(
            statement
        )

        return result.one_or_none()