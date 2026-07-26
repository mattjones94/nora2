from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.organization import Organization
from app.database.session import get_database_session
from app.api.v1.admin.organizations.schemas import (
    OrganizationCreate,
    OrganizationResponse,
)


router = APIRouter(
    prefix="/organizations",
    tags=["Admin - Organizations"],
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_database_session),
]


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    payload: OrganizationCreate,
    session: DatabaseSession,
) -> Organization:
    """Create a new NORA organization."""

    organization = Organization(
        name=payload.name,
        slug=payload.slug,
    )

    session.add(organization)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this slug already exists.",
        ) from exc

    await session.refresh(organization)

    return organization


@router.get(
    "",
    response_model=list[OrganizationResponse],
)
async def list_organizations(
    session: DatabaseSession,
) -> list[Organization]:
    """Return all organizations stored in NORA."""

    result = await session.execute(
        select(Organization).order_by(Organization.name),
    )

    return list(result.scalars().all())