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

from app.api.v1.admin.departments.exceptions import (
    DepartmentError,
    DepartmentNotFoundError,
    DepartmentSlugConflictError,
    OrganizationInactiveError,
    OrganizationNotFoundError,
)
from app.api.v1.admin.departments.schemas import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.api.v1.admin.departments.service import DepartmentService
from app.database.models.department import Department
from app.database.session import get_database_session


router = APIRouter(
    prefix="/organizations/{organization_id}/departments",
    tags=["Admin - Departments"],
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_database_session),
]


def translate_department_error(
    error: DepartmentError,
) -> HTTPException:
    """Translate department errors into HTTP responses."""

    if isinstance(
        error,
        (
            OrganizationNotFoundError,
            DepartmentNotFoundError,
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
            DepartmentSlugConflictError,
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


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    organization_id: int,
    payload: DepartmentCreate,
    session: DatabaseSession,
) -> Department:
    """Create a department within an organization."""

    service = DepartmentService(session)

    try:
        return await service.create(
            organization_id=organization_id,
            payload=payload,
        )
    except DepartmentError as error:
        raise translate_department_error(error) from error


@router.get(
    "",
    response_model=list[DepartmentResponse],
)
async def list_departments(
    organization_id: int,
    session: DatabaseSession,
    include_inactive: Annotated[
        bool,
        Query(),
    ] = False,
) -> list[Department]:
    """List departments within an organization."""

    service = DepartmentService(session)

    try:
        return await service.list_by_organization(
            organization_id=organization_id,
            include_inactive=include_inactive,
        )
    except DepartmentError as error:
        raise translate_department_error(error) from error


@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
)
async def get_department(
    organization_id: int,
    department_id: int,
    session: DatabaseSession,
) -> Department:
    """Return one department within an organization."""

    service = DepartmentService(session)

    try:
        return await service.get_by_id(
            organization_id=organization_id,
            department_id=department_id,
        )
    except DepartmentError as error:
        raise translate_department_error(error) from error


@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
)
async def update_department(
    organization_id: int,
    department_id: int,
    payload: DepartmentUpdate,
    session: DatabaseSession,
) -> Department:
    """Update selected department fields."""

    service = DepartmentService(session)

    try:
        return await service.update(
            organization_id=organization_id,
            department_id=department_id,
            payload=payload,
        )
    except DepartmentError as error:
        raise translate_department_error(error) from error


@router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_department(
    organization_id: int,
    department_id: int,
    session: DatabaseSession,
) -> Response:
    """Deactivate a department without deleting its records."""

    service = DepartmentService(session)

    try:
        await service.deactivate(
            organization_id=organization_id,
            department_id=department_id,
        )
    except DepartmentError as error:
        raise translate_department_error(error) from error

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )