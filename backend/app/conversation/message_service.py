from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.message_repository import (
    ConversationMessageRepository,
)
from app.database.models.conversation_message import (
    ConversationMessage,
)
from app.database.models.conversation_session import (
    ConversationSession,
)


class ConversationMessageError(Exception):
    """Base error raised while storing conversation messages."""


class ConversationMessageSessionNotFoundError(
    ConversationMessageError
):
    """Raised when a message references an unavailable session."""

    def __init__(self) -> None:
        super().__init__(
            "The conversation session could not be found."
        )


class ConversationMessageService:
    """Store ordered conversation messages and response timing."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session
        self._messages = ConversationMessageRepository(
            session
        )

    async def add_user_message(
        self,
        *,
        session_id: int,
        content: str,
    ) -> ConversationMessage:
        """Store one completed public user message."""

        return await self._create_message(
            session_id=session_id,
            role="user",
            message_type="user_message",
            content=content,
            status="completed",
            is_user_visible=True,
            completed_at=self._utc_now(),
        )

    async def add_assistant_message(
        self,
        *,
        session_id: int,
        content: str,
        provider_name: str | None,
        model_name: str | None,
        request_started_at: datetime,
        completed_at: datetime,
        total_response_time_ms: int,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> ConversationMessage:
        """
        Store one completed assistant response.

        First-token timing remains null until streaming is implemented.
        """

        return await self._create_message(
            session_id=session_id,
            role="assistant",
            message_type="assistant_message",
            content=content,
            status="completed",
            is_user_visible=True,
            provider_name=provider_name,
            model_name=model_name,
            request_started_at=request_started_at,
            completed_at=completed_at,
            total_response_time_ms=total_response_time_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def list_recent_history(
        self,
        *,
        session_id: int,
        limit: int = 20,
    ) -> list[ConversationMessage]:
        """Return recent public messages for future model context."""

        if limit < 1 or limit > 100:
            raise ValueError(
                "limit must be between 1 and 100"
            )

        return await self._messages.list_recent_visible(
            session_id=session_id,
            limit=limit,
        )

    async def _create_message(
        self,
        *,
        session_id: int,
        role: str,
        message_type: str,
        content: str | None,
        status: str,
        is_user_visible: bool,
        provider_name: str | None = None,
        model_name: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        request_started_at: datetime | None = None,
        model_started_at: datetime | None = None,
        first_token_at: datetime | None = None,
        completed_at: datetime | None = None,
        time_to_first_token_ms: int | None = None,
        model_time_to_first_token_ms: int | None = None,
        total_response_time_ms: int | None = None,
    ) -> ConversationMessage:
        """Create one ordered message within a locked session."""

        try:
            await self._lock_session(
                session_id=session_id,
            )

            sequence_number = (
                await self._messages.get_next_sequence_number(
                    session_id=session_id,
                )
            )

            message = ConversationMessage(
                session_id=session_id,
                sequence_number=sequence_number,
                role=role,
                message_type=message_type,
                status=status,
                content=content,
                provider_name=provider_name,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                request_started_at=request_started_at,
                model_started_at=model_started_at,
                first_token_at=first_token_at,
                completed_at=completed_at,
                time_to_first_token_ms=time_to_first_token_ms,
                model_time_to_first_token_ms=(
                    model_time_to_first_token_ms
                ),
                total_response_time_ms=total_response_time_ms,
                is_user_visible=is_user_visible,
            )

            saved_message = await self._messages.create(
                message
            )

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return saved_message

    async def _lock_session(
        self,
        *,
        session_id: int,
    ) -> None:
        """
        Lock the parent session while assigning the next sequence number.

        This prevents two simultaneous requests from receiving the same
        sequence number within one conversation.
        """

        statement = (
            select(
                ConversationSession.id
            )
            .where(
                ConversationSession.id == session_id,
            )
            .with_for_update()
        )

        resolved_session_id = await self._session.scalar(
            statement
        )

        if resolved_session_id is None:
            raise ConversationMessageSessionNotFoundError()

    def _utc_now(self) -> datetime:
        """Return naive UTC for the current MySQL DateTime fields."""

        return datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )