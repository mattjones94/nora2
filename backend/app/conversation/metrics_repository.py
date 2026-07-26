from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation_session_metric import (
    ConversationSessionMetric,
)


class ConversationMetricsRepository:
    """Handle persistence operations for conversation metrics."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def get_by_session_id(
        self,
        session_id: int,
    ) -> ConversationSessionMetric | None:
        """Return the metrics record belonging to one session."""

        statement = select(
            ConversationSessionMetric
        ).where(
            ConversationSessionMetric.session_id == session_id,
        )

        return await self._session.scalar(
            statement
        )

    async def update(
        self,
        metrics: ConversationSessionMetric,
        changes: Mapping[str, object],
    ) -> ConversationSessionMetric:
        """Apply calculated metric changes."""

        for field_name, value in changes.items():
            setattr(
                metrics,
                field_name,
                value,
            )

        await self._session.flush()
        await self._session.refresh(
            metrics
        )

        return metrics