from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation_tool_execution import (
    ConversationToolExecution,
)


class ConversationToolExecutionRepository:
    """Persist audited tool attempts for completed assistant turns."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def create_many(
        self,
        executions: Sequence[
            ConversationToolExecution
        ],
    ) -> list[ConversationToolExecution]:
        """Add multiple tool-execution rows to the current transaction."""

        saved_executions = list(
            executions
        )

        if not saved_executions:
            return []

        self._session.add_all(
            saved_executions
        )

        await self._session.flush()

        return saved_executions