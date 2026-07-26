from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.department_details.exceptions import (
    DepartmentDetailConflictError,
    DepartmentDetailError,
    DepartmentDetailNotFoundError,
    DepartmentNotFoundError,
    OrganizationNotFoundError,
)
from app.api.v1.admin.department_details.schemas import (
    DepartmentDetailResponse,
    DepartmentDetailUpsert,
)
from app.api.v1.admin.department_details.service import (
    DepartmentDetailService,
)
from app.database.models.department_detail import (
    DepartmentDetail,
)
from app.database.session import get_database_session


router = APIRouter(
    prefix=(
        "/organizations/{organization_id}"
        "/departments/{department_id}"
        "/details"
    ),
    tags=["Admin - Department Details"],
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_database_session),
]


def translate_department_detail_error(
    error: DepartmentDetailError,
) -> HTTPException:
    """Translate department-detail errors into HTTP responses."""

    if isinstance(
        error,
        (
            OrganizationNotFoundError,
            DepartmentNotFoundError,
            DepartmentDetailNotFoundError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    if isinstance(
        error,
        DepartmentDetailConflictError,
    ):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    )


@router.get(
    "",
    response_model=DepartmentDetailResponse,
)
async def get_department_details(
    organization_id: int,
    department_id: int,
    session: DatabaseSession,
) -> DepartmentDetail:
    """Return the details record belonging to a department."""

    service = DepartmentDetailService(
        session
    )

    try:
        return await service.get(
            organization_id=organization_id,
            department_id=department_id,
        )
    except DepartmentDetailError as error:
        raise translate_department_detail_error(
            error
        ) from error


@router.put(
    "",
    response_model=DepartmentDetailResponse,
)
async def upsert_department_details(
    organization_id: int,
    department_id: int,
    payload: DepartmentDetailUpsert,
    session: DatabaseSession,
) -> DepartmentDetail:
    """Create or replace the details belonging to a department."""

    service = DepartmentDetailService(
        session
    )

    try:
        return await service.upsert(
            organization_id=organization_id,
            department_id=department_id,
            payload=payload,
        )
    except DepartmentDetailError as error:
        raise translate_department_detail_error(
            error
        ) from error