from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.departments.exceptions import (
    DepartmentNotFoundError,
    DepartmentSlugConflictError,
    OrganizationInactiveError,
    OrganizationNotFoundError,
)
from app.api.v1.admin.departments.repository import (
    DepartmentRepository,
)
from app.api.v1.admin.departments.schemas import (
    DepartmentCreate,
    DepartmentUpdate,
)
from app.api.v1.admin.organizations.repository import (
    OrganizationRepository,
)
from app.database.models.department import Department


class DepartmentService:
    """Coordinate department business rules and transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._departments = DepartmentRepository(session)
        self._organizations = OrganizationRepository(session)

    async def create(
        self,
        organization_id: int,
        payload: DepartmentCreate,
    ) -> Department:
        """Create a department under an active organization."""

        organization = await self._organizations.get_by_id(
            organization_id,
        )

        if organization is None:
            raise OrganizationNotFoundError(
                "The organization does not exist.",
            )

        if organization.status != "active":
            raise OrganizationInactiveError(
                "Departments cannot be added to an inactive organization.",
            )

        existing_department = await self._departments.get_by_slug(
            organization_id=organization_id,
            slug=payload.slug,
        )

        if existing_department is not None:
            raise DepartmentSlugConflictError(
                "This organization already has a department "
                "with that slug.",
            )

        department = Department(
            organization_id=organization_id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
        )

        try:
            await self._departments.create(department)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()

            raise DepartmentSlugConflictError(
                "This organization already has a department "
                "with that slug.",
            ) from exc
        except Exception:
            await self._session.rollback()
            raise

        return department

    async def list_by_organization(
        self,
        organization_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[Department]:
        """List departments belonging to an organization."""

        await self._require_organization(organization_id)

        return await self._departments.list_by_organization(
            organization_id=organization_id,
            include_inactive=include_inactive,
        )

    async def get_by_id(
        self,
        organization_id: int,
        department_id: int,
    ) -> Department:
        """Return one department within its organization."""

        department = await self._departments.get_by_id(
            organization_id=organization_id,
            department_id=department_id,
        )

        if department is None:
            raise DepartmentNotFoundError(
                "The department does not exist.",
            )

        return department

    async def update(
        self,
        organization_id: int,
        department_id: int,
        payload: DepartmentUpdate,
    ) -> Department:
        """Update a department using only supplied fields."""

        department = await self.get_by_id(
            organization_id=organization_id,
            department_id=department_id,
        )

        changes = payload.model_dump(
            exclude_unset=True,
        )

        requested_slug = changes.get("slug")

        if (
            isinstance(requested_slug, str)
            and requested_slug != department.slug
        ):
            existing_department = await self._departments.get_by_slug(
                organization_id=organization_id,
                slug=requested_slug,
            )

            if existing_department is not None:
                raise DepartmentSlugConflictError(
                    "This organization already has a department "
                    "with that slug.",
                )

        if not changes:
            return department

        try:
            updated_department = await self._departments.update(
                department=department,
                changes=changes,
            )

            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()

            raise DepartmentSlugConflictError(
                "This organization already has a department "
                "with that slug.",
            ) from exc
        except Exception:
            await self._session.rollback()
            raise

        return updated_department

    async def deactivate(
        self,
        organization_id: int,
        department_id: int,
    ) -> Department:
        """Deactivate a department without deleting its records."""

        department = await self.get_by_id(
            organization_id=organization_id,
            department_id=department_id,
        )

        if department.status == "inactive":
            return department

        try:
            deactivated_department = await self._departments.deactivate(
                department,
            )

            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return deactivated_department

    async def _require_organization(
        self,
        organization_id: int,
    ) -> None:
        """Ensure that an organization exists."""

        organization = await self._organizations.get_by_id(
            organization_id,
        )

        if organization is None:
            raise OrganizationNotFoundError(
                "The organization does not exist.",
            )