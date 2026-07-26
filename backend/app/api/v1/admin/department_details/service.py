from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.department_details.exceptions import (
    DepartmentDetailConflictError,
    DepartmentDetailNotFoundError,
    DepartmentNotFoundError,
    OrganizationNotFoundError,
)
from app.api.v1.admin.department_details.repository import (
    DepartmentDetailRepository,
)
from app.api.v1.admin.department_details.schemas import (
    DepartmentDetailUpsert,
)
from app.api.v1.admin.departments.repository import (
    DepartmentRepository,
)
from app.api.v1.admin.organizations.repository import (
    OrganizationRepository,
)
from app.database.models.department_detail import (
    DepartmentDetail,
)


class DepartmentDetailService:
    """Coordinate department-details rules and transactions."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

        self._details = DepartmentDetailRepository(
            session
        )

        self._departments = DepartmentRepository(
            session
        )

        self._organizations = OrganizationRepository(
            session
        )

    async def get(
        self,
        organization_id: int,
        department_id: int,
    ) -> DepartmentDetail:
        """Return details for one organization-scoped department."""

        await self._require_department(
            organization_id=organization_id,
            department_id=department_id,
        )

        detail = await self._details.get_by_department(
            organization_id=organization_id,
            department_id=department_id,
        )

        if detail is None:
            raise DepartmentDetailNotFoundError(
                "Department details have not been created."
            )

        return detail

    async def upsert(
        self,
        organization_id: int,
        department_id: int,
        payload: DepartmentDetailUpsert,
    ) -> DepartmentDetail:
        """Create or replace the details record for a department."""

        await self._require_department(
            organization_id=organization_id,
            department_id=department_id,
        )

        existing_detail = await self._details.get_by_department(
            organization_id=organization_id,
            department_id=department_id,
        )

        values = payload.model_dump()

        try:
            if existing_detail is None:
                detail = DepartmentDetail(
                    organization_id=organization_id,
                    department_id=department_id,
                    **values,
                )

                saved_detail = await self._details.create(
                    detail
                )
            else:
                saved_detail = await self._details.update(
                    detail=existing_detail,
                    changes=values,
                )

            await self._session.commit()

        except IntegrityError as error:
            await self._session.rollback()

            raise DepartmentDetailConflictError(
                "A details record already exists for this department."
            ) from error

        except Exception:
            await self._session.rollback()
            raise

        return saved_detail

    async def _require_department(
        self,
        organization_id: int,
        department_id: int,
    ) -> None:
        """Confirm the organization and department both exist."""

        organization = await self._organizations.get_by_id(
            organization_id
        )

        if organization is None:
            raise OrganizationNotFoundError(
                "The organization does not exist."
            )

        department = await self._departments.get_by_id(
            organization_id=organization_id,
            department_id=department_id,
        )

        if department is None:
            raise DepartmentNotFoundError(
                "The department does not exist within this organization."
            )