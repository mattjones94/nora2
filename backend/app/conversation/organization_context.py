from sqlalchemy.ext.asyncio import AsyncSession


from app.features.organizations.repository import (
    OrganizationRepository,
)
from app.tools.context import ToolContext


class OrganizationContextError(Exception):
    """Base error raised while resolving public organization context."""


class OrganizationContextNotFoundError(OrganizationContextError):
    """Raised when an organization slug cannot be resolved."""

    def __init__(self, organization_slug: str) -> None:
        super().__init__(
            f"Organization '{organization_slug}' was not found."
        )


class OrganizationContextInactiveError(OrganizationContextError):
    """Raised when the resolved organization is inactive."""

    def __init__(self, organization_slug: str) -> None:
        super().__init__(
            f"Organization '{organization_slug}' is inactive."
        )


class OrganizationContextResolver:
    """Resolve a public organization slug into trusted tool context."""

    def __init__(self, session: AsyncSession) -> None:
        self._organization_repository = OrganizationRepository(session)

    async def resolve(
        self,
        organization_slug: str,
    ) -> ToolContext:
        normalized_slug = organization_slug.strip().lower()

        if not normalized_slug:
            raise OrganizationContextNotFoundError(
                organization_slug=organization_slug,
            )

        organization = await self._organization_repository.get_by_slug(
            organization_slug=normalized_slug,
        )

        if organization is None:
            raise OrganizationContextNotFoundError(
                organization_slug=normalized_slug,
            )

        if organization.status != "active":
            raise OrganizationContextInactiveError(
                organization_slug=normalized_slug,
            )

        return ToolContext(
            organization_id=organization.id,
            organization_slug=organization.slug,
        )