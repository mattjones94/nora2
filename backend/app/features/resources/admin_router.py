from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.resource import Resource
from app.database.session import get_database_session
from app.features.resources.exceptions import (
    DepartmentInactiveError,
    DepartmentNotFoundError,
    OrganizationInactiveError,
    OrganizationNotFoundError,
    ResourceError,
    ResourceNotFoundError,
    ResourceSlugConflictError,
)
from app.features.resources.schemas import (
    ResourceCreate,
    ResourceResponse,
    ResourceStatus,
    ResourceType,
    ResourceUpdate,
)
from app.features.resources.service import (
    ResourceService,
)


router = APIRouter(
    prefix="/organizations/{organization_id}/resources",
    tags=["Admin - Resources"],
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_database_session),
]


def translate_resource_error(
    error: ResourceError,
) -> HTTPException:
    """Translate resource domain errors into HTTP responses."""

    if isinstance(
        error,
        (
            OrganizationNotFoundError,
            DepartmentNotFoundError,
            ResourceNotFoundError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    if isinstance(
        error,
        (
            OrganizationInactiveError,
            DepartmentInactiveError,
            ResourceSlugConflictError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    )


def to_resource_response(
    resource: Resource,
) -> ResourceResponse:
    """Translate Resource model fields into the API contract."""

    aliases = (
        list(
            resource.aliases_json
        )
        if resource.aliases_json is not None
        else None
    )

    topics = (
        list(
            resource.topics_json
        )
        if resource.topics_json is not None
        else None
    )

    return ResourceResponse(
        id=resource.id,
        organization_id=resource.organization_id,
        department_id=resource.department_id,
        title=resource.title,
        slug=resource.slug,
        resource_type=resource.resource_type,
        category=resource.category,
        summary=resource.summary,
        content_text=resource.content_text,
        url=resource.url,
        aliases=aliases,
        topics=topics,
        when_to_use=resource.when_to_use,
        when_not_to_use=resource.when_not_to_use,
        status=resource.status,
        display_order=resource.display_order,
        created_at=resource.created_at,
        updated_at=resource.updated_at,
    )


@router.post(
    "",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_resource(
    organization_id: int,
    payload: ResourceCreate,
    session: DatabaseSession,
) -> ResourceResponse:
    """Create a resource within an organization."""

    service = ResourceService(
        session
    )

    try:
        resource = await service.create(
            organization_id=organization_id,
            payload=payload,
        )
    except ResourceError as error:
        raise translate_resource_error(
            error
        ) from error

    return to_resource_response(
        resource
    )


@router.get(
    "",
    response_model=list[ResourceResponse],
)
async def list_resources(
    organization_id: int,
    session: DatabaseSession,
    department_id: Annotated[
        int | None,
        Query(
            ge=1,
        ),
    ] = None,
    resource_status: Annotated[
        ResourceStatus | None,
        Query(
            alias="status",
        ),
    ] = None,
    resource_type: Annotated[
        ResourceType | None,
        Query(),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
) -> list[ResourceResponse]:
    """
    List organization resources with optional filters.

    Results may be filtered by department, status, and resource type.
    """

    service = ResourceService(
        session
    )

    try:
        resources = await service.list_by_organization(
            organization_id=organization_id,
            department_id=department_id,
            resource_status=resource_status,
            resource_type=resource_type,
            limit=limit,
            offset=offset,
        )
    except ResourceError as error:
        raise translate_resource_error(
            error
        ) from error

    return [
        to_resource_response(
            resource
        )
        for resource in resources
    ]


@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
)
async def get_resource(
    organization_id: int,
    resource_id: int,
    session: DatabaseSession,
) -> ResourceResponse:
    """Return one resource within an organization."""

    service = ResourceService(
        session
    )

    try:
        resource = await service.get_by_id(
            organization_id=organization_id,
            resource_id=resource_id,
        )
    except ResourceError as error:
        raise translate_resource_error(
            error
        ) from error

    return to_resource_response(
        resource
    )


@router.patch(
    "/{resource_id}",
    response_model=ResourceResponse,
)
async def update_resource(
    organization_id: int,
    resource_id: int,
    payload: ResourceUpdate,
    session: DatabaseSession,
) -> ResourceResponse:
    """Update explicitly supplied resource fields."""

    service = ResourceService(
        session
    )

    try:
        resource = await service.update(
            organization_id=organization_id,
            resource_id=resource_id,
            payload=payload,
        )
    except ResourceError as error:
        raise translate_resource_error(
            error
        ) from error

    return to_resource_response(
        resource
    )


@router.delete(
    "/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_resource(
    organization_id: int,
    resource_id: int,
    session: DatabaseSession,
) -> Response:
    """Deactivate a resource without deleting its data."""

    service = ResourceService(
        session
    )

    try:
        await service.deactivate(
            organization_id=organization_id,
            resource_id=resource_id,
        )
    except ResourceError as error:
        raise translate_resource_error(
            error
        ) from error

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )