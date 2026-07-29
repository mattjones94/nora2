from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.department import Department


class DepartmentRepository:
    """Handle persistence operations for departments."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def create(
        self,
        department: Department,
    ) -> Department:
        """Add a department to the current database transaction."""

        self._session.add(
            department
        )

        await self._session.flush()
        await self._session.refresh(
            department
        )

        return department

    async def get_by_id(
        self,
        organization_id: int,
        department_id: int,
    ) -> Department | None:
        """Find a department within a specific organization."""

        statement = select(
            Department
        ).where(
            Department.id == department_id,
            Department.organization_id == organization_id,
        )

        result = await self._session.scalars(
            statement
        )

        return result.one_or_none()

    async def get_by_slug(
        self,
        organization_id: int,
        slug: str,
    ) -> Department | None:
        """Find a department by its organization-scoped slug."""

        statement = select(
            Department
        ).where(
            Department.organization_id == organization_id,
            Department.slug == slug,
        )

        result = await self._session.scalars(
            statement
        )

        return result.one_or_none()

    async def list_by_organization(
        self,
        organization_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[Department]:
        """Return departments belonging to an organization."""

        statement = (
            select(
                Department
            )
            .where(
                Department.organization_id == organization_id,
            )
            .order_by(
                Department.name,
                Department.id,
            )
        )

        if not include_inactive:
            statement = statement.where(
                Department.status == "active",
            )

        result = await self._session.scalars(
            statement
        )

        return list(
            result.all()
        )

    async def update(
        self,
        department: Department,
        changes: Mapping[str, object],
    ) -> Department:
        """Apply validated changes to a department."""

        for field_name, value in changes.items():
            setattr(
                department,
                field_name,
                value,
            )

        await self._session.flush()
        await self._session.refresh(
            department
        )

        return department

    async def deactivate(
        self,
        department: Department,
    ) -> Department:
        """Mark a department inactive without deleting its data."""

        department.status = "inactive"

        await self._session.flush()
        await self._session.refresh(
            department
        )

        return department