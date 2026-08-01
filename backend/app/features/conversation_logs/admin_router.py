from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_database_session
from app.features.conversation_logs.exceptions import (
    ConversationLogError,
    ConversationLogMetricsNotFoundError,
    ConversationLogNotFoundError,
    InvalidConversationLogDateRangeError,
    InvalidConversationLogSessionIdError,
    OrganizationNotFoundError,
)
from app.features.conversation_logs.schemas import (
    ConversationAnalyticsSummaryResponse,
    ConversationLogDetailResponse,
    ConversationLogListResponse,
    ConversationSessionStatus,
)
from app.features.conversation_logs.service import (
    ConversationLogService,
)


router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Admin - Conversation Logs"],
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_database_session),
]


def translate_conversation_log_error(
    error: ConversationLogError,
) -> HTTPException:
    """Translate conversation-log errors into HTTP responses."""

    if isinstance(
        error,
        (
            OrganizationNotFoundError,
            ConversationLogNotFoundError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    if isinstance(
        error,
        (
            InvalidConversationLogSessionIdError,
            InvalidConversationLogDateRangeError,
        ),
    ):
        return HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        )

    if isinstance(
        error,
        ConversationLogMetricsNotFoundError,
    ):
        return HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=str(error),
        )

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    )


@router.get(
    "/conversations",
    response_model=ConversationLogListResponse,
)
async def list_conversation_logs(
    organization_id: int,
    session: DatabaseSession,
    conversation_status: Annotated[
        ConversationSessionStatus | None,
        Query(
            alias="status",
        ),
    ] = None,
    started_from: Annotated[
        datetime | None,
        Query(),
    ] = None,
    started_to: Annotated[
        datetime | None,
        Query(),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 25,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
) -> ConversationLogListResponse:
    """
    List conversations belonging to one organization.

    Results are returned newest first and contain session-level
    metrics without loading full message content.
    """

    service = ConversationLogService(
        session
    )

    try:
        return await service.list_conversations(
            organization_id=organization_id,
            conversation_status=conversation_status,
            started_from=started_from,
            started_to=started_to,
            limit=limit,
            offset=offset,
        )
    except ConversationLogError as error:
        raise translate_conversation_log_error(
            error
        ) from error


@router.get(
    "/conversation-analytics/summary",
    response_model=ConversationAnalyticsSummaryResponse,
)
async def get_conversation_analytics_summary(
    organization_id: int,
    session: DatabaseSession,
    conversation_status: Annotated[
        ConversationSessionStatus | None,
        Query(
            alias="status",
        ),
    ] = None,
    started_from: Annotated[
        datetime | None,
        Query(),
    ] = None,
    started_to: Annotated[
        datetime | None,
        Query(),
    ] = None,
) -> ConversationAnalyticsSummaryResponse:
    """
    Return aggregated conversation analytics for one organization.

    Every aggregate uses the same optional session-status and
    session-start date filters.
    """

    service = ConversationLogService(
        session
    )

    try:
        return await service.get_analytics_summary(
            organization_id=organization_id,
            conversation_status=conversation_status,
            started_from=started_from,
            started_to=started_to,
        )
    except ConversationLogError as error:
        raise translate_conversation_log_error(
            error
        ) from error


@router.get(
    "/conversations/{session_id}",
    response_model=ConversationLogDetailResponse,
)
async def get_conversation_log(
    organization_id: int,
    session_id: str,
    session: DatabaseSession,
) -> ConversationLogDetailResponse:
    """
    Return one selected conversation with its metrics, messages,
    and audited tool executions.
    """

    service = ConversationLogService(
        session
    )

    try:
        return await service.get_conversation(
            organization_id=organization_id,
            public_id=session_id,
        )
    except ConversationLogError as error:
        raise translate_conversation_log_error(
            error
        ) from error