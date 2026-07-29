from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.metrics_repository import (
    ConversationMetricsRepository,
)
from app.database.models.conversation_message import (
    ConversationMessage,
)
from app.database.models.conversation_session import (
    ConversationSession,
)
from app.database.models.conversation_session_metric import (
    ConversationSessionMetric,
)


class ConversationMetricsError(Exception):
    """Base error raised while calculating conversation metrics."""


class ConversationMetricsNotFoundError(
    ConversationMetricsError
):
    """Raised when a session does not have a metrics record."""

    def __init__(self) -> None:
        super().__init__(
            "The conversation metrics record could not be found."
        )


class ConversationMetricsService:
    """Calculate and store aggregate metrics for one conversation."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session
        self._metrics = ConversationMetricsRepository(
            session
        )

    async def refresh(
        self,
        *,
        session_id: int,
    ) -> ConversationSessionMetric:
        """Recalculate metrics from authoritative session messages."""

        metrics = await self._metrics.get_by_session_id(
            session_id=session_id,
        )

        if metrics is None:
            raise ConversationMetricsNotFoundError()

        conversation_session = await self._session.get(
            ConversationSession,
            session_id,
        )

        if conversation_session is None:
            raise ConversationMetricsNotFoundError()

        user_message_count = await self._count_messages(
            session_id=session_id,
            message_type="user_message",
        )

        assistant_message_count = await self._count_messages(
            session_id=session_id,
            message_type="assistant_message",
        )

        timing_statement = select(
            func.avg(
                ConversationMessage.total_response_time_ms
            ),
            func.max(
                ConversationMessage.total_response_time_ms
            ),
        ).where(
            ConversationMessage.session_id == session_id,
            ConversationMessage.message_type
            == "assistant_message",
            ConversationMessage.status == "completed",
            ConversationMessage.total_response_time_ms.is_not(
                None
            ),
        )

        timing_result = (
            await self._session.execute(
                timing_statement
            )
        ).one()

        average_total_response_time = (
            round(timing_result[0])
            if timing_result[0] is not None
            else None
        )

        maximum_total_response_time = (
            int(timing_result[1])
            if timing_result[1] is not None
            else None
        )

        token_statement = select(
            func.coalesce(
                func.sum(
                    ConversationMessage.input_tokens
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    ConversationMessage.output_tokens
                ),
                0,
            ),
        ).where(
            ConversationMessage.session_id == session_id,
        )

        token_result = (
            await self._session.execute(
                token_statement
            )
        ).one()

        tool_statement = select(
            func.coalesce(
                func.sum(
                    ConversationMessage.tool_call_count
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    ConversationMessage.successful_tool_call_count
                ),
                0,
            ),
        ).where(
            ConversationMessage.session_id == session_id,
            ConversationMessage.message_type
            == "assistant_message",
            ConversationMessage.status == "completed",
        )

        tool_result = (
            await self._session.execute(
                tool_statement
            )
        ).one()

        tool_call_count = int(
            tool_result[0]
        )

        successful_tool_call_count = int(
            tool_result[1]
        )

        failed_tool_call_count = max(
            0,
            (
                tool_call_count
                - successful_tool_call_count
            ),
        )

        duration_seconds = max(
            0,
            round(
                (
                    self._utc_now()
                    - conversation_session.started_at
                ).total_seconds()
            ),
        )

        try:
            refreshed_metrics = await self._metrics.update(
                metrics=metrics,
                changes={
                    "user_message_count": user_message_count,
                    "assistant_message_count": (
                        assistant_message_count
                    ),
                    "tool_call_count": tool_call_count,
                    "successful_tool_call_count": (
                        successful_tool_call_count
                    ),
                    "failed_tool_call_count": (
                        failed_tool_call_count
                    ),
                    "duration_seconds": duration_seconds,
                    "average_total_response_time_ms": (
                        average_total_response_time
                    ),
                    "maximum_total_response_time_ms": (
                        maximum_total_response_time
                    ),
                    "total_input_tokens": int(
                        token_result[0]
                    ),
                    "total_output_tokens": int(
                        token_result[1]
                    ),
                },
            )

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return refreshed_metrics

    async def _count_messages(
        self,
        *,
        session_id: int,
        message_type: str,
    ) -> int:
        """Count completed messages of one type."""

        statement = select(
            func.count(
                ConversationMessage.id
            )
        ).where(
            ConversationMessage.session_id == session_id,
            ConversationMessage.message_type == message_type,
            ConversationMessage.status == "completed",
        )

        count = await self._session.scalar(
            statement
        )

        return int(
            count or 0
        )

    def _utc_now(self) -> datetime:
        """Return naive UTC for MySQL DateTime compatibility."""

        return datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )