from datetime import datetime, timezone
from time import perf_counter
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.chat.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCloseResponse,
)
from app.conversation.message_service import (
    ConversationMessageService,
)
from app.conversation.metrics_service import (
    ConversationMetricsService,
)
from app.conversation.organization_context import (
    OrganizationContextError,
    OrganizationContextInactiveError,
    OrganizationContextNotFoundError,
    OrganizationContextResolver,
)
from app.conversation.orchestrator import (
    ConversationOrchestrator,
)
from app.conversation.response_contracts import (
    ConversationToolContextRecord,
)
from app.conversation.session_service import (
    ConversationSessionError,
    ConversationSessionExpiredError,
    ConversationSessionNotFoundError,
    ConversationSessionService,
    ConversationSessionUnavailableError,
    InvalidConversationSessionIdError,
)
from app.database.session import get_database_session

from app.llm.runtime_provider import (
    ModelClientNotConfiguredError,
    get_model_runtime,
)


router = APIRouter(
    prefix="/organizations/{organization_slug}/chat",
    tags=["Public - Chat"],
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_database_session),
]


def translate_organization_context_error(
    error: OrganizationContextError,
) -> HTTPException:
    """Translate organization-context errors into HTTP responses."""

    if isinstance(
        error,
        OrganizationContextNotFoundError,
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    if isinstance(
        error,
        OrganizationContextInactiveError,
    ):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    )


def translate_conversation_session_error(
    error: ConversationSessionError,
) -> HTTPException:
    """Translate conversation-session errors into HTTP responses."""

    if isinstance(
        error,
        InvalidConversationSessionIdError,
    ):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    if isinstance(
        error,
        ConversationSessionNotFoundError,
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    if isinstance(
        error,
        (
            ConversationSessionExpiredError,
            ConversationSessionUnavailableError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=str(error),
        )

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    )


@router.post(
    "/messages",
    response_model=ChatMessageResponse,
)
async def submit_chat_message(
    organization_slug: str,
    payload: ChatMessageRequest,
    session: DatabaseSession,
) -> ChatMessageResponse:
    """Process and store one public conversation turn."""

    request_started_at = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    request_timer = perf_counter()

    resolver = OrganizationContextResolver(
        session
    )

    try:
        tool_context = await resolver.resolve(
            organization_slug=organization_slug,
        )
    except OrganizationContextError as error:
        raise translate_organization_context_error(
            error
        ) from error

    try:
        model_runtime = get_model_runtime()
    except ModelClientNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The chat service is not currently available.",
        ) from error

    model_client = model_runtime.client
    model_profile = model_runtime.profile

    conversation_session_service = ConversationSessionService(
        session
    )

    try:
        conversation_session = (
            await conversation_session_service.resolve_or_create(
                organization_id=tool_context.organization_id,
                public_id=payload.session_id,
                model_profile_key=model_profile.profile_key,
                channel="web",
            )
        )
    except ConversationSessionError as error:
        raise translate_conversation_session_error(
            error
        ) from error

    message_service = ConversationMessageService(
        session
    )

    stored_history = await message_service.list_recent_history(
        session_id=conversation_session.id,
        limit=20,
    )

    conversation_history = [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in stored_history
        if message.content is not None
    ]


    stored_tool_context = (
        await message_service.list_recent_tool_context(
            session_id=conversation_session.id,
            limit=5,
        )
    )

    tool_context_records: list[
        ConversationToolContextRecord
    ] = []

    for message in stored_tool_context:
        if (
            message.tool_name is None
            or message.tool_arguments_json is None
            or message.tool_result_json is None
        ):
            raise RuntimeError(
                "A verified historical tool-result "
                "message was incomplete."
            )

        tool_context_records.append(
            ConversationToolContextRecord(
                sequence_number=message.sequence_number,
                tool_name=message.tool_name,
                validated_arguments_json=dict(
                    message.tool_arguments_json
                ),
                result_json=dict(
                    message.tool_result_json
                ),
            )
        )

    tool_context_history = tuple(
        tool_context_records
    )

    await message_service.add_user_message(
        session_id=conversation_session.id,
        content=payload.message,
    )

    orchestrator = ConversationOrchestrator(
        client=model_client,
    )

    result = await orchestrator.handle_message(
        user_message=payload.message,
        session=session,
        context=tool_context,
        conversation_history=conversation_history,
        tool_context_history=tool_context_history,
    )

    completed_at = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    total_response_time_ms = max(
        0,
        round(
            (
                perf_counter()
                - request_timer
            )
            * 1000
        ),
    )

    await message_service.add_assistant_message(
        session_id=conversation_session.id,
        content=result.message,
        provider_name=(
            result.provider_name
            or model_profile.provider_name
        ),
        model_name=(
            result.model_name
            or model_profile.model_name
        ),
        request_started_at=request_started_at,
        completed_at=completed_at,
        total_response_time_ms=total_response_time_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        tool_call_count=result.tool_call_count,
        successful_tool_call_count=(
            result.successful_tool_call_count
        ),
        tool_executions=result.tool_executions,
        tool_results=result.tool_results,
    )

    metrics_service = ConversationMetricsService(
        session
    )

    await metrics_service.refresh(
        session_id=conversation_session.id,
    )

    return ChatMessageResponse(
        organization_id=tool_context.organization_id,
        organization_slug=tool_context.organization_slug,
        session_id=conversation_session.public_id,
        assistant_message=result.message,
    )


@router.post(
    "/sessions/{session_id}/close",
    response_model=ChatSessionCloseResponse,
)
async def close_chat_session(
    organization_slug: str,
    session_id: str,
    session: DatabaseSession,
) -> ChatSessionCloseResponse:
    """Explicitly close one active public conversation session."""

    resolver = OrganizationContextResolver(
        session
    )

    try:
        organization_context = await resolver.resolve(
            organization_slug=organization_slug,
        )
    except OrganizationContextError as error:
        raise translate_organization_context_error(
            error
        ) from error

    session_service = ConversationSessionService(
        session
    )

    try:
        closed_session = await session_service.close(
            organization_id=organization_context.organization_id,
            public_id=session_id,
            close_reason="user_ended",
        )
    except ConversationSessionError as error:
        raise translate_conversation_session_error(
            error
        ) from error

    return ChatSessionCloseResponse(
        organization_id=organization_context.organization_id,
        organization_slug=organization_context.organization_slug,
        session_id=closed_session.public_id,
        status=closed_session.status,
        close_reason=(
            closed_session.close_reason
            or "user_ended"
        ),
    )