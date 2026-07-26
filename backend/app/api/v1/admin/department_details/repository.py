from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.department_detail import (
    DepartmentDetail,
)


class DepartmentDetailRepository:
    """Handle persistence operations for department details."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def create(
        self,
        detail: DepartmentDetail,
    ) -> DepartmentDetail:
        """Add a department-details record to the transaction."""

        self._session.add(detail)

        await self._session.flush()
        await self._session.refresh(detail)

        return detail

    async def get_by_department(
        self,
        organization_id: int,
        department_id: int,
    ) -> DepartmentDetail | None:
        """Find details for one department within an organization."""

        statement = select(
            DepartmentDetail
        ).where(
            DepartmentDetail.organization_id == organization_id,
            DepartmentDetail.department_id == department_id,
        )

        result = await self._session.scalars(
            statement
        )

        return result.one_or_none()

    async def update(
        self,
        detail: DepartmentDetail,
        changes: Mapping[str, object],
    ) -> DepartmentDetail:
        """Replace editable values on a department-details record."""

        for field_name, value in changes.items():
            setattr(
                detail,
                field_name,
                value,
            )

        await self._session.flush()
        await self._session.refresh(detail)

        return detail