from datetime import datetime
from typing import NamedTuple

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation_message import (
    ConversationMessage,
)
from app.database.models.conversation_session import (
    ConversationSession,
)
from app.database.models.conversation_session_metric import (
    ConversationSessionMetric,
)
from app.database.models.conversation_tool_execution import (
    ConversationToolExecution,
)
from app.features.conversation_logs.schemas import (
    ConversationSessionStatus,
)


ConversationLogListRow = tuple[
    ConversationSession,
    ConversationSessionMetric | None,
]

ConversationLogDetailRow = tuple[
    ConversationSession,
    ConversationSessionMetric | None,
]

class ConversationAnalyticsSessionCountsRow(
    NamedTuple
):
    """Aggregated session counts grouped by status."""

    total: int

    active: int
    closed: int
    expired: int
    abandoned: int
    error: int


class ConversationAnalyticsMetricTotalsRow(
    NamedTuple
):
    """Aggregated values stored in session metrics."""

    user_message_count: int
    assistant_message_count: int
    error_count: int

    average_duration_seconds: float | None

    total_input_tokens: int
    total_output_tokens: int


class ConversationAnalyticsPerformanceRow(
    NamedTuple
):
    """Aggregated assistant-message timing values."""

    average_total_response_time_ms: float | None
    maximum_total_response_time_ms: int | None

    average_time_to_first_token_ms: float | None
    maximum_time_to_first_token_ms: int | None

    average_model_time_to_first_token_ms: (
        float | None
    )


class ConversationAnalyticsToolUsageRow(
    NamedTuple
):
    """Aggregated execution data for one tool."""

    tool_name: str

    execution_count: int
    succeeded_count: int

    execution_failed_count: int
    arguments_rejected_count: int
    unknown_tool_count: int

    average_duration_ms: float | None
    maximum_duration_ms: int | None


class ConversationLogRepository:
    """Read organization-scoped conversation log data."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def list_by_organization(
        self,
        *,
        organization_id: int,
        conversation_status: (
            ConversationSessionStatus | None
        ),
        started_from: datetime | None,
        started_to: datetime | None,
        limit: int,
        offset: int,
    ) -> list[ConversationLogListRow]:
        """
        Return organization conversations with stored metrics.

        Results are ordered newest first and use deterministic ID
        ordering when sessions have the same start time.
        """

        statement = (
            select(
                ConversationSession,
                ConversationSessionMetric,
            )
            .outerjoin(
                ConversationSessionMetric,
                (
                    ConversationSessionMetric.session_id
                    == ConversationSession.id
                ),
            )
            .where(
                ConversationSession.organization_id
                == organization_id,
            )
        )

        if conversation_status is not None:
            statement = statement.where(
                ConversationSession.status
                == conversation_status,
            )

        if started_from is not None:
            statement = statement.where(
                ConversationSession.started_at
                >= started_from,
            )

        if started_to is not None:
            statement = statement.where(
                ConversationSession.started_at
                <= started_to,
            )

        statement = (
            statement
            .order_by(
                ConversationSession.started_at.desc(),
                ConversationSession.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(
            statement
        )

        return [
            (
                row[0],
                row[1],
            )
            for row in result.all()
        ]

    async def count_by_organization(
        self,
        *,
        organization_id: int,
        conversation_status: (
            ConversationSessionStatus | None
        ),
        started_from: datetime | None,
        started_to: datetime | None,
    ) -> int:
        """Count organization conversations matching the filters."""

        statement = select(
            func.count(
                ConversationSession.id
            )
        ).where(
            ConversationSession.organization_id
            == organization_id,
        )

        if conversation_status is not None:
            statement = statement.where(
                ConversationSession.status
                == conversation_status,
            )

        if started_from is not None:
            statement = statement.where(
                ConversationSession.started_at
                >= started_from,
            )

        if started_to is not None:
            statement = statement.where(
                ConversationSession.started_at
                <= started_to,
            )

        count = await self._session.scalar(
            statement
        )

        return int(
            count or 0
        )

    async def get_by_public_id(
        self,
        *,
        organization_id: int,
        public_id: str,
    ) -> ConversationLogDetailRow | None:
        """
        Return one organization-scoped conversation and its metrics.

        The organization and public session ID are applied together in
        the database query to prevent cross-organization disclosure.
        """

        statement = (
            select(
                ConversationSession,
                ConversationSessionMetric,
            )
            .outerjoin(
                ConversationSessionMetric,
                (
                    ConversationSessionMetric.session_id
                    == ConversationSession.id
                ),
            )
            .where(
                ConversationSession.organization_id
                == organization_id,
                ConversationSession.public_id
                == public_id,
            )
        )

        result = await self._session.execute(
            statement
        )

        row = result.one_or_none()

        if row is None:
            return None

        return (
            row[0],
            row[1],
        )

    async def list_messages_by_session(
        self,
        *,
        session_id: int,
    ) -> list[ConversationMessage]:
        """
        Return all stored messages for a conversation in sequence order.

        Administrative logs include both visible and internal messages.
        The is_user_visible field allows the UI to distinguish them.
        """

        statement = (
            select(
                ConversationMessage
            )
            .where(
                ConversationMessage.session_id
                == session_id,
            )
            .order_by(
                ConversationMessage.sequence_number.asc(),
                ConversationMessage.id.asc(),
            )
        )

        result = await self._session.scalars(
            statement
        )

        return list(
            result.all()
        )

    async def list_tool_executions_by_session(
        self,
        *,
        session_id: int,
    ) -> list[ConversationToolExecution]:
        """
        Return audited tool executions in conversation order.

        Joining through the assistant message verifies that both the
        message and tool execution belong to the requested session.
        """

        statement = (
            select(
                ConversationToolExecution
            )
            .join(
                ConversationMessage,
                (
                    ConversationMessage.id
                    == ConversationToolExecution
                    .assistant_message_id
                ),
            )
            .where(
                ConversationToolExecution.session_id
                == session_id,
                ConversationMessage.session_id
                == session_id,
            )
            .order_by(
                ConversationMessage.sequence_number.asc(),
                ConversationToolExecution.execution_order.asc(),
                ConversationToolExecution.id.asc(),
            )
        )

        result = await self._session.scalars(
            statement
        )

        return list(
            result.all()
        )

    async def get_analytics_session_counts(
        self,
        *,
        organization_id: int,
        conversation_status: (
            ConversationSessionStatus | None
        ),
        started_from: datetime | None,
        started_to: datetime | None,
    ) -> ConversationAnalyticsSessionCountsRow:
        """Return matching conversation counts grouped by status."""

        statement = select(
            func.count(
                ConversationSession.id
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ConversationSession.status
                            == "active",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ConversationSession.status
                            == "closed",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ConversationSession.status
                            == "expired",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ConversationSession.status
                            == "abandoned",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ConversationSession.status
                            == "error",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
        ).where(
            ConversationSession.organization_id
            == organization_id,
        )

        if conversation_status is not None:
            statement = statement.where(
                ConversationSession.status
                == conversation_status,
            )

        if started_from is not None:
            statement = statement.where(
                ConversationSession.started_at
                >= started_from,
            )

        if started_to is not None:
            statement = statement.where(
                ConversationSession.started_at
                <= started_to,
            )

        row = (
            await self._session.execute(
                statement
            )
        ).one()

        return ConversationAnalyticsSessionCountsRow(
            total=int(row[0] or 0),
            active=int(row[1] or 0),
            closed=int(row[2] or 0),
            expired=int(row[3] or 0),
            abandoned=int(row[4] or 0),
            error=int(row[5] or 0),
        )

    async def get_analytics_metric_totals(
        self,
        *,
        organization_id: int,
        conversation_status: (
            ConversationSessionStatus | None
        ),
        started_from: datetime | None,
        started_to: datetime | None,
    ) -> ConversationAnalyticsMetricTotalsRow:
        """
        Return message, error, duration, and token aggregates.

        Session metrics are joined to their parent sessions so all
        analytics filters use the session's organization and start
        timestamp.
        """

        statement = (
            select(
                func.coalesce(
                    func.sum(
                        ConversationSessionMetric
                        .user_message_count
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        ConversationSessionMetric
                        .assistant_message_count
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        ConversationSessionMetric
                        .error_count
                    ),
                    0,
                ),
                func.avg(
                    ConversationSessionMetric
                    .duration_seconds
                ),
                func.coalesce(
                    func.sum(
                        ConversationSessionMetric
                        .total_input_tokens
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        ConversationSessionMetric
                        .total_output_tokens
                    ),
                    0,
                ),
            )
            .join(
                ConversationSession,
                (
                    ConversationSession.id
                    == ConversationSessionMetric.session_id
                ),
            )
            .where(
                ConversationSession.organization_id
                == organization_id,
                ConversationSessionMetric.organization_id
                == organization_id,
            )
        )

        if conversation_status is not None:
            statement = statement.where(
                ConversationSession.status
                == conversation_status,
            )

        if started_from is not None:
            statement = statement.where(
                ConversationSession.started_at
                >= started_from,
            )

        if started_to is not None:
            statement = statement.where(
                ConversationSession.started_at
                <= started_to,
            )

        row = (
            await self._session.execute(
                statement
            )
        ).one()

        return ConversationAnalyticsMetricTotalsRow(
            user_message_count=int(
                row[0] or 0
            ),
            assistant_message_count=int(
                row[1] or 0
            ),
            error_count=int(
                row[2] or 0
            ),
            average_duration_seconds=(
                float(row[3])
                if row[3] is not None
                else None
            ),
            total_input_tokens=int(
                row[4] or 0
            ),
            total_output_tokens=int(
                row[5] or 0
            ),
        )

    async def get_analytics_performance(
        self,
        *,
        organization_id: int,
        conversation_status: (
            ConversationSessionStatus | None
        ),
        started_from: datetime | None,
        started_to: datetime | None,
    ) -> ConversationAnalyticsPerformanceRow:
        """
        Return assistant-response timing aggregates.

        These values are calculated directly from completed assistant
        messages instead of averaging the per-session averages.
        """

        statement = (
            select(
                func.avg(
                    ConversationMessage
                    .total_response_time_ms
                ),
                func.max(
                    ConversationMessage
                    .total_response_time_ms
                ),
                func.avg(
                    ConversationMessage
                    .time_to_first_token_ms
                ),
                func.max(
                    ConversationMessage
                    .time_to_first_token_ms
                ),
                func.avg(
                    ConversationMessage
                    .model_time_to_first_token_ms
                ),
            )
            .join(
                ConversationSession,
                (
                    ConversationSession.id
                    == ConversationMessage.session_id
                ),
            )
            .where(
                ConversationSession.organization_id
                == organization_id,
                ConversationMessage.message_type
                == "assistant_message",
                ConversationMessage.status
                == "completed",
            )
        )

        if conversation_status is not None:
            statement = statement.where(
                ConversationSession.status
                == conversation_status,
            )

        if started_from is not None:
            statement = statement.where(
                ConversationSession.started_at
                >= started_from,
            )

        if started_to is not None:
            statement = statement.where(
                ConversationSession.started_at
                <= started_to,
            )

        row = (
            await self._session.execute(
                statement
            )
        ).one()

        return ConversationAnalyticsPerformanceRow(
            average_total_response_time_ms=(
                float(row[0])
                if row[0] is not None
                else None
            ),
            maximum_total_response_time_ms=(
                int(row[1])
                if row[1] is not None
                else None
            ),
            average_time_to_first_token_ms=(
                float(row[2])
                if row[2] is not None
                else None
            ),
            maximum_time_to_first_token_ms=(
                int(row[3])
                if row[3] is not None
                else None
            ),
            average_model_time_to_first_token_ms=(
                float(row[4])
                if row[4] is not None
                else None
            ),
        )

    async def list_analytics_tool_usage(
        self,
        *,
        organization_id: int,
        conversation_status: (
            ConversationSessionStatus | None
        ),
        started_from: datetime | None,
        started_to: datetime | None,
    ) -> list[
        ConversationAnalyticsToolUsageRow
    ]:
        """Return execution statistics grouped by tool name."""

        execution_count = func.count(
            ConversationToolExecution.id
        )

        statement = (
            select(
                ConversationToolExecution.tool_name,
                execution_count,
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ConversationToolExecution
                                .status
                                == "succeeded",
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ConversationToolExecution
                                .status
                                == "execution_failed",
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ConversationToolExecution
                                .status
                                == "arguments_rejected",
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ConversationToolExecution
                                .status
                                == "unknown_tool",
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.avg(
                    ConversationToolExecution.duration_ms
                ),
                func.max(
                    ConversationToolExecution.duration_ms
                ),
            )
            .join(
                ConversationSession,
                (
                    ConversationSession.id
                    == ConversationToolExecution.session_id
                ),
            )
            .where(
                ConversationSession.organization_id
                == organization_id,
                ConversationToolExecution.organization_id
                == organization_id,
            )
        )

        if conversation_status is not None:
            statement = statement.where(
                ConversationSession.status
                == conversation_status,
            )

        if started_from is not None:
            statement = statement.where(
                ConversationSession.started_at
                >= started_from,
            )

        if started_to is not None:
            statement = statement.where(
                ConversationSession.started_at
                <= started_to,
            )

        statement = (
            statement
            .group_by(
                ConversationToolExecution.tool_name
            )
            .order_by(
                execution_count.desc(),
                ConversationToolExecution.tool_name.asc(),
            )
        )

        rows = (
            await self._session.execute(
                statement
            )
        ).all()

        return [
            ConversationAnalyticsToolUsageRow(
                tool_name=str(row[0]),
                execution_count=int(
                    row[1] or 0
                ),
                succeeded_count=int(
                    row[2] or 0
                ),
                execution_failed_count=int(
                    row[3] or 0
                ),
                arguments_rejected_count=int(
                    row[4] or 0
                ),
                unknown_tool_count=int(
                    row[5] or 0
                ),
                average_duration_ms=(
                    float(row[6])
                    if row[6] is not None
                    else None
                ),
                maximum_duration_ms=(
                    int(row[7])
                    if row[7] is not None
                    else None
                ),
            )
            for row in rows
        ]