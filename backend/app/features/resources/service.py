from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.department import Department
from app.database.models.organization import Organization
from app.database.models.resource import Resource
from app.features.departments.repository import (
    DepartmentRepository,
)
from app.features.organizations.repository import (
    OrganizationRepository,
)
from app.features.resources.exceptions import (
    DepartmentInactiveError,
    DepartmentNotFoundError,
    OrganizationInactiveError,
    OrganizationNotFoundError,
    ResourceNotFoundError,
    ResourcePublicationValidationError,
    ResourceSlugConflictError,
    ResourceValidationError,
)
from app.features.resources.repository import (
    ResourceRepository,
)
from app.features.resources.schemas import (
    ResourceCreate,
    ResourceStatus,
    ResourceType,
    ResourceUpdate,
)


class ResourceService:
    """Coordinate resource business rules and transactions."""

    _REQUIRED_UPDATE_FIELDS = {
        "title",
        "slug",
        "resource_type",
        "status",
        "display_order",
    }

    _URL_REQUIRED_TYPES = {
        "external_link",
        "form",
        "website",
    }

    _CONTENT_RESOURCE_TYPES = {
        "document",
        "guide",
        "information",
    }

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

        self._resources = ResourceRepository(
            session
        )

        self._organizations = OrganizationRepository(
            session
        )

        self._departments = DepartmentRepository(
            session
        )

    async def create(
        self,
        organization_id: int,
        payload: ResourceCreate,
    ) -> Resource:
        """Create a resource within an active organization."""

        organization = await self._require_organization(
            organization_id
        )

        if organization.status != "active":
            raise OrganizationInactiveError(
                "Resources cannot be added to an inactive "
                "organization."
            )

        if payload.department_id is not None:
            await self._require_active_department(
                organization_id=organization_id,
                department_id=payload.department_id,
            )

        existing_resource = await self._resources.get_by_slug(
            organization_id=organization_id,
            slug=payload.slug,
        )

        if existing_resource is not None:
            raise ResourceSlugConflictError(
                "This organization already has a resource "
                "with that slug."
            )

        values = self._create_values(
            payload
        )

        self._validate_publication(
            resource_type=values["resource_type"],
            status=values["status"],
            summary=values["summary"],
            content_text=values["content_text"],
            url=values["url"],
        )

        resource = Resource(
            organization_id=organization_id,
            **values,
        )

        try:
            await self._resources.create(
                resource
            )

            await self._session.commit()
            await self._session.refresh(
                resource
            )

        except IntegrityError as error:
            await self._session.rollback()

            raise ResourceSlugConflictError(
                "This organization already has a resource "
                "with that slug."
            ) from error

        except Exception:
            await self._session.rollback()
            raise

        return resource

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
        """List resources belonging to an organization."""

        await self._require_organization(
            organization_id
        )

        if department_id is not None:
            await self._require_department(
                organization_id=organization_id,
                department_id=department_id,
            )

        return await self._resources.list_by_organization(
            organization_id=organization_id,
            department_id=department_id,
            resource_status=resource_status,
            resource_type=resource_type,
            limit=limit,
            offset=offset,
        )

    async def get_by_id(
        self,
        organization_id: int,
        resource_id: int,
    ) -> Resource:
        """Return one resource within its organization."""

        resource = await self._resources.get_by_id(
            organization_id=organization_id,
            resource_id=resource_id,
        )

        if resource is None:
            raise ResourceNotFoundError(
                "The resource does not exist."
            )

        return resource

    async def update(
        self,
        organization_id: int,
        resource_id: int,
        payload: ResourceUpdate,
    ) -> Resource:
        """Update a resource using only explicitly supplied fields."""

        resource = await self.get_by_id(
            organization_id=organization_id,
            resource_id=resource_id,
        )

        changes = self._update_values(
            payload
        )

        if not changes:
            return resource

        requested_slug = changes.get(
            "slug"
        )

        if (
            isinstance(
                requested_slug,
                str,
            )
            and requested_slug != resource.slug
        ):
            existing_resource = await self._resources.get_by_slug(
                organization_id=organization_id,
                slug=requested_slug,
            )

            if existing_resource is not None:
                raise ResourceSlugConflictError(
                    "This organization already has a resource "
                    "with that slug."
                )

        final_department_id = changes.get(
            "department_id",
            resource.department_id,
        )

        if (
            "department_id" in changes
            and final_department_id is not None
        ):
            await self._require_active_department(
                organization_id=organization_id,
                department_id=final_department_id,
            )

        final_resource_type = changes.get(
            "resource_type",
            resource.resource_type,
        )

        final_status = changes.get(
            "status",
            resource.status,
        )

        final_summary = changes.get(
            "summary",
            resource.summary,
        )

        final_content_text = changes.get(
            "content_text",
            resource.content_text,
        )

        final_url = changes.get(
            "url",
            resource.url,
        )

        if final_status == "published":
            organization = await self._require_organization(
                organization_id
            )

            if organization.status != "active":
                raise OrganizationInactiveError(
                    "Resources cannot be published for an inactive "
                    "organization."
                )

            if final_department_id is not None:
                await self._require_active_department(
                    organization_id=organization_id,
                    department_id=final_department_id,
                )

        self._validate_publication(
            resource_type=final_resource_type,
            status=final_status,
            summary=final_summary,
            content_text=final_content_text,
            url=final_url,
        )

        try:
            updated_resource = await self._resources.update(
                resource=resource,
                changes=changes,
            )

            await self._session.commit()
            await self._session.refresh(
                updated_resource
            )

        except IntegrityError as error:
            await self._session.rollback()

            raise ResourceSlugConflictError(
                "This organization already has a resource "
                "with that slug."
            ) from error

        except Exception:
            await self._session.rollback()
            raise

        return updated_resource

    async def deactivate(
        self,
        organization_id: int,
        resource_id: int,
    ) -> Resource:
        """Deactivate a resource without deleting its data."""

        resource = await self.get_by_id(
            organization_id=organization_id,
            resource_id=resource_id,
        )

        if resource.status == "inactive":
            return resource

        try:
            deactivated_resource = (
                await self._resources.deactivate(
                    resource
                )
            )

            await self._session.commit()
            await self._session.refresh(
                deactivated_resource
            )

        except Exception:
            await self._session.rollback()
            raise

        return deactivated_resource

    async def _require_organization(
        self,
        organization_id: int,
    ) -> Organization:
        """Return an organization or raise a domain error."""

        organization = await self._organizations.get_by_id(
            organization_id
        )

        if organization is None:
            raise OrganizationNotFoundError(
                "The organization does not exist."
            )

        return organization

    async def _require_department(
        self,
        organization_id: int,
        department_id: int,
    ) -> Department:
        """Return an organization-scoped department."""

        department = await self._departments.get_by_id(
            organization_id=organization_id,
            department_id=department_id,
        )

        if department is None:
            raise DepartmentNotFoundError(
                "The department does not exist in this "
                "organization."
            )

        return department

    async def _require_active_department(
        self,
        organization_id: int,
        department_id: int,
    ) -> Department:
        """Return an active organization-scoped department."""

        department = await self._require_department(
            organization_id=organization_id,
            department_id=department_id,
        )

        if department.status != "active":
            raise DepartmentInactiveError(
                "Resources cannot be assigned to an inactive "
                "department."
            )

        return department

    @classmethod
    def _create_values(
        cls,
        payload: ResourceCreate,
    ) -> dict[str, Any]:
        """Translate the create contract into model field names."""

        values = payload.model_dump()

        url = values.pop(
            "url"
        )

        aliases = values.pop(
            "aliases"
        )

        topics = values.pop(
            "topics"
        )

        values["url"] = (
            str(url)
            if url is not None
            else None
        )

        values["aliases_json"] = aliases
        values["topics_json"] = topics

        return values

    @classmethod
    def _update_values(
        cls,
        payload: ResourceUpdate,
    ) -> dict[str, Any]:
        """Translate explicitly supplied update fields."""

        changes = payload.model_dump(
            exclude_unset=True,
        )

        for field_name in cls._REQUIRED_UPDATE_FIELDS:
            if (
                field_name in changes
                and changes[field_name] is None
            ):
                raise ResourceValidationError(
                    f"{field_name} cannot be null."
                )

        if "url" in changes:
            url = changes["url"]

            changes["url"] = (
                str(url)
                if url is not None
                else None
            )

        if "aliases" in changes:
            changes["aliases_json"] = changes.pop(
                "aliases"
            )

        if "topics" in changes:
            changes["topics_json"] = changes.pop(
                "topics"
            )

        return changes

    @classmethod
    def _validate_publication(
        cls,
        *,
        resource_type: str,
        status: str,
        summary: str | None,
        content_text: str | None,
        url: str | None,
    ) -> None:
        """Validate the complete state of a published resource."""

        if status != "published":
            return

        has_url = cls._has_text(
            url
        )

        if (
            resource_type in cls._URL_REQUIRED_TYPES
            and not has_url
        ):
            raise ResourcePublicationValidationError(
                "A published external link, form, or website "
                "must contain a URL."
            )

        if resource_type in cls._CONTENT_RESOURCE_TYPES:
            has_content = any(
                (
                    cls._has_text(
                        summary
                    ),
                    cls._has_text(
                        content_text
                    ),
                    has_url,
                )
            )

            if not has_content:
                raise ResourcePublicationValidationError(
                    "A published document, guide, or information "
                    "resource must contain a summary, content, "
                    "or URL."
                )

    @staticmethod
    def _has_text(
        value: str | None,
    ) -> bool:
        """Return whether an optional string contains useful text."""

        return bool(
            value
            and value.strip()
        )