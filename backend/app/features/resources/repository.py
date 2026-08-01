from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.resource import Resource
from app.features.resources.schemas import (
    ResourceStatus,
    ResourceType,
)


class ResourceRepository:
    """Handle persistence operations for organization resources."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def create(
        self,
        resource: Resource,
    ) -> Resource:
        """Add a resource to the current database transaction."""

        self._session.add(
            resource
        )

        await self._session.flush()
        await self._session.refresh(
            resource
        )

        return resource

    async def get_by_id(
        self,
        organization_id: int,
        resource_id: int,
    ) -> Resource | None:
        """Find a resource within a specific organization."""

        statement = select(
            Resource
        ).where(
            Resource.id == resource_id,
            Resource.organization_id == organization_id,
        )

        result = await self._session.scalars(
            statement
        )

        return result.one_or_none()

    async def get_by_slug(
        self,
        organization_id: int,
        slug: str,
    ) -> Resource | None:
        """Find a resource by its organization-scoped slug."""

        statement = select(
            Resource
        ).where(
            Resource.organization_id == organization_id,
            Resource.slug == slug,
        )

        result = await self._session.scalars(
            statement
        )

        return result.one_or_none()

    async def list_by_organization(
        self,
        organization_id: int,
        *,
        department_id: int | None = None,
        resource_status: ResourceStatus | None = None,
        resource_type: ResourceType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Resource]:
        """
        Return resources belonging to an organization.

        Optional filters can restrict results by department, status,
        or resource type.
        """

        statement = select(
            Resource
        ).where(
            Resource.organization_id == organization_id,
        )

        if department_id is not None:
            statement = statement.where(
                Resource.department_id == department_id,
            )

        if resource_status is not None:
            statement = statement.where(
                Resource.status == resource_status,
            )

        if resource_type is not None:
            statement = statement.where(
                Resource.resource_type == resource_type,
            )

        statement = (
            statement
            .order_by(
                Resource.display_order.asc(),
                Resource.title.asc(),
                Resource.id.asc(),
            )
            .offset(
                offset
            )
            .limit(
                limit
            )
        )

        result = await self._session.scalars(
            statement
        )

        return list(
            result.all()
        )

    async def update(
        self,
        resource: Resource,
        changes: Mapping[str, object],
    ) -> Resource:
        """Apply validated changes to a resource."""

        for field_name, value in changes.items():
            setattr(
                resource,
                field_name,
                value,
            )

        await self._session.flush()
        await self._session.refresh(
            resource
        )

        return resource

    async def deactivate(
        self,
        resource: Resource,
    ) -> Resource:
        """Mark a resource inactive without deleting its data."""

        resource.status = "inactive"

        await self._session.flush()
        await self._session.refresh(
            resource
        )

        return resource