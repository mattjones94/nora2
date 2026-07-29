from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.message_repository import (
    ConversationMessageRepository,
)
from app.conversation.response_contracts import (
    ConversationToolExecutionRecord,
)
from app.conversation.tool_execution_repository import (
    ConversationToolExecutionRepository,
)
from app.database.models.conversation_message import (
    ConversationMessage,
)
from app.database.models.conversation_session import (
    ConversationSession,
)
from app.database.models.conversation_tool_execution import (
    ConversationToolExecution,
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


class ConversationMessageToolExecutionMismatchError(
    ConversationMessageError
):
    """Raised when assistant aggregate counts and audit records differ."""

    def __init__(
        self,
        detail: str,
    ) -> None:
        super().__init__(
            "Assistant tool-execution metadata was inconsistent: "
            f"{detail}"
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

        self._tool_executions = (
            ConversationToolExecutionRepository(
                session
            )
        )

    async def add_user_message(
        self,
        *,
        session_id: int,
        content: str,
    ) -> ConversationMessage:
        """Store one completed public user message."""

        try:
            saved_message, _ = (
                await self._create_message_in_transaction(
                    session_id=session_id,
                    role="user",
                    message_type="user_message",
                    content=content,
                    status="completed",
                    is_user_visible=True,
                    completed_at=self._utc_now(),
                )
            )

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return saved_message

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
        tool_call_count: int = 0,
        successful_tool_call_count: int = 0,
        tool_executions: Sequence[
            ConversationToolExecutionRecord
        ] = (),
    ) -> ConversationMessage:
        """
        Store one completed assistant response and its tool audits.

        The assistant message and all associated tool-execution rows
        are committed atomically. First-token timing remains null until
        streaming is implemented.
        """

        execution_records = tuple(
            tool_executions
        )

        self._validate_tool_execution_records(
            tool_call_count=tool_call_count,
            successful_tool_call_count=(
                successful_tool_call_count
            ),
            tool_executions=execution_records,
        )

        try:
            (
                saved_message,
                organization_id,
            ) = await self._create_message_in_transaction(
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
                tool_call_count=tool_call_count,
                successful_tool_call_count=(
                    successful_tool_call_count
                ),
            )

            audit_rows = [
                ConversationToolExecution(
                    session_id=session_id,
                    assistant_message_id=saved_message.id,
                    organization_id=organization_id,
                    execution_order=(
                        execution.execution_order
                    ),
                    attempt_phase=(
                        execution.attempt_phase
                    ),
                    tool_name=execution.tool_name,
                    validated_arguments_json=(
                        execution.validated_arguments_json
                    ),
                    status=execution.status,
                    failure_category=(
                        execution.failure_category
                    ),
                    duration_ms=execution.duration_ms,
                )
                for execution in execution_records
            ]

            await self._tool_executions.create_many(
                audit_rows
            )

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return saved_message

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

    async def _create_message_in_transaction(
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
        tool_call_count: int = 0,
        successful_tool_call_count: int = 0,
        request_started_at: datetime | None = None,
        model_started_at: datetime | None = None,
        first_token_at: datetime | None = None,
        completed_at: datetime | None = None,
        time_to_first_token_ms: int | None = None,
        model_time_to_first_token_ms: int | None = None,
        total_response_time_ms: int | None = None,
    ) -> tuple[
        ConversationMessage,
        int,
    ]:
        """
        Create one ordered message without committing the transaction.

        The locked session supplies the trusted organization identifier.
        """

        organization_id = await self._lock_session(
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
            tool_call_count=tool_call_count,
            successful_tool_call_count=(
                successful_tool_call_count
            ),
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

        return (
            saved_message,
            organization_id,
        )

    def _validate_tool_execution_records(
        self,
        *,
        tool_call_count: int,
        successful_tool_call_count: int,
        tool_executions: tuple[
            ConversationToolExecutionRecord,
            ...
        ],
    ) -> None:
        """Verify assistant aggregates match their detailed audit rows."""

        if tool_call_count != len(
            tool_executions
        ):
            raise (
                ConversationMessageToolExecutionMismatchError(
                    "tool_call_count did not equal the number "
                    "of execution records."
                )
            )

        recorded_successes = sum(
            1
            for execution in tool_executions
            if execution.status == "succeeded"
        )

        if (
            successful_tool_call_count
            != recorded_successes
        ):
            raise (
                ConversationMessageToolExecutionMismatchError(
                    "successful_tool_call_count did not equal "
                    "the number of successful records."
                )
            )

        expected_orders = tuple(
            range(
                1,
                len(tool_executions) + 1,
            )
        )

        actual_orders = tuple(
            execution.execution_order
            for execution in tool_executions
        )

        if actual_orders != expected_orders:
            raise (
                ConversationMessageToolExecutionMismatchError(
                    "execution_order values were not contiguous "
                    "and chronological."
                )
            )

    async def _lock_session(
        self,
        *,
        session_id: int,
    ) -> int:
        """
        Lock the parent session and return its organization identifier.

        This prevents simultaneous requests from receiving the same
        sequence number and ensures audit organization scope comes
        from the trusted parent session.
        """

        statement = (
            select(
                ConversationSession.organization_id
            )
            .where(
                ConversationSession.id == session_id,
            )
            .with_for_update()
        )

        organization_id = await self._session.scalar(
            statement
        )

        if organization_id is None:
            raise ConversationMessageSessionNotFoundError()

        return int(
            organization_id
        )

    def _utc_now(self) -> datetime:
        """Return naive UTC for the current MySQL DateTime fields."""

        return datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )